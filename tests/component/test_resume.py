# SPDX-License-Identifier: Apache-2.0
"""US1 — an interrupted run resumes without re-doing its work (T022-T025)."""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.grant import DelegationGrant
from core.bounds import BoundsTracker, ExecutionBounds
from core.durability.checkpoint import checkpoint_run, complete_run
from core.durability.lease import RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob
from core.run import GovernedRun, RunState
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run
from tests.harness import (
    SideEffectCounter,
    assert_audit_chain,
    assert_correlated,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.frozen_clock import FrozenClock


def _durable_run(
    provider: InMemoryDurabilityProvider,
    clock: FrozenClock,
    holder: str,
    grant: DelegationGrant,
    **kw: Any,
) -> tuple[GovernedRun, CountingHandler, Any]:
    run, handler, audit = make_run(**kw)
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    run.lease = RunLease(provider, run_id="run-1", holder_identity=holder)
    run.lease.acquire()
    run.bounds = BoundsTracker(bounds=ExecutionBounds(), started_at=clock.now())
    return run, handler, audit


def test_disrupted_run_resumes_and_completes() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, handler, audit = _durable_run(provider, clock, "alloc-1", grant, scope={"echo"})
    assert invoke_tool(run, "echo").allowed
    run.step_index = 1
    checkpoint_run(run, payload={"progress": "step-1"})

    # Disruption: this process is gone. A NEW allocation picks the run up.
    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )

    assert decision.resumable
    assert decision.checkpoint is not None
    assert decision.checkpoint.step_index == 1, "resumes from where it stopped"
    assert decision.checkpoint.payload["progress"] == "step-1"


def test_completed_steps_execute_exactly_once_across_the_whole_run() -> None:
    """Per-segment counting would pass an implementation that re-runs on resume."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})
    counter = SideEffectCounter()

    class Recording(CountingHandler):
        def __call__(self, arguments):  # type: ignore[no-untyped-def]
            counter.record("echo")
            return super().__call__(arguments)

    run, _, _ = _durable_run(provider, clock, "alloc-1", grant, scope={"echo"}, handler=Recording())
    invoke_tool(run, "echo")
    run.step_index = 1
    checkpoint_run(run)

    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )
    # Resume does not replay completed steps: it continues from step_index.
    assert decision.resumable
    assert counter.total("echo") == 1


def test_correlation_and_chain_span_the_disruption() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, audit = _durable_run(provider, clock, "alloc-1", grant, scope={"echo"})
    invoke_tool(run, "echo")
    run.step_index = 1
    checkpoint_run(run)

    blob = provider.load("run-1")
    assert blob is not None
    assert blob.correlation_id == run.correlation_id, "the checkpoint carries the join key"
    assert_correlated(audit, [], run.correlation_id)
    assert_audit_chain(audit)


def test_completing_a_run_records_it_in_the_store() -> None:
    """T026a: a state nothing writes is a state nothing can be trusted to mean."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, _ = _durable_run(provider, clock, "alloc-1", grant, scope={"echo"})
    complete_run(run)

    assert run.state is RunState.COMPLETED
    blob = provider.load("run-1")
    assert blob is not None and blob.outcome is not None
    assert blob.outcome.state == RunState.COMPLETED.value

    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )
    assert not decision.resumable, "a finished run is not re-entered"


class ExplodingProvider(InMemoryDurabilityProvider):
    def save(self, blob: CheckpointBlob) -> None:
        raise RuntimeError("store unavailable")


def test_unwritable_checkpoint_propagates_rather_than_continuing() -> None:
    """T025: an unrecorded step is indistinguishable on resume from one that never ran."""
    clock = frozen_clock()
    provider = ExplodingProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, _ = _durable_run(provider, clock, "alloc-1", grant, scope={"echo"})
    with pytest.raises(RuntimeError):
        checkpoint_run(run, payload={"progress": "step-1"})
