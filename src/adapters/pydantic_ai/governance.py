# SPDX-License-Identifier: Apache-2.0
"""GovernanceCapability — first among co-resident capabilities, fails closed.

ADR-0019 and constitution Principle III make two properties load-bearing, and
both are asserted by the conformance lane rather than trusted to configuration:

1. Governance runs *first*. Capabilities follow middleware semantics — the first
   in the list wraps outermost — so this declares ``position='outermost'``,
   which the framework enforces by topological sort regardless of how a caller
   orders the list. ``build_governed_agent`` also prepends it; the declaration is
   what holds when someone constructs an agent by hand.
2. Governance fails closed. An error anywhere in the wrapping path denies the
   call. There is no branch here that converts a fault into an allow.

The capability contributes glue only. It does not reimplement the hook algebra —
enforcement lives in core and is reached through ``invoke_tool``.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai.capabilities.abstract import AbstractCapability, CapabilityOrdering
from pydantic_ai.toolsets import AbstractToolset

from adapters.pydantic_ai.run_context import AdapterRunContext
from adapters.pydantic_ai.tools import GovernedToolError, GovernedToolset

#: Marker appended to ``GovernedRun.probe_log`` when the governance capability admits a
#: call. Co-resident capabilities observe it to prove governance decided first; core
#: hooks use the same log for their own ordering assertions.
GOVERNANCE_PROBE_MARKER = "pre:adapter_governance"


class GovernanceCapability(AbstractCapability[AdapterRunContext]):
    """Governance as a capability: first among co-residents, fail-closed.

    Two layers, and both matter:

    * ``wrap_tool_execute`` is the *ordering* layer. It is outermost in the
      middleware chain, so its admission check runs before any co-resident
      capability sees the call. It then delegates — governance decides first, it
      does not decide alone.
    * ``get_wrapper_toolset`` is the *interception* layer. The returned
      ``GovernedToolset`` is terminal: execution goes to ``invoke_tool`` and never
      to a framework tool body, so no capability downstream can produce an
      ungoverned execution.
    """

    def get_ordering(self) -> CapabilityOrdering | None:
        return CapabilityOrdering(position="outermost")

    def get_wrapper_toolset(
        self, toolset: AbstractToolset[AdapterRunContext]
    ) -> AbstractToolset[AdapterRunContext] | None:
        try:
            return GovernedToolset(toolset)
        except Exception as exc:  # pragma: no cover - defensive
            # Failing to install governance must not yield an ungoverned agent.
            raise GovernedToolError(
                "action unavailable: governance could not be installed",
                reason_code="governance_unavailable",
            ) from exc

    async def wrap_tool_execute(
        self,
        ctx: Any,
        *,
        call: Any,
        tool_def: Any,
        args: Any,
        handler: Any,
    ) -> Any:
        deps = getattr(ctx, "deps", None)
        if not isinstance(deps, AdapterRunContext) or not deps.is_active():
            raise GovernedToolError(
                "action unavailable: no active governed run",
                reason_code="run_unavailable",
            )
        deps.governed_run.probe_log.append(GOVERNANCE_PROBE_MARKER)
        return await handler(args)
