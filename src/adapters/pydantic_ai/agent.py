# SPDX-License-Identifier: Apache-2.0
"""Adapter entry points: start a governed run, build a governed agent.

``start_adapter_run`` is a thin call onto ``start_governed_run`` — the adapter
manufactures no authority of its own, and cannot: intersection, expiry, and
mirroring all live in core. Missing identity, definition, or correlation refuses
the start rather than producing a run with weaker authority.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.toolsets import AbstractToolset

from adapters.pydantic_ai.governance import GovernanceCapability
from adapters.pydantic_ai.run_context import AdapterRunContext
from core.approvals import ApprovalHook, DenyAllApprovalHook
from core.audit.sink import AuditSink
from core.authority.clock import Clock
from core.authority.fabric import IdentityFabric
from core.authority.types import AuthorityScope
from core.durability import DurabilityProvider, InMemoryDurabilityProvider
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


def start_adapter_run(
    *,
    correlation_id: str | None,
    subject_user_id: str,
    agent_definition_id: str,
    requested_scope: AuthorityScope,
    identity_fabric: IdentityFabric,
    registry: ToolRegistry,
    clock: Clock | None = None,
    audit_sink: AuditSink | None = None,
    approval_hook: ApprovalHook | None = None,
    durability: DurabilityProvider | None = None,
) -> AdapterRunContext:
    """Start a governed run and return the deps object bound to it.

    ``include_governance`` is deliberately not exposed: an adapter-started run
    cannot opt out of the built-in governance hook set.
    """
    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        requested_scope=requested_scope,
        identity_fabric=identity_fabric,
        registry=registry,
        clock=clock,
        audit_sink=audit_sink,
    )
    return AdapterRunContext(
        governed_run=run,
        approval_hook=approval_hook if approval_hook is not None else DenyAllApprovalHook(),
        durability=durability if durability is not None else InMemoryDurabilityProvider(),
    )


def build_governed_agent(
    model: Any,
    *,
    toolsets: Sequence[AbstractToolset[AdapterRunContext]] | None = None,
    capabilities: Sequence[Any] | None = None,
    **agent_kwargs: Any,
) -> Agent[AdapterRunContext, Any]:
    """Build an agent with governance installed first among capabilities.

    Governance is prepended here and also declares ``position='outermost'``, so
    the observable ordering holds even if a caller reorders the sequence.
    """
    co_resident = list(capabilities) if capabilities is not None else []
    return Agent(
        model,
        deps_type=AdapterRunContext,
        toolsets=list(toolsets) if toolsets is not None else None,
        capabilities=[GovernanceCapability(), *co_resident],
        **agent_kwargs,
    )
