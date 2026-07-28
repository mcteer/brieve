# SPDX-License-Identifier: Apache-2.0
"""Governed run initiation — refuse uncorrelated or unauthenticated authority starts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink
from core.authority.clock import Clock, SystemClock
from core.authority.errors import AuthorityRefuseError
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant
from core.authority.hashing import content_hash
from core.authority.manufacture import manufacture_authority
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
) -> GovernedRun:
    """Start an active governed run with bound task authority, or refuse.

    ``tenant_id`` is the claim a surface established, when there was a surface. Runs
    started without one — the adapter, the older suites — resolve the configured default.
    Resolved before anything is audited, because the refusal path writes an entry too.
    """
    cid = validate_correlation_id(correlation_id)
    tenant = resolve_tenant(tenant_id)
    clk: Clock = clock if clock is not None else SystemClock()
    sink: AuditSink = audit_sink if audit_sink is not None else InMemoryAuditSink()

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

    try:
        sink.append_event(
            correlation_id=cid,
            tenant_id=tenant,
            event_type=AuditEventType.RUN_START,
            payload={"scope": sorted(run.scope)},
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
