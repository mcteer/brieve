# SPDX-License-Identifier: Apache-2.0
"""Driving the scheduler, and reading back what a resumed allocation actually did (014).

Shared by every dispatch-level row in this package. These rows are `host_enclave` by
nature — they stop and re-dispatch allocations, which nothing the scheduler placed can do —
so they read state as an OPERATOR through `tests.harness.OperatorCredentials`, the posture
the `make conformance` comment already names for this lane.

**Everything here reads the trail and the stores, never the allocation logs.** A row that
asserted on stdout would be asserting what the run *said* it did; the point of the feature
is that what happened is recorded. The logs are for debugging a red row, and the failure
messages name the command.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from typing import Any

import pg8000.dbapi
import pytest

from surfaces.dispatch.nomad import NomadDispatcher
from tests.harness.operator_credentials import OperatorCredentials

NOMAD_ADDR = "http://127.0.0.1:4646"
JOB_ID = "agent-run"
TENANT = "tenant-local"

#: How many bracketed steps a disruption row's run is dispatched to take.
#:
#: Sized so the run is still going when the row stops it, and finishes soon after being
#: revived. Each step is several durable round trips — a stop check, the bracket's intent and
#: result, a checkpoint, and a `TOOL_OUTCOME` append with its hash chaining — so the run takes
#: real time doing real work rather than sleeping. `time.sleep` in the entrypoint would be a
#: test affordance in production code, which 010 spent a user story removing.
#:
#: If a row ever reports that the run finished before it could be disrupted, this is the
#: number to raise — and the row says so rather than passing vacuously.
DISRUPTION_STEPS = 400

#: Where the row waits for the run to get to before disrupting it. Low, because what the
#: exactly-once assertion needs is *some* completed prefix and *some* remainder, not a
#: particular split.
DISRUPT_AFTER_STEP = 3


def unique(prefix: str) -> str:
    """A distinct run id per invocation.

    Per invocation, not merely per test: yesterday's run has already closed today's intents,
    and a row asserting against work it did not do is worse than a red one.
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def connection() -> Any:
    cred = OperatorCredentials().fetch()
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=5432,
        database="brieve",
        user=cred.username,
        password=cred.password,
    )
    conn.autocommit = True
    return conn


