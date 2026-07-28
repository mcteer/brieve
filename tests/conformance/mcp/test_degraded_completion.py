# SPDX-License-Identifier: Apache-2.0
"""Row: the agent does the part it still can (FR-016).

A dependency being down should produce partial work rather than nothing. Writing the
Terraform and handing it back with "the workspace was unreachable" is what a competent
colleague does, and refusing outright wastes work the agent could have completed.

The half that matters more is the last assertion: **the result must not read as done.**
Returning plan output that looks applied is worse than returning nothing, because someone
acts on it.
"""

from __future__ import annotations

from core.dependencies.gate import DEPENDENCY_UNAVAILABLE, denial_class_for
from core.dependencies.types import DenialClass, HealthState
from core.run import GovernedRun
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class Down:
    def state_of(self, product: str) -> HealthState:
        return HealthState.UNHEALTHY


def _mixed_run() -> tuple[GovernedRun, CountingHandler, CountingHandler]:
    """A run with one reachable tool and one that needs a downed product."""
    plan = CountingHandler()
    apply_ = CountingHandler()
    run, _, _ = make_run(tool_name="plan", scope={"plan", "apply"}, handler=plan)
    run.registry.register("plan", plan)
    run.registry.register("apply", apply_, product="terraform-cloud")
    run.dependency_health = Down()
    return run, plan, apply_


def test_row_the_reachable_half_completes() -> None:
    run, plan, _ = _mixed_run()

    result = invoke_tool(run, "plan", {})

    assert result.allowed is True
    assert plan.call_count == 1, "work that needed nothing from the product was refused"


def test_row_the_unreachable_half_is_refused_and_named() -> None:
    run, _, apply_ = _mixed_run()

    result = invoke_tool(run, "apply", {})

    assert result.allowed is False
    assert apply_.call_count == 0
    assert "terraform-cloud" in (result.message or ""), (
        "the refusal did not say which dependency was unavailable, so a caller cannot "
        "report what was not attempted"
    )


def test_row_the_refusal_is_the_availability_class() -> None:
    """Only availability invites an alternative. A policy denial must not."""
    run, _, _ = _mixed_run()
    result = invoke_tool(run, "apply", {})

    assert denial_class_for(result.reason_code or "") is DenialClass.AVAILABILITY
    assert DenialClass.AVAILABILITY.is_model_visible()


def test_row_the_result_is_not_presented_as_a_completed_action() -> None:
    """T053. Returning plan output that reads as applied is worse than returning nothing.

    Asserted on the refusal itself: it is not `allowed`, it carries the availability
    reason code, and its message says what was *not* attempted rather than what was done.
    """
    run, _, _ = _mixed_run()
    result = invoke_tool(run, "apply", {})

    assert result.allowed is False, "an unreachable dependency reported success"
    assert result.reason_code == DEPENDENCY_UNAVAILABLE
    message = (result.message or "").lower()
    assert "not reachable" in message
    for claimed in ("applied", "completed", "succeeded", "done"):
        assert claimed not in message, (
            f"the refusal message says {claimed!r}, which reads as work having happened"
        )
