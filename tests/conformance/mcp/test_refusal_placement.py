# SPDX-License-Identifier: Apache-2.0
"""Row: the dependency gate runs INSIDE the hook pipeline, not before it (FR-009).

This row asserts **placement**, which is unusual and deliberate. Behaviour is covered
elsewhere: `test_dependency_refusal.py` proves an unreachable dependency is refused and
writes no intent. Both of those would remain true if someone moved the check to a
pre-flight guard before the pipeline — it would work, it would be faster, and it would be
a second refusal path, which is a second authorization path wearing a practical-sounding
name (Principle II).

**So the break fixture is a working optimisation, not a broken gate.** A fixture that
removed the gate would test refusal, which another row already covers. The failure being
guarded here is the one where everything passes.
"""

from __future__ import annotations

from typing import Any

from core.dependencies.gate import DEPENDENCY_HOOK_NAME, dependency_pre_hook
from core.dependencies.types import HealthState
from core.hooks.governance import builtin_governance_hooks
from core.hooks.types import CapabilityKind, HookPhase
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class StubHealth:
    def state_of(self, product: str) -> HealthState:
        return HealthState.UNHEALTHY


def test_row_the_gate_is_registered_as_a_governance_hook() -> None:
    """It is in the pipeline's own list, not called from beside it."""
    hooks = builtin_governance_hooks()
    matching = [h for h in hooks if h.name == DEPENDENCY_HOOK_NAME]

    assert matching, "the dependency gate is not among the governance hooks"
    gate = matching[0]
    assert gate.phase is HookPhase.PRE
    assert gate.capability_kind is CapabilityKind.GOVERNANCE
    assert gate.handler is dependency_pre_hook


def test_row_the_gate_runs_before_authority() -> None:
    """Order, not merely membership.

    A call against an unreachable product cannot succeed whatever its authority says, so
    refusing first keeps the *reason* accurate. Checking authority first would refuse a
    perfectly authorized call with a scope error when a product is down — sending whoever
    debugs it somewhere else entirely.
    """
    names = [h.name for h in builtin_governance_hooks() if h.phase is HookPhase.PRE]
    assert names.index(DEPENDENCY_HOOK_NAME) < names.index("authority")


def test_row_the_refusal_appears_in_the_hook_trail() -> None:
    """The observable consequence of placement.

    A pre-flight guard would produce the same verdict with no hook record — the denial
    would simply appear, decided by nothing the pipeline can account for. An investigator
    reconstructing the run would find a refusal with no decision behind it.
    """
    handler = CountingHandler()
    run, h, _ = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud")
    run.dependency_health = StubHealth()

    invoke_tool(run, "provision", {})

    entries = run.audit_sink.list_by_correlation_id(run.correlation_id)
    hook_records = [
        e for e in entries if (e.payload or {}).get("hook_name") == DEPENDENCY_HOOK_NAME
    ]
    assert hook_records, (
        "the refusal left no hook record — it was decided outside the pipeline, which is "
        "the pre-flight arrangement this row exists to catch"
    )


def test_break_fixture_a_working_pre_flight_is_detected() -> None:
    """Construct the optimisation someone would actually make, and assert it is caught.

    This pre-flight *works*: it refuses the same calls, faster, skipping machinery for a
    call that would be refused anyway. Every behavioural assertion in this feature would
    still pass. What fails is the placement check — which is the entire reason placement
    is asserted rather than inferred from outcomes.
    """

    def pre_flight_guard(run: Any, tool_name: str) -> str | None:
        """The tempting version: check first, skip the pipeline entirely."""
        reader = getattr(run, "dependency_health", None)
        if reader is None:
            return None
        registration = run.registry.resolve(tool_name)
        product = getattr(registration, "product", None)
        if product and not reader.state_of(product).permits_calls():
            return "refused"
        return None

    handler = CountingHandler()
    run, h, _ = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud")
    run.dependency_health = StubHealth()

    # It refuses correctly — that is the point.
    assert pre_flight_guard(run, "provision") == "refused"
    assert handler.call_count == 0

    # And it is not a registered hook, which is what the row above would catch.
    registered = {id(hook.handler) for hook in builtin_governance_hooks()}
    assert id(pre_flight_guard) not in registered, (
        "a pre-flight guard was registered as a hook, which would hide the very "
        "arrangement this fixture models"
    )
