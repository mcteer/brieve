# SPDX-License-Identifier: Apache-2.0
"""The sweeper's logic: resume on recovery, and never resume a run that has moved on.

The store has its own tests. These are about the decisions — which is where the failures
are silent, because a sweeper that resumes too much simply runs work twice and a sweeper
that resumes too little looks exactly like a hang.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.dependencies.types import HealthState
from core.durability.sweeper import SuspendedRunRecord, Sweeper


@dataclass
class FakeIndex:
    rows: dict[str, list[SuspendedRunRecord]]
    forgotten: list[str]

    def awaiting(self, product: str) -> list[SuspendedRunRecord]:
        return list(self.rows.get(product, ()))

    def forget(self, run_id: str) -> None:
        self.forgotten.append(run_id)


class FakeCheckpoint:
    def __init__(self, run_state: str | None = "suspended", outcome: Any = None) -> None:
        self.run_state = run_state
        self.outcome = outcome


def _record(run_id: str, product: str = "terraform-cloud") -> SuspendedRunRecord:
    return SuspendedRunRecord(
        run_id=run_id,
        correlation_id=f"corr-{run_id}",
        awaiting=product,
        suspended_at=datetime(2026, 1, 1, tzinfo=UTC),
        step_index=3,
    )


def _sweeper(
    rows: dict[str, list[SuspendedRunRecord]],
    *,
    health: HealthState = HealthState.HEALTHY,
    checkpoints: dict[str, Any] | None = None,
    dispatch_error: Exception | None = None,
) -> tuple[Sweeper, FakeIndex, list[str]]:
    index = FakeIndex(rows=rows, forgotten=[])
    dispatched: list[str] = []

    def _dispatch(record: SuspendedRunRecord) -> None:
        if dispatch_error is not None:
            raise dispatch_error
        dispatched.append(record.run_id)

    sweeper = Sweeper(
        index=index,
        health=lambda _p: health,
        load_checkpoint=lambda run_id: (checkpoints or {}).get(run_id, FakeCheckpoint()),
        dispatch_resume=_dispatch,
    )
    return sweeper, index, dispatched


def test_one_sweep_resumes_every_run_waiting_on_that_product() -> None:
    """Recovery is platform-level, so the response is. No run polls for itself."""
    rows = {"terraform-cloud": [_record("run-1"), _record("run-2"), _record("run-3")]}
    sweeper, index, dispatched = _sweeper(rows)

    outcome = sweeper.sweep(["terraform-cloud"])

    assert dispatched == ["run-1", "run-2", "run-3"]
    assert outcome.resumed == ["run-1", "run-2", "run-3"]
    assert index.forgotten == ["run-1", "run-2", "run-3"]


def test_an_unhealthy_product_is_not_swept() -> None:
    """The health checker owns that judgement; a second opinion here would drift from it."""
    rows = {"terraform-cloud": [_record("run-1")]}
    sweeper, _, dispatched = _sweeper(rows, health=HealthState.UNHEALTHY)

    assert sweeper.sweep(["terraform-cloud"]).resumed == []
    assert dispatched == []


def test_a_run_whose_checkpoint_completed_is_dropped_not_resumed() -> None:
    """The failure direction nobody notices — the run simply runs again."""
    rows = {"terraform-cloud": [_record("run-1")]}
    sweeper, index, dispatched = _sweeper(
        rows, checkpoints={"run-1": FakeCheckpoint(outcome=object())}
    )

    outcome = sweeper.sweep(["terraform-cloud"])

    assert dispatched == [], "a finished run was resumed"
    assert outcome.stale == ["run-1"]
    assert index.forgotten == ["run-1"]


def test_a_missing_checkpoint_is_dropped_rather_than_retried_forever() -> None:
    rows = {"terraform-cloud": [_record("run-1")]}
    sweeper, index, dispatched = _sweeper(rows, checkpoints={"run-1": None})

    outcome = sweeper.sweep(["terraform-cloud"])

    assert dispatched == []
    assert outcome.stale == ["run-1"]
    assert index.forgotten == ["run-1"]


def test_a_failed_dispatch_keeps_the_run_in_the_index() -> None:
    """Forgetting first would lose the run, and a lost suspended run IS a hang."""
    rows = {"terraform-cloud": [_record("run-1")]}
    sweeper, index, _ = _sweeper(rows, dispatch_error=RuntimeError("scheduler down"))

    outcome = sweeper.sweep(["terraform-cloud"])

    assert outcome.resumed == []
    assert index.forgotten == [], "a run was dropped without being resumed"
    assert outcome.failed and "scheduler down" in outcome.failed[0][1]


def test_one_failure_does_not_strand_the_others() -> None:
    rows = {"terraform-cloud": [_record("run-1"), _record("run-2")]}
    index = FakeIndex(rows=rows, forgotten=[])
    dispatched: list[str] = []

    def _dispatch(record: SuspendedRunRecord) -> None:
        if record.run_id == "run-1":
            raise RuntimeError("transient")
        dispatched.append(record.run_id)

    sweeper = Sweeper(
        index=index,
        health=lambda _p: HealthState.HEALTHY,
        load_checkpoint=lambda _r: FakeCheckpoint(),
        dispatch_resume=_dispatch,
    )
    outcome = sweeper.sweep(["terraform-cloud"])

    assert dispatched == ["run-2"]
    assert outcome.resumed == ["run-2"]
    assert len(outcome.failed) == 1


def test_failures_are_reported_rather_than_swallowed() -> None:
    """A sweep that silently skipped rows would look identical to a clean one."""
    rows = {"terraform-cloud": [_record("run-1")]}
    sweeper, _, _ = _sweeper(rows, dispatch_error=RuntimeError("boom"))

    outcome = sweeper.sweep(["terraform-cloud"])
    assert outcome.acted == 0
    assert outcome.failed, "a failure left no record for an operator to see"
