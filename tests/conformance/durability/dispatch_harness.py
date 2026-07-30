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
import os
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


def wait_dead(alloc: str, *, timeout: float = 900.0) -> None:
    """Wait for the task to reach a terminal state.

    Generously bounded because a cold allocation builds a virtualenv and downloads packages
    inside the container — measured at over two minutes. A bound tight enough to be
    impatient turns a slow run into a red row, which sends someone to debug passing code.

    **Raised from 420s after the first full `make conformance` run.** Every row here passed
    when run on its own and one timed out inside the whole gate, which is the difference the
    number has to absorb: the suite dispatches allocations back to back, so a run that starts
    while three others are building their environments waits on the node rather than on
    anything under test. A bound that only holds when the row runs alone is a bound that turns
    a busy machine into a red gate.
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


def assert_entrypoint_ran(alloc: str) -> None:
    """Fail distinctly when an allocation died before reaching our code.

    Each allocation bootstraps itself — `pip install uv`, then a virtualenv, then the
    package — and that fetches from the public index. When the network hiccups the task exits
    non-zero having never run the entrypoint, and every assertion downstream then reports the
    property under test as broken. One such run cost ten minutes and reported "exhausting the
    revival budget failed the allocation", which is a sentence about the cap describing a
    read timeout from `files.pythonhosted.org`.

    The signature is an exit code the entrypoint never produces together with no stdout at
    all: the entrypoint prints before it can fail, so silence means it never started.
    """
    if exit_code(alloc) in (0, 1):
        return
    stdout = _nomad(["alloc", "logs", alloc, "harness"]).strip()
    if stdout:
        return
    pytest.fail(
        f"allocation {alloc} exited {exit_code(alloc)} with no output from the entrypoint, so "
        f"it never ran: this is a bootstrap or network failure, not a property failing. "
        f"nomad alloc logs -stderr {alloc} harness"
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


def dependency_store() -> Any:
    """The real dependency store, reached with an operator credential.

    The concrete store rather than a double, because what these rows drive is the SWEEPER,
    and the sweeper reads this store inside the mcp service. A double here would let the row
    tell itself a product had recovered while the thing that decides read something else.
    """
    from core.dependencies.store import PostgresDependencyStore

    # Typed as the workload credential class because that is what production passes. The
    # operator credential satisfies the same `.fetch()` shape and is the only thing a host
    # process can hold — there is no attested identity here, which is the property this lane
    # exists to preserve. Cast rather than widen the production signature: a `core` class that
    # advertised acceptance of a static-token credential would make the fallback available to
    # production by import, which is how a test affordance becomes a deployment.
    credentials: Any = OperatorCredentials()
    return PostgresDependencyStore(credentials=credentials)


def mark_reachable(product: str, *, reachable: bool) -> None:
    """Make the platform believe a product is up, or down.

    Recovery is HYSTERETIC — `DEFAULT_RECOVERY_THRESHOLD` consecutive successes — and failure
    is not, which is why marking down is one call and marking up is several. Asymmetric by
    design (009): marking unhealthy fast costs a suspension the sweeper resolves, while
    marking healthy fast resumes every waiting run into a product that fails again.
    """
    store = dependency_store()
    if not reachable:
        store.record_probe(product=product, reachable=False, detail="arranged by a 014 row")
        return
    for _ in range(5):
        health = store.record_probe(product=product, reachable=True, detail="arranged")
        if health.state.permits_calls():
            return
    pytest.fail(f"{product} would not come back healthy after five successful probes")


def arrange_disrupted(
    conn: Any,
    run_id: str,
    *,
    tool_name: str,
    step_index: int = 1,
    grant_ttl: str = "8 hours",
    resume_count: int = 0,
    scope_tools: tuple[str, ...] = ("echo",),
    definition: str = "planner-agent",
) -> str:
    """Write the state a disrupted run would have left, and return the grant id.

    **Arranged from the host rather than produced by killing an allocation, and that is a
    deliberate trade this docstring owes the reader.** What a kill gives you is authenticity;
    what it costs is control — the exactly-once row spends five minutes and a polling race to
    catch a run mid-bracket, and it can only ever leave the ONE interrupted state that racing
    produces. The rows below need a specific interrupted state: an open intent for a tool whose
    observer answers a particular way, or a grant that has already lapsed.

    So the disruption these rows study is arranged, and the disruption itself is proven
    elsewhere — `test_dispatched_resume.py` kills a real allocation. Each row here says which
    of the two it is relying on.

    Everything written here is what the entrypoint itself writes on the fresh path: a grant
    row, a checkpoint referencing it, and a bracket left open.
    """
    grant_id = f"grant-{uuid.uuid4().hex}"
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO grants (grant_id, subject_user_id, agent_definition_id, "
            "requested_scope, issued_at, expires_at) "
            "VALUES (%s, %s, %s, %s::jsonb, now(), now() + %s::interval)",
            (
                grant_id,
                "alice",
                definition,
                # Sorted, like the provider writes it — the resumed run manufactures its
                # authority from this scope, so a row that stored it differently would be
                # arranging a grant the platform would never have issued.
                json.dumps({"tool_names": sorted(scope_tools), "product_actions": []}),
                grant_ttl,
            ),
        )
        cursor.execute(
            "INSERT INTO checkpoints (blob_id, payload, correlation_id, grant_id, step_index, "
            "written_by, resume_count) VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s) "
            "ON CONFLICT (blob_id) DO UPDATE SET grant_id = EXCLUDED.grant_id, "
            "step_index = EXCLUDED.step_index, resume_count = EXCLUDED.resume_count",
            (
                run_id,
                json.dumps({"step": step_index}),
                run_id,
                grant_id,
                step_index,
                "alloc-1",
                resume_count,
            ),
        )
        # The open bracket: an intent with no result, which is the only thing re-observation
        # has to resolve. The key matches what `core.hooks.engine` would have written.
        cursor.execute(
            "INSERT INTO intents (run_id, idempotency_key, step_index, tool_name, recorded_at) "
            "VALUES (%s, %s, %s, %s, now()) ON CONFLICT DO NOTHING",
            (run_id, f"{run_id}:{step_index}:{tool_name}", step_index, tool_name),
        )
    finally:
        cursor.close()
    return grant_id


def _vault(path: str, *, method: str, body: dict[str, Any] | None = None) -> int:
    """Reach the enclave's Vault as an OPERATOR, to arrange what a product would hold.

    The re-observation rows have to make "the write landed" true or false *in Vault*, because
    the shipped `VaultWriteObserver` reads Vault and believes what it finds. Arranging it any
    other way — a scripted observer, a flag in the database — would test the row's own fixture
    rather than the observer, which is what clarify Q3 rejected.
    """
    import ssl
    import urllib.request

    addr = (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")
    token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROOT_TOKEN") or ""
    cacert = os.environ.get("VAULT_CACERT")
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
        f"{addr}/v1/{path}",
        data=data,
        headers={"X-Vault-Token": token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def arrange_effect_landed(idempotency_key: str) -> None:
    """Make the interrupted write look like it succeeded, to the shipped observer.

    The observer reads `secret/metadata/{key}`, which exists exactly when something was
    written at `secret/data/{key}`. So this writes there, and the observer's answer is
    genuinely derived from the product's state rather than handed to it.
    """
    status = _vault(
        f"secret/data/{idempotency_key}",
        method="POST",
        body={"data": {"arranged_by": "014 re-observation row"}},
    )
    assert status in (200, 204), f"could not arrange the landed effect in Vault: HTTP {status}"


def clear_effect(idempotency_key: str) -> None:
    """Remove the arranged state, so the next run of this row starts from the same place.

    `metadata` rather than `data`: deleting the data leaves a tombstone whose METADATA still
    exists, and the observer reads metadata — so a data-only delete would leave the next
    "did not land" direction observing that it had.
    """
    _vault(f"secret/metadata/{idempotency_key}", method="DELETE")


def step_key(run_id: str, step_index: int, tool_name: str) -> str:
    """The bracket key `core.hooks.engine` writes: run, step, tool."""
    return f"{run_id}:{step_index}:{tool_name}"


def suspended_rows(conn: Any, run_id: str) -> list[dict[str, Any]]:
    """What the sweeper would find for this run."""
    rows = query(
        conn,
        "SELECT awaiting, step_index, subject_user_id, tenant_id, agent_definition_id, "
        "       subject_roles, packs, steps, invoke_tools "
        "FROM suspended_runs WHERE run_id = %s",
        (run_id,),
    )
    keys = (
        "awaiting",
        "step_index",
        "subject_user_id",
        "tenant_id",
        "agent_definition_id",
        "subject_roles",
        "packs",
        "steps",
        "invoke_tools",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


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
