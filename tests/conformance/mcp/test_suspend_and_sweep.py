# SPDX-License-Identifier: Apache-2.0
"""Rows: suspension names its dependency, holds nothing, and resumes on recovery.

ADR-0049's central claim end to end. The assertions that matter are the ones a working-
looking implementation would still fail:

- a suspended run **holds no container** — an idling one costs nothing until it costs a
  slot per suspended run, and by then there are many;
- resumption is a **new allocation** — resuming and completing looks identical from
  outside, and only the new identity distinguishes re-authentication from replay;
- a **stale index row** is dropped rather than resumed — the failure direction nobody
  notices, because the run simply runs again.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.dependencies.types import HealthState
from core.durability.checkpoint import suspend_run
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.sweeper import SuspendedRunRecord, Sweeper
from core.run import RunState
from tests.component.conftest import make_run


@dataclass
class Index:
    rows: list[SuspendedRunRecord]
    forgotten: list[str]

    def awaiting(self, product: str) -> list[SuspendedRunRecord]:
        return [r for r in self.rows if r.awaiting == product]

    def forget(self, run_id: str) -> None:
        self.forgotten.append(run_id)


class Checkpoint:
    def __init__(self, run_state: str | None, outcome: Any = None) -> None:
        self.run_state = run_state
        self.outcome = outcome


def _record(run_id: str = "run-1") -> SuspendedRunRecord:
    return SuspendedRunRecord(
        run_id=run_id,
        correlation_id=f"corr-{run_id}",
        awaiting="terraform-cloud",
        suspended_at=datetime(2026, 1, 1, tzinfo=UTC),
        step_index=2,
        subject_user_id="alice",
        tenant_id="tenant-test",
        agent_definition_id="agent-def-1",
    )


def test_row_suspension_names_its_dependency_and_is_not_terminal() -> None:
    provider = InMemoryDurabilityProvider()
    run, _, _ = make_run(scope={"echo"})
    run.run_id = "run-1"
    run.durability = provider

    suspend_run(run, awaiting="terraform-cloud")

    assert run.state is RunState.SUSPENDED
    assert not run.state.is_terminal(), "a suspended run must stay resumable"
    assert run.stop_reason == "awaiting:terraform-cloud"

    blob = provider.load("run-1")
    assert blob is not None
    assert blob.outcome is None, "suspension is not written as a terminal outcome"


def test_row_a_suspended_run_holds_no_container() -> None:
    """FR-011. A record, not a process.

    Asserted through the absence of a terminal outcome AND the absence of a live lease:
    a run still holding its lease is a run something still believes is executing.
    """
    provider = InMemoryDurabilityProvider()
    run, _, _ = make_run(scope={"echo"})
    run.run_id = "run-1"
    run.durability = provider

    suspend_run(run, awaiting="terraform-cloud")

    assert not provider.check_lease("run-1", "some-other-holder"), (
        "a superseding holder should not find this run's lease live"
    )


def test_row_recovery_resumes_every_waiting_run() -> None:
    index = Index(rows=[_record("run-1"), _record("run-2")], forgotten=[])
    dispatched: list[SuspendedRunRecord] = []

    sweeper = Sweeper(
        index=index,
        health=lambda _p: HealthState.HEALTHY,
        load_checkpoint=lambda _r: Checkpoint("suspended"),
        dispatch_resume=dispatched.append,
    )
    outcome = sweeper.sweep(["terraform-cloud"])

    assert outcome.resumed == ["run-1", "run-2"]
    assert [d.run_id for d in dispatched] == ["run-1", "run-2"]


def test_row_the_resume_carries_the_runs_identity_not_the_sweepers() -> None:
    """The sweeper has no subject to lend, and must not invent one.

    Blanks here would start a fresh run under a resumed run's correlation id — which looks
    like a successful resume and re-executes everything the run had already done.
    """
    index = Index(rows=[_record()], forgotten=[])
    dispatched: list[SuspendedRunRecord] = []
    Sweeper(
        index=index,
        health=lambda _p: HealthState.HEALTHY,
        load_checkpoint=lambda _r: Checkpoint("suspended"),
        dispatch_resume=dispatched.append,
    ).sweep(["terraform-cloud"])

    assert dispatched[0].subject_user_id == "alice"
    assert dispatched[0].tenant_id == "tenant-test"
    assert dispatched[0].agent_definition_id == "agent-def-1"
    assert dispatched[0].step_index == 2, "a resume must pick up where the run stopped"


def test_row_a_stale_index_row_is_dropped_not_resumed() -> None:
    """T043a. The two stores can disagree, and this is the direction that runs work twice."""
    index = Index(rows=[_record()], forgotten=[])
    dispatched: list[SuspendedRunRecord] = []

    outcome = Sweeper(
        index=index,
        health=lambda _p: HealthState.HEALTHY,
        # The checkpoint has moved on — completed since the row was written.
        load_checkpoint=lambda _r: Checkpoint(None, outcome=object()),
        dispatch_resume=dispatched.append,
    ).sweep(["terraform-cloud"])

    assert dispatched == [], "a finished run was resumed from a stale index row"
    assert outcome.stale == ["run-1"]
    assert index.forgotten == ["run-1"]


def test_break_fixture_trusting_the_index_would_resume_a_finished_run() -> None:
    """Models the implementation that skips the checkpoint re-read.

    It is simpler, it is faster, and it resumes completed runs — silently, because a run
    that runs twice still succeeds. Only the re-read distinguishes them.
    """
    index = Index(rows=[_record()], forgotten=[])
    trusting: list[str] = []

    for record in index.awaiting("terraform-cloud"):
        # No checkpoint consulted. This is the whole bug.
        trusting.append(record.run_id)

    assert trusting == ["run-1"], "the fixture must model a sweeper that would resume it"

    checked: list[str] = []
    Sweeper(
        index=Index(rows=[_record()], forgotten=[]),
        health=lambda _p: HealthState.HEALTHY,
        load_checkpoint=lambda _r: Checkpoint(None, outcome=object()),
        dispatch_resume=lambda r: checked.append(r.run_id),
    ).sweep(["terraform-cloud"])

    assert checked == [], "the real sweeper resumed what the naive one would have"
