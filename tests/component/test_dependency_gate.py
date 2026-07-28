# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the gate refuses before execution, and is inert when unconfigured.

The two behaviours are easy to collapse into one and the collapse is invisible: "unknown
health for a monitored product is unhealthy" and "a run with no dependency mechanism
denies everything" would both be implemented by refusing whenever the reader says nothing.
The second breaks every run that predates this feature, while looking exactly like the
first working correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.dependencies.gate import DEPENDENCY_UNAVAILABLE, denial_class_for
from core.dependencies.types import DenialClass, DependencyHealthReader, HealthState
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class StubHealth:
    """A reader, and nothing more — it has no way to record health.

    Typed as the protocol a run holds, which names only `state_of`.
    """

    def __init__(self, states: dict[str, HealthState]) -> None:
        self._states = states

    def state_of(self, product: str) -> HealthState:
        return self._states.get(product, HealthState.UNKNOWN)


def _run_with_product(health: DependencyHealthReader | None):  # type: ignore[no-untyped-def]
    """A run whose tool reaches a product.

    ``product`` is set without a ``product_mode``, deliberately: entitlement mirroring
    engages on federate/broker modes and would decide these calls for reasons that have
    nothing to do with dependency health. The gate reads the product tag either way.
    """
    handler = CountingHandler()
    run, h, audit = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud")
    if health is not None:
        run.dependency_health = health
    return run, h, audit


def test_gate_is_inert_when_no_reader_is_configured() -> None:
    """Every 002-era run is in this position, which is why it must not refuse."""
    run, handler, _ = _run_with_product(None)
    result = invoke_tool(run, "provision", {})
    assert result.allowed is True
    assert handler.call_count == 1


def test_unhealthy_dependency_is_refused_before_execution() -> None:
    run, handler, _ = _run_with_product(StubHealth({"terraform-cloud": HealthState.UNHEALTHY}))
    result = invoke_tool(run, "provision", {})

    assert result.allowed is False
    assert result.reason_code == DEPENDENCY_UNAVAILABLE
    assert handler.call_count == 0, "the tool body ran despite the refusal"


def test_unknown_is_treated_as_unhealthy() -> None:
    """Guessing reachable is how a dead dependency gets called anyway."""
    run, handler, _ = _run_with_product(StubHealth({}))
    result = invoke_tool(run, "provision", {})
    assert result.allowed is False
    assert handler.call_count == 0


def test_healthy_dependency_permits_the_call() -> None:
    """Without this, every assertion above would also pass against a gate that always denies."""
    run, handler, _ = _run_with_product(StubHealth({"terraform-cloud": HealthState.HEALTHY}))
    result = invoke_tool(run, "provision", {})
    assert result.allowed is True
    assert handler.call_count == 1


def test_a_tool_with_no_product_has_no_dependency_to_be_down() -> None:
    run, _, _ = make_run(tool_name="echo", scope={"echo"})
    run.dependency_health = StubHealth({})

    assert invoke_tool(run, "echo", {}).allowed is True


def test_the_two_denial_classes_do_not_blur() -> None:
    """Only availability is model-visible.

    Backwards, an agent is taught that a scope refusal is something to route around —
    which inverts Principles II and III, and nothing would break visibly while it learned.
    """
    assert denial_class_for(DEPENDENCY_UNAVAILABLE) is DenialClass.AVAILABILITY
    assert denial_class_for("scope_denied") is DenialClass.POLICY
    assert DenialClass.AVAILABILITY.is_model_visible()
    assert not DenialClass.POLICY.is_model_visible()


def test_the_refusal_tells_the_agent_what_it_may_do_instead() -> None:
    """The availability class invites an alternative rather than a retry."""
    run, _, _ = _run_with_product(StubHealth({"terraform-cloud": HealthState.UNHEALTHY}))
    result = invoke_tool(run, "provision", {})
    message = (result.message or "").lower()
    assert "terraform-cloud" in message
    assert "not reachable" in message
    assert "availability" in message


def test_health_staleness_is_visible_on_the_record() -> None:
    from core.dependencies.types import DependencyHealth

    record = DependencyHealth(
        product="terraform-cloud",
        state=HealthState.HEALTHY,
        checked_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert record.checked_at.year == 2026, "when it was checked must survive the record"
