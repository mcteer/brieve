# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for governed-core component tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from tests.harness import capture_audit


class CountingHandler:
    def __init__(self, result: Any = None, *, raise_exc: Exception | None = None) -> None:
        self.call_count = 0
        self._result = result if result is not None else {"ok": True}
        self._raise = raise_exc

    def __call__(self, arguments: Mapping[str, Any]) -> Any:
        self.call_count += 1
        if self._raise is not None:
            raise self._raise
        return self._result


def make_run(
    *,
    tool_name: str = "echo",
    handler: CountingHandler | None = None,
    scope: set[str] | None = None,
    include_governance: bool = True,
    hooks: list[Any] | None = None,
    correlation_id: str = "corr-test-001",
) -> tuple[GovernedRun, CountingHandler, Any]:
    h = handler if handler is not None else CountingHandler()
    registry = ToolRegistry()
    registry.register(tool_name, h)
    audit = capture_audit()
    run = start_governed_run(
        correlation_id=correlation_id,
        scope=scope if scope is not None else {tool_name},
        registry=registry,
        audit_sink=audit,
        hooks=hooks,
        include_governance=include_governance,
    )
    return run, h, audit
