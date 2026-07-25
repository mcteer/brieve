# SPDX-License-Identifier: Apache-2.0
"""Mapping 1 of 4: framework tools to hook-wrapped governed tool calls.

Every tool call the agent issues is routed to ``invoke_tool``. The wrapped
toolset supplies the *schema* the model sees; the core registry supplies the
*body*. The framework's own execution path is never taken — that is the whole
point, and why this class does not call ``super().call_tool``.

A tool the model can see but the core registry does not hold is denied by core
as unregistered, which is the correct answer rather than an adapter-side error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai.toolsets import ToolsetTool, WrapperToolset

from adapters.pydantic_ai.run_context import AdapterRunContext
from core.tools.invoke import invoke_tool


class GovernedToolError(Exception):
    """Raised when the governed pipeline refuses a call.

    Surfaces to the framework as a failed tool call. It carries the core's
    user-facing message, which FR-013 requires to explain the refusal without
    disclosing secrets or out-of-scope entitlements.
    """

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass
class GovernedToolset(WrapperToolset[AdapterRunContext]):
    """Route every wrapped tool call through the governed pipeline."""

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AdapterRunContext],
    ) -> Any:
        deps = getattr(ctx, "deps", None)
        if not isinstance(deps, AdapterRunContext) or not deps.is_active():
            # No governed run means no authority to act under. Deny; never fall
            # through to the wrapped toolset.
            raise GovernedToolError(
                "action unavailable: no active governed run",
                reason_code="run_unavailable",
            )

        result = invoke_tool(deps.governed_run, name, tool_args)
        if not result.allowed:
            raise GovernedToolError(result.message, reason_code=result.reason_code)
        return result.tool_result
