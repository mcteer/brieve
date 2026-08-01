# SPDX-License-Identifier: Apache-2.0
"""Stopping a run — withdrawal, not the pause ADR-0049 removed.

ADR-0049 forbids a run *waiting* on a human. It says nothing about a person ending their
own request, and that is the distinction the whole operation rests on: the state written is
terminal, so nothing waits and no recovering dependency can bring the run back. A stop a
dependency could undo would be a pause wearing another name.

**The resurrection row is the one that matters most**, and it exists because the defect it
catches shipped for three features: `save` was last-write-wins, so a routine checkpoint —
which carries no outcome — wrote NULL over a terminal state, and a stop held only until the
run next checkpointed. The guard is one simplification away from that at all times.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob, RunOutcome
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.run import RunState
from core.runs.index import InMemoryRunIndex, RunIndexEntry
from core.runs.refusals import OperationRefused
from surfaces.api.runs import stop_run_for


def _subject(user: str = "alice", tenant: str = "tenant-a") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def _index(*, subject: str = "alice", tenant: str = "tenant-a") -> InMemoryRunIndex:
    index = InMemoryRunIndex()
    index.record(
        RunIndexEntry(
            run_id="run-1",
            correlation_id="corr-1",
            subject_user_id=subject,
            tenant_id=tenant,
            agent_definition_id="planner-agent",
            created_at=datetime(2026, 7, 28, tzinfo=UTC),
        )
    )
    return index


def _running(durability: Any) -> None:
    """A run mid-flight: a checkpoint with no outcome, which is what one looks like."""
    durability.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={"step": 3},
            correlation_id="corr-1",
            grant_id="grant-1",
            step_index=3,
            written_by="allocation-a",
            outcome=None,
        )
    )


def test_a_stop_reaches_a_terminal_state() -> None:
    durability = InMemoryDurabilityProvider()
    _running(durability)

    response = stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    assert response.state is RunState.STOPPED
    assert response.state.is_terminal()
    assert response.stop_reason == "stopped_by:alice"


def test_the_stop_is_attributable_and_distinguishable_from_a_bound() -> None:
    """FR-012. `stopped_by:<subject>` names a person; an execution bound names a limit.

    An investigator asking "why did this end" gets a different answer for each, which is
    the point — a run someone ended and a run that ran out of time are different events.
    """
    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    blob = durability.load("run-1")
    assert blob is not None and blob.outcome is not None
    assert blob.outcome.stop_reason == "stopped_by:alice"
    assert blob.outcome.stop_reason.startswith("stopped_by:")


def test_a_routine_checkpoint_cannot_resurrect_a_stopped_run() -> None:
    """The row the terminal-once guard exists for.

    The running allocation does not know it has been stopped yet — it is mid-step, and it
    checkpoints as it always does. That write carries no outcome. Before the guard it
    nulled the terminal state and the run continued; the stop held only until this moment.
    """
    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    # The allocation, still unaware, checkpoints its next step.
    durability.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={"step": 4},
            correlation_id="corr-1",
            grant_id="grant-1",
            step_index=4,
            written_by="allocation-a",
            outcome=None,
        )
    )

    blob = durability.load("run-1")
    assert blob is not None and blob.outcome is not None, (
        "a routine checkpoint erased the stop — the run is alive again and nobody asked "
        "for it to be"
    )
    assert blob.outcome.state == RunState.STOPPED.value


def test_the_first_terminal_write_wins() -> None:
    """The stop-versus-finish race, resolved by the guard rather than by luck.

    Both outcomes are legitimate; the record must show one. Which one is arbitrary — that
    it is *one* is not.
    """
    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    # The allocation finishes its step and records completion, unaware of the stop.
    durability.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={"step": 4},
            correlation_id="corr-1",
            grant_id="grant-1",
            step_index=4,
            written_by="allocation-a",
            outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
        )
    )

    blob = durability.load("run-1")
    assert blob is not None and blob.outcome is not None
    assert blob.outcome.state == RunState.STOPPED.value


def test_only_the_starter_may_stop() -> None:
    """Withdrawing consent is available only to whoever gave it."""
    durability = InMemoryDurabilityProvider()
    _running(durability)

    with pytest.raises(OperationRefused) as caught:
        stop_run_for(
            run_id="run-1",
            subject=_subject(user="bob"),
            index=_index(subject="alice"),
            durability=durability,
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "not_permitted"


def test_another_tenant_is_answered_as_absent() -> None:
    durability = InMemoryDurabilityProvider()

    with pytest.raises(OperationRefused) as caught:
        stop_run_for(
            run_id="run-1",
            subject=_subject(tenant="tenant-a"),
            index=_index(tenant="tenant-b"),
            durability=durability,
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "no_such_record"


def test_stopping_twice_reports_the_existing_state() -> None:
    """Asking twice is not an error (FR-011)."""
    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    second = stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    assert second.already_terminal
    assert second.state is RunState.STOPPED
    assert second.stop_reason == "stopped_by:alice"


def test_a_stopped_run_is_invisible_to_the_sweeper() -> None:
    """FR-009, asserted against 009's own predicate rather than a reimplementation.

    Zero new code holds this — `_is_suspended` already refuses any checkpoint carrying a
    terminal outcome. The row exists because the property is load-bearing and currently
    rests on two lines nobody may simplify.
    """
    from core.durability.sweeper import _is_suspended

    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=durability,
        audit=InMemoryAuditSink(),
    )

    assert not _is_suspended(durability.load("run-1"))
