# SPDX-License-Identifier: Apache-2.0
"""US3 — a run whose consent has expired parks instead of resuming (T035-T040)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from core.authority.grant import DelegationGrant, GrantExpiredError, issue_grant
from core.authority.types import AuthorityScope
from core.durability.checkpoint import checkpoint_run, park_run
from core.durability.lease import RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.run import GovernedRun, RunState
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.frozen_clock import FrozenClock


def _run_with(
    provider: InMemoryDurabilityProvider,
    clock: FrozenClock,
    grant: DelegationGrant,
    handler: CountingHandler | None = None,
) -> tuple[GovernedRun, CountingHandler, Any]:
    run, h, audit = make_run(scope={"echo"}, handler=handler)
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    run.lease = RunLease(provider, run_id="run-1", holder_identity="alloc-1")
    run.lease.acquire()
    return run, h, audit


def test_resume_under_expired_consent_parks_with_zero_further_steps() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=30),
    )
    handler = CountingHandler()
    run, _, _ = _run_with(provider, clock, grant, handler)
    invoke_tool(run, "echo")
    checkpoint_run(run)
    executions_before = handler.call_count

    clock.advance(timedelta(minutes=31))
    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )

    assert decision.state is RunState.PARKED
    assert decision.park_reason == "grant_expired"
    assert decision.authority is None, "parked runs hold no live authority"
    assert handler.call_count == executions_before, "zero steps after parking"


def test_parked_run_is_durable_and_resumable_under_fresh_consent() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    expired = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=5),
    )
    run, _, _ = _run_with(provider, clock, expired)
    checkpoint_run(run, payload={"progress": "step-1"})
    clock.advance(timedelta(minutes=6))

    park_run(run, reason="grant_expired")
    assert run.state is RunState.PARKED

    # Parked is NOT terminal: fresh consent lets the same checkpoint resume.
    renewed = durability_grant(clock, tool_names={"echo"})
    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=renewed,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )
    assert decision.resumable
    assert decision.checkpoint is not None
    assert decision.checkpoint.payload["progress"] == "step-1", "the work survived"


def test_consent_expiring_mid_run_stops_at_the_same_boundary() -> None:
    """One behaviour, not two: the next step cannot be authorized either way."""
    clock = frozen_clock()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=10),
    )
    clock.advance(timedelta(minutes=11))

    from core.authority.manufacture import manufacture_authority

    with pytest.raises(GrantExpiredError):
        manufacture_authority(
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
            identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
            clock=clock,
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
            grant=grant,
        )


def test_parking_does_not_mark_the_run_terminal() -> None:
    """Marking it terminal would make resume refuse a run that is merely waiting."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})
    run, _, _ = _run_with(provider, clock, grant)

    park_run(run, reason="grant_expired")

    blob = provider.load("run-1")
    assert blob is not None
    assert blob.outcome is None, "PARKED is not written as a terminal outcome"
    assert not RunState.PARKED.is_terminal()
