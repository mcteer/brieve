# SPDX-License-Identifier: Apache-2.0
"""The step boundary notices a stop — and where it notices is the whole semantic.

C3 chose "the current step finishes; no further step begins" over killing the allocation.
That choice is not enforced by a timer or a signal handler: it falls out of *where* the
check sits. After the bracket, before the next intent. A step already begun completes and
records its result; nothing new starts; no intent is left open.

Killing the allocation would be faster and would manufacture precisely the open intent
005's re-observation exists to resolve — on a run that is terminal and will therefore never
resume to resolve it. Permanent, which is the one outcome bracketing exists to prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from core.durability.checkpoint import stop_requested
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob, RunOutcome
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.run import RunState
from core.runs.index import InMemoryRunIndex, RunIndexEntry
from surfaces.api.runs import stop_run_for


def _Run(durability: Any, run_id: str = "run-1") -> Any:
    """The parts of a governed run this check reads, and nothing else.

    Returned as `Any` rather than built as a `GovernedRun`: constructing a real one needs
    a fabric, a registry, and a clock, none of which this check touches — and a fixture
    that assembled them would be asserting about run construction rather than about the
    boundary read.
    """

    return SimpleNamespace(durability=durability, run_id=run_id, correlation_id="corr-1")


def _subject() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id="tenant-a",
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def _index() -> InMemoryRunIndex:
    index = InMemoryRunIndex()
    index.record(
        RunIndexEntry(
            run_id="run-1",
            correlation_id="corr-1",
            subject_user_id="alice",
            tenant_id="tenant-a",
            agent_definition_id="planner-agent",
            created_at=datetime(2026, 7, 28, tzinfo=UTC),
        )
    )
    return index


def _running(durability: Any) -> None:
    durability.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={},
            correlation_id="corr-1",
            grant_id="grant-1",
            step_index=1,
            written_by="allocation-a",
            outcome=None,
        )
    )


def test_a_healthy_run_is_not_asked_to_stop() -> None:
    """The positive control: without it, a check that always reported a stop would pass
    every other row here."""
    durability = InMemoryDurabilityProvider()
    _running(durability)

    assert stop_requested(_Run(durability)) is None


def test_a_stopped_run_is_noticed_with_its_reason() -> None:
    durability = InMemoryDurabilityProvider()
    _running(durability)
    stop_run_for(run_id="run-1", subject=_subject(), index=_index(), durability=durability)

    assert stop_requested(_Run(durability)) == "stopped_by:alice"


def test_a_completed_run_is_not_a_stopped_one() -> None:
    """Only STOPPED ends the loop this way. A run that finished has already stopped
    looping, and reporting it here would make 'stopped' mean 'terminal', which would let a
    completed run's ending be attributed to a person who never asked."""
    durability = InMemoryDurabilityProvider()
    durability.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={},
            correlation_id="corr-1",
            grant_id="grant-1",
            step_index=1,
            written_by="allocation-a",
            outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
        )
    )

    assert stop_requested(_Run(durability)) is None


def test_an_unreadable_record_does_not_end_a_healthy_run() -> None:
    """A database blip must not stop work nobody asked to stop.

    The stop is durable; it will be seen at the next boundary. Failing closed here would
    mean every transient read error ends someone's run, which is a far larger harm than a
    stop taking one extra step to land.
    """

    class Broken:
        def load(self, blob_id: str) -> Any:
            raise RuntimeError("store unreachable")

    assert stop_requested(_Run(Broken())) is None


def test_a_run_with_no_durability_continues() -> None:
    """An in-process run with no store cannot be stopped this way, and must not be
    accidentally stopped by the absence of one."""
    assert stop_requested(_Run(None)) is None
