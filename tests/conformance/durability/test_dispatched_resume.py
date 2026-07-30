# SPDX-License-Identifier: Apache-2.0
"""A disrupted DISPATCHED run finishes what it started (014 T016, T029, SC-001/002/011).

**This is the row the feature exists to make possible.** 005 shipped five durability
properties, every one asserted against `resume_run` the function — which had no caller in
`src/` for nine features. So "a disrupted run resumes exactly once" described a function
nobody invoked, and the platform's durable-execution claim rested on it.

What makes these rows different from every earlier resume row is what they drive: a real
allocation, really killed by the scheduler, and a second allocation that has to finish the
work. Nothing here is simulated except the choice of when to pull the plug.

Slow by construction, and the spec's own Assumption accepts it: the run does hundreds of
bracketed steps so there is something to interrupt, and each step is real durable writes
rather than a sleep.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def test_row_a_killed_dispatched_run_resumes_and_completes_exactly_once(conn: Any) -> None:
    """SC-001 and SC-002, through a dispatch.

    Exactly-once is measured with `TOOL_OUTCOME` events rather than `intents` rows, and the
    difference matters: the intents table collapses a re-run step into one row by primary key,
    so counting it would report exactly-once for an implementation that re-executed
    everything. Every invocation appends its own event.
    """
    run_id = h.unique("dispatched-resume")
    dispatcher = h.dispatcher()

    # ---- a run, dispatched, and interrupted while it still had work left
    dispatcher.dispatch(**h.dispatch_args(run_id))
    first_job = dispatcher.dispatched_job_id(run_id)
    assert first_job, "the dispatcher returned a handle naming no scheduled job"

    h.wait_for_progress(conn, run_id, min_step=h.DISRUPT_AFTER_STEP)
    first_alloc = h.allocation_of(first_job)
    h.stop_allocation(first_alloc)
    h.wait_dead(first_alloc)

    disrupted = h.checkpoint(conn, run_id)
    # THE PRECONDITION, asserted rather than assumed. If the run finished before the stop
    # landed there is nothing to resume, and a row that carried on would be asserting that a
    # completed run stays completed — passing while proving nothing.
    assert disrupted["run_state"] is None, (
        f"the run reached a terminal state ({disrupted['run_state']!r}) before it could be "
        f"disrupted, so there is nothing to resume. Raise DISRUPTION_STEPS in "
        f"dispatch_harness.py; do not relax this assertion."
    )
    assert disrupted["step_index"] < h.DISRUPTION_STEPS - 1, "the run had no work left"
    invocations_before = h.tool_invocations(conn, run_id)
    assert invocations_before > 0, "the interrupted run never invoked its tool"

    # ---- revived, in a new allocation, as a declared resume
    dispatcher.dispatch(**h.dispatch_args(run_id, resume=True))
    second_job = dispatcher.dispatched_job_id(run_id)
    assert second_job and second_job != first_job, "the resume reused the first dispatch's job"
    second_alloc = h.allocation_of(second_job)
    h.wait_dead(second_alloc)

    final = h.checkpoint(conn, run_id)
    assert final["run_state"] == "completed", (
        f"the resumed run ended {final!r} rather than completing. "
        f"nomad alloc logs -stderr {second_alloc} harness"
    )

    # ---- the pending work actually ran (analyze H2)
    #
    # Exiting zero with the remaining steps silently dropped would pass a completion-only
    # assertion, and it is the *more likely* defect of the two: a resume that skips everything
    # looks exactly like a resume that finished everything.
    assert final["step_index"] > disrupted["step_index"], (
        "the resumed allocation completed without advancing the run — its pending steps were "
        "dropped, which a completion assertion alone cannot tell from success"
    )

    # ---- exactly once, across BOTH allocations
    invocations = h.tool_invocations(conn, run_id)
    assert invocations == h.DISRUPTION_STEPS, (
        f"the run's steps were invoked {invocations} times across both allocations, expected "
        f"exactly {h.DISRUPTION_STEPS} — more means a completed step was re-executed, fewer "
        f"means work was dropped ({invocations_before} happened before the disruption)"
    )

    # ---- fresh authority in the resumed allocation (SC-002)
    credentials = h.credential_ids(conn, run_id)
    assert len(credentials) >= 2, (
        "the resumed allocation issued no authority of its own; a resume must re-authenticate "
        "rather than carry a credential across the disruption"
    )
    assert len(set(credentials)) == len(credentials), (
        f"a credential id repeated across allocations ({credentials}) — nothing may carry "
        f"authority across the disruption (FR-011, ADR-0048)"
    )

    # ---- and the revival is in the trail, with its attempt number
    resumed = h.events(conn, run_id, "run_resumed")
    assert len(resumed) == 1, f"expected one RUN_RESUMED, got {resumed}"
    assert resumed[0]["outcome"] == "continued"
    assert resumed[0]["attempt"] == 1, "the first revival is attempt 1, not 0"
    assert final["resume_count"] == 1, "the checkpoint must record the revival it survived"


def test_row_a_fresh_dispatch_reusing_a_finished_runs_identifiers_is_not_a_resume(
    conn: Any,
) -> None:
    """FR-002 and the id-collision edge case, through a dispatch (T029).

    A dispatch carrying a *used* run_id and a non-zero step index, without the flag, must
    start fresh and skip nothing. This is the failure D1 rejected inference to avoid: had the
    entrypoint inferred "a checkpoint exists, so this is a resume", a collision would become a
    silent resume that skips work it never did.

    Asserted as a pair. The second dispatch carries the flag and finds a terminal run, which
    must not be re-entered either — the same identifiers, two flag values, two correct and
    opposite behaviours.
    """
    run_id = h.unique("dispatched-fresh")
    dispatcher = h.dispatcher()
    short = dict(steps=4)

    # A complete run, so the identifiers are genuinely used.
    dispatcher.dispatch(**h.dispatch_args(run_id, **short))
    first = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(first)
    assert h.checkpoint(conn, run_id)["run_state"] == "completed"
    after_first = h.tool_invocations(conn, run_id)

    # WITH the flag: a terminal run is not re-entered, and its work does not run again.
    dispatcher.dispatch(**h.dispatch_args(run_id, resume=True, **short))
    resumed_alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(resumed_alloc)

    assert h.tool_invocations(conn, run_id) == after_first, (
        "a resume of a terminally-finished run re-executed its steps"
    )
    stopped = h.events(conn, run_id, "run_resumed")
    assert stopped and stopped[-1]["outcome"] == "stopped", (
        f"a resume finding a finished run must record why it did nothing, got {stopped}"
    )

    # WITHOUT the flag, on a fresh run id whose checkpoint already exists: starts fresh.
    #
    # A separate id because the terminal-once guard would otherwise keep the completed state
    # and make "started fresh" unobservable — which is correct behaviour and a bad assertion.
    collision_id = h.unique("dispatched-collision")
    dispatcher.dispatch(**h.dispatch_args(collision_id, **short))
    h.wait_dead(h.allocation_of(h.job_of(dispatcher, collision_id)))
    baseline = h.tool_invocations(conn, collision_id)
    assert baseline == 4, f"the baseline run did not invoke its four steps ({baseline})"

    resumed = h.events(conn, collision_id, "run_resumed")
    assert resumed == [], (
        "a dispatch that never declared itself a resume produced a RUN_RESUMED event — the "
        "entrypoint inferred a resume from the identifiers, which is exactly what D1 forbids"
    )
