# SPDX-License-Identifier: Apache-2.0
"""US3 — entitlement mirroring federate/broker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_denied_closed,
    assert_no_secret_values,
    assert_no_side_effect,
    capture_audit,
    fake_identity_fabric,
    fake_product_api,
    frozen_clock,
)
from tests.harness.fake_identity_fabric import FakeIdentityFabric
from tests.harness.fake_product_api import FakeProductApi

PRODUCT = "workspace"
ACTION_OK = "product.workspace.read"
ACTION_DENY = "product.workspace.write"


def _product_run(
    *,
    mode: str,
    entitlements: frozenset[str],
    requested_actions: frozenset[str] | None = None,
    product_api: FakeProductApi | None = None,
) -> tuple[GovernedRun, CountingHandler, FakeProductApi, InMemoryAuditSink, FakeIdentityFabric]:
    api = product_api if product_api is not None else fake_product_api(mode=mode)
    handler = CountingHandler()

    def tool_body(arguments: Mapping[str, Any]) -> dict[str, str]:
        handler(arguments)
        return api.wield(
            subject_user_id="user-1",
            action=str(arguments.get("action", ACTION_OK)),
            credential_id=arguments.get("credential_id")
            if isinstance(arguments.get("credential_id"), str)
            else None,
        )

    registry = ToolRegistry()
    action = ACTION_OK
    registry.register(
        "product_tool",
        tool_body,
        product_mode=mode,  # type: ignore[arg-type]
        product=PRODUCT,
        product_action=action,
    )
    actions = (
        requested_actions if requested_actions is not None else frozenset({ACTION_OK, ACTION_DENY})
    )
    fabric = fake_identity_fabric(
        tool_names={"product_tool"},
        product_actions=set(actions),
        ceiling_tools={"product_tool"},
        ceiling_actions=set(actions),
        entitlements={("user-1", PRODUCT): entitlements},
    )
    audit = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-mirror",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(
            tool_names=frozenset({"product_tool"}),
            product_actions=actions,
        ),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    return run, handler, api, audit, fabric


def test_broker_deny_missing_entitlement() -> None:
    run, handler, api, audit, _ = _product_run(mode="broker", entitlements=frozenset())
    result = invoke_tool(run, "product_tool", {})
    assert_denied_closed(result, reason="mirroring_denied")
    assert_no_side_effect(handler)
    assert api.call_count == 0
    types = [e.event_type for e in audit.list_by_correlation_id(run.correlation_id)]
    assert AuditEventType.MIRRORING_DECISION in types
    assert_no_secret_values(audit)


def test_broker_allow_with_entitlement() -> None:
    run, handler, api, audit, _ = _product_run(mode="broker", entitlements=frozenset({ACTION_OK}))
    result = invoke_tool(run, "product_tool", {"action": ACTION_OK})
    assert result.allowed
    assert handler.call_count == 1
    assert api.call_count == 1
    assert_no_secret_values(audit)


def test_federate_allow() -> None:
    run, handler, api, audit, _ = _product_run(mode="federate", entitlements=frozenset({ACTION_OK}))
    result = invoke_tool(run, "product_tool", {})
    assert result.allowed
    assert handler.call_count == 1
    assert_no_secret_values(audit)


def test_empty_entitlements_deny() -> None:
    run, handler, api, _, _ = _product_run(mode="broker", entitlements=frozenset())
    result = invoke_tool(run, "product_tool", {})
    assert_denied_closed(result, reason="mirroring_denied")
    assert api.call_count == 0
    assert_no_side_effect(handler)


def test_mid_run_entitlement_shrink() -> None:
    run, handler, api, _, fabric = _product_run(mode="broker", entitlements=frozenset({ACTION_OK}))
    assert invoke_tool(run, "product_tool", {}).allowed
    fabric.shrink_entitlements("user-1", PRODUCT, frozenset())
    result = invoke_tool(run, "product_tool", {})
    assert_denied_closed(result, reason="mirroring_denied")
    assert api.call_count == 1  # only first wield


def test_action_in_entitlements_but_not_live_effective() -> None:
    """Wide entitlements cannot authorize outside live_effective.product_actions."""
    api = fake_product_api(mode="broker")
    handler = CountingHandler()

    def tool_body(arguments: Mapping[str, Any]) -> dict[str, str]:
        handler(arguments)
        return api.wield(subject_user_id="user-1", action=ACTION_DENY)

    registry = ToolRegistry()
    registry.register(
        "product_tool",
        tool_body,
        product_mode="broker",
        product=PRODUCT,
        product_action=ACTION_DENY,
    )
    fabric = fake_identity_fabric(
        tool_names={"product_tool"},
        product_actions={ACTION_OK, ACTION_DENY},
        ceiling_tools={"product_tool"},
        ceiling_actions={ACTION_OK, ACTION_DENY},
        entitlements={("user-1", PRODUCT): frozenset({ACTION_OK, ACTION_DENY})},
    )
    # Request only ACTION_OK in task scope — ACTION_DENY not in issued effective
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-dual-bound",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(
            tool_names=frozenset({"product_tool"}),
            product_actions=frozenset({ACTION_OK}),
        ),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=capture_audit(),
    )
    result = invoke_tool(run, "product_tool", {})
    assert_denied_closed(result, reason="authority_insufficient")
    assert api.call_count == 0
    assert_no_side_effect(handler)
