# SPDX-License-Identifier: Apache-2.0
"""Governed run initiation — refuse uncorrelated starts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink, build_next_entry
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
    hooks: list[HookRegistration] = field(default_factory=list)
    state: RunState = RunState.ACTIVE
    probe_log: list[str] = field(default_factory=list)


def start_governed_run(
    *,
    correlation_id: str | None,
    scope: frozenset[str] | set[str],
    registry: ToolRegistry,
    audit_sink: AuditSink | None = None,
    hooks: list[HookRegistration] | None = None,
    include_governance: bool = True,
) -> GovernedRun:
    """Start an active governed run or refuse if correlation ID is missing/blank."""
    cid = validate_correlation_id(correlation_id)

    sink: AuditSink = audit_sink if audit_sink is not None else InMemoryAuditSink()
    registered: list[HookRegistration] = list(hooks) if hooks is not None else []
    if include_governance:
        registered = [*builtin_governance_hooks(), *registered]

    run = GovernedRun(
        correlation_id=cid,
        scope=frozenset(scope),
        registry=registry,
        audit_sink=sink,
        hooks=registered,
        state=RunState.ACTIVE,
    )

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


__all__ = ["GovernedRun", "RunState", "start_governed_run", "CorrelationRequiredError"]
