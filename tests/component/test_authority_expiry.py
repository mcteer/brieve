# SPDX-License-Identifier: Apache-2.0
"""US5 — authority expires; no auto-refresh."""

from __future__ import annotations

from datetime import timedelta

from core.audit.schema import AuditEventType
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_denied_closed,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)


def test_expiry_denies_before_body() -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    clock = frozen_clock()
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-expiry",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(tool_names={"echo"}),
        clock=clock,
        registry=registry,
        audit_sink=audit,
    )
    assert invoke_tool(run, "echo", {}).allowed
    clock.advance(timedelta(minutes=16))
    result = invoke_tool(run, "echo", {})
    assert_denied_closed(result, reason="authority_expired")
    assert handler.call_count == 1  # second invoke did not execute
    types = [e.event_type for e in audit.list_by_correlation_id(run.correlation_id)]
    assert AuditEventType.AUTHORITY_EXPIRED in types
