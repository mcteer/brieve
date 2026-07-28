# SPDX-License-Identifier: Apache-2.0
"""Row: a call against a known-dead dependency is refused before it runs.

**No intent record** is the substantive half (FR-007, SC-004). Attempting a call against a
dead dependency writes an intent that must later be resolved by re-observation — against
the same dead dependency. The bracket that exists to make interrupted steps resolvable
becomes the thing that cannot be resolved, so refusing before execution is not an
optimisation, it is what keeps the resume path from deadlocking on itself.
"""

from __future__ import annotations

from core.dependencies.gate import DEPENDENCY_UNAVAILABLE
from core.dependencies.types import HealthState
from core.durability.memory import InMemoryDurabilityProvider
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class StubHealth:
    def __init__(self, state: HealthState) -> None:
        self._state = state

    def state_of(self, product: str) -> HealthState:
        return self._state


def _bracketed_run(state: HealthState):  # type: ignore[no-untyped-def]
    """A run whose tool is non-repeatable, so the bracket would engage if we got that far."""
    handler = CountingHandler()
    run, h, _ = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud", repeatable=False)
    run.durability = InMemoryDurabilityProvider()
    run.run_id = "run-refusal"
    run.dependency_health = StubHealth(state)
    return run, h


def test_row_refusal_precedes_execution() -> None:
    run, handler = _bracketed_run(HealthState.UNHEALTHY)
    result = invoke_tool(run, "provision", {})

    assert result.allowed is False
    assert result.reason_code == DEPENDENCY_UNAVAILABLE
    assert handler.call_count == 0


def test_row_no_intent_record_is_written() -> None:
    """The assertion that matters, and the one a behaviour-only row would miss."""
    run, _ = _bracketed_run(HealthState.UNHEALTHY)
    invoke_tool(run, "provision", {})

    provider = run.durability
    assert provider is not None
    assert provider.open_intents("run-refusal") == [], (
        "a refused call left an intent for resume to resolve against the same dead dependency"
    )


def test_row_a_permitted_call_does_write_one() -> None:
    """The control. Without it, every assertion above passes against a broken bracket.

    If the bracket never engaged at all, "no intent record" would be trivially true and
    would prove nothing about the refusal.
    """
    run, handler = _bracketed_run(HealthState.HEALTHY)
    result = invoke_tool(run, "provision", {})

    assert result.allowed is True
    assert handler.call_count == 1
    provider = run.durability
    assert provider is not None
    assert provider.open_intents("run-refusal") == [], "a completed step should close its bracket"


def test_row_the_denial_is_audited() -> None:
    run, _ = _bracketed_run(HealthState.UNHEALTHY)
    _, _, audit = make_run(tool_name="provision", scope={"provision"})
    invoke_tool(run, "provision", {})

    entries = run.audit_sink.list_by_correlation_id(run.correlation_id)
    denials = [
        e
        for e in entries
        if (e.payload or {}).get("reason_code") == DEPENDENCY_UNAVAILABLE
    ]
    assert denials, "an availability refusal left no trace in the trail"
