# SPDX-License-Identifier: Apache-2.0
"""US1 — narrowed authority issued and audited."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.audit.schema import AuditEventType
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_audit_chain,
    assert_correlated,
    assert_no_secret_values,
    assert_scope_narrowed,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)


def test_authority_issued_narrowed_and_joined(span_exporter: InMemorySpanExporter) -> None:
    user_scope = AuthorityScope(
        tool_names=frozenset({"echo", "other"}),
        product_actions=frozenset({"product.read"}),
    )
    fabric = fake_identity_fabric(
        tool_names=set(user_scope.tool_names),
        product_actions=set(user_scope.product_actions),
        ceiling_tools=set(user_scope.tool_names),
        ceiling_actions=set(user_scope.product_actions),
    )
    requested = AuthorityScope(
        tool_names=frozenset({"echo"}),
        product_actions=frozenset({"product.read"}),
    )
    registry = ToolRegistry()
    registry.register("echo", CountingHandler())
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-auth-issue",
        subject_user_id="user-1",
        requested_scope=requested,
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    assert_scope_narrowed(run.authority, at_most=user_scope)
    assert run.authority.effective.tool_names == frozenset({"echo"})
    types = [e.event_type for e in audit.list_by_correlation_id(run.correlation_id)]
    assert AuditEventType.AUTHORITY_ISSUED in types
    result = invoke_tool(run, "echo", {})
    assert result.allowed
    spans = span_exporter.get_finished_spans()
    assert_correlated(audit, spans, run.correlation_id)
    assert_audit_chain(audit)
    assert_no_secret_values(audit, spans)
