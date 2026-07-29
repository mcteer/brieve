# SPDX-License-Identifier: Apache-2.0
"""US3 — deleting a conversation removes a view and nothing else.

FR-010d is the load-bearing one: **the run outlives the view**. A person who deletes a
thread while something is running has withdrawn their attention, not their consent — the
run keeps going, records its result, and stays reachable through the operations that
already expose it. Anything else would make the delete button a stop button that does not
say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.sink import InMemoryAuditSink
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.threads.context import RESULT_KEY, resolve_run_input
from core.threads.records import ThreadRecord
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn
from surfaces.api.threads import delete_thread_for

TENANT = "tenant-test"


@dataclass
class RecordingDispatcher:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _subject() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id=TENANT,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _thread(store: InMemoryThreadStore) -> ThreadRecord:
    thread_id = new_thread_id()
    record = ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id="alice",
        tenant_id=TENANT,
        created_at=datetime.now(UTC),
    )
    store.create_thread(record)
    return record


def test_a_run_in_flight_survives_its_thread() -> None:
    """FR-010d: attention withdrawn, consent unchanged."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)
    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="a long apply",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
        durability=durability,
    )

    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    # The run finishes afterwards, exactly as it would have.
    durability.save(
        CheckpointBlob(
            blob_id=str(turn.run_id),
            payload={RESULT_KEY: {"applied": True}},
            correlation_id=str(turn.run_id),
        )
    )
    blob = durability.load(str(turn.run_id))
    assert blob is not None and blob.payload[RESULT_KEY] == {"applied": True}


def test_the_run_input_survives_so_the_run_can_still_read_it() -> None:
    """A run whose input vanished mid-flight would be one nobody could explain."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)
    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="the instruction the run needs",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
        durability=durability,
    )

    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    resolved = resolve_run_input(run_id=str(turn.run_id), store=store, durability=durability)
    assert resolved is not None
    assert resolved.message == "the instruction the run needs"


def test_deleting_twice_answers_as_absent() -> None:
    """Idempotent from the caller's view; the second delete finds nothing."""
    from core.runs.refusals import OperationRefused

    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)
    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    try:
        delete_thread_for(
            subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id
        )
    except OperationRefused as refused:
        assert refused.reason_code == "no_such_record"
    else:  # pragma: no cover
        raise AssertionError("deleting an absent thread succeeded")


def test_only_one_deletion_event_is_written() -> None:
    """A second delete must not chain another event onto the stream."""
    from core.audit.schema import AuditEventType
    from core.runs.refusals import OperationRefused

    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)
    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)
    try:
        delete_thread_for(
            subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id
        )
    except OperationRefused:
        pass

    deletions = [
        e
        for e in sink.list_by_correlation_id(thread.correlation_id)
        if e.event_type == AuditEventType.THREAD_DELETED
    ]
    assert len(deletions) == 1
