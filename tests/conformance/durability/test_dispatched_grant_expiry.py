# SPDX-License-Identifier: Apache-2.0
"""Withdrawn consent ends a dispatched run, terminally (014 T026, US4, SC-007).

**This row was impossible before this feature, and not because nobody wrote it.** The
dispatched path issued no grant and persisted none, so there was no record for a resume to
check expiry against — `resume_run` requires a `DelegationGrant` and nothing dispatched could
supply one. US4 was a requirement no code could evaluate. The `grants` table is what makes the
question askable, and this row is what makes the answer evidence.

ADR-0049 over ADR-0026: expiry is a BOUND, recorded and final, not a pause awaiting
re-consent. There is no human to re-consent to.
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


def test_row_a_resume_under_lapsed_consent_stops_with_zero_further_steps(conn: Any) -> None:
    """Stopped, recorded, terminal, and nothing ran.

    The grant is arranged already-expired rather than by waiting out a short TTL, and the
    difference is only in wall clock: `assert_live` compares the record against the clock, so a
    grant that expired a minute ago and one that expires while the row waits are the same input.
    Waiting would add a minute to a merge-blocking lane to test the clock rather than the bound.
    """
    run_id = h.unique("grant-expiry")
    dispatcher = h.dispatcher()
    # Negative interval: consent that lapsed before the revival was attempted.
    h.arrange_disrupted(conn, run_id, tool_name="echo", step_index=1, grant_ttl="-1 hours")

    dispatcher.dispatch(
        **h.dispatch_args(
            run_id,
            resume=True,
            agent_definition_id="planner-agent",
            requested_tools=frozenset({"echo"}),
            subject_roles=frozenset({"operator"}),
            packs=frozenset(),
            invoke_tools=False,
            steps=6,
        )
    )
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    # EXIT ZERO. A bound is an ending, not a failure — an allocation that failed here would
    # make every expired grant look like an outage to whoever reads allocation states.
    assert h.exit_code(alloc) == 0, (
        f"a bounded stop failed the allocation (exit {h.exit_code(alloc)}). "
        f"nomad alloc logs -stderr {alloc} harness"
    )

    final = h.checkpoint(conn, run_id)
    assert final["run_state"] == "stopped", f"expected a stopped run, got {final!r}"
    assert final["stop_reason"] == "grant_expired"

    # Zero subsequent steps: the run must not advance past where the disruption left it.
    assert final["step_index"] == 1, (
        f"the run advanced to step {final['step_index']} under lapsed consent — a bound checked "
        f"after the work is not a bound"
    )
    assert h.tool_invocations(conn, run_id) == 0, "a tool ran under withdrawn permission"

    recorded = h.events(conn, run_id, "run_resumed")
    assert recorded and recorded[-1]["outcome"] == "stopped"
    assert recorded[-1]["reason"] == "grant_expired", (
        "the trail must say WHY the run stopped; a stop with no reason is one nobody can act on"
    )


def test_row_reissuing_consent_revives_nothing(conn: Any) -> None:
    """Terminal means terminal.

    A fresh grant does not restart a stopped run: the terminal checkpoint is what `resume_run`
    refuses and what the sweeper's `_is_suspended` drops as stale. Both halves matter — without
    the first a new grant would restart finished work, without the second the sweeper would
    retry it forever.
    """
    run_id = h.unique("grant-reissue")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="echo", step_index=1, grant_ttl="-1 hours")

    resume_args = h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
        packs=frozenset(),
        invoke_tools=False,
        steps=6,
    )
    dispatcher.dispatch(**resume_args)
    h.wait_dead(h.allocation_of(h.job_of(dispatcher, run_id)))
    assert h.checkpoint(conn, run_id)["stop_reason"] == "grant_expired"

    # Consent, re-issued — a new grant, live, pointed at by the same checkpoint.
    h.arrange_disrupted(conn, run_id, tool_name="echo", step_index=1, grant_ttl="8 hours")

    dispatcher.dispatch(**resume_args)
    second = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(second)
    h.assert_entrypoint_ran(second)

    final = h.checkpoint(conn, run_id)
    assert final["run_state"] == "stopped", (
        f"a re-issued grant revived a terminally stopped run ({final!r}) — the terminal-once "
        f"guard and resume's terminal check are what prevent this, and one of them gave way"
    )
    assert h.tool_invocations(conn, run_id) == 0
