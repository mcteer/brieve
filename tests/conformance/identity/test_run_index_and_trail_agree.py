# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the run index and the audit trail do not diverge quietly.

This feature gives the platform two accounts of what ran: the index, which a person reads,
and the audit trail, which an investigator reads. They are written in the same motion by
the same dispatch — but to different stores, with no transaction spanning them.

**Two accounts that can disagree quietly is how an investigator ends up trusting the wrong
one.** So the divergence is asserted rather than assumed, and the row is loud when it
happens.

**It waits for the allocation to reach a terminal state before comparing.** The index is
written at dispatch; `run_start` is written inside the allocation, minutes later on a cold
one. Comparing inside that window would flake at exactly the cadence cold allocations
occur — and a flaky divergence row teaches people to re-run the one row whose job is to be
believed.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import pytest

from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.runs.index import PostgresRunIndex
from surfaces.dispatch.nomad import NomadDispatcher

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

NOMAD_ADDR = "http://127.0.0.1:4646"
TENANT = "tenant-conformance"


def _credentials() -> VaultDatabaseCredentials:
    return VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance")


def _wait_terminal(dispatched_job_id: str, *, timeout: float = 720.0) -> str:
    """Wait for the allocation to finish. Twelve minutes, as the other dispatch rows use.

    Every allocation installs its dependencies from scratch — there is no shared cache —
    and a shorter budget reports a run that was working as a hang.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{NOMAD_ADDR}/v1/job/{dispatched_job_id}/allocations", timeout=5
            ) as response:
                allocations = json.loads(response.read())
        except (urllib.error.URLError, OSError):
            allocations = []
        if allocations and str(allocations[0].get("ClientStatus", "")) in {"complete", "failed"}:
            return str(allocations[0]["ClientStatus"])
        time.sleep(2)
    return "timeout"


def _trail_has(connection: Any, correlation_id: str) -> bool:
    cur = connection.cursor()
    cur.execute("SELECT 1 FROM audit_entries WHERE correlation_id = %s LIMIT 1", (correlation_id,))
    return cur.fetchone() is not None


def test_row_a_dispatched_run_appears_in_both_accounts(run_connection: Any) -> None:
    """The index a person reads and the trail an investigator reads agree.

    Dispatched with a real subject and tenant, waited to completion, then both stores are
    asked. A run present in one and absent from the other is the silent disagreement this
    row exists to make loud.
    """
    correlation_id = f"divergence-{uuid.uuid4().hex[:12]}"
    index = PostgresRunIndex(credentials=_credentials())
    dispatcher = NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id="agent-run", run_index=index)

    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )

    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched, "the dispatcher returned a handle naming no scheduled job"
    status = _wait_terminal(dispatched)
    assert status == "complete", f"the allocation ended {status!r}; the run never wrote its trail"

    page = index.list_for(tenant_id=TENANT, subject_user_id="alice", limit=200)
    in_index = any(e.correlation_id == correlation_id for e in page.entries)
    in_trail = _trail_has(run_connection, correlation_id)

    assert in_index and in_trail, (
        f"the two accounts of this run disagree — index={in_index}, trail={in_trail}. "
        "One of them is now lying to whoever reads it, and which one is not obvious "
        "from either."
    )


def test_row_the_index_records_the_subject_the_trail_records(run_connection: Any) -> None:
    """Not merely that both know of the run — that they agree about whose it was.

    A run present in both under different subjects would satisfy the row above and be a
    worse failure than absence: two confident, contradictory answers to "who did this".
    """
    correlation_id = f"divergence-subject-{uuid.uuid4().hex[:12]}"
    index = PostgresRunIndex(credentials=_credentials())
    dispatcher = NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id="agent-run", run_index=index)

    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )
    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched
    assert _wait_terminal(dispatched) == "complete"

    entry = index.get(run_id=correlation_id, tenant_id=TENANT)
    assert entry is not None and entry.subject_user_id == "alice"

    cur = run_connection.cursor()
    cur.execute(
        "SELECT payload FROM audit_entries WHERE correlation_id = %s AND event_type = %s",
        (correlation_id, "authority_issued"),
    )
    rows = cur.fetchall()
    assert rows, "the run wrote no authority record, so there is nothing to compare against"
    payload = rows[0][0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["subject_user_id"] == entry.subject_user_id
