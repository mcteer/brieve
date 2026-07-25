# SPDX-License-Identifier: Apache-2.0
"""US1 / FR-015 — post-hooks still run after tool-body error."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.audit.schema import AuditEventType
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run
from tests.harness import assert_audit_chain, assert_no_secret_values


def test_tool_body_error_still_runs_post_hooks(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler(raise_exc=RuntimeError("boom"))
    run, _h, audit = make_run(handler=handler)
    result = invoke_tool(run, "echo", {})
    assert result.executed is True
    assert result.allowed is False
    assert result.decision == "deny"
    assert handler.call_count == 1

    types = [e.event_type for e in audit.list_by_correlation_id(run.correlation_id)]
    assert AuditEventType.TOOL_OUTCOME in types
    assert AuditEventType.POST_DECISION in types
    assert_audit_chain(audit)
    assert_no_secret_values(audit, span_exporter.get_finished_spans())
