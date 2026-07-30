# SPDX-License-Identifier: Apache-2.0
"""Withdrawn consent ends a run, terminally (014 T025, US4, FR-014).

ADR-0049 supersedes ADR-0026 here, and the supersession is the whole point: an expired grant
used to mean "park for re-consent", and there is no human to re-consent to. So expiry is a
BOUND — recorded, final, and never a pause.

**These rows became meaningful only in 014.** Before the grant store existed the dispatched
path had nothing to check expiry against, so US4 was a requirement no code could evaluate.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from core.authority.grant import DelegationGrant
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import ResumeDecision, resume_run
from core.durability.types import CheckpointBlob, RunOutcome
from core.run import RunState
from tests.harness import durability_grant, fake_identity_fabric, frozen_clock


def _resume_with(
    provider: Any, grant: DelegationGrant, clock: Any, holder: str = "alloc-2"
) -> ResumeDecision:
    return resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity=holder,
        identity_fabric=fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names={"echo"},
            ceiling_tools={"echo"},
        ),
        clock=clock,
    )


def test_an_expired_grant_stops_the_run_before_any_step() -> None:
    """Consent is checked before the lease is even claimed.

    The ordering matters: a run whose consent has lapsed must not acquire the run, manufacture
    authority, or observe anything. Each of those is an action taken under permission that no
    longer exists.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"}, duration=timedelta(minutes=5))
    provider.save_grant(grant)
    provider.save(CheckpointBlob(blob_id="run-1", grant_id=grant.grant_id, step_index=2))

    clock.advance(timedelta(hours=1))
    decision = _resume_with(provider, grant, clock)

    assert decision.state is RunState.STOPPED
    assert decision.stop_reason == "grant_expired"
    assert decision.authority is None, "no authority may be manufactured under lapsed consent"
    # The attempt was not spent: consent is checked before the claim, so an expired grant does
    # not consume a revival from the budget.
    assert decision.resume_count == 0


def test_a_reissued_grant_does_not_revive_a_stopped_run() -> None:
    """Terminal means terminal — renewing consent revives nothing.

    A stopped run carries a terminal checkpoint, so `resume_run` refuses to re-enter it and
    the sweeper's `_is_suspended` drops it as a stale candidate. Both halves matter: without
    the first a new grant would restart finished work, and without the second the sweeper
    would retry it on every pass forever.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    expired = durability_grant(clock, tool_names={"echo"}, duration=timedelta(minutes=5))
    provider.save_grant(expired)
    provider.save(
        CheckpointBlob(
            blob_id="run-1",
            grant_id=expired.grant_id,
            step_index=2,
            outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason="grant_expired"),
        )
    )

    fresh = durability_grant(clock, tool_names={"echo"}, duration=timedelta(hours=8))
    provider.save_grant(fresh)
    decision = _resume_with(provider, fresh, clock)

    assert decision.state.is_terminal()
    assert not decision.resumable, "a terminal run was re-entered under a re-issued grant"


def test_a_refused_resume_records_its_reason_rather_than_raising() -> None:
    """FR-014: every refusal is a recorded decision, not an exception.

    An exception escaping past the `ResumeDecision` contract would leave the run holding the
    lease with no reason written, and nothing downstream could tell a refused resume from a
    crashed one. The two have completely different remedies.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"}, duration=timedelta(minutes=1))
    provider.save_grant(grant)
    provider.save(CheckpointBlob(blob_id="run-1", grant_id=grant.grant_id))
    clock.advance(timedelta(hours=1))

    decision = _resume_with(provider, grant, clock)

    assert decision.stop_reason, "a refusal with no reason is a refusal nobody can act on"
    assert decision.state is RunState.STOPPED