def query(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params) if params else cursor.execute(sql)
        return [list(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def dispatcher() -> NomadDispatcher:
    body = _nomad(["job", "status", JOB_ID])
    if "No job(s) with prefix" in body or not body:
        pytest.fail(
            f"the parameterized job {JOB_ID!r} is not registered — run `make dev-up`. Not "
            "skippable: a resume proven only hermetically has not been proven to survive a "
            "disruption, which is the whole claim."
        )
    return NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id=JOB_ID)


def _nomad(args: list[str]) -> str:
    return subprocess.run(["nomad", *args], capture_output=True, text=True).stdout


def job_of(dispatcher: NomadDispatcher, run_id: str) -> str:
    """The dispatched job id, asserted present.

    `dispatched_job_id` is Optional by design — it answers "did this dispatcher dispatch
    that run" — and every row here has just dispatched, so absence is a harness fault rather
    than a property under test.
    """
    job_id = dispatcher.dispatched_job_id(run_id)
    if not job_id:
        pytest.fail(f"the dispatcher recorded no scheduled job for {run_id}")
    return job_id


def allocation_of(job_id: str) -> str:
    """The allocation the scheduler placed for a dispatched job."""
    for _ in range(60):
        for line in _nomad(["job", "status", job_id]).splitlines():
            parts = line.split()
            if parts and len(parts[0]) == 8 and all(c in "0123456789abcdef" for c in parts[0]):
                return parts[0]
        time.sleep(1)
    pytest.fail(f"no allocation was placed for {job_id}")


def task_state(alloc: str) -> str:
    raw = _nomad(["alloc", "status", "-json", alloc])
    try:
        states = json.loads(raw).get("TaskStates") or {}
    except json.JSONDecodeError:
        return "pending"
    return str((states.get("harness") or {}).get("State") or "pending")


def exit_code(alloc: str) -> int | None:
    raw = _nomad(["alloc", "status", "-json", alloc])
    try:
        states = json.loads(raw).get("TaskStates") or {}
    except json.JSONDecodeError:
        return None
    events = [
        e
        for e in ((states.get("harness") or {}).get("Events") or [])
        if e.get("Type") == "Terminated"
    ]
    return int(events[-1].get("ExitCode", 1)) if events else None


def wait_dead(alloc: str, *, timeout: float = 420.0) -> None:
    """Wait for the task to reach a terminal state.

    Generously bounded because a cold allocation builds a virtualenv and downloads packages
    inside the container — measured at over two minutes. A bound tight enough to be
    impatient turns a slow run into a red row, which sends someone to debug passing code.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if task_state(alloc) == "dead":
            return
        time.sleep(2)
    pytest.fail(
        f"allocation {alloc} was still {task_state(alloc)!r} after {timeout}s. The rows did "
        f"not fail; this run did not finish: nomad alloc logs {alloc} harness"
    )


def stop_allocation(alloc: str) -> None:
    """The disruption. A real allocation, really killed.

    `reschedule` and `restart` are both zero attempts in the jobspec, so nothing brings this
    back — a failed run is a failed run, and a second allocation would get a second identity
    for work the first was already fenced out of.
    """
    subprocess.run(["nomad", "alloc", "stop", alloc], capture_output=True, text=True)


def wait_for_progress(conn: Any, run_id: str, *, min_step: int, timeout: float = 420.0) -> int:
    """Wait until the run has checkpointed at least ``min_step``, and report where it got to.

    Polls the CHECKPOINT rather than the log, so what the row waits on is the same durable
    record the resume will later read.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = query(
            conn, "SELECT step_index, run_state FROM checkpoints WHERE blob_id = %s", (run_id,)
        )
        if rows and rows[0][0] >= min_step:
            return int(rows[0][0])
        time.sleep(0.2)
    pytest.fail(
        f"run {run_id} never checkpointed step {min_step} within {timeout}s — it may not have "
        f"started at all. Check the allocation, not this assertion."
    )


def checkpoint(conn: Any, run_id: str) -> dict[str, Any]:
    rows = query(
        conn,
        "SELECT step_index, run_state, stop_reason, resume_count, grant_id, written_by "
        "FROM checkpoints WHERE blob_id = %s",
        (run_id,),
    )
    if not rows:
        return {}
    step, state, reason, resumes, grant_id, written_by = rows[0]
    return {
        "step_index": step,
        "run_state": state,
        "stop_reason": reason,
        "resume_count": resumes,
        "grant_id": grant_id,
        "written_by": written_by,
    }


def events(conn: Any, run_id: str, event_type: str) -> list[dict[str, Any]]:
    """Audit entries of one type, in sequence order — the evidence path, not the log."""
    rows = query(
        conn,
        "SELECT payload FROM audit_entries WHERE correlation_id = %s AND event_type = %s "
        "ORDER BY seq",
        (run_id, event_type),
    )
    out: list[dict[str, Any]] = []
    for (payload,) in rows:
        out.append(payload if isinstance(payload, dict) else json.loads(payload))
    return out


def event_order(conn: Any, run_id: str) -> list[str]:
    """Every event type this run wrote, in order. What an investigator reads."""
    return [
        str(row[0])
        for row in query(
            conn,
            "SELECT event_type FROM audit_entries WHERE correlation_id = %s ORDER BY seq",
            (run_id,),
        )
    ]


def tool_invocations(conn: Any, run_id: str) -> int:
    """How many times a tool actually ran, across every allocation of this run.

    **This is the exactly-once measurement**, and the obvious alternative does not work:
    counting `intents` rows cannot detect re-execution, because the table's primary key is
    `(run_id, idempotency_key)` and the insert is `ON CONFLICT DO NOTHING` — a step run twice
    writes one row. `TOOL_OUTCOME` is appended per invocation with no such collapsing, so a
    re-executed step shows up as an extra event.
    """
    return len(events(conn, run_id, "tool_outcome"))


def credential_ids(conn: Any, run_id: str) -> list[str]:
    """The credential each allocation manufactured, in order.

    Fresh authority is asserted by these being *different*: a resumed allocation that
    somehow carried the prior credential across the disruption would repeat one (SC-002).
    """
    return [str(p.get("credential_id") or "") for p in events(conn, run_id, "authority_issued")]


def dispatch_args(run_id: str, **overrides: Any) -> dict[str, Any]:
    """A `vault-agent` dispatch, which is what the disruption rows need.

    `vault_write` rather than a fixture tool, and the reason is structural: it is
    **non-repeatable with a real observer**, so `invoke_tool` brackets it in
    `core.hooks.engine` and an interruption leaves a genuine open intent for re-observation
    to resolve. Every fixture tool is repeatable, so a run built on one has nothing to
    re-observe and would assert exactly-once vacuously.

    The handler itself writes nothing to Vault (it validates and returns), so these rows buy
    no write capability — the observer is the live half, and it reads.
    """
    args: dict[str, Any] = {
        "correlation_id": run_id,
        "subject_user_id": "alice",
        "tenant_id": TENANT,
        "agent_definition_id": "vault-agent",
        "requested_tools": frozenset({"vault_write"}),
        "subject_roles": frozenset({"vault-operator"}),
        "packs": frozenset({"vault"}),
        "invoke_tools": True,
        "run_id": run_id,
        "steps": DISRUPTION_STEPS,
    }
    args.update(overrides)
    return args
