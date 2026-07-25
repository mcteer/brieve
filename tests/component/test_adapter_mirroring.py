# SPDX-License-Identifier: Apache-2.0
"""US2 — entitlement mirroring holds on the adapter path (FR-005).

The adapter must not weaken 003's rule that a brokered action is checked against
the requester's own product entitlements before any shared-grain credential is
wielded. Same property as ``test_entitlement_mirroring``, reached through an
agent run rather than a direct ``invoke_tool`` call.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.pydantic_ai.run_context import AdapterRunContext
from adapters.pydantic_ai.tools import GovernedToolError
from core.registry.memory import ToolRegistry
from tests.harness import assert_no_side_effect, fake_identity_fabric
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture
from tests.harness.fake_product_api import fake_product_api

PRODUCT = "terraform"
ACTION = "plan"


def _mirroring_fixture(
    *, entitlements: frozenset[str]
) -> tuple[Any, AdapterRunContext, CountingHandler, Any]:
    handler = CountingHandler()
    api = fake_product_api()
    registry = ToolRegistry()
    registry.register(
        "product_tool",
        handler,
        product_mode="broker",
        product=PRODUCT,
        product_action=ACTION,
    )
    fabric = fake_identity_fabric(
        tool_names={"product_tool"},
        product_actions={ACTION},
        ceiling_tools={"product_tool"},
        ceiling_actions={ACTION},
        entitlements={("user-1", PRODUCT): entitlements},
    )
    agent, deps, _handlers, _audit = governed_agent_fixture(
        tool_calls=[("product_tool", {})],
        registry=registry,
        framework_tools=["product_tool"],
        scope_tools=["product_tool"],
        scope_actions=[ACTION],
        fabric=fabric,
    )
    return agent, deps, handler, api


@pytest.mark.anyio
async def test_missing_entitlement_denies_with_zero_product_wields() -> None:
    agent, deps, handler, api = _mirroring_fixture(entitlements=frozenset())

    with pytest.raises(GovernedToolError):
        await agent.run("go", deps=deps)

    assert_no_side_effect(handler)
    assert api.call_count == 0, "no shared-grain credential may be wielded without entitlement"


@pytest.mark.anyio
async def test_entitled_requester_is_allowed_once() -> None:
    agent, deps, handler, _api = _mirroring_fixture(entitlements=frozenset({ACTION}))

    await agent.run("go", deps=deps)

    assert handler.call_count == 1
