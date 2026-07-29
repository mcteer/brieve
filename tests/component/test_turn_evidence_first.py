# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the trail records a turn before the turn does anything.

This is the row ADR-0051 exists for. Two properties, and the second is the one that is
easy to lose:

1. Every **accepted** turn — dispatched, declined, or scope-refused — has a
   `TURN_RECORDED` event carrying the message verbatim, written before dispatch and before
   the turn row. A declined ask is still an ask, and after its thread is deleted this event
   is the only copy of it.
2. Every **pre-acceptance** refusal has a `TURN_REFUSED` event carrying the message's
   *size* and never its content. Recording the content would make an append-only store
   growable at whatever rate a caller can be refused; recording nothing would make
   flooding invisible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.refusals import OperationRefused
from core.threads.records import MAX_MESSAGE_BYTES, RATE_LIMIT_ACTS, ThreadRecord, TurnDisposition
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn

TENANT = "tenant-test"


@dataclass
class RecordingDispatcher:
    """Counts dispatches so a row can assert that none happened."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@dataclass
class ExplodingDispatcher:
    """Dispatch fails after the evidence is written — the crash the ordering survives."""

    def dispatch(self, **kwargs: Any) -> None:
        raise RuntimeError("scheduler unreachable")


def _subject(user: str = "alice", tenant: str = TENANT) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _thread(store: InMemoryThreadStore, *, subject: str = "alice") -> ThreadRecord:
    thread_id = new_thread_id()
    thread = ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id=subject,
        tenant_id=TENANT,
        created_at=datetime.now(UTC),
    )
    store.create_thread(thread)
    return thread


def _events(sink: InMemoryAuditSink, thread: ThreadRecord) -> list[Any]:
    return sink.list_by_correlation_id(thread.correlation_id)


@pytest.mark.parametrize(
    ("agent", "startable", "expected"),
    [
        ("planner-agent", True, TurnDisposition.DISPATCHED),
        (None, None, TurnDisposition.DECLINED),
        ("planner-agent", False, TurnDisposition.REFUSED),
    ],
)
def test_every_accepted_disposition_is_recorded_with_the_message(
    agent: str | None, startable: bool | None, expected: TurnDisposition
) -> None:
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="please plan the migration",
        store=store,
        audit_sink=sink,
        dispatcher=RecordingDispatcher(),
        agent_definition_id=agent,
        startable=startable,
    )

    assert turn.disposition is expected
    recorded = [e for e in _events(sink, thread) if e.event_type == AuditEventType.TURN_RECORDED]
    assert len(recorded) == 1
    assert recorded[0].payload["message"] == "please plan the migration"
    assert recorded[0].payload["disposition"] == str(expected)


def test_the_event_precedes_the_dispatch() -> None:
    """The ordering, proven by a dispatch that fails.

    If the evidence were written after dispatch, this crash would leave a run started with
    no record of why. Because it is written first, the trail explains a run the view never
    got to record — which is the direction this design permits.
    """
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    with pytest.raises(RuntimeError):
        accept_turn(
            subject=_subject(),
            thread_id=thread.thread_id,
            message="do the thing",
            store=store,
            audit_sink=sink,
            dispatcher=ExplodingDispatcher(),
            agent_definition_id="planner-agent",
            startable=True,
        )

    recorded = [e for e in _events(sink, thread) if e.event_type == AuditEventType.TURN_RECORDED]
    assert len(recorded) == 1, "the message was not recorded before the dispatch was attempted"
    assert recorded[0].payload["message"] == "do the thing"
    assert store.turns_of(thread_id=thread.thread_id) == []


def test_the_declined_event_survives_its_thread() -> None:
    """D4's whole point: the asks that started nothing are the ones an investigator wants."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="something the platform cannot do",
        store=store,
        audit_sink=sink,
        agent_definition_id=None,
    )
    store.delete_thread(thread_id=thread.thread_id, tenant_id=TENANT)

    recorded = [e for e in _events(sink, thread) if e.event_type == AuditEventType.TURN_RECORDED]
    assert recorded[0].payload["message"] == "something the platform cannot do"
    assert recorded[0].payload["reason"] == "nothing_to_dispatch"


def test_an_oversized_message_is_refused_and_its_content_is_not_recorded() -> None:
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)
    secret = "s3cr3t-" * 2000  # comfortably over the bound

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(),
            thread_id=thread.thread_id,
            message=secret,
            store=store,
            audit_sink=sink,
        )
    assert refused.value.reason_code == "message_too_large"

    events = _events(sink, thread)
    assert [e.event_type for e in events] == [AuditEventType.TURN_REFUSED]
    payload = events[0].payload
    assert payload["message_bytes"] == len(secret.encode())
    assert "message" not in payload
    assert "s3cr3t" not in str(payload), "the refusal record carried the content it must not"
    assert store.turns_of(thread_id=thread.thread_id) == []


def test_a_rate_limited_message_is_refused_and_its_content_is_not_recorded() -> None:
    """The flood this split exists to bound: refusals must not grow the trail by content."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)
    for _ in range(RATE_LIMIT_ACTS):
        _thread(store)  # creations count, which is the pass-4 finding

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(),
            thread_id=thread.thread_id,
            message="a message nobody should have to store",
            store=store,
            audit_sink=sink,
            dispatcher=RecordingDispatcher(),
            agent_definition_id="planner-agent",
            startable=True,
        )
    assert refused.value.reason_code == "rate_limited"

    refusals = [e for e in _events(sink, thread) if e.event_type == AuditEventType.TURN_REFUSED]
    assert len(refusals) == 1
    assert refusals[0].payload["reason"] == "rate_limited"
    assert "message" not in refusals[0].payload
    assert "nobody should have to store" not in str(refusals[0].payload)


def test_a_message_at_the_bound_is_accepted() -> None:
    """The boundary itself, so the refusal is off-by-nothing."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="x" * MAX_MESSAGE_BYTES,
        store=store,
        audit_sink=sink,
        agent_definition_id=None,
    )

    assert turn.disposition is TurnDisposition.DECLINED
    assert len(_events(sink, thread)) == 1


def test_the_context_bound_is_recorded_on_the_event() -> None:
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="first",
        store=store,
        audit_sink=sink,
        agent_definition_id=None,
    )

    recorded = [e for e in _events(sink, thread) if e.event_type == AuditEventType.TURN_RECORDED]
    assert recorded[0].payload["context_run_ids"] == []
    assert recorded[0].payload["context_dropped"] == []
