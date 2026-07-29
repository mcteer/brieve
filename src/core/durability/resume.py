# SPDX-License-Identifier: Apache-2.0
"""Resume a disrupted run — re-attest, re-acquire, re-observe, continue, stop, or suspend.

The order below is not stylistic. Each step is a gate on the next:

1. **Is there anything to resume?** A terminal run is not re-entered.
2. **Is consent still live?** An expired grant is withdrawn permission, so the run
   STOPS rather than resuming — an execution bound like any other (ADR-0049).
3. **Do we own the run?** Acquire the lease *before* acting, so a zombie is superseded
   before it can write anything more (FR-009).
4. **What actually happened?** Resolve open intents by observation, never by
   assumption. ``cannot_determine`` SUSPENDS, naming the dependency it could not
   observe, so the sweeper can resume it when that dependency recovers (ADR-0049).

On re-authentication: this module does **not** try to prevent credential replay,
because the substrate already does. A resumed run is a new Nomad allocation with a new
attested identity (ADR-0048), so the prior credential is unobtainable rather than
forbidden. What this code owes is the *negative* guarantee — introduce no path that
carries authority across the disruption. There is deliberately no parameter here for a
recovered credential, and none should be added.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from core.authority.clock import Clock
from core.authority.errors import AuthorityRefuseError
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant, GrantExpiredError
from core.authority.manufacture import ManufacturedAuthority, manufacture_authority
from core.authority.matrix import MatrixFallback
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
    #: Why the run stopped, when it stopped. An execution bound, not a suspension.
    stop_reason: str | None = None
    #: The dependency a SUSPENDED run waits on. Required for the sweeper to find it —
    #: a suspension nobody can match to a recovery is a run that never resumes.
    awaiting: str | None = None
    #: Steps observed to have already taken effect — skip these.
    completed_steps: list[IntentRecord] = field(default_factory=list)
    #: Steps observed *not* to have taken effect — these may proceed.
    pending_steps: list[IntentRecord] = field(default_factory=list)
    #: Set when this resume fell back to a different qualified cell than the run pinned.
    #:
    #: Carried for the same reason `ManufacturedAuthority` carries it: this function holds
    #: no sink and no tenant, so the caller that has both emits `MATRIX_FALLBACK`. A resumed
    #: run's fallback going unrecorded is the identical defect one phase later.
    matrix_fallback: MatrixFallback | None = None

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
    depends_on: Mapping[str, str] | None = None,
) -> ResumeDecision:
    """Decide whether and how a run continues.

    ``depends_on`` maps a tool name to the **product** it reaches, so a suspension names
    something the health checker also names. Optional, and absent it falls back to the
    tool name — which is honest rather than convenient: the sweeper watches products, so
    a suspension carrying only a tool name will not be matched by a product recovering.
    Resume has no registry of its own, and inventing one here would be a second place that
    decides what a tool depends on.
    """
    checkpoint = provider.load(blob_id)
    if checkpoint is None:
        # Not "start over": a missing checkpoint means we cannot know what already
        # happened, and guessing is the failure re-observation exists to prevent.
        # STOPPED, not suspended: a missing checkpoint does not come back. Suspending
        # would leave the sweeper waiting on a dependency that was never the problem.
        return ResumeDecision(
            state=RunState.STOPPED,
            stop_reason="checkpoint_missing",
        )

    if checkpoint.outcome is not None:
        recorded = RunState(checkpoint.outcome.state)
        if recorded.is_terminal():
            return ResumeDecision(state=recorded, checkpoint=checkpoint)

    try:
        grant.assert_live(clock, correlation_id=correlation_id)
    except GrantExpiredError:
        # ADR-0049 supersedes ADR-0026 here: grant expiry is a BOUND, recorded and
        # final, not a pause awaiting re-consent. There is no human to re-consent to.
        return ResumeDecision(
            state=RunState.STOPPED,
            checkpoint=checkpoint,
            stop_reason="grant_expired",
        )

    # Acquire before observing or acting: a zombie that writes between our observation
    # and our first step would invalidate the observation we just made.
    lease = RunLease(provider, run_id=run_id, holder_identity=holder_identity)
    lease.acquire()

    # Fresh authority under the surviving grant, from THIS allocation's identity.
    # Nothing is read from the checkpoint here, and nothing should be.
    try:
        authority = manufacture_authority(
            subject_user_id=grant.subject_user_id,
            requested_scope=grant.requested_scope,
            identity_fabric=identity_fabric,
            clock=clock,
            agent_definition_id=grant.agent_definition_id,
            correlation_id=correlation_id,
        )
    except AuthorityRefuseError as exc:
        # STOPPED with the reason, like every other failure in this function.
        #
        # Without this the exception escapes past the ResumeDecision contract **with the
        # lease already acquired** four lines above — so the run holds the lease, records no
        # reason, and nothing downstream can tell a refused resume from a crashed one.
        #
        # This was tolerable while the only refusals here were fabric-level errors. 013's
        # matrix makes it an ordinary mid-flight state: a cell can be WITHDRAWN between the
        # run starting and the run resuming (D6), and a pack a definition names can stop
        # being loaded. Both are expected, both must stop with the reason recorded
        # (FR-010, SC-004).
        return ResumeDecision(
            state=RunState.STOPPED,
            checkpoint=checkpoint,
            stop_reason=str(getattr(exc, "reason_code", "") or "authority_refused"),
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
                # The only suspension: the outcome cannot be determined because
                # something is unreachable. Names what it waits on so the sweeper can
                # resume it on recovery.
                return ResumeDecision(
                    state=RunState.SUSPENDED,
                    checkpoint=checkpoint,
                    awaiting=(depends_on or {}).get(intent.tool_name, intent.tool_name),
                    stop_reason=_unobservable_reason(intent, observation),
                )

    return ResumeDecision(
        state=RunState.ACTIVE,
        checkpoint=checkpoint,
        authority=authority,
        completed_steps=completed,
        pending_steps=pending,
        matrix_fallback=authority.matrix_fallback,
    )


def _unobservable_reason(intent: IntentRecord, observation: Observation) -> str:
    detail = f": {observation.detail}" if observation.detail else ""
    return f"unobservable_step:{intent.tool_name}#{intent.step_index}{detail}"
