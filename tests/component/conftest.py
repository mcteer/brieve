# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for governed-core component tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from tests.harness import capture_audit, fake_identity_fabric, frozen_clock


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
    subject_user_id: str = "user-1",
) -> tuple[GovernedRun, CountingHandler, Any]:
    h = handler if handler is not None else CountingHandler()
    tools = scope if scope is not None else {tool_name}
    registry = ToolRegistry()
    registry.register(tool_name, h)
    # Ensure every in-scope tool name is registered for multi-tool tests
    for name in tools:
        if name != tool_name and name not in getattr(registry, "_tools", {}):
            registry.register(name, CountingHandler())
    audit = capture_audit()
    fabric = fake_identity_fabric(
        subject_user_id=subject_user_id,
        tool_names=tools,
        ceiling_tools=tools,
    )
    clock = frozen_clock()
    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        requested_scope=AuthorityScope(tool_names=frozenset(tools)),
        identity_fabric=fabric,
        clock=clock,
        registry=registry,
        audit_sink=audit,
        hooks=hooks,
        include_governance=include_governance,
    )
    return run, h, audit
