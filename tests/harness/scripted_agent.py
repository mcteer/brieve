# SPDX-License-Identifier: Apache-2.0
"""Deterministic agent that emits a fixed sequence of tool calls (no live model)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.run import GovernedRun
from core.tools.invoke import InvokeResult, invoke_tool


def scripted_agent(
    calls: Sequence[tuple[str, Mapping[str, Any]]],
) -> Any:
    """Return a callable that invokes the given tool calls against a GovernedRun."""

    def run(governed_run: GovernedRun) -> list[InvokeResult]:
        results: list[InvokeResult] = []
        for tool_name, arguments in calls:
            results.append(invoke_tool(governed_run, tool_name, arguments))
        return results

    return run
