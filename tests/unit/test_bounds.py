# SPDX-License-Identifier: Apache-2.0
"""US6 — a run cannot consume authority indefinitely (T057-T062)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from tests.component.conftest import CountingHandler, make_run
from tests.harness import durability_grant, frozen_clock
from tests.harness.frozen_clock import FrozenClock

from core.bounds import BoundsTracker, ExecutionBoundExceeded, ExecutionBounds
from core.durability.checkpoint import stop_run
from core.durability.lease import RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.run import RunState
from core.tools.invoke import invoke_tool


def _tracker(clock: FrozenClock, **kw: Any) -> BoundsTracker:
    return BoundsTracker(bounds=ExecutionBounds(**kw), started_at=clock.now())


def test_max_duration_stops_the_run_with_the_reason() -> None:
    clock = frozen_clock()
    tracker = _tracker(clock, max_duration=timedelta(minutes=30))
    clock.advance(timedelta(minutes=31))

    with pytest.raises(ExecutionBoundExceeded) as excinfo:
        tracker.check(clock)
    assert excinfo.value.reason == "max_duration"


def test_step_limit_stops_the_run_with_the_reason() -> None:
    clock = frozen_clock()
    tracker = _tracker(clock, max_steps=3)
    for _ in range(3):
        tracker.record_progress(clock.now())

    with pytest.raises(ExecutionBoundExceeded) as excinfo:
        tracker.check(clock)
    assert excinfo.value.reason == "max_steps"


def test_stuck_wait_watchdog_stops_the_run_with_the_reason() -> None:
    clock = frozen_clock()
    tracker = _tracker(clock, stuck_wait_timeout=timedelta(minutes=10))
    tracker.record_progress(clock.now())
    clock.advance(timedelta(minutes=11))

    with pytest.raises(ExecutionBoundExceeded) as excinfo:
        tracker.check(clock)
    assert excinfo.value.reason == "stuck_wait"


def test_progress_resets_the_watchdog_but_not_the_duration() -> None:
    """A run that keeps working is not stuck; it can still outlive its duration."""
    clock = frozen_clock()
    tracker = _tracker(
        clock, max_duration=timedelta(hours=1), stuck_wait_timeout=timedelta(minutes=10)
    )
    for _ in range(5):
        clock.advance(timedelta(minutes=9))
        tracker.record_progress(clock.now())
        tracker.check(clock)

    clock.advance(timedelta(minutes=20))
    with pytest.raises(ExecutionBoundExceeded) as excinfo:
        tracker.check(clock)
    assert excinfo.value.reason == "max_duration"


def test_bounded_run_performs_no_further_steps() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})
    handler = CountingHandler()

    run, _, _ = make_run(scope={"echo"}, handler=handler)
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    run.lease = RunLease(provider, run_id="run-1", holder_identity="alloc-1")
    run.lease.acquire()
    run.bounds = _tracker(clock, max_steps=1)

    assert invoke_tool(run, "echo").allowed
    executions = handler.call_count

    with pytest.raises(ExecutionBoundExceeded):
        invoke_tool(run, "echo")
    assert handler.call_count == executions, "the bound stopped it before the body ran"


def test_stopping_records_the_reason_as_data() -> None:
    """SC-007: 'with the reason recorded' must be satisfiable by a query, not a log."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, _ = make_run(scope={"echo"})
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant

    stop_run(run, reason="max_steps")

    assert run.state is RunState.STOPPED
    assert run.stop_reason == "max_steps"
    blob = provider.load("run-1")
    assert blob is not None and blob.outcome is not None
    assert blob.outcome.state == RunState.STOPPED.value
    assert blob.outcome.stop_reason == "max_steps"


def test_bounds_are_checked_in_the_invoke_path_not_a_timer() -> None:
    """A bound enforced by a separate timer fails silently when the timer does."""
    import inspect

    from core.tools import invoke as invoke_module

    source = inspect.getsource(invoke_module)
    assert "run.bounds.check" in source
    for forbidden in ("threading.Timer", "asyncio.create_task", "Thread("):
        assert forbidden not in source
