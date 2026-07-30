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

    # This row's successor picks up near the START of the step list, so it has almost the
    # whole run to do — after a cold allocation start, and while the incumbent it superseded is
    # still competing for the same database. It relies on the harness default being sized for
    # that rather than for a resume finishing a small remainder.
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
    assert final["run_state"] == "completed", (
        f"the successor did not finish the run it took over: {final!r}. "
        f"nomad alloc logs -stderr {second_alloc} harness"
    )

    # ---- the loser owns the run no longer, and the run is not left half-owned
    holder = h.query(conn, "SELECT holder_identity FROM run_leases WHERE run_id = %s", (run_id,))
    assert holder, "the run has no lease at all"
    assert holder[0][0] != holder_before, (
        f"the lease still names the superseded holder {holder_before!r} — the successor never "
        f"claimed the run, so nothing was fenced"
    )

    # ---- duplicated work is BOUNDED, and this row's first version got the bound wrong
    #
    # It asserted `steps + 1`, reasoning that only the one in-flight call could survive the
    # supersede. That is true of the LEASE CHECK and false of the row, and caching the
    # allocation environment is what exposed the difference: the incumbent went from ~90s of
    # startup to ~2s, so it now covers far more ground in the window this row cares about.
    #
    # The window is not "after the successor claimed". It is **between the successor reading
    # the checkpoint and the incumbent noticing it has been superseded**. In it, the incumbent
    # is still legitimately advancing a run it still owns, and every step it takes there is a
    # step the successor has already decided to redo. That duplication is inherent to
    # overlapping a LIVE incumbent — which is the pathological case this row engineers on
    # purpose, and not the case resume exists for: in production the successor is dispatched
    # *because* the original is gone.
    #
    # So the count cannot be pinned to the step total, and pretending otherwise makes the row
    # a function of how fast the machine is. What it can do is separate working fencing from
    # absent fencing, and the gap there is enormous: an unfenced incumbent runs its own list to
    # completion, so both instances would do nearly every step and the total would approach
    # twice the run. The bound is set there, and the assertion below is the sharp one.
    invocations = h.tool_invocations(conn, run_id)
    assert invocations < h.DISRUPTION_STEPS * 2, (
        f"{invocations} invocations for {h.DISRUPTION_STEPS} steps — approaching double means "
        f"the superseded allocation ran its list to the end alongside the successor, so it was "
        f"never fenced at all (FR-009, SC-008)"
    )

    # ---- THE SHARP ONE: the superseded instance wrote nothing after losing the run.
    #
    # Timing-independent, which the count is not. `checkpoint_run` asserts the lease before
    # every write, so once the successor holds it the incumbent's writes raise rather than
    # land — and the final state of the run therefore cannot bear the loser's name. This is
    # FR-009's actual claim ("rejected, not merely raced") in the form a row can check.
    assert final["written_by"] != holder_before, (
        f"the run's last checkpoint was written by the SUPERSEDED holder {holder_before!r} — "
        f"its writes were racing the successor's rather than being rejected"
    )
