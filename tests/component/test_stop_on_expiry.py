# SPDX-License-Identifier: Apache-2.0
"""A run whose consent has expired STOPS instead of resuming.

Was "parks instead of resuming", and the change is ADR-0049 superseding ADR-0026's
re-consent rule. Grant expiry is an execution bound like any other: recorded, terminal,
and resolved by nobody. The test that used to assert a parked run resumed "under fresh
consent" asserted precisely the mechanism that was removed — there is no human being asked
to re-consent, so there is nothing for fresh consent to be.

The other half of what PARKED conflated lives in the suspension tests below: waiting on a
machine condition, which does clear itself.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from core.authority.grant import DelegationGrant, GrantExpiredError, issue_grant
from core.authority.types import AuthorityScope
from core.durability.checkpoint import checkpoint_run, suspend_run
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


def test_resume_under_expired_consent_stops_with_zero_further_steps() -> None:
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

    assert decision.state is RunState.STOPPED
    assert decision.state.is_terminal(), "a bound is terminal — nothing resumes it"
    assert decision.stop_reason == "grant_expired"
    assert decision.authority is None, "stopped runs hold no live authority"
    assert handler.call_count == executions_before, "zero steps after stopping"


def test_fresh_consent_does_not_revive_a_run_that_hit_its_bound() -> None:
    """The inverse of what this asserted before, and the substance of ADR-0049.

    It used to prove that a parked run resumed once consent was renewed. That was the
    re-consent loop the ADR removes: a run reaching its grant's end has hit a bound, and
    bounds are not renegotiated mid-run. Consent to start a run was consent to finish it,
    and the run finished.
    """
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

    # Resuming under the EXPIRED grant stops, and records why.
    stopped = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=expired,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )
    assert stopped.state is RunState.STOPPED
    assert stopped.stop_reason == "grant_expired"

    # And the work is still on disk. Stopping is not losing — an operator can read what
    # the run had done. What they cannot do is hand it a new grant and continue it.
    blob = provider.load("run-1")
    assert blob is not None
    assert blob.payload["progress"] == "step-1", "the record survived the bound"


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


def test_suspension_does_not_mark_the_run_terminal() -> None:
    """The half of PARKED that survives: waiting on a machine condition.

    Marking it terminal would make resume refuse a run that is merely waiting — and the
    sweeper would then have nothing it could ever pick up, which presents as a hang rather
    than as an error.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})
    run, _, _ = _run_with(provider, clock, grant)

    suspend_run(run, awaiting="terraform-cloud")

    blob = provider.load("run-1")
    assert blob is not None
    assert blob.outcome is None, "SUSPENDED is not written as a terminal outcome"
    assert not RunState.SUSPENDED.is_terminal()
    assert run.stop_reason == "awaiting:terraform-cloud", "a suspension names its dependency"


def test_a_suspension_must_name_what_it_waits_on() -> None:
    """A suspension with no named dependency is a run the sweeper can never find.

    It would sit suspended forever — the exact hang ADR-0049 exists to prevent, produced
    by the mechanism meant to prevent it. So it is refused at the point of suspending
    rather than discovered later by its absence.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})
    run, _, _ = _run_with(provider, clock, grant)

    with pytest.raises(ValueError, match="must name the dependency"):
        suspend_run(run, awaiting="   ")
