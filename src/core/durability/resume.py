# SPDX-License-Identifier: Apache-2.0
"""Resume a disrupted run — re-attest, re-acquire, re-observe, continue or park.

The order below is not stylistic. Each step is a gate on the next:

1. **Is there anything to resume?** A terminal run is not re-entered.
2. **Is consent still live?** An expired grant is withdrawn permission, so the run
   parks rather than resuming (FR-005).
3. **Do we own the run?** Acquire the lease *before* acting, so a zombie is superseded
   before it can write anything more (FR-009).
4. **What actually happened?** Resolve open intents by observation, never by
   assumption. ``cannot_determine`` parks (FR-008).

On re-authentication: this module does **not** try to prevent credential replay,
because the substrate already does. A resumed run is a new Nomad allocation with a new
attested identity (ADR-0048), so the prior credential is unobtainable rather than
forbidden. What this code owes is the *negative* guarantee — introduce no path that
carries authority across the disruption. There is deliberately no parameter here for a
recovered credential, and none should be added.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.authority.clock import Clock
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant, GrantExpiredError
from core.authority.manufacture import ManufacturedAuthority, manufacture_authority
from core.durability.lease import RunLease
from core.durability.types import CheckpointBlob, DurabilityProvider, IntentRecord
from core.observation.bracket import resolve_open_intents
from core.observation.types import Observation, ObservationOutcome, Observer
from core.run import RunState


@dataclass(frozen=True)
class ResumeDecision:
    """What resume concluded, and why.

    Returned rather than acted upon so the reasoning is visible to the caller and to
    the audit trail, instead of being buried in control flow.
    """

    state: RunState
    checkpoint: CheckpointBlob | None = None
    authority: ManufacturedAuthority | None = None
    park_reason: str | None = None
    #: Steps observed to have already taken effect — skip these.
    completed_steps: list[IntentRecord] = field(default_factory=list)
    #: Steps observed *not* to have taken effect — these may proceed.
    pending_steps: list[IntentRecord] = field(default_factory=list)

    @property
    def resumable(self) -> bool:
        return self.state is RunState.ACTIVE


def resume_run(
    provider: DurabilityProvider,
    *,
    blob_id: str,
    run_id: str,
    grant: DelegationGrant,
    holder_identity: str,
    identity_fabric: IdentityFabric,
    clock: Clock,
    observers: dict[str, Observer] | None = None,
    correlation_id: str | None = None,
) -> ResumeDecision:
    """Decide whether and how a run continues."""
    checkpoint = provider.load(blob_id)
    if checkpoint is None:
        # Not "start over": a missing checkpoint means we cannot know what already
        # happened, and guessing is the failure re-observation exists to prevent.
        return ResumeDecision(
            state=RunState.PARKED,
            park_reason="checkpoint_missing",
        )

    if checkpoint.outcome is not None:
        recorded = RunState(checkpoint.outcome.state)
        if recorded.is_terminal():
            return ResumeDecision(state=recorded, checkpoint=checkpoint)

    try:
        grant.assert_live(clock, correlation_id=correlation_id)
    except GrantExpiredError:
        return ResumeDecision(
            state=RunState.PARKED,
            checkpoint=checkpoint,
            park_reason="grant_expired",
        )

    # Acquire before observing or acting: a zombie that writes between our observation
    # and our first step would invalidate the observation we just made.
    lease = RunLease(provider, run_id=run_id, holder_identity=holder_identity)
    lease.acquire()

    # Fresh authority under the surviving grant, from THIS allocation's identity.
    # Nothing is read from the checkpoint here, and nothing should be.
    authority = manufacture_authority(
        subject_user_id=grant.subject_user_id,
        requested_scope=grant.requested_scope,
        identity_fabric=identity_fabric,
        clock=clock,
        agent_definition_id=grant.agent_definition_id,
        correlation_id=correlation_id,
    )

    resolved = resolve_open_intents(provider, run_id=run_id, observers=observers or {}, clock=clock)
    completed: list[IntentRecord] = []
    pending: list[IntentRecord] = []
    for intent, observation in resolved:
        match observation.outcome:
            case ObservationOutcome.HAPPENED:
                completed.append(intent)
            case ObservationOutcome.DID_NOT_HAPPEN:
                pending.append(intent)
            case ObservationOutcome.CANNOT_DETERMINE:
                return ResumeDecision(
                    state=RunState.PARKED,
                    checkpoint=checkpoint,
                    park_reason=_unobservable_reason(intent, observation),
                )

    return ResumeDecision(
        state=RunState.ACTIVE,
        checkpoint=checkpoint,
        authority=authority,
        completed_steps=completed,
        pending_steps=pending,
    )


def _unobservable_reason(intent: IntentRecord, observation: Observation) -> str:
    detail = f": {observation.detail}" if observation.detail else ""
    return f"unobservable_step:{intent.tool_name}#{intent.step_index}{detail}"
