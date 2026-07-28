# SPDX-License-Identifier: Apache-2.0
"""Terminal run states — T017a.

Without COMPLETED, a resume attempt against a finished run re-enters the loop and
re-runs work under a consent the user believes is spent. Without STOPPED distinct from
PARKED, a bounded run looks resumable and the bound means nothing.
"""

from __future__ import annotations

import pytest
from tests.harness import durability_grant, fake_identity_fabric, frozen_clock, write_checkpoint
from tests.harness.frozen_clock import FrozenClock

from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import ResumeDecision, resume_run
from core.durability.types import RunOutcome
from core.run import RunState


def _resume(
    provider: InMemoryDurabilityProvider,
    grant: DelegationGrant,
    clock: FrozenClock,
    fabric: IdentityFabric,
) -> ResumeDecision:
    return resume_run(
        provider,
        blob_id="blob-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fabric,
        clock=clock,
    )


@pytest.mark.parametrize("terminal", [RunState.COMPLETED, RunState.STOPPED, RunState.REFUSED])
def test_terminal_run_is_not_re_entered(terminal: RunState) -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock)
    write_checkpoint(
        provider,
        blob_id="blob-1",
        correlation_id="corr-1",
        grant_id=grant.grant_id,
        step_index=3,
        written_by="alloc-1",
        outcome=RunOutcome(state=terminal.value),
    )

    decision = _resume(provider, grant, clock, fake_identity_fabric(tool_names={"read_tool"}))

    assert decision.state is terminal
    assert not decision.resumable
    # Nothing was manufactured: a terminal run gets no fresh authority.
    assert decision.authority is None


def test_stopped_carries_its_reason() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock)
    write_checkpoint(
        provider,
        blob_id="blob-1",
        correlation_id="corr-1",
        grant_id=grant.grant_id,
        step_index=9,
        written_by="alloc-1",
        outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason="max_steps"),
    )

    blob = provider.load("blob-1")
    assert blob is not None
    assert blob.outcome is not None
    assert blob.outcome.stop_reason == "max_steps"


def test_active_run_resumes() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock)
    write_checkpoint(
        provider,
        blob_id="blob-1",
        correlation_id="corr-1",
        grant_id=grant.grant_id,
        step_index=2,
        written_by="alloc-1",
    )

    decision = _resume(provider, grant, clock, fake_identity_fabric(tool_names={"read_tool"}))

    assert decision.state is RunState.ACTIVE
    assert decision.resumable
    assert decision.authority is not None


def test_missing_checkpoint_parks_rather_than_starting_over() -> None:
    """Not knowing what already happened is exactly the case guessing must not cover."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock)

    decision = _resume(provider, grant, clock, fake_identity_fabric(tool_names={"read_tool"}))

    assert decision.state is RunState.STOPPED
    assert decision.stop_reason == "checkpoint_missing"


def test_parked_is_not_terminal() -> None:
    """Parked is waiting, not failed — it must stay resumable."""
    assert not RunState.SUSPENDED.is_terminal(), (
        "SUSPENDED must stay resumable — terminal here means the sweeper resumes nothing"
    )
    assert RunState.COMPLETED.is_terminal()
    assert RunState.STOPPED.is_terminal()
