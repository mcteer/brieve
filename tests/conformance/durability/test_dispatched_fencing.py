# SPDX-License-Identifier: Apache-2.0
"""One actor per run, through a real dispatch overlap (014 T028, US5, SC-008).

FR-009 asks for something stronger than "the successor wins the race": a superseded
instance's writes must be **rejected**, which is a comparison whose answer does not depend on
who got there first. The lease compares identity, and under ADR-0048 a resumed run is a new
allocation with a new attested identity — so the zombie is holding something that provably is
not current.

The overlap is engineered rather than waited for: the first allocation is left RUNNING and a
resume is dispatched underneath it. That is the zombie case exactly — an instance that lost
contact with the platform but not with the database.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def test_row_a_superseded_allocation_writes_nothing_further(conn: Any) -> None:
    """The successor completes; the superseded instance achieves nothing.

    Both halves are asserted, and the second is the one that needs a real overlap: a row that
    only checked "the run completed" would pass against a platform with no fencing at all,
    because the zombie's writes look exactly like the winner's.
    """
    run_id = h.unique("fencing")
    dispatcher = h.dispatcher()

    # ---- the incumbent, still running and still writing
    dispatcher.dispatch(**h.dispatch_args(run_id))
    first_alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_for_progress(conn, run_id, min_step=h.DISRUPT_AFTER_STEP)

    incumbent = h.checkpoint(conn, run_id)
    assert incumbent["run_state"] is None, "the incumbent finished before it could be overlapped"
    holder_before = incumbent["written_by"]

    # ---- the successor, dispatched WITHOUT stopping the first. Both are now alive, and the
    # first does not know it has been replaced — which is the whole point.
    dispatcher.dispatch(**h.dispatch_args(run_id, resume=True))
    second_alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    assert second_alloc != first_alloc

    h.wait_dead(second_alloc)

    h.assert_entrypoint_ran(second_alloc)
    # The incumbent must also end — its next lease-checked write raises, which fails the
    # allocation. That failure is the mechanism working, not a defect.
    deadline = time.time() + 300
    while time.time() < deadline and h.task_state(first_alloc) != "dead":
        time.sleep(5)
    assert h.task_state(first_alloc) == "dead", (
        f"the superseded allocation was still running after the successor finished. It holds a "
        f"lease it no longer owns: nomad alloc logs -stderr {first_alloc} harness"
    )

    final = h.checkpoint(conn, run_id)
    assert final["written_by"] != holder_before or final["run_state"] == "completed", (
        "the last write came from the superseded instance"
    )

    # ---- zero side effects from the loser, counted through the trail
    #
    # Exactly one invocation per step across BOTH allocations. A zombie that kept invoking
    # tools after being superseded would push this over the total, and that is the count SC-008
    # is really about: fencing that rejects state writes but not tool calls is fencing that
    # stops the record and not the effect.
    invocations = h.tool_invocations(conn, run_id)
    assert invocations <= h.DISRUPTION_STEPS, (
        f"{invocations} invocations for {h.DISRUPTION_STEPS} steps — the superseded allocation "
        f"went on calling tools after losing the run (FR-009, SC-008)"
    )

    # And the run is not left half-owned: whoever holds the lease is the successor.
    holder = h.query(conn, "SELECT holder_identity FROM run_leases WHERE run_id = %s", (run_id,))
    assert holder, "the run has no lease at all"
    assert holder[0][0] != holder_before, (
        f"the lease still names the superseded holder {holder_before!r} — the successor never "
        f"claimed the run, so nothing was fenced"
    )
