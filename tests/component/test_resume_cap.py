# SPDX-License-Identifier: Apache-2.0
"""The revival cap (014 T009, clarify Q1, D3).

A flapping dependency must not revive one run forever. Every recovery revives it, every
revival re-suspends, and without a bound the pair runs until someone notices — which for a
sweeper on a timer means nobody does.

What these rows prove: the arithmetic, that exhaustion is **terminal** rather than another
suspension, that a claim which never succeeded costs nothing, and that no caller can raise
the cap. What they do not prove is that five is the right number; the contract says so too.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob
from core.run import RESUME_ATTEMPT_CAP, RunState
from tests.harness import durability_grant, fake_identity_fabric, frozen_clock


def _resume(provider: Any, *, holder: str = "alloc-2", clock: Any = None) -> Any:
    clock = clock or frozen_clock()
    return resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=durability_grant(clock, tool_names={"echo"}),
        holder_identity=holder,
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )


@pytest.mark.parametrize("already_used", range(RESUME_ATTEMPT_CAP))
def test_a_revival_within_the_cap_continues(already_used: int) -> None:
    """Attempt N of five continues, for every N the cap admits.

    Parameterized across the whole range rather than spot-checked at one value: an
    off-by-one at either edge is the failure mode a single case misses, and "attempt 5 of 5
    is refused" would be a bound that stops one revival early with no way to tell from the
    reason code.
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=already_used))

    decision = _resume(provider)

    assert decision.state is RunState.ACTIVE
    assert decision.resumable
    assert decision.resume_count == already_used + 1


def test_the_revival_past_the_cap_stops_terminally() -> None:
    """Attempt six is a STOP, with the reason, and never a suspension.

    Terminal is the load-bearing half. A run past its cap that suspended would wait for a
    revival that can never come: it would sit in the suspended-run index forever while the
    sweeper picked it up and refused it on every pass — a bound presenting as a leak.
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=RESUME_ATTEMPT_CAP))

    decision = _resume(provider)

    assert decision.state is RunState.STOPPED
    assert decision.stop_reason == "resume_attempts_exhausted"
    assert decision.state.is_terminal()
    assert not decision.resumable
    # No authority was manufactured for a run that is not going to run. The cap is checked
    # before the fabric is consulted, so an exhausted run costs nothing to refuse.
    assert decision.authority is None


def test_the_count_is_persisted_by_the_resume_itself() -> None:
    """Spent, therefore recorded — before the resumed allocation can die again.

    A resumed allocation can be killed at any point after the claim. An attempt that was
    spent but not written is an attempt that never happened, and a bound that forgets its
    own arithmetic is a suggestion.
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=2))

    _resume(provider)

    stored = provider.load("run-1")
    assert stored is not None
    assert stored.resume_count == 3


def test_a_claim_that_fails_leaves_the_count_untouched() -> None:
    """The ordering property, from the cap's side (T008 ⇄ T027).

    `acquire()` never raises for a *loser* — it is an unconditional supersede, because a
    resumed run must win against the zombie it replaces. So the case this guards is the
    claim that cannot be made at all: an unreachable store, or a credential that fails
    auth. Incrementing first would spend an attempt on a resume that never owned the run,
    so a store having a bad minute would eat a flapping run's whole budget and then stop it
    citing exhausted attempts — a bound reporting a cause that never occurred.
    """

    class ClaimFails(InMemoryDurabilityProvider):
        def acquire_lease(self, run_id: str, holder_identity: str) -> None:
            raise RuntimeError("state store unreachable")

    failing = ClaimFails()
    failing.save(CheckpointBlob(blob_id="run-1", resume_count=1))

    with pytest.raises(RuntimeError):
        _resume(failing)

    stored = failing.load("run-1")
    assert stored is not None
    assert stored.resume_count == 1, "a resume that never claimed the run must cost nothing"


def test_the_cap_cannot_be_supplied_by_a_caller() -> None:
    """Asserted against the signature, the way 013 asserted the model tier.

    FR-009c: the cap never comes from workflow code, the agent definition, or dispatch
    metadata. The strongest available form of that is a function with nowhere to put one —
    so this row reads the parameter list rather than trying an override and observing that
    it was ignored, which would pass just as well against a parameter that exists and is
    quietly discarded.
    """
    params = set(inspect.signature(resume_run).parameters)

    for forbidden in ("cap", "max_attempts", "resume_attempt_cap", "attempts", "resume_count"):
        assert forbidden not in params, (
            f"resume_run must not accept {forbidden!r}: a bound the bounded thing can raise "
            "is not a bound (FR-009c)"
        )


def test_a_post_resume_checkpoint_save_preserves_the_count() -> None:
    """The H1 wipe, from the store side.

    `save()` overwrites the whole row, so a per-step blob built without the count would
    reset it — making the cap clear itself whenever any work happens, and the flap row a row
    that can never reach its bound. Every revival does *some* work before re-suspending, so
    this defect would not be visible as a failure anywhere: the run would simply never stop.
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=2))

    decision = _resume(provider)
    assert decision.resume_count == 3

    # What a resumed run's step loop does: save a checkpoint for the step it just finished,
    # threading the decision's count through as the entrypoint does.
    provider.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={"step": 0},
            step_index=0,
            resume_count=decision.resume_count,
        )
    )
    assert (reloaded := provider.load("run-1")) is not None
    assert reloaded.resume_count == 3

    # And the same save WITHOUT the count still cannot lower it — the caller threads it, and
    # the store refuses to go backwards. Both, because one is a habit and the other is a
    # guarantee.
    provider.save(CheckpointBlob(blob_id="run-1", payload={"step": 1}, step_index=1))
    assert (after := provider.load("run-1")) is not None
    assert after.resume_count == 3
