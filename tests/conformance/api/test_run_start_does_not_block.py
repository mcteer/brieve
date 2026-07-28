# SPDX-License-Identifier: Apache-2.0
"""Row: starting a run dispatches a real allocation and returns immediately (FR-007a).

Against real Nomad, because Nomad is inside our boundary. An earlier version of this row
was a hermetic test against `InProcessDispatcher` — it proved the surface returned a handle
without blocking, and proved nothing whatever about dispatch. `NomadDispatcher` was
exercised by no test at all, and the job it dispatches to did not exist, so a run started
through the API against a real enclave would have failed at runtime while every test
passed.

What this row establishes, in order:

1. The dispatch is **accepted** and returns a handle without waiting.
2. The response comes back **while the allocation is still being placed** — the timing
   assertion, and the reason a run's duration cannot be the request's duration.
3. Nomad **actually placed** an allocation, so the handle refers to something.
4. That allocation obtained its own credentials **by presenting its own identity**, which
   is what makes the run's authority attested rather than handed to it.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pytest

from core.run import RunState
from surfaces.dispatch.nomad import NomadDispatcher

# Drives the scheduler, so it cannot run inside something the scheduler placed.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

NOMAD_ADDR = "http://127.0.0.1:4646"
JOB_ID = "agent-run"
TENANT = "tenant-conformance"


def _scheduler_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{NOMAD_ADDR}/v1/status/leader", timeout=3):  # noqa: S310
            return True
    except (urllib.error.URLError, OSError):
        return False


def _job_registered() -> bool:
    try:
        with urllib.request.urlopen(f"{NOMAD_ADDR}/v1/job/{JOB_ID}", timeout=3) as response:  # noqa: S310
            return json.loads(response.read()).get("ParameterizedJob") is not None
    except (urllib.error.URLError, OSError):
        return False


@pytest.fixture
def dispatcher() -> NomadDispatcher:
    if not _scheduler_reachable():
        pytest.fail(
            "the scheduler is unreachable — run `make dev-up`. This row is not skippable: "
            "a dispatch path proven only against a double has not been proven."
        )
    if not _job_registered():
        pytest.fail(
            f"the parameterized job {JOB_ID!r} is not registered. Run "
            f"`nomad job run -var=repo=$PWD infra/jobs/agent-run.nomad.hcl`. Without it "
            "the dispatcher submits to nothing and the handle refers to nothing."
        )
    return NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id=JOB_ID)


def _correlation_id() -> str:
    return f"api-conformance-run-{uuid.uuid4().hex[:12]}"


def test_row_dispatch_returns_a_handle_without_blocking(dispatcher: NomadDispatcher) -> None:
    correlation_id = _correlation_id()

    started = time.monotonic()
    handle = dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )
    elapsed = time.monotonic() - started

    assert handle.correlation_id == correlation_id
    assert handle.state is RunState.ACTIVE

    # The timing assertion. The allocation takes tens of seconds to pull an image and
    # install dependencies; the dispatch must not wait for any of it. Generous, because
    # the claim is "does not wait for the run", not "is fast".
    assert elapsed < 10, f"dispatch took {elapsed:.1f}s — it waited for something"


def test_row_the_handle_refers_to_a_real_allocation(dispatcher: NomadDispatcher) -> None:
    """Nomad placed something. Without this the handle could be a fabrication."""
    correlation_id = _correlation_id()
    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        # A REGISTERED definition, and a role that binds to something — as of 010 the
        # entrypoint resolves both from the trust fabric, so "agent-def-1" (which this row
        # used, and which exists nowhere) now refuses `unknown_agent_definition` and fails
        # the allocation.
        #
        # That is 010 working rather than 010 breaking this row: the id was arbitrary
        # because the fabric was a dictionary that answered for any key. This row's subject
        # is the attestation path, not the definition id, so it takes a real one.
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )

    for _ in range(30):
        state = dispatcher.state_of(correlation_id)
        assert state is not None, "the dispatcher lost a run it had just started"
        allocations = _allocations_for(dispatcher, correlation_id)
        if allocations:
            break
        time.sleep(1)
    else:  # pragma: no cover - only on a scheduler that never places
        pytest.fail("no allocation was placed for the dispatched run")


def test_row_the_allocation_holds_its_own_attested_identity(dispatcher: NomadDispatcher) -> None:
    """The claim that matters, and the reason this runs against real Nomad.

    Nothing is handed to the allocation. It reaches the state store by presenting its own
    workload identity or it does not reach it at all — so the run completing is itself the
    evidence that the attestation path worked end to end.
    """
    correlation_id = _correlation_id()
    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
    )

    # Twelve minutes, raised from five in 010 after cold allocations were still
    # DOWNLOADING dependencies when the clock ran out at five and again at seven. Every
    # allocation installs from scratch — there is no shared cache — so the budget has to
    # cover a cold one or the row reports "the allocation did not start the run", which is
    # a stopwatch describing itself as a defect and sends whoever reads it to dispatch.
    #
    # The slowness is the enclave's, not this row's. Worth its own look: a uv cache shared
    # across allocations would take minutes off every dispatched run.
    deadline = time.monotonic() + 720
    alloc_id = ""
    while time.monotonic() < deadline:
        allocations = _allocations_for(dispatcher, correlation_id)
        if allocations:
            alloc = allocations[0]
            alloc_id = str(alloc.get("ID", ""))
            if str(alloc.get("ClientStatus", "")).lower() in {"complete", "failed"}:
                break
        time.sleep(5)

    assert alloc_id, "no allocation was placed"
    logs = subprocess.run(  # noqa: S603
        ["nomad", "alloc", "logs", alloc_id, "harness"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = logs.stdout + logs.stderr
    assert correlation_id in combined, (
        "the allocation did not start the run it was dispatched for.\n"
        f"--- allocation output ---\n{combined[-3000:]}"
    )
    assert "started" in combined


def _allocations_for(dispatcher: NomadDispatcher, correlation_id: str) -> list[dict[str, object]]:
    """Allocations of the dispatch this run produced.

    Resolved through the dispatcher's own record of what it dispatched, rather than by
    scanning the job listing for matching metadata: ``Meta`` is **null** in the summary
    listing, so a scan finds nothing and every assertion downstream fails for a reason
    that has nothing to do with what is being tested. Going through the dispatcher also
    exercises the code path a caller would use.
    """
    job_id = dispatcher.dispatched_job_id(correlation_id)
    if job_id is None:
        return []
    try:
        with urllib.request.urlopen(  # noqa: S310
            f"{NOMAD_ADDR}/v1/job/{urllib.parse.quote(job_id, safe='')}/allocations", timeout=5
        ) as resp:
            allocations: list[dict[str, object]] = json.loads(resp.read())
            return allocations
    except (urllib.error.URLError, OSError):
        return []
