# SPDX-License-Identifier: Apache-2.0
"""US3 — enforcement errors deny; never allow."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.errors import RegistryError
from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)
from core.registry.memory import ToolRegistration, ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    SECRET_MARKER,
    assert_denied_closed,
    assert_no_secret_values,
    assert_no_side_effect,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)


class FlakyRegistry(ToolRegistry):
    def resolve(self, name: str) -> ToolRegistration:
        raise RegistryError("injected registry failure")


class FailAfterAuditSink(InMemoryAuditSink):
    def __init__(self, fail_on_append_index: int) -> None:
        super().__init__()
        self._fail_on = fail_on_append_index
        self._appends = 0

    def append(self, entry: AuditEntry) -> None:
        if self._appends >= self._fail_on:
            raise RuntimeError("audit append failed")
        self._appends += 1
        super().append(entry)


def _raising_pre(_ctx: HookContext) -> HookDecision:
    raise RuntimeError(f"hook failed {SECRET_MARKER}")


def _start(
    *,
    correlation_id: str,
    registry: ToolRegistry,
    audit_sink: InMemoryAuditSink,
    hooks: list[HookRegistration] | None = None,
    include_governance: bool = True,
) -> GovernedRun:
    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(tool_names={"echo"}),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit_sink,
        hooks=hooks,
        include_governance=include_governance,
    )
    return run


def test_pre_hook_raise_denies(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    audit = capture_audit()
    bad = HookRegistration(
        name="bad_pre",
        phase=HookPhase.PRE,
        capability_kind=CapabilityKind.OTHER,
        handler=_raising_pre,
    )
    run = _start(
        correlation_id="corr-fc-1",
        registry=registry,
        audit_sink=audit,
        hooks=[bad],
    )
    result = invoke_tool(run, "echo", {"token": SECRET_MARKER})
    assert_denied_closed(result, reason="internal_error")
    assert_no_side_effect(handler)
    assert_no_secret_values(audit, span_exporter.get_finished_spans())


def test_registry_failure_denies(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = FlakyRegistry()
    registry.register("echo", handler)
    audit = capture_audit()
    run = _start(
        correlation_id="corr-fc-2",
        registry=registry,
        audit_sink=audit,
    )
    result = invoke_tool(run, "echo", {})
    assert_denied_closed(result, reason="internal_error")
    assert_no_side_effect(handler)
    assert_no_secret_values(audit, span_exporter.get_finished_spans())


def test_missing_governance_dependency_denies(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    audit = capture_audit()
    run = _start(
        correlation_id="corr-fc-3",
        registry=registry,
        audit_sink=audit,
        include_governance=False,
        hooks=[],
    )
    result = invoke_tool(run, "echo", {})
    assert_denied_closed(result, reason="internal_error")
    assert_no_side_effect(handler)
    _ = span_exporter


def test_pre_path_audit_append_failure_denies(span_exporter: InMemorySpanExporter) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    # 0=authority_issued, 1=run_start, 2+=invoke path
    audit = FailAfterAuditSink(fail_on_append_index=2)
    run = _start(
        correlation_id="corr-fc-4",
        registry=registry,
        audit_sink=audit,
    )
    result = invoke_tool(run, "echo", {})
    assert_denied_closed(result, reason="internal_error")
    assert result.evidential_gap is True
    assert_no_side_effect(handler)
    _ = span_exporter


def test_post_path_audit_append_failure_not_clean_success(
    span_exporter: InMemorySpanExporter,
) -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)

    class FailAfterTool(InMemoryAuditSink):
        def append(self, entry: AuditEntry) -> None:
            if entry.event_type.value == "post_decision":
                raise RuntimeError("post audit fail")
            super().append(entry)

    audit = FailAfterTool()
    run = _start(
        correlation_id="corr-fc-5",
        registry=registry,
        audit_sink=audit,
    )
    result = invoke_tool(run, "echo", {})
    assert result.allowed is False
    assert result.decision == "deny"
    assert result.executed is True
    assert result.evidential_gap is True
    _ = span_exporter
