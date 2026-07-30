# SPDX-License-Identifier: Apache-2.0
"""A flapping dependency does not revive one run forever (014 T024, SC-006a).

The failure this bounds is not dramatic: a product that recovers and fails and recovers again
revives the run each time, the run re-suspends each time, and the pair runs until somebody
notices. For a sweeper on a timer, nobody does.

So the bound is the point, and **terminal** is the load-bearing half. A run past its cap that
suspended again would wait for a revival that can never come — it would sit in the index while
the sweeper picked it up and refused it on every pass, which is a bound presenting as a leak.

Slow by construction: six dispatches, each a real allocation. The spec's Assumption accepts
minutes per row, because waiting is what this row tests.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.run import RESUME_ATTEMPT_CAP
from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def test_row_a_flapping_dependency_revives_a_run_exactly_to_its_cap(conn: Any) -> None:
    """Exactly `RESUME_ATTEMPT_CAP` revivals, then a terminal stop, then nothing.

    The flap is driven by dispatching each revival directly rather than by waiting for the
    sweeper, and that is a deliberate narrowing: the sweeper's revival is already in force in
    `test_dispatched_suspension_cycle.py`, and re-proving it here would add five sweep
    intervals to a row that is about arithmetic. What each dispatch stands in for is one
    recovery — the same call the sweeper would make, with the same flag.
    """
    run_id = h.unique("cap-flap")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="terraform_apply", step_index=1)

    revival = h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
        packs=frozenset({"terraform"}),
        invoke_tools=False,
        steps=4,
    )

    # ---- every revival the cap allows: suspends, stays resumable, costs one attempt
    for attempt in range(1, RESUME_ATTEMPT_CAP + 1):
        dispatcher.dispatch(**revival)
        alloc = h.allocation_of(h.job_of(dispatcher, run_id))
        h.wait_dead(alloc)
        h.assert_entrypoint_ran(alloc)

        events = h.events(conn, run_id, "run_resumed")
        assert len(events) == attempt, f"revival {attempt} was not recorded: {events}"
        assert events[-1]["attempt"] == attempt, (
            f"the trail numbered this revival {events[-1]['attempt']}, expected {attempt} — the "
            f"count must survive each disruption, which is why it lives on the checkpoint"
        )
        assert events[-1]["outcome"] == "suspended", (
            f"revival {attempt} did not re-suspend, so the flap is not flapping: {events[-1]}"
        )

        state = h.checkpoint(conn, run_id)
        assert state["resume_count"] == attempt
        assert state["run_state"] is None, (
            f"the run went terminal at revival {attempt}, before its cap of "
            f"{RESUME_ATTEMPT_CAP} — a bound that stops early is as wrong as one that never "
            f"stops"
        )

    # ---- one revival past the cap: STOPPED, with the reason, and never suspended again
    dispatcher.dispatch(**revival)
    final_alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(final_alloc)
    h.assert_entrypoint_ran(final_alloc)

    assert h.exit_code(final_alloc) == 0, (
        f"exhausting the revival budget failed the allocation (exit "
        f"{h.exit_code(final_alloc)}) — a bound is an ending, not a crash"
    )

    final = h.checkpoint(conn, run_id)
    assert final["run_state"] == "stopped", f"the cap did not stop the run: {final!r}"
    assert final["stop_reason"] == "resume_attempts_exhausted"

    last = h.events(conn, run_id, "run_resumed")[-1]
    assert last["outcome"] == "stopped", f"the sixth revival suspended again: {last}"
    assert last["reason"] == "resume_attempts_exhausted"

    # ---- and it stays stopped. The index must not hold a row for a run nothing can revive.
    assert h.suspended_rows(conn, run_id) == [], (
        "an exhausted run is still indexed as suspended — the sweeper will pick it up and "
        "refuse it on every pass forever, which is a bound presenting as a leak"
    )
