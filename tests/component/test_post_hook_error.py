# SPDX-License-Identifier: Apache-2.0
"""US1 edge — post-hook exception after successful body is failed-closed."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)
from core.tools.invoke import invoke_tool
from tests.component.conftest import make_run
from tests.harness import assert_audit_chain


def _boom(_ctx: HookContext) -> HookDecision:
    raise RuntimeError("post boom")


def test_post_hook_error_after_success(span_exporter: InMemorySpanExporter) -> None:
    post = HookRegistration(
        name="probe_post",
        phase=HookPhase.POST,
        capability_kind=CapabilityKind.OTHER,
        handler=_boom,
    )
    run, handler, audit = make_run(hooks=[post])
    result = invoke_tool(run, "echo", {})
    assert handler.call_count == 1
    assert result.executed is True
    assert result.allowed is False
    assert result.decision == "deny"

    entries = audit.list_by_correlation_id(run.correlation_id)
    assert any(e.event_type.value == "tool_outcome" for e in entries)
    assert any(
        e.event_type.value == "post_decision" and e.payload.get("outcome") == "deny"
        for e in entries
    )
    assert_audit_chain(audit)
    _ = span_exporter
