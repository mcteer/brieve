# SPDX-License-Identifier: Apache-2.0
"""US4 / SC-006 — governance runs before other; assert_hook_order fails if reversed."""

from __future__ import annotations

import pytest
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
from tests.harness import assert_hook_order


def _allow(ctx: HookContext) -> HookDecision:
    return HookDecision(outcome="allow", reason_code="ok", message="ok")


def test_governance_before_other(span_exporter: InMemorySpanExporter) -> None:
    # Register other BEFORE governance extras — engine must still sort governance first.
    other_pre = HookRegistration(
        name="other_pre",
        phase=HookPhase.PRE,
        capability_kind=CapabilityKind.OTHER,
        handler=_allow,
    )
    run, _h, _audit = make_run(hooks=[other_pre])
    invoke_tool(run, "echo", {})
    assert run.probe_log[0] == "pre:governance"
    assert "pre:other" in run.probe_log
    assert_hook_order(run.probe_log)
    _ = span_exporter


def test_assert_hook_order_fails_if_reversed() -> None:
    with pytest.raises(AssertionError, match="governance hook observed after other"):
        assert_hook_order(["other", "governance"])
    with pytest.raises(AssertionError, match="governance hook observed after other"):
        assert_hook_order(["pre:other", "pre:governance"])
