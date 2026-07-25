# SPDX-License-Identifier: Apache-2.0
"""US1 edge — two tool calls share one correlation ID with distinct records."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.tools.invoke import invoke_tool
from tests.component.conftest import make_run
from tests.harness import assert_audit_chain, assert_correlated


def test_two_invokes_share_correlation_id(span_exporter: InMemorySpanExporter) -> None:
    run, handler, audit = make_run()
    r1 = invoke_tool(run, "echo", {"n": 1})
    r2 = invoke_tool(run, "echo", {"n": 2})
    assert r1.correlation_id == r2.correlation_id == run.correlation_id
    assert handler.call_count == 2

    entries = audit.list_by_correlation_id(run.correlation_id)
    pre = [e for e in entries if e.event_type.value == "pre_decision"]
    assert len(pre) >= 2
    assert_correlated(audit, span_exporter.get_finished_spans(), run.correlation_id)
    assert_audit_chain(audit)
