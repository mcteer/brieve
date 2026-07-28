# SPDX-License-Identifier: Apache-2.0
"""Row: the two kinds of "no" stay distinct, in the trail and to the model (FR-008, SC-005).

The subtlest thing in this feature, and the one where being **backwards** does the damage.

A policy denial is the governance boundary holding: an agent that treats it as an obstacle
to route around inverts Principles II and III. An availability denial invites a legitimate
alternative — write the Terraform, hand it back, say the workspace was unreachable.

Blur them and an agent learns that refusals are negotiable. Nothing breaks visibly while it
learns that, which is why this is a row rather than a comment.
"""

from __future__ import annotations

from core.dependencies.gate import DEPENDENCY_UNAVAILABLE, denial_class_for
from core.dependencies.types import DenialClass, HealthState
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class Unhealthy:
    def state_of(self, product: str) -> HealthState:
        return HealthState.UNHEALTHY


def _availability_refusal():  # type: ignore[no-untyped-def]
    handler = CountingHandler()
    run, h, _ = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud")
    run.dependency_health = Unhealthy()
    return invoke_tool(run, "provision", {})


def _policy_refusal():  # type: ignore[no-untyped-def]
    """Out of scope: the tool is not in the run's authority."""
    handler = CountingHandler()
    run, h, _ = make_run(tool_name="echo", scope={"echo"}, handler=handler)
    run.registry.register("forbidden", h)
    return invoke_tool(run, "forbidden", {})


def test_row_the_classes_are_distinguishable() -> None:
    availability = _availability_refusal()
    policy = _policy_refusal()

    assert availability.allowed is False
    assert policy.allowed is False
    assert availability.reason_code != policy.reason_code, (
        "an operator cannot tell 'not reachable' from 'not allowed', and those send you "
        "to entirely different places"
    )
    assert denial_class_for(availability.reason_code or "") is DenialClass.AVAILABILITY
    assert denial_class_for(policy.reason_code or "") is DenialClass.POLICY


def test_row_only_availability_is_model_visible() -> None:
    assert DenialClass.AVAILABILITY.is_model_visible()
    assert not DenialClass.POLICY.is_model_visible()


def test_row_the_availability_message_invites_an_alternative() -> None:
    """It tells the agent what it may do instead — which is the point of the class."""
    result = _availability_refusal()
    message = (result.message or "").lower()

    assert "terraform-cloud" in message
    assert "availability limit" in message
    assert "not a permission one" in message


def test_row_the_policy_message_invites_nothing() -> None:
    """The complement, and the half that matters more.

    A scope refusal that suggested an alternative would teach exactly the behaviour the
    governance layer exists to prevent.
    """
    result = _policy_refusal()
    message = (result.message or "").lower()

    for invitation in ("instead", "alternative", "another route", "retry"):
        assert invitation not in message, (
            f"a policy denial suggested {invitation!r} — that teaches an agent to route "
            "around a governance boundary"
        )


def test_break_fixture_collapsing_the_classes_is_detected() -> None:
    """If every reason code mapped to one class, this row would be vacuous."""
    collapsed = {denial_class_for(code) for code in (DEPENDENCY_UNAVAILABLE, "scope_denied")}
    assert len(collapsed) == 2, "the two denial classes collapsed into one"
