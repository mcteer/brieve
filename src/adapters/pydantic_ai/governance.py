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

from collections.abc import Sequence
from typing import Any

from pydantic_ai.capabilities import ToolSearch
from pydantic_ai.capabilities.abstract import AbstractCapability, CapabilityOrdering
from pydantic_ai.toolsets import AbstractToolset

from adapters.pydantic_ai.run_context import AdapterRunContext
from adapters.pydantic_ai.tools import GovernedToolError, GovernedToolset
from core.disclosure import record_discovery

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


class DisclosureGovernance(GovernanceCapability):
    """Governance, placed inside the framework's search layer at the toolset seam.

    Subclasses rather than replaces `GovernanceCapability`: `get_wrapper_toolset` and
    `wrap_tool_execute` are inherited unchanged, so the terminal `GovernedToolset` and the
    admission check are exactly the ones every other run uses. The only difference is where
    this sits relative to `ToolSearch` — see the module docstring for why that is safe.
    """

    def get_ordering(self) -> CapabilityOrdering | None:
        return CapabilityOrdering(position="outermost", wrapped_by=(ToolSearch,))


def recording_search_fn(ctx: Any, queries: Sequence[str], tools: Sequence[Any]) -> list[str]:
    """Answer a search, and write down that it happened. Decides nothing (FR-006a).

    Wraps the framework's own keyword algorithm so the platform observes the queries and the
    result without becoming part of the answer. **There is no return path here that can
    refuse a search**: the matches the algorithm produced are handed straight back. That is
    FR-006a expressed as a shape rather than as a promise — a recorder able to return a
    filtered list would be a decision point wearing an observer's name, and would make
    disclosure part of the authority path (ADR-0061).

    Installed as `ToolSearch(search_fn=...)` rather than wrapping the toolset, so the
    framework's own search layer stays the one in the chain and nothing is double-wrapped.

    The run is read from ``ctx.deps`` at call time rather than captured at build time: the
    agent is built once and the deps belong to a run, so a captured reference would record
    one run's searches against another's trail.
    """
    from pydantic_ai.toolsets._tool_search import keywords_search_fn

    matched = list(keywords_search_fn(ctx, queries, tools))

    deps = getattr(ctx, "deps", None)
    if not isinstance(deps, AdapterRunContext) or not deps.is_active():
        # No governed run to record against. The search still answers — refusing it here
        # would make discovery refusable through the back door, which FR-006a forbids.
        return matched

    # How many deferred tools the model still cannot see. Counted from the corpus the search
    # layer holds and the names discovered so far this run, so it describes the model's view
    # rather than the registry's.
    already = set(getattr(ctx, "discovered_tool_names", set()) or set())
    remaining = len({t.name for t in tools} - (already | set(matched)))

    # The WRITE lives in core. An adapter that appends audit directly has reimplemented a
    # core concern, and `test_adapter_holds_no_authority_or_audit_logic` says so.
    record_discovery(
        deps.governed_run,
        queries=queries,
        matched=matched,
        undisclosed_remaining=remaining,
    )
    return matched


def deferred_toolset(
    toolset: AbstractToolset[AdapterRunContext],
) -> AbstractToolset[AdapterRunContext]:
    """Mark every tool in ``toolset`` for deferred loading.

    Uses the framework's own `defer_loading()` rather than constructing a
    `DeferredLoadingToolset` directly, so the marking travels the supported path and cannot
    drift from what the search layer expects to find.
    """
    return toolset.defer_loading()
