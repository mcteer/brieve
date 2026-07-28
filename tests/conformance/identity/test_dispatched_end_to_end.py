# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a dispatched run resolves every term from the live trust fabric (SC-002).

**This is the row that proves the plumbing.** The per-term rows prove the mechanism: that a
ceiling read from the registry bounds authority, that two roles resolve to different scopes.
Each proves its own term. A feature that stopped there would have a correct identity fabric
that nothing instantiated — which is precisely what 008 shipped for the dispatch path, and what this
repository has now recorded eleven times under different names.

So this row dispatches a real allocation, whose entrypoint constructs the production fabric
from its own attested identity, and reads the audit trail back to see what happened. Nothing
here is stubbed: no fake, no supplied token.

Runs on the HOST rather than in an allocation, because it drives the scheduler — a row
placed by the scheduler cannot watch the scheduler place something.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid

import pytest

from surfaces.dispatch.nomad import NomadDispatcher

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

NOMAD_ADDR = "http://127.0.0.1:4646"
JOB_ID = "agent-run"
TENANT = "tenant-conformance"


def _job_registered() -> bool:
    try:
        with urllib.request.urlopen(f"{NOMAD_ADDR}/v1/job/{JOB_ID}", timeout=3) as response:  # noqa: S310
            return json.loads(response.read()).get("ParameterizedJob") is not None
    except (urllib.error.URLError, OSError):
        return False


def _allocation_state(dispatched_job_id: str, *, timeout: float = 720.0) -> tuple[str, str]:
    """Wait for the dispatched allocation to finish and return (client status, alloc id).

    Twelve minutes, because every allocation installs its dependencies from scratch before
    running anything — there is no shared cache, and a cold one has been measured past
    seven. A shorter budget reports `timeout` for a run that was working, which reads as a
    hang and is a stopwatch.
    """
    deadline = time.monotonic() + timeout
    alloc_id = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{NOMAD_ADDR}/v1/job/{dispatched_job_id}/allocations", timeout=5
            ) as response:
                allocations = json.loads(response.read())
        except (urllib.error.URLError, OSError):
            allocations = []
        if allocations:
            alloc = allocations[0]
            alloc_id = alloc.get("ID", "")
            status = alloc.get("ClientStatus", "")
            if status in {"complete", "failed"}:
                return status, alloc_id
        time.sleep(2)
    return "timeout", alloc_id


@pytest.fixture
def dispatcher() -> NomadDispatcher:
    if not _job_registered():
        pytest.fail(
            f"the parameterized job {JOB_ID!r} is not registered — run `make dev-up`. "
            "This row is not skippable: an entrypoint proven only by unit tests has not "
            "been proven to run."
        )
    return NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id=JOB_ID)


def test_row_a_dispatched_run_resolves_authority_from_the_trust_fabric(
    dispatcher: NomadDispatcher,
) -> None:
    """The entrypoint constructs the production fabric and a run starts under it.

    `planner-agent`'s ceiling and the `operator` role binding both come from the trust
    fabric; the allocation authenticates with its own workload identity and holds no token
    of any kind. If the entrypoint still imported a fake, or the agent-run role lacked the
    read policy, or the ceiling record were absent, this allocation would exit non-zero.
    """
    correlation_id = f"identity-e2e-{uuid.uuid4().hex[:12]}"

    handle = dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo", "plan"}),
        subject_roles=frozenset({"operator"}),
    )

    assert handle.correlation_id == correlation_id
    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched, "the dispatcher returned a handle naming no scheduled job"

    status, alloc_id = _allocation_state(dispatched)
    assert status == "complete", (
        f"the dispatched allocation ended {status!r} (alloc {alloc_id}). Its entrypoint "
        f"resolves authority from the trust fabric now — run "
        f"`nomad alloc logs -stderr {alloc_id} run` to see which resolution refused."
    )


def test_row_a_definition_with_no_ceiling_record_fails_the_allocation(
    dispatcher: NomadDispatcher,
) -> None:
    """The negative, and it is what makes the row above mean something.

    An entrypoint that quietly fell back to a fake — or that resolved a default ceiling for
    an unknown definition — would complete this allocation successfully. Failing is the
    correct outcome, and it is only observable end to end.
    """
    correlation_id = f"identity-e2e-unknown-{uuid.uuid4().hex[:12]}"

    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="definition-that-is-not-registered",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )

    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched, "the dispatcher returned a handle naming no scheduled job"
    status, alloc_id = _allocation_state(dispatched)

    assert status == "failed", (
        f"a run under an unregistered definition ended {status!r} (alloc {alloc_id}) — the "
        "entrypoint resolved a ceiling for a definition that does not exist, which is the "
        "open-ceiling failure FR-003 exists to prevent"
    )
