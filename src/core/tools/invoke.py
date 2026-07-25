# SPDX-License-Identifier: Apache-2.0
"""Sole public entry that executes tool bodies through the hook pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from core.hooks.engine import run_pipeline
from core.run import GovernedRun


class InvokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    allowed: bool
    decision: Literal["allow", "deny"]
    reason_code: str
    message: str
    correlation_id: str
    executed: bool
    evidential_gap: bool = False
    tool_result: Any = None


def invoke_tool(
    run: GovernedRun,
    tool_name: str,
    arguments: Mapping[str, Any] | None = None,
) -> InvokeResult:
    """Invoke a tool through the fail-closed pre/post hook pipeline.

    There is no supported path to run a tool handler while skipping pre-hooks.
    """
    args: Mapping[str, Any] = arguments if arguments is not None else {}
    outcome = run_pipeline(run, tool_name, args)
    allowed = outcome.decision == "allow" and not outcome.evidential_gap
    return InvokeResult(
        allowed=allowed,
        decision=outcome.decision,  # type: ignore[arg-type]
        reason_code=outcome.reason_code,
        message=outcome.message,
        correlation_id=run.correlation_id,
        executed=outcome.executed,
        evidential_gap=outcome.evidential_gap,
        tool_result=outcome.tool_result,
    )
