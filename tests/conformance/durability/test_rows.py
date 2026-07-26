# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the seven durability rows, in force (ADR-0047, FR-013).

Each runs against **both** providers via the ``provider`` fixture. They assert the
seam's behaviour, not any implementation's: that is what makes ADR-0024's claim
checkable rather than asserted.

Single-node caveat, recorded so the claim is not read as broader than it is: the
enclave runs one Vault node and one Nomad server, so fencing and parking are proven
against single-node behaviour and multi-node partition is not exercised.
"""

from __future__ import annotations

from datetime import timedelta

from core.authority.grant import DelegationGrant, issue_grant
from core.authority.types import AuthorityScope
from core.durability.lease import RunLease
from core.durability.resume import ResumeDecision, resume_run
from core.durability.types import CheckpointBlob, DurabilityProvider, IntentRecord, RunOutcome
from core.observation.types import ObservationOutcome, Observer
from core.run import RunState
from tests.conformance.durability import rows
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    ScriptedObserver,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.frozen_clock import FrozenClock


def _write(
    provider: DurabilityProvider,
    run_id: str,
    *,
    step: int,
    outcome: RunOutcome | None = None,
) -> None:
    provider.save(
        CheckpointBlob(
            blob_id=run_id,
            payload={"progress": f"step-{step}"},
            correlation_id="corr-conformance",
            grant_id="grant-1",
            step_index=step,
            written_by="alloc-1",
            outcome=outcome,
        )
    )


def _resume(
    provider: DurabilityProvider,
    run_id: str,
    grant: DelegationGrant,
    clock: FrozenClock,
    observers: dict[str, Observer] | None = None,
) -> ResumeDecision:
    return resume_run(
        provider,
        blob_id=run_id,
        run_id=run_id,
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
        observers=observers or {},
    )


# ------------------------------------------------------------------ row 1: kill/resume


def test_kill_and_resume(provider: DurabilityProvider, run_id: str) -> None:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"echo"})
    _write(provider, run_id, step=2)

    decision = _resume(provider, run_id, grant, clock)

    rows.assert_resumes_from_checkpoint(decision.checkpoint, expected_step=2)
    assert decision.resumable
    rows.assert_executed_exactly_once({"step-1": 1}, "step-1")


# ------------------------------------------- row 2: re-authenticate, never replay


def test_reauthenticate_never_replay(provider: DurabilityProvider, run_id: str) -> None:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"echo"})
    _write(provider, run_id, step=1)

    decision = _resume(provider, run_id, grant, clock)
    assert decision.checkpoint is not None

    rows.assert_no_credential_in_checkpoint(decision.checkpoint)
    rows.assert_fresh_authority(
        "pre-disruption-credential",
        decision.authority.credential.credential_id if decision.authority else None,
    )


# ------------------------------------------ row 3: re-observe, never re-execute


def test_reobserve_never_reexecute(provider: DurabilityProvider, run_id: str) -> None:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"echo"})
    _write(provider, run_id, step=1)
    key = f"{run_id}:1:provision"
    provider.record_intent(
        IntentRecord(
            run_id=run_id,
            step_index=1,
            tool_name="provision",
            idempotency_key=key,
            recorded_at=clock.now(),
        )
    )

    happened = _resume(
        provider,
        run_id,
        grant,
        clock,
        {"provision": ScriptedObserver(outcomes={key: ObservationOutcome.HAPPENED})},
    )
    rows.assert_observation_decides(
        ObservationOutcome.HAPPENED,
        repeated=key in [i.idempotency_key for i in happened.pending_steps],
    )
    assert [i.idempotency_key for i in happened.completed_steps] == [key]


# -------------------------------------------- row 4: fencing against double resume


def test_fencing_against_double_resume(provider: DurabilityProvider, run_id: str) -> None:
    first = RunLease(provider, run_id=run_id, holder_identity="alloc-1")
    second = RunLease(provider, run_id=run_id, holder_identity="alloc-2")
    first.acquire()
    second.acquire()

    rows.assert_superseded_is_rejected(provider, run_id, "alloc-1")
    assert second.held()


# ------------------------------------------------ row 5: parking on grant expiry


def test_park_on_grant_expiry(provider: DurabilityProvider, run_id: str) -> None:
    clock = frozen_clock()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=10),
    )
    _write(provider, run_id, step=1)
    clock.advance(timedelta(minutes=11))

    decision = _resume(provider, run_id, grant, clock)

    rows.assert_parked(decision.state, decision.park_reason, expected_prefix="grant_expired")
    assert decision.authority is None


# ---------------------------------------- row 6: duplicate side-effect rejection


def test_duplicate_side_effect_rejection(provider: DurabilityProvider, run_id: str) -> None:
    """A repeat of the same step is recognisable as the same step (FR-010)."""
    clock = frozen_clock()
    key = f"{run_id}:3:provision"
    record = IntentRecord(
        run_id=run_id,
        step_index=3,
        tool_name="provision",
        idempotency_key=key,
        recorded_at=clock.now(),
    )
    provider.record_intent(record)
    provider.record_intent(record)  # a retry of the same step, not a new one

    open_intents = provider.open_intents(run_id)
    keys = [i.idempotency_key for i in open_intents if i.idempotency_key == key]
    assert len(keys) == 1, "the retry was recorded as a second step"
    rows.assert_same_step_same_key(keys[0], key)


# ------------------------------------------------- row 7: drain across upgrade


def test_drain_across_upgrade(provider: DurabilityProvider, run_id: str) -> None:
    """A controlled in-process handover — simulated, and labelled as such.

    Not a real rolling upgrade: the enclave is single-node, and this asserts that a
    handover preserves the run and its evidence, which is the part a rolling upgrade
    would also have to satisfy.
    """
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"echo"})
    _write(provider, run_id, step=4)
    outgoing = RunLease(provider, run_id=run_id, holder_identity="alloc-old")
    outgoing.acquire()

    incoming = RunLease(provider, run_id=run_id, holder_identity="alloc-new")
    incoming.acquire()
    decision = _resume(provider, run_id, grant, clock)

    assert decision.resumable, "the run did not survive the handover"
    assert decision.checkpoint is not None
    rows.assert_evidence_spans_disruption(decision.checkpoint, "corr-conformance")
    rows.assert_superseded_is_rejected(provider, run_id, "alloc-old")


def test_terminal_run_is_not_resumed(provider: DurabilityProvider, run_id: str) -> None:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"echo"})
    _write(provider, run_id, step=9, outcome=RunOutcome(state=RunState.COMPLETED.value))

    decision = _resume(provider, run_id, grant, clock)

    assert decision.state is RunState.COMPLETED
    assert not decision.resumable
