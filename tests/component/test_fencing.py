# SPDX-License-Identifier: Apache-2.0
"""US5 — a resumed run invalidates any instance still running elsewhere (T050-T056).

The requirement is rejection, not a race won. Under ADR-0048 the superseded instance is
presenting an identity that provably is not current, so the check has no timing in it.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.grant import DelegationGrant
from core.durability.checkpoint import checkpoint_run
from core.durability.lease import LeaseSupersededError, RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.run import GovernedRun
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run
from tests.harness import durability_grant, frozen_clock
from tests.harness.frozen_clock import FrozenClock


def _instance(
    provider: InMemoryDurabilityProvider,
    clock: FrozenClock,
    grant: DelegationGrant,
    holder: str,
    handler: CountingHandler | None = None,
) -> tuple[GovernedRun, CountingHandler, Any]:
    run, h, audit = make_run(scope={"echo"}, handler=handler)
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    lease = RunLease(provider, run_id="run-1", holder_identity=holder)
    run.lease = lease
    lease.acquire()
    return run, h, audit


def test_superseded_instance_tool_call_is_rejected_with_no_side_effect() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    zombie_handler = CountingHandler()
    zombie, _, _ = _instance(provider, clock, grant, "alloc-1", zombie_handler)
    assert invoke_tool(zombie, "echo").allowed
    executions = zombie_handler.call_count

    # A new allocation resumes the run.
    fresh, _, _ = _instance(provider, clock, grant, "alloc-2")

    with pytest.raises(LeaseSupersededError):
        invoke_tool(zombie, "echo")

    assert zombie_handler.call_count == executions, "zero side effects from the zombie"


def test_superseded_instance_checkpoint_write_is_rejected() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    zombie, _, _ = _instance(provider, clock, grant, "alloc-1")
    checkpoint_run(zombie, payload={"progress": "from-alloc-1"})

    fresh, _, _ = _instance(provider, clock, grant, "alloc-2")
    checkpoint_run(fresh, payload={"progress": "from-alloc-2"})

    with pytest.raises(LeaseSupersededError):
        checkpoint_run(zombie, payload={"progress": "stale"})

    blob = provider.load("run-1")
    assert blob is not None
    assert blob.payload["progress"] == "from-alloc-2", "current state was not overwritten"


def test_rejection_is_distinguishable_from_an_ordinary_denial() -> None:
    """An operator needs to tell 'a policy refused this' from 'you are a zombie'."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    zombie, _, _ = _instance(provider, clock, grant, "alloc-1")
    fresh, _, _ = _instance(provider, clock, grant, "alloc-2")

    with pytest.raises(LeaseSupersededError) as excinfo:
        invoke_tool(zombie, "echo")

    assert excinfo.value.reason_code == "lease_superseded"
    # Not an InvokeResult deny: a zombie's caller must stop, not read a refusal and
    # move on to the next tool.
    assert not isinstance(excinfo.value, ValueError)


def test_exactly_one_holder_after_simultaneous_resume() -> None:
    provider = InMemoryDurabilityProvider()

    first = RunLease(provider, run_id="run-1", holder_identity="alloc-1")
    second = RunLease(provider, run_id="run-1", holder_identity="alloc-2")
    first.acquire()
    second.acquire()

    assert second.held()
    assert not first.held(), "the loser is refused, not queued"


def test_blank_holder_identity_is_refused() -> None:
    """Two blank identities would compare equal, silently disabling fencing."""
    provider = InMemoryDurabilityProvider()
    with pytest.raises(ValueError, match="non-empty"):
        RunLease(provider, run_id="run-1", holder_identity="  ")
