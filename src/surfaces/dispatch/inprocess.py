# SPDX-License-Identifier: Apache-2.0
"""In-process dispatcher, for hermetic tests only.

Deliberately **not** the one that proves anything about run start. Nomad is inside our
boundary — we deploy it — so a run-start path exercised only against this double has not
been exercised. The enclave rows use :mod:`surfaces.dispatch.nomad`.

What this is for: letting the surface's own logic (authentication, scoping, refusal) be
tested without an enclave, which is the same division 005 drew between hermetic and
enclave lanes.
"""

from __future__ import annotations

from core.audit.sink import AuditSink
from core.authority.fabric import IdentityFabric
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from surfaces.dispatch.types import RunHandle


class InProcessDispatcher:
    """Starts a governed run in this process and records its handle."""

    def __init__(
        self,
        *,
        identity_fabric: IdentityFabric,
        registry: ToolRegistry,
        audit_sink: AuditSink,
    ) -> None:
        self._fabric = identity_fabric
        self._registry = registry
        self._audit = audit_sink
        self._handles: dict[str, RunHandle] = {}

    def dispatch(
        self,
        *,
        correlation_id: str,
        subject_user_id: str,
        tenant_id: str,
        agent_definition_id: str,
        requested_tools: frozenset[str],
        run_id: str | None = None,
        step_index: int | None = None,
        subject_roles: frozenset[str] = frozenset(),
    ) -> RunHandle:
        run = start_governed_run(
            correlation_id=correlation_id,
            subject_user_id=subject_user_id,
            tenant_id=tenant_id,
            agent_definition_id=agent_definition_id,
            requested_scope=AuthorityScope(tool_names=requested_tools),
            identity_fabric=self._fabric,
            registry=self._registry,
            audit_sink=self._audit,
        )
        handle = RunHandle(
            run_id=run_id or run.run_id or run.correlation_id,
            correlation_id=run.correlation_id,
            state=run.state,
        )
        self._handles[handle.run_id] = handle
        return handle

    def state_of(self, run_id: str) -> RunHandle | None:
        return self._handles.get(run_id)


__all__ = ["InProcessDispatcher"]
