# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a user cannot exceed themselves through an agent (SC-007, FR-010).

The compensating control ADR-0044 requires. Both authorization domains are checked
independently and both must agree: the harness domain says what the agent may attempt, the
product domain says what *this person* may do inside the product, and either refusing
refuses the call.

**Two checks that must agree are not one check consulted twice.** The failure worth guarding
is an implementation that resolved the harness scope, found it sufficient, and never asked
the product — which passes every test about scope and every test about denial, and quietly
lets an agent act with more authority in a product than the person who asked for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.harness import (
    assert_no_side_effect,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.fake_identity_fabric import (
    DEFAULT_AGENT_DEFINITION_ID,
    FakeBrokeredMaterialSource,
)
from tests.harness.fake_product_api import FakeProductApi

PRODUCT = "workspace"
READ = "product.workspace.read"
WRITE = "product.workspace.write"


def _run(*, user_entitlements: frozenset[str], action: str) -> tuple[Any, list[int]]:
    calls: list[int] = []
    api = FakeProductApi(mode="broker", entitlements={"user-1": user_entitlements})

    def tool_body(arguments: Mapping[str, Any]) -> dict[str, str]:
        calls.append(1)
        return api.wield(subject_user_id="user-1", action=action)

    registry = ToolRegistry()
    registry.register(
        "product_tool", tool_body, product_mode="broker", product=PRODUCT, product_action=action
    )
    run = start_governed_run(
        correlation_id="corr-mirror-bites",
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(
            tool_names=frozenset({"product_tool"}), product_actions=frozenset({READ, WRITE})
        ),
        # The HARNESS domain is deliberately wide: the agent's scope permits the action.
        # If the run is refused, only the product domain can have refused it.
        identity_fabric=fake_identity_fabric(
            tool_names={"product_tool"},
            product_actions={READ, WRITE},
            ceiling_tools={"product_tool"},
            ceiling_actions={READ, WRITE},
            entitlements={("user-1", PRODUCT): user_entitlements},
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=capture_audit(),
        brokered_material_source=FakeBrokeredMaterialSource(),
    )
    return (run, calls)


def test_a_user_narrower_than_the_agent_cannot_exceed_themselves() -> None:
    """The row. Harness domain permits the write; the person may only read."""
    run, calls = _run(user_entitlements=frozenset({READ}), action=WRITE)

    result = invoke_tool(run, "product_tool", {"action": WRITE})

    assert not result.allowed
    assert result.reason_code == "mirroring_denied"
    assert not calls, "the tool wielded a credential the requesting user could not have used"


def test_the_same_call_succeeds_for_a_user_who_may_make_it() -> None:
    """The positive control, and the reason the row above is about mirroring.

    Identical agent, identical scope, identical action — only the person's product
    entitlements differ. Without this, a hook that denied every product call would satisfy
    the row above perfectly.
    """
    run, calls = _run(user_entitlements=frozenset({READ, WRITE}), action=WRITE)

    result = invoke_tool(run, "product_tool", {"action": WRITE})

    assert result.allowed
    assert calls == [1]


def test_zero_side_effects_on_the_refused_attempt() -> None:
    """Refused BEFORE execution, not observed to have failed after it (SC-007).

    A check that ran after the wield would produce the same verdict and a changed
    workspace, which is the whole difference between a control and a report.
    """
    run, calls = _run(user_entitlements=frozenset(), action=WRITE)

    invoke_tool(run, "product_tool", {"action": WRITE})

    assert not calls
    assert_no_side_effect(type("H", (), {"call_count": len(calls)})())
