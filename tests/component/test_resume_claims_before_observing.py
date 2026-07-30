# SPDX-License-Identifier: Apache-2.0
"""One actor per run: the claim comes before the observation (014 T027, US5, FR-009).

The ordering is the guarantee. A zombie that writes between our observation and our first step
would invalidate the observation we just made — so the lease is acquired *before* anything is
observed, and `resume_run`'s docstring carries the numbered list this row asserts.

**The call ORDER is asserted, not just the outcome.** A correct-looking implementation that
observed first and claimed second would produce identical decisions on every input a test
happens to try, and would be wrong exactly when two allocations overlap — which is the only
case the property is about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob, IntentRecord
from core.observation.types import ObservationOutcome
from tests.harness import ScriptedObserver, durability_grant, fake_identity_fabric, frozen_clock


class _Recording(InMemoryDurabilityProvider):
    """Notes the order of the operations the resume performs on the store."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def acquire_lease(self, run_id: str, holder_identity: str) -> None:
        self.calls.append("acquire_lease")
        super().acquire_lease(run_id, holder_identity)

    def open_intents(self, run_id: str) -> list[IntentRecord]:
        self.calls.append("open_intents")
        return super().open_intents(run_id)

    def save(self, blob: CheckpointBlob) -> None:
        self.calls.append("save")
        super().save(blob)


def _prepared(provider: Any) -> Any:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"vault_write"})
    provider.save_grant(grant)
    provider.save(CheckpointBlob(blob_id="run-1", grant_id=grant.grant_id, resume_count=1))
    provider.record_intent(
        IntentRecord(
            run_id="run-1",
            idempotency_key="run-1:0:vault_write",
            step_index=0,
            tool_name="vault_write",
            recorded_at=datetime.now(UTC),
        )
    )
    provider.calls.clear()
    return clock, grant


def test_the_lease_is_claimed_before_any_intent_is_observed() -> None:
    provider = _Recording()
    clock, grant = _prepared(provider)

    resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names={"vault_write"},
            ceiling_tools={"vault_write"},
        ),
        clock=clock,
        observers={"vault_write": ScriptedObserver(default=ObservationOutcome.HAPPENED)},
    )

    assert "acquire_lease" in provider.calls
    assert "open_intents" in provider.calls
    assert provider.calls.index("acquire_lease") < provider.calls.index("open_intents"), (
        f"observation preceded the claim ({provider.calls}) — a zombie writing in that window "
        f"would invalidate the observation the resume then acts on"
    )


def test_the_attempt_is_counted_after_the_claim_not_before() -> None:
    """The persisted count follows the claim, so a claim that never lands costs nothing."""
    provider = _Recording()
    clock, grant = _prepared(provider)

    resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names={"vault_write"},
            ceiling_tools={"vault_write"},
        ),
        clock=clock,
        observers={"vault_write": ScriptedObserver(default=ObservationOutcome.HAPPENED)},
    )

    assert provider.calls.index("acquire_lease") < provider.calls.index("save")


def test_a_claim_that_cannot_be_made_leaves_the_count_untouched() -> None:
    """The T008 ⇄ T027 interaction, from the fencing side.

    `acquire()` never raises for a *loser* — it supersedes unconditionally, because a resumed
    run must win against the zombie it replaces. So the case that matters is a claim that
    cannot be made at all, and an attempt spent on a resume that never owned the run would let
    an unreachable store exhaust a healthy run's budget.
    """

    class ClaimFails(_Recording):
        def acquire_lease(self, run_id: str, holder_identity: str) -> None:
            raise RuntimeError("state store unreachable")

    provider = ClaimFails()
    clock, grant = _prepared(provider)

    with pytest.raises(RuntimeError):
        resume_run(
            provider,
            blob_id="run-1",
            run_id="run-1",
            grant=grant,
            holder_identity="alloc-2",
            identity_fabric=fake_identity_fabric(
                subject_user_id=grant.subject_user_id,
                tool_names={"vault_write"},
                ceiling_tools={"vault_write"},
            ),
            clock=clock,
        )

    stored = provider.load("run-1")
    assert stored is not None
    assert stored.resume_count == 1, "an attempt was spent by a resume that never claimed the run"
