# SPDX-License-Identifier: Apache-2.0
"""Emit one OpenTelemetry span per hook decision (no vendor SDK)."""

from __future__ import annotations

from opentelemetry import trace

from core.hooks.types import HookDecision


def emit_hook_decision_span(decision: HookDecision, *, capability_kind: str) -> None:
    """Record a hook decision as an OTel span with safe attributes only."""
    tracer = trace.get_tracer("core.hooks")
    with tracer.start_as_current_span("hook.decision") as span:
        span.set_attribute("correlation_id", decision.correlation_id)
        span.set_attribute("tool_name", decision.tool_name)
        span.set_attribute("decision", decision.outcome)
        span.set_attribute("phase", str(decision.phase) if decision.phase is not None else "")
        span.set_attribute("hook_name", decision.hook_name)
        span.set_attribute("capability_kind", capability_kind)
        span.set_attribute("reason_code", decision.reason_code)
