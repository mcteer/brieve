# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — SC-004 and SC-009a: the trail is the record, and deletion proves it.

ADR-0051's central claim, as a row. A thread holding dispatched, declined, and
scope-refused turns is reconstructed **completely** from the audit trail alone — and then
the thread is deleted and the reconstruction is *unchanged*.

That second half is what makes deletion demonstrably not a masking primitive. If any part
of the reconstruction depended on thread storage, deleting a conversation would quietly
shrink what an investigator can see, and the person who most wants that is exactly the
person with a delete button.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.threads.records import ThreadRecord, TurnDisposition
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn
from surfaces.api.threads import delete_thread_for

TENANT = "tenant-test"


@dataclass
class RecordingDispatcher:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _subject(user: str = "alice") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=TENANT,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


@dataclass
class Reconstructed:
    """What an investigator can rebuild from the trail alone."""

    subject: str
    messages: list[str]
    dispositions: list[str]
    run_ids: list[str]
    deleted: bool


def reconstruct(sink: InMemoryAuditSink, correlation_id: str) -> Reconstructed:
    """Rebuild a thread from its events. **Reads no thread storage** — that is the point.

    Written here rather than in `src` deliberately: it is what an investigator would do
    with the trail, not a product capability. If this needed anything the trail does not
    carry, the row would fail to compile rather than merely fail.
    """
    events = sink.list_by_correlation_id(correlation_id)
    turns = [e for e in events if e.event_type == AuditEventType.TURN_RECORDED]
    deletions = [e for e in events if e.event_type == AuditEventType.THREAD_DELETED]
    subjects = {str(e.payload.get("subject_user_id", "")) for e in turns}
    return Reconstructed(
        subject=subjects.pop() if len(subjects) == 1 else "",
        messages=[str(e.payload["message"]) for e in turns],
        dispositions=[str(e.payload["disposition"]) for e in turns],
        run_ids=[str(e.payload["run_id"]) for e in turns if e.payload.get("run_id")],
        deleted=bool(deletions),
    )


def _populated_thread() -> tuple[InMemoryThreadStore, InMemoryAuditSink, ThreadRecord]:
    """One thread with all three accepted dispositions, in a known order."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread_id = new_thread_id()
    thread = ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id="alice",
        tenant_id=TENANT,
        created_at=datetime.now(UTC),
    )
    store.create_thread(thread)

    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="plan the migration",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
    )
    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="what else can you do?",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id=None,
    )
    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="apply it in production",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=False,
    )
    return store, sink, thread


def test_a_thread_is_reconstructable_from_the_trail_alone() -> None:
    """SC-004: who asked what, in what order, and which runs resulted."""
    store, sink, thread = _populated_thread()

    rebuilt = reconstruct(sink, thread.correlation_id)

    assert rebuilt.subject == "alice"
    assert rebuilt.messages == [
        "plan the migration",
        "what else can you do?",
        "apply it in production",
    ]
    assert rebuilt.dispositions == [
        str(TurnDisposition.DISPATCHED),
        str(TurnDisposition.DECLINED),
        str(TurnDisposition.REFUSED),
    ]
    assert len(rebuilt.run_ids) == 1


def test_the_reconstruction_is_unchanged_after_the_thread_is_deleted() -> None:
    """SC-009a, and ADR-0051's whole argument in one assertion."""
    store, sink, thread = _populated_thread()
    before = reconstruct(sink, thread.correlation_id)

    delete_thread_for(
        subject=_subject(),
        store=store,
        audit_sink=sink,
        thread_id=thread.thread_id,
    )

    after = reconstruct(sink, thread.correlation_id)

    assert store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT) is None
    assert store.turns_of(thread_id=thread.thread_id) == []
    assert after.messages == before.messages
    assert after.dispositions == before.dispositions
    assert after.run_ids == before.run_ids
    assert after.deleted is True, "the deletion itself is not in the trail"


def test_the_declined_message_survives_as_its_only_copy() -> None:
    """The case D4 was written for: an ask that started nothing, after deletion."""
    store, sink, thread = _populated_thread()
    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    rebuilt = reconstruct(sink, thread.correlation_id)

    assert "what else can you do?" in rebuilt.messages


def test_the_deletion_event_names_what_was_removed() -> None:
    """An investigator should not have to infer the size of what went."""
    store, sink, thread = _populated_thread()

    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    deletion = [
        e
        for e in sink.list_by_correlation_id(thread.correlation_id)
        if e.event_type == AuditEventType.THREAD_DELETED
    ][0]
    assert deletion.payload["turn_count"] == 3
    assert len(deletion.payload["run_ids"]) == 1
    assert deletion.payload["subject_user_id"] == "alice"


def test_every_dispatched_run_stays_explainable_after_deletion() -> None:
    """ "Why did this run happen" must survive the conversation that started it."""
    store, sink, thread = _populated_thread()
    rebuilt_before = reconstruct(sink, thread.correlation_id)
    run_id = rebuilt_before.run_ids[0]

    delete_thread_for(subject=_subject(), store=store, audit_sink=sink, thread_id=thread.thread_id)

    rationale = [
        e
        for e in sink.list_by_correlation_id(thread.correlation_id)
        if e.event_type == AuditEventType.TURN_RECORDED and e.payload.get("run_id") == run_id
    ]
    assert len(rationale) == 1
    assert rationale[0].payload["message"] == "plan the migration"
    assert rationale[0].payload["subject_user_id"] == "alice"


def test_deletion_is_refused_for_someone_elses_thread() -> None:
    """The delete button is not a way to remove somebody else's record."""
    from core.runs.refusals import OperationRefused

    store, sink, thread = _populated_thread()

    try:
        delete_thread_for(
            subject=_subject(user="mallory"),
            store=store,
            audit_sink=sink,
            thread_id=thread.thread_id,
        )
    except OperationRefused as refused:
        assert refused.reason_code == "not_permitted"
    else:  # pragma: no cover - the row failed
        raise AssertionError("another subject deleted this thread")

    assert store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT) is not None
