# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a brokered call refuses when there is no broker (research Finding 6).

`mirroring.py` used to obtain brokered material by calling two identity-fabric methods
documented "(fake only)", passing the literal string
``HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET``, and then returning ``allow``.
Production code performing a simulated exchange. A deployment configuring a brokered
product had its calls permitted against material that was never obtained.

**The entitlement check in front of it was real**, so the compensating control ADR-0044
requires was present and this was not an open door. What it was is a stub that reads as a
working mechanism — and Principle IV names the brokered path's management token as the one
permitted standing credential in the entire platform, so the mechanism it exists for
looking finished is exactly the wrong impression to leave.

**The order these rows assert is the load-bearing part.** A call the user is not entitled
to make must be denied for *that* reason. Refusing it for a missing broker would report a
platform gap where there was a policy answer — sending whoever reads the trail to our
roadmap instead of to their own access.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from tests.harness import capture_audit, fake_identity_fabric, frozen_clock
from tests.harness.fake_identity_fabric import (
    DEFAULT_AGENT_DEFINITION_ID,
    FakeBrokeredMaterialSource,
)

PRODUCT = "workspace"
ACTION = "product.workspace.read"


def _run(*, entitlements: frozenset[str], with_broker: bool) -> tuple[GovernedRun, list[int]]:
    calls: list[int] = []

    def tool_body(arguments: Mapping[str, Any]) -> dict[str, str]:
        calls.append(1)
        return {"ok": "wielded"}

    registry = ToolRegistry()
    registry.register(
        "product_tool",
        tool_body,
        product_mode="broker",
        product=PRODUCT,
        product_action=ACTION,
    )
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-broker",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(
            tool_names=frozenset({"product_tool"}), product_actions=frozenset({ACTION})
        ),
        identity_fabric=fake_identity_fabric(
            tool_names={"product_tool"},
            product_actions={ACTION},
            ceiling_tools={"product_tool"},
            ceiling_actions={ACTION},
            entitlements={("user-1", PRODUCT): entitlements},
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=capture_audit(),
        # The production case is None. Nothing in `src/` supplies one, because ADR-0044's
        # credential translation is a separate feature.
        brokered_material_source=FakeBrokeredMaterialSource() if with_broker else None,
    )
    return run, calls


def test_row_a_brokered_call_refuses_when_no_broker_is_configured() -> None:
    """The production configuration, and it must not permit."""
    run, calls = _run(entitlements=frozenset({ACTION}), with_broker=False)

    result = invoke_tool(run, "product_tool", {})

    assert not result.allowed
    assert result.reason_code == "broker_not_implemented"
    assert not calls, "the tool ran against material that was never obtained"


def test_row_the_refusal_says_the_mechanism_is_missing() -> None:
    """A refusal naming nothing sends an operator to their own configuration.

    The gap is ours, and the message has to say so or they will spend the afternoon
    checking permissions that are correct.
    """
    run, _ = _run(entitlements=frozenset({ACTION}), with_broker=False)
    invoke_tool(run, "product_tool", {})

    entries = run.audit_sink.list_by_correlation_id(run.correlation_id)
    codes = {(e.payload or {}).get("reason_code") for e in entries}
    assert "broker_not_implemented" in codes


def test_row_an_entitlement_denial_still_wins() -> None:
    """Order, and it is the whole reason this file has three rows instead of one.

    An unentitled call is denied for the entitlement, not for the broker — because that is
    a decision the platform made about a person's permissions, and reporting a platform
    gap in its place would be a false statement about why someone was refused.
    """
    run, calls = _run(entitlements=frozenset(), with_broker=False)

    result = invoke_tool(run, "product_tool", {})

    assert not result.allowed
    assert result.reason_code == "mirroring_denied", (
        "an unentitled brokered call reported the missing broker instead of the "
        "entitlement denial, which describes the platform where it should describe access"
    )
    assert not calls


def test_break_fixture_a_supplied_broker_allows() -> None:
    """The positive control, and it is what makes the three rows above mean anything.

    Without it, a hook that denied every brokered call unconditionally — a plausible
    over-correction — would satisfy all of them. This proves the refusal is about the
    absent mechanism rather than about brokering being disallowed.
    """
    run, calls = _run(entitlements=frozenset({ACTION}), with_broker=True)

    result = invoke_tool(run, "product_tool", {})

    assert result.allowed
    assert calls == [1]
