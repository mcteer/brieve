# SPDX-License-Identifier: Apache-2.0
"""Governed run initiation — refuse uncorrelated or unauthenticated authority starts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink, build_next_entry
from core.authority.clock import Clock, SystemClock
from core.authority.errors import AuthorityRefuseError
from core.authority.fabric import IdentityFabric
from core.authority.hashing import content_hash
from core.authority.manufacture import manufacture_authority
from core.authority.types import AuthorityScope, TaskCredentialRef
from core.correlation import validate_correlation_id
from core.errors import CoreError, CorrelationRequiredError
from core.hooks.governance import builtin_governance_hooks
from core.hooks.types import HookRegistration
from core.registry.memory import ToolRegistry


class RunState(StrEnum):
    ACTIVE = "active"
    REFUSED = "refused"


@dataclass
class GovernedRun:
    correlation_id: str
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
    probe_log: list[str] = field(default_factory=list)
    # Recomputed by the authority hook on every invoke; issue-time authority never widens it.
    live_effective: AuthorityScope | None = None


def start_governed_run(
    *,
    correlation_id: str | None,
    subject_user_id: str,
    agent_definition_id: str,
    requested_scope: AuthorityScope,
    identity_fabric: IdentityFabric,
    registry: ToolRegistry,
    clock: Clock | None = None,
    audit_sink: AuditSink | None = None,
    hooks: list[HookRegistration] | None = None,
    include_governance: bool = True,
) -> GovernedRun:
    """Start an active governed run with bound task authority, or refuse."""
    cid = validate_correlation_id(correlation_id)
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
            entry = build_next_entry(
                sink,
                correlation_id=cid,
                event_type=AuditEventType.AUTHORITY_REFUSED,
                payload={"reason_code": exc.reason_code},
            )
            sink.append(entry)
        except Exception:
            pass
        raise

    registered: list[HookRegistration] = list(hooks) if hooks is not None else []
    if include_governance:
        registered = [*builtin_governance_hooks(), *registered]

    run = GovernedRun(
        correlation_id=cid,
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
        issued = build_next_entry(
            sink,
            correlation_id=cid,
            event_type=AuditEventType.AUTHORITY_ISSUED,
            payload=issued_payload,
        )
        sink.append(issued)
    except Exception as exc:
        run.state = RunState.REFUSED
        raise AuthorityRefuseError(
            f"authority issuance could not be audited: {type(exc).__name__}",
            reason_code="internal_error",
            correlation_id=cid,
        ) from exc

    entry = build_next_entry(
        sink,
        correlation_id=cid,
        event_type=AuditEventType.RUN_START,
        payload={"scope": sorted(run.scope)},
    )
    try:
        sink.append(entry)
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
