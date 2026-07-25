# SPDX-License-Identifier: Apache-2.0
"""US4 — identity/exchange failures deny or refuse."""

from __future__ import annotations

import pytest

from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_denied_closed,
    assert_no_secret_values,
    assert_no_side_effect,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)


def test_identity_unavailable_at_start() -> None:
    fabric = fake_identity_fabric(tool_names={"echo"})
    fabric.fail_user = True
    with pytest.raises(AuthorityRefuseError) as exc:
        start_governed_run(
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
            correlation_id="corr-id-fail",
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            registry=ToolRegistry(),
            audit_sink=capture_audit(),
        )
    assert exc.value.reason_code == "identity_unavailable"


def test_exchange_failed_at_start() -> None:
    fabric = fake_identity_fabric(tool_names={"echo"})
    fabric.fail_ceiling = True
    fabric.fail_reason = "exchange_failed"
    with pytest.raises(AuthorityRefuseError) as exc:
        start_governed_run(
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
            correlation_id="corr-ex-fail",
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            registry=ToolRegistry(),
            audit_sink=capture_audit(),
        )
    assert exc.value.reason_code == "exchange_failed"


def test_entitlement_resolve_fail_at_invoke() -> None:
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register(
        "product_tool",
        handler,
        product_mode="broker",
        product="workspace",
        product_action="product.workspace.read",
    )
    fabric = fake_identity_fabric(
        tool_names={"product_tool"},
        product_actions={"product.workspace.read"},
        ceiling_tools={"product_tool"},
        ceiling_actions={"product.workspace.read"},
        entitlements={("user-1", "workspace"): frozenset({"product.workspace.read"})},
    )
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-ent-fail",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(
            tool_names=frozenset({"product_tool"}),
            product_actions=frozenset({"product.workspace.read"}),
        ),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    fabric.fail_entitlements = True
    result = invoke_tool(run, "product_tool", {})
    assert_denied_closed(result, reason="identity_unavailable")
    assert_no_side_effect(handler)
    assert_no_secret_values(audit)
