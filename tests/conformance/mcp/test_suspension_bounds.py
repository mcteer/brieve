# SPDX-License-Identifier: Apache-2.0
"""Row: suspension expires against the run's EXISTING maximum duration (FR-013).

Not a new ceiling, no timeout that grants by default, and no escalation that lowers a
requirement. A dependency down long enough to exhaust a run's whole budget indicates a
failure well beyond this platform's concern — the right outcome there is a stopped run and
an alert, not a platform that keeps trying.
"""

from __future__ import annotations

from datetime import timedelta

from core.authority.grant import issue_grant
from core.authority.types import AuthorityScope
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.run import RunState
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock


def test_row_a_dependency_down_past_the_bound_stops_the_run() -> None:
    """The grant runs out while the run waits, and the run stops rather than waiting on."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=30),
    )

    # The dependency stays down long enough to exhaust the grant.
    clock.advance(timedelta(minutes=31))

    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )

    # STOPPED, not suspended again. The bound is the bound.
    assert decision.state is RunState.STOPPED
    assert decision.state.is_terminal()


def test_row_suspension_introduces_no_second_ceiling() -> None:
    """There is no `resume_after`, retry counter, or escalation field to introduce one.

    Each would be a way for a run to wait on a clock or a person rather than on a named
    machine condition, which is the distinction ADR-0049 is entirely about.
    """
    from core.durability.sweeper import SuspendedRunRecord

    fields = set(SuspendedRunRecord.__dataclass_fields__)
    for forbidden in ("resume_after", "retry_count", "attempts", "escalate_at", "deadline"):
        assert forbidden not in fields, (
            f"{forbidden!r} would let a suspended run wait on something other than its "
            "named dependency"
        )
