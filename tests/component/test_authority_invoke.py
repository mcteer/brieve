# SPDX-License-Identifier: Apache-2.0
"""US1/US2 — invoke allow/deny under live_effective; mid-run policy shrink."""

from __future__ import annotations

from typing import Any

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_denied_closed,
    assert_no_side_effect,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)


def test_in_scope_allow_under_live_effective() -> None:
    run, handler, _audit = _make(["echo", "other"], requested={"echo"})
    result = invoke_tool(run, "echo", {})
    assert result.allowed
    assert handler.call_count == 1


def test_tool_outside_live_effective_denied() -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    registry.register("other", handler)
    fabric = fake_identity_fabric(tool_names={"echo", "other"}, ceiling_tools={"echo", "other"})
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-inv-deny",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    # "other" is registered but not in issued effective → out_of_scope at engine
    result = invoke_tool(run, "other", {})
    assert_denied_closed(result, reason="out_of_scope")
    assert_no_side_effect(handler)


def test_mid_run_policy_shrink_denies() -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    registry.register("other", handler)
    fabric = fake_identity_fabric(
        tool_names={"echo", "other"},
        ceiling_tools={"echo", "other"},
    )
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-policy-shrink",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo", "other"})),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    assert invoke_tool(run, "other", {}).allowed
    fabric.shrink_policy(AuthorityScope(tool_names=frozenset({"echo"})))
    result = invoke_tool(run, "other", {})
    assert_denied_closed(result, reason="authority_insufficient")


def _make(tools: list[str], requested: set[str]) -> tuple[Any, CountingHandler, Any]:
    handler = CountingHandler()
    registry = ToolRegistry()
    for t in tools:
        registry.register(t, handler)
    fabric = fake_identity_fabric(tool_names=set(tools), ceiling_tools=set(tools))
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-inv-allow",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(requested)),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    return run, handler, audit
