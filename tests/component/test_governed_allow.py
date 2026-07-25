# SPDX-License-Identifier: Apache-2.0
"""US1 — in-scope allow path fully joined."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.audit.schema import AuditEventType
from core.tools.invoke import invoke_tool
from tests.component.conftest import make_run
from tests.harness import (
    assert_audit_chain,
    assert_correlated,
    assert_no_secret_values,
    scripted_agent,
)


def test_in_scope_allow_once_and_joined(span_exporter: InMemorySpanExporter) -> None:
    run, handler, audit = make_run()
    agent = scripted_agent([("echo", {"x": 1})])
    results = agent(run)
    assert len(results) == 1
    result = results[0]
    assert result.allowed is True
    assert result.decision == "allow"
    assert result.executed is True
    assert handler.call_count == 1

    entries = audit.list_by_correlation_id(run.correlation_id)
    types = [e.event_type for e in entries]
    assert AuditEventType.RUN_START in types
    assert AuditEventType.PRE_DECISION in types
    assert AuditEventType.TOOL_OUTCOME in types
    assert AuditEventType.POST_DECISION in types

    spans = span_exporter.get_finished_spans()
    assert spans
    assert_correlated(audit, spans, run.correlation_id)
    assert_audit_chain(audit)
    assert_no_secret_values(audit, spans)


def test_invoke_tool_allow(span_exporter: InMemorySpanExporter) -> None:
    run, handler, audit = make_run()
    result = invoke_tool(run, "echo", {"a": "b"})
    assert result.allowed
    assert handler.call_count == 1
    assert_audit_chain(audit)
    assert_no_secret_values(audit, span_exporter.get_finished_spans())
