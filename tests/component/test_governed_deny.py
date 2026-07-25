# SPDX-License-Identifier: Apache-2.0
"""US2 — unregistered / out-of-scope deny with zero side effects."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    assert_denied_closed,
    assert_no_side_effect,
    capture_audit,
    scripted_agent,
)


def test_unregistered_denied(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    audit = capture_audit()
    run = start_governed_run(
        correlation_id="corr-deny-1",
        scope={"echo"},
        registry=registry,
        audit_sink=audit,
    )
    result = invoke_tool(run, "missing", {})
    assert_denied_closed(result, reason="unregistered")
    assert_no_side_effect(handler)
    trail = audit.list_by_correlation_id(run.correlation_id)
    assert any(e.correlation_id == run.correlation_id for e in trail)
    _ = span_exporter


def test_out_of_scope_denied(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    registry.register("other", handler)
    audit = capture_audit()
    run = start_governed_run(
        correlation_id="corr-deny-2",
        scope={"echo"},
        registry=registry,
        audit_sink=audit,
    )
    agent = scripted_agent([("other", {})])
    results = agent(run)
    assert_denied_closed(results[0], reason="out_of_scope")
    assert_no_side_effect(handler)
    _ = span_exporter
