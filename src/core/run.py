# SPDX-License-Identifier: Apache-2.0
"""Governed run initiation — refuse uncorrelated or unauthenticated authority starts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink
from core.authority.clock import Clock, SystemClock
from core.authority.entitlements import BrokeredMaterialSource
from core.authority.errors import AuthorityRefuseError
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant
from core.authority.hashing import content_hash
from core.authority.manufacture import ManufacturedAuthority, manufacture_authority
from core.authority.types import AuthorityScope, TaskCredentialRef
from core.correlation import validate_correlation_id
from core.errors import CoreError, CorrelationRequiredError
from core.hooks.governance import builtin_governance_hooks
from core.hooks.types import HookRegistration
from core.identity.tenant import resolve_tenant
from core.registry.memory import ToolRegistry

if TYPE_CHECKING:
    # Type-only: importing the durability package at runtime would cycle back here
    # through resume.py, which needs RunState.
    from core.bounds import BoundsTracker
    from core.dependencies.types import DependencyHealthReader
    from core.durability.lease import RunLease
    from core.durability.types import DurabilityProvider


#: How many times one run may be revived before the platform stops reviving it (D3).
#:
#: **Deliberately not in `core.bounds`**, which is where "beside the other bounds" would
#: put it. Every constant there — `DEFAULT_MAX_DURATION`, `DEFAULT_MAX_STEPS`,
#: `DEFAULT_STUCK_WAIT` — is the default for a field on `ExecutionBounds`, a dataclass a
#: caller constructs. A cap living there would arrive with an override slot already
#: fitted, and the next person to want a longer flap would fit one. FR-009c forbids
#: exactly that: the cap never comes from workflow code, the agent definition, or
#: dispatch metadata, because a bound the bounded thing can raise is not a bound. Here it
#: is a module constant that `core.durability.resume` reads directly rather than accepts
#: as a parameter — so there is no seam to pass a larger number through, and the
#: component row asserts that by inspecting the signature.
#:
#: Five is a tunable starting point rather than a finding: large enough that a real
#: outage's recovery — one suspension, one revival — never approaches it, small enough
#: that a flapping dependency stops within minutes. The rows prove exhaustion is terminal
#: and recorded. They do not prove five is the number an operator wants.
RESUME_ATTEMPT_CAP = 5


class RunState(StrEnum):
    """Terminal states are three, not one.

    002 shipped ACTIVE and REFUSED, which sufficed while nothing had to survive a
    restart. Durable execution needs all three distinctions: without COMPLETED a resume
    attempt against a finished run re-enters the loop, and calling a bounded stop
    SUSPENDED would invite resuming past the bound.

    ``PARKED`` used to live here and meant "stopped for a human to resolve". ADR-0049
    removed that category — consent to start a run is consent to finish it — so the state
    went with it rather than being renamed. Keeping the name would have carried the
    human-in-the-loop connotation into ``SUSPENDED``, which is the one state that most
    needs it gone: a suspended run waits on a *machine condition* that clears itself.
    """

    ACTIVE = "active"
    REFUSED = "refused"
    #: Finished its work.
    COMPLETED = "completed"
    #: Halted by an execution bound; ``stop_reason`` records which one.
    STOPPED = "stopped"
    #: Waiting on a named dependency to become reachable again. Resumable by the
    #: sweeper, never by a person, and never by a timeout that grants by default.
    SUSPENDED = "suspended"

    def is_terminal(self) -> bool:
        """True when there is nothing left to resume.

        ``SUSPENDED`` is deliberately absent: it is the one non-terminal stop, and the
        sweeper's whole job is to resume it. Adding it here would make the sweeper able to
        resume nothing while every test still passed — and omitting ``STOPPED`` would let a
        run resume past a bound it already hit.
        """
        return self in {RunState.REFUSED, RunState.COMPLETED, RunState.STOPPED}


@dataclass
class GovernedRun:
    correlation_id: str
    #: Bounding dimension carried onto every audit entry this run writes (008, FR-010d).
    tenant_id: str
    scope: frozenset[str]
    registry: ToolRegistry
    audit_sink: AuditSink
    authority: TaskCredentialRef
    run_salt: bytes
    subject_user_id: str
    # Threaded so live policy re-resolution on every invoke is per-definition, not global.
    agent_definition_id: str
    identity_fabric: IdentityFabric
    clock: Clock
    hooks: list[HookRegistration] = field(default_factory=list)
    state: RunState = RunState.ACTIVE
    #: Set on the transition to STOPPED, so FR-011's "reason recorded" is data.
    stop_reason: str | None = None
    #: Durable consent this run proceeds under (005). None for un-granted 002/003 runs.
    grant: DelegationGrant | None = None
    #: Single-writer claim. None when the run is not durability-managed.
    lease: RunLease | None = None
    #: Stable id for lease and bracket records. Defaults to the correlation id.
    run_id: str = ""
    #: Where checkpoints and brackets go. None for 002/003-era runs.
    durability: DurabilityProvider | None = None
    #: Progress against execution bounds, advanced by the invoke path.
    bounds: BoundsTracker | None = None
    #: Monotonic step counter; the resume point recorded on each checkpoint.
    step_index: int = 0
    #: How many times this run has been revived, carried so every checkpoint it writes
    #: reports the same number (014, D3).
    #:
    #: On the run because `checkpoint_run` is the single place checkpoints are built, and it
    #: has only the run to build from. Without this field the helpers that go *through* it —
    #: `suspend_run`, `stop_run`, `complete_run` — would each write a blob claiming zero
    #: revivals, and the suspension path is exactly where a flapping run's count matters. The
    #: stores refuse to lower a count, so this is the second of two defences rather than the
    #: only one; it exists so the in-memory blob agrees with the row instead of merely
    #: failing to corrupt it.
    resume_count: int = 0
    probe_log: list[str] = field(default_factory=list)
    # Recomputed by the authority hook on every invoke; issue-time authority never widens it.
    live_effective: AuthorityScope | None = None
    #: What the platform believes about the products this run's tools reach (009).
    #:
    #: On the run rather than closed over by the hook, because `builtin_governance_hooks()`
    #: takes no arguments and a handler receives only a `HookContext` — so without a field
    #: here there is no path from the dependency gate to the health it must consult.
    #:
    #: Optional and defaulting to None so every 002-era caller keeps working. **None means
    #: the gate is inert, not that everything is unhealthy**: "unknown health for a
    #: monitored product is unhealthy" and "a run with no dependency mechanism denies
    #: everything" are different claims, and collapsing them would make every existing run
    #: refuse every tool call while looking like the gate working.
    dependency_health: DependencyHealthReader | None = None

    #: Where a shared-grain credential comes from, for products that cannot federate.
    #:
    #: ``None`` in production and that is not an oversight — ADR-0044's credential
    #: translation is its own feature, so nothing can supply this yet, and a brokered call
    #: refuses `broker_not_implemented` rather than proceeding against material that was
    #: never obtained. Optional and defaulting to ``None`` so every existing caller keeps
    #: compiling; the harness supplies a stub where a row's subject is the governance
    #: AROUND brokering rather than brokering itself.
    brokered_material_source: BrokeredMaterialSource | None = None


def start_governed_run(
    *,
    correlation_id: str | None,
    subject_user_id: str,
    tenant_id: str | None = None,
    agent_definition_id: str,
    requested_scope: AuthorityScope,
    identity_fabric: IdentityFabric,
    registry: ToolRegistry,
    clock: Clock | None = None,
    audit_sink: AuditSink | None = None,
    hooks: list[HookRegistration] | None = None,
    include_governance: bool = True,
    dependency_health: DependencyHealthReader | None = None,
    brokered_material_source: BrokeredMaterialSource | None = None,
    content_pins: Mapping[str, str] | None = None,
    manufactured: ManufacturedAuthority | None = None,
) -> GovernedRun:
    """Start an active governed run with bound task authority, or refuse.

    ``tenant_id`` is the claim a surface established, when there was a surface. Runs
    started without one — the adapter, the older suites — resolve the configured default.
    Resolved before anything is audited, because the refusal path writes an entry too.

    ``manufactured`` lets a caller that has **already** manufactured this run's authority
    supply it instead of having a second credential made (014). One caller needs that:
    `resume_run` manufactures fresh authority as part of deciding whether the run may
    continue at all, and re-manufacturing here would mean the credential the run executes
    under is not the one resume vetted, with two ``AUTHORITY_ISSUED`` events for one
    revival — which an investigator reads as two runs.

    Supplying it also moves who records a matrix fallback, and that follows the rule
    `MATRIX_FALLBACK`'s own docstring already states — *"written by whoever holds the sink
    — `start_governed_run` at run start, the resume caller on resume"*. A caller holding a
    `ManufacturedAuthority` has already seen its fallback, and it must record the fallback
    even when the decision then stops or suspends the run and this function is never
    reached. So when the authority is supplied, the emit belongs to the supplier and is
    skipped here; emitting in both places would file one substitution twice.

    **A resumed run is constructed by this function and no other.** A parallel assembly
    path was the alternative, and it is the more dangerous one: hooks are registered here,
    so a second constructor is a place a future hook can fail to be added, and a resumed run
    would then execute ungoverned while every test passed (Principle II).
    """
    cid = validate_correlation_id(correlation_id)
    tenant = resolve_tenant(tenant_id)
    clk: Clock = clock if clock is not None else SystemClock()
    sink: AuditSink = audit_sink if audit_sink is not None else InMemoryAuditSink()

    supplied = manufactured is not None
    if manufactured is None:
        try:
            manufactured = manufacture_authority(
                subject_user_id=subject_user_id,
                requested_scope=requested_scope,
                identity_fabric=identity_fabric,
                clock=clk,
                agent_definition_id=agent_definition_id,
                correlation_id=cid,
            )
        except AuthorityRefuseError as exc:
            try:
                sink.append_event(
                    correlation_id=cid,
                    tenant_id=tenant,
                    event_type=AuditEventType.AUTHORITY_REFUSED,
                    payload={"reason_code": exc.reason_code},
                )
            except Exception:
                pass
            raise

    # The fallback travels back on the return value; the emit belongs here, where the sink
    # and the tenant already are. `MATRIX_FALLBACK` had no writer at all until this line:
    # the module that RESOLVES a fallback holds neither, and `AuditEntry` requires both.
    #
    # Before AUTHORITY_ISSUED, deliberately. "The model that ran was not the model that was
    # pinned" is a fact about the authority being issued, so it must not appear after the
    # record saying authority was issued — an investigator reading in order would otherwise
    # see the run start under a cell nothing had yet said was substituted.
    #
    # Skipped when the authority was supplied: the supplier saw the fallback first and
    # records it for every outcome, including the ones that never reach this line.
    if manufactured.matrix_fallback is not None and not supplied:
        try:
            sink.append_event(
                correlation_id=cid,
                tenant_id=tenant,
                event_type=AuditEventType.MATRIX_FALLBACK,
                payload=manufactured.matrix_fallback.as_payload(run_id=cid),
            )
        except Exception as exc:
            # A fallback that could not be recorded is a fallback nobody can see, which
            # FR-010 forbids as squarely as falling back to an unqualified cell. Refusing
            # here rather than proceeding: the run would otherwise be running a model its
            # definition does not name, with no record saying so.
            raise AuthorityRefuseError(
                f"matrix fallback could not be audited: {type(exc).__name__}",
                reason_code="internal_error",
                correlation_id=cid,
            ) from exc

    registered: list[HookRegistration] = list(hooks) if hooks is not None else []
    if include_governance:
        registered = [*builtin_governance_hooks(), *registered]

    run = GovernedRun(
        correlation_id=cid,
        tenant_id=tenant,
        scope=frozenset(manufactured.credential.effective.tool_names),
        registry=registry,
        audit_sink=sink,
        authority=manufactured.credential,
        run_salt=manufactured.run_salt,
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        identity_fabric=identity_fabric,
        clock=clk,
        hooks=registered,
        state=RunState.ACTIVE,
        dependency_health=dependency_health,
        brokered_material_source=brokered_material_source,
    )

    issued_payload = {
        "credential_id": manufactured.credential.credential_id,
        "subject_user_id": subject_user_id,
        "expires_at": manufactured.credential.expires_at.isoformat(),
        "effective_tools": sorted(manufactured.credential.effective.tool_names),
        "effective_actions": sorted(manufactured.credential.effective.product_actions),
        "credential_ref_hash": content_hash(
            manufactured.run_salt, manufactured.credential.credential_id
        ),
    }

    try:
        sink.append_event(
            correlation_id=cid,
            tenant_id=tenant,
            event_type=AuditEventType.AUTHORITY_ISSUED,
            payload=issued_payload,
        )
    except Exception as exc:
        run.state = RunState.REFUSED
        raise AuthorityRefuseError(
            f"authority issuance could not be audited: {type(exc).__name__}",
            reason_code="internal_error",
            correlation_id=cid,
        ) from exc

    # What content this run executes, pinned (FR-020, T019b). Opaque name→digest pairs:
    # the core records them without knowing what a pack is, which is what keeps this
    # product-blind. Without it, a run resumed in a new allocation reloads content from
    # disk and verifies digests against the manifest SITTING BESIDE the content — so
    # edited content verifies clean and the run continues at a different version,
    # silently. This is what lets an attestation name the pack version the way FR-021
    # already names consulted guidance.
    start_payload: dict[str, object] = {"scope": sorted(run.scope)}
    if content_pins:
        start_payload["content_pins"] = dict(sorted(content_pins.items()))

    try:
        sink.append_event(
            correlation_id=cid,
            tenant_id=tenant,
            event_type=AuditEventType.RUN_START,
            payload=start_payload,
        )
    except Exception as exc:
        run.state = RunState.REFUSED
        raise CoreError(
            f"run start could not be audited: {type(exc).__name__}",
            correlation_id=cid,
        ) from exc
    return run


__all__ = [
    "GovernedRun",
    "RunState",
    "start_governed_run",
    "CorrelationRequiredError",
    "AuthorityRefuseError",
]
