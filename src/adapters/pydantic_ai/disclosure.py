# SPDX-License-Identifier: Apache-2.0
"""Deferred disclosure, composed so governance stays terminal (036, ADR-0040/ADR-0061).

**The whole problem is where the search layer sits.** `GovernedToolset` is terminal — it
routes to `invoke_tool` and never delegates inward — which is what stops anything downstream
producing an ungoverned execution. A search meta-tool arriving there is refused as an
unregistered tool, because that is exactly what it is. So the search layer must sit
*outside* governance: it answers its own meta-tool without delegating, and passes real tool
calls inward to be governed.

Three things were measured to get this right, and each one killed an obvious approach:

1. **The framework auto-injects `ToolSearch`** (`_AUTO_INJECT_CAPABILITY_TYPES`). Building a
   `ToolSearchToolset` by hand produces two — the framework's wrapped around ours — and the
   second one fails on its own reserved `search_tools` name. So the adapter never constructs
   the search layer; it marks tools deferred and lets the framework supply it.
2. **Capability wrappers nest by list order**, applied over `reversed(capabilities)`, so the
   *first* capability is outermost. `GovernanceCapability` declares `position='outermost'`,
   which put governance outside the search layer and sent every search into `invoke_tool`.
3. **`ToolSearch` implements no `wrap_tool_execute`.** It is a toolset-layer capability
   only. That is the fact that makes the fix safe: declaring governance `wrapped_by`
   `ToolSearch` moves it inside the *toolset* nesting while leaving the middleware chain
   untouched, so Principle III's "GovernanceCapability runs first among co-resident
   capabilities" still holds — there is no co-resident middleware to run after.

The exemption a search enjoys is therefore **positional and never a name match**. Nothing
here compares a tool name to `search_tools`; a search cannot reach the governed entry
because of where the layers sit. A name-based exemption would be a bypass anybody could
create by registering a tool with that name (ADR-0061).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic_ai.capabilities import CapabilityOrdering, ToolSearch
from pydantic_ai.toolsets import AbstractToolset

from adapters.pydantic_ai.governance import GovernanceCapability
from adapters.pydantic_ai.run_context import AdapterRunContext
from core.audit.schema import AuditEventType


class DisclosurePosture(StrEnum):
    """Which posture a run is actually in — recorded, never inferred (FR-004, SC-006).

    A run that asked for deferral and did not get it must not look like a run that got it.
    That is the unstated-posture failure this platform legislates against everywhere else,
    and the reason this is a three-valued property rather than a boolean.
    """

    #: Every tool's schema presented up front. Today's behaviour, and the default.
    EAGER = "eager"
    #: Tools cost a catalog line until the model reaches for one.
    DEFERRED = "deferred"
    #: Deferral was requested and could not be composed for this run. Stated, not silent.
    EAGER_FALLBACK = "eager_fallback"


class DisclosureGovernance(GovernanceCapability):
    """Governance, placed inside the framework's search layer at the toolset seam.

    Subclasses rather than replaces `GovernanceCapability`: `get_wrapper_toolset` and
    `wrap_tool_execute` are inherited unchanged, so the terminal `GovernedToolset` and the
    admission check are exactly the ones every other run uses. The only difference is where
    this sits relative to `ToolSearch` — see the module docstring for why that is safe.
    """

    def get_ordering(self) -> CapabilityOrdering | None:
        return CapabilityOrdering(position="outermost", wrapped_by=(ToolSearch,))


@dataclass
class DiscoveryRecorder:
    """Writes `DISCOVERY_OBSERVED` for each search, and decides nothing.

    Wraps the framework's search function so the platform sees the queries and the result
    without becoming part of the answer. **There is no return path by which this can refuse
    a search** — it observes and hands the matches straight back, which is FR-006a expressed
    as a shape rather than as a promise. A recorder that could return a filtered list would
    be a decision point wearing an observer's name.
    """

    deps: AdapterRunContext
    #: How many deferred tools exist in total, so the record can say how many remain hidden.
    deferred_total: int

    def __post_init__(self) -> None:
        self._disclosed: set[str] = set()

    def __call__(
        self,
        ctx: Any,
        queries: Sequence[str],
        tools: Sequence[Any],
    ) -> list[str]:
        from pydantic_ai.toolsets._tool_search import keywords_search_fn

        matched = keywords_search_fn(ctx, queries, tools)
        self._disclosed.update(matched)

        run = self.deps.governed_run
        run.audit_sink.append_event(
            correlation_id=run.correlation_id,
            tenant_id=run.tenant_id,
            event_type=AuditEventType.DISCOVERY_OBSERVED,
            payload={
                "queries": list(queries),
                # Names only — the schemas a search discloses go to the model, never here.
                "matched": list(matched),
                # An empty match is written like any other. The search that found nothing is
                # the one most worth reading (ADR-0061).
                "undisclosed_remaining": max(self.deferred_total - len(self._disclosed), 0),
            },
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


__all__ = [
    "DiscoveryRecorder",
    "DisclosureGovernance",
    "DisclosurePosture",
    "deferred_toolset",
]
