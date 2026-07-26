# SPDX-License-Identifier: Apache-2.0
"""US4 — an interrupted step is resolved by looking, not by guessing (T041-T049)."""

from __future__ import annotations

from core.authority.grant import DelegationGrant
from core.authority.types import AuthorityScope
from core.durability.checkpoint import checkpoint_run
from core.durability.lease import RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import ResumeDecision, resume_run
from core.durability.types import IntentRecord
from core.observation.types import ObservationOutcome, Observer
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, RunState, start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    ScriptedObserver,
    capture_audit,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.frozen_clock import FrozenClock


def _durable_run(
    provider: InMemoryDurabilityProvider,
    clock: FrozenClock,
    grant: DelegationGrant,
    *,
    observer: Observer | None = None,
    repeatable: bool = False,
) -> tuple[GovernedRun, CountingHandler]:
    registry = ToolRegistry()
    handler = CountingHandler()
    registry.register("provision", handler, repeatable=repeatable, observer=observer)
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-obs-1",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"provision"})),
        identity_fabric=fake_identity_fabric(tool_names={"provision"}, ceiling_tools={"provision"}),
        clock=clock,
        registry=registry,
        audit_sink=capture_audit(),
    )
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    run.lease = RunLease(provider, run_id="run-1", holder_identity="alloc-1")
    run.lease.acquire()
    return run, handler


def _interrupt_after_effect(
    provider: InMemoryDurabilityProvider, clock: FrozenClock, *, tool: str = "provision"
) -> str:
    """An intent with no result: the step took effect, the result was never written."""
    key = f"run-1:0:{tool}"
    provider.record_intent(
        IntentRecord(
            run_id="run-1",
            step_index=0,
            tool_name=tool,
            idempotency_key=key,
            recorded_at=clock.now(),
        )
    )
    return key


def _resume(
    provider: InMemoryDurabilityProvider,
    grant: DelegationGrant,
    clock: FrozenClock,
    observers: dict[str, Observer],
) -> ResumeDecision:
    return resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"provision"}, ceiling_tools={"provision"}),
        clock=clock,
        observers=observers,
    )


def test_non_repeatable_call_is_bracketed() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)

    assert invoke_tool(run, "provision").allowed

    # Completed cleanly: the bracket closed, so nothing is open for resume to resolve.
    assert provider.open_intents("run-1") == []


def test_repeatable_call_is_not_bracketed() -> None:
    """Paying for observation on every call would be correct but expensive."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant, repeatable=True)

    invoke_tool(run, "provision")

    assert provider.open_intents("run-1") == []
    assert not provider._intents, "no bracket written for a repeatable tool"


def test_observed_effect_is_not_repeated() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, handler = _durable_run(provider, clock, grant)
    checkpoint_run(run, payload={})
    key = _interrupt_after_effect(provider, clock)

    observer = ScriptedObserver(outcomes={key: ObservationOutcome.HAPPENED})
    decision = _resume(provider, grant, clock, {"provision": observer})

    assert decision.resumable
    assert [i.idempotency_key for i in decision.completed_steps] == [key]
    assert decision.pending_steps == []
    assert observer.calls == [key], "it looked, rather than assuming"


def test_absent_effect_lets_the_step_proceed() -> None:
    """Both directions are required: only skipping proves the platform can skip."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)
    checkpoint_run(run, payload={})
    key = _interrupt_after_effect(provider, clock)

    observer = ScriptedObserver(outcomes={key: ObservationOutcome.DID_NOT_HAPPEN})
    decision = _resume(provider, grant, clock, {"provision": observer})

    assert decision.resumable
    assert [i.idempotency_key for i in decision.pending_steps] == [key]
    assert decision.completed_steps == []


def test_unobservable_step_parks() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)
    checkpoint_run(run, payload={})
    _interrupt_after_effect(provider, clock)

    decision = _resume(
        provider,
        grant,
        clock,
        {"provision": ScriptedObserver()},  # defaults to cannot-determine
    )

    assert decision.state is RunState.PARKED
    assert decision.park_reason is not None
    assert decision.park_reason.startswith("unobservable_step:provision")


def test_unreachable_external_system_is_not_evidence() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)
    checkpoint_run(run, payload={})
    _interrupt_after_effect(provider, clock)

    decision = _resume(provider, grant, clock, {"provision": ScriptedObserver(raises=True)})

    assert decision.state is RunState.PARKED, "an unreachable system means we do not know"


def test_missing_observer_parks_rather_than_guessing() -> None:
    """Not having a way to look is not evidence of anything."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)
    checkpoint_run(run, payload={})
    _interrupt_after_effect(provider, clock)

    decision = _resume(provider, grant, clock, {})

    assert decision.state is RunState.PARKED
    assert "no observer registered" in (decision.park_reason or "")


def test_idempotency_key_is_stable_per_step_and_distinct_across_steps() -> None:
    """FR-010: a retry of a step is the same step; a later call is a different one."""
    from core.hooks.engine import _idempotency_key

    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant)

    first = _idempotency_key(run, "provision")
    again = _idempotency_key(run, "provision")
    run.step_index += 1
    later = _idempotency_key(run, "provision")

    assert first == again
    assert first != later
