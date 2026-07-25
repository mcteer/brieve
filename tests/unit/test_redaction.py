# SPDX-License-Identifier: Apache-2.0
"""Argument values and raw exception text must not enter audit/span attributes."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from tests.component.conftest import CountingHandler, make_run
from tests.harness import SECRET_MARKER, assert_no_secret_values

from core.tools.invoke import invoke_tool


def test_argument_values_not_in_audit_or_spans(span_exporter: InMemorySpanExporter) -> None:
    run, _handler, audit = make_run()
    invoke_tool(run, "echo", {"token": SECRET_MARKER, "n": 1})
    spans = span_exporter.get_finished_spans()
    assert_no_secret_values(audit, spans)
    for entry in audit.list_by_correlation_id(run.correlation_id):
        assert SECRET_MARKER not in entry.model_dump_json()
    entries = audit.list_by_correlation_id(run.correlation_id)
    pre = [e for e in entries if e.event_type.value == "pre_decision"]
    assert pre and "argument_keys" in pre[0].payload


def test_raw_exception_text_not_in_audit(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler(raise_exc=RuntimeError(f"leak {SECRET_MARKER}"))
    run, _h, audit = make_run(handler=handler)
    invoke_tool(run, "echo", {})
    spans = span_exporter.get_finished_spans()
    assert_no_secret_values(audit, spans)
    for entry in audit.list_by_correlation_id(run.correlation_id):
        assert SECRET_MARKER not in entry.model_dump_json()
