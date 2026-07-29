# SPDX-License-Identifier: Apache-2.0
"""US2 — a second turn knows about the first, under a bound the person can see.

This is the difference between a conversation and a sequence of independent submissions,
and the reason threads exist. Three properties, each with its own failure mode:

- what carries forward is **verbatim**, because summarizing is an ADR-0039 role this
  feature deliberately does not acquire;
- the bound is **stated**, not emergent, so it cannot change silently when something
  downstream does;
- what falls outside it is **visible**, because a person who does not know the platform
  forgot something reads a worse answer as a worse platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.sink import InMemoryAuditSink
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.threads.context import RESULT_KEY, resolve_run_input, serialize_result
from core.threads.records import CONTEXT_TURNS, ThreadRecord, TurnDisposition
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn

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


def _finish(durability: InMemoryDurabilityProvider, run_id: str, result: Any) -> None:
    durability.save(
        CheckpointBlob(
            blob_id=run_id,
            payload={RESULT_KEY: result},
            correlation_id=run_id,
            step_index=0,
            written_by="test",
        )
    )


def _send(
    store: InMemoryThreadStore,
    sink: InMemoryAuditSink,
    thread: ThreadRecord,
    durability: InMemoryDurabilityProvider,
    dispatcher: RecordingDispatcher,
    message: str,
) -> Any:
    return accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message=message,
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
        durability=durability,
    )


def test_the_second_turn_receives_the_first_turns_result() -> None:
    """US2's core scenario, from the turn's decision through to what the run reads."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)

    first = _send(store, sink, thread, durability, dispatcher, "plan the migration")
    result = {"plan": ["survey", "apply"], "risk": "low"}
    _finish(durability, str(first.run_id), result)

    second = _send(store, sink, thread, durability, dispatcher, "now do step one")

    assert second.context_run_ids == (first.run_id,)
    resolved = resolve_run_input(run_id=str(second.run_id), store=store, durability=durability)
    assert resolved is not None
    assert resolved.message == "now do step one"
    assert resolved.context == ((first.run_id, serialize_result(result)),)


def test_a_run_that_has_not_finished_is_not_carried() -> None:
    """Nothing to carry: a running turn has no result yet."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)

    _send(store, sink, thread, durability, dispatcher, "still working")
    second = _send(store, sink, thread, durability, dispatcher, "and another")

    assert second.context_run_ids == ()
    assert second.context_dropped == ()


def test_declined_and_refused_turns_never_enter_context() -> None:
    """They have no run, so there is nothing of theirs to carry."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)

    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="nothing to dispatch",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id=None,
        durability=durability,
    )
    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="not permitted",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=False,
        durability=durability,
    )

    third = _send(store, sink, thread, durability, dispatcher, "now something real")
    assert third.context_run_ids == ()


def test_the_bound_carries_the_newest_and_drops_the_oldest_visibly() -> None:
    """SC-002a: exactly the stated amount, and the person can tell what was left out."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)

    finished: list[str] = []
    for i in range(CONTEXT_TURNS + 1):
        turn = _send(store, sink, thread, durability, dispatcher, f"turn {i}")
        _finish(durability, str(turn.run_id), {"index": i})
        finished.append(str(turn.run_id))

    latest = _send(store, sink, thread, durability, dispatcher, "one more")

    assert len(latest.context_run_ids) == CONTEXT_TURNS
    # Newest first: the most recent CONTEXT_TURNS runs, and the oldest visibly dropped.
    assert list(latest.context_run_ids) == list(reversed(finished))[:CONTEXT_TURNS]
    assert latest.context_dropped == (finished[0],)


def test_the_dropped_set_is_recorded_on_the_turn_and_in_its_event() -> None:
    """Inspectable after the fact, not merely rendered once."""
    from core.audit.schema import AuditEventType

    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)
    for i in range(CONTEXT_TURNS + 1):
        turn = _send(store, sink, thread, durability, dispatcher, f"turn {i}")
        _finish(durability, str(turn.run_id), {"index": i})

    latest = _send(store, sink, thread, durability, dispatcher, "one more")

    events = [
        e
        for e in sink.list_by_correlation_id(thread.correlation_id)
        if e.event_type == AuditEventType.TURN_RECORDED
    ]
    assert events[-1].payload["context_dropped"] == list(latest.context_dropped)
    assert events[-1].payload["context_run_ids"] == list(latest.context_run_ids)


def test_context_is_never_summarized() -> None:
    """FR-009: verbatim, because summarizing needs a model binding this feature lacks.

    Asserted on bytes rather than on intent — a summarizer would produce something
    *shorter*, and the comparison to the stored serialization catches any transformation
    at all, including one nobody described as summarizing.
    """
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)

    first = _send(store, sink, thread, durability, dispatcher, "plan it")
    verbose = {"steps": [f"step {i} with a long description" for i in range(40)]}
    _finish(durability, str(first.run_id), verbose)

    second = _send(store, sink, thread, durability, dispatcher, "continue")
    resolved = resolve_run_input(run_id=str(second.run_id), store=store, durability=durability)

    assert resolved is not None
    carried = resolved.context[0][1]
    assert carried == serialize_result(verbose)
    assert len(carried) == len(serialize_result(verbose))


def test_the_turn_records_what_it_carried_even_for_a_declined_turn() -> None:
    """A decline still had context computed for it, and the record says so."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    durability, dispatcher = InMemoryDurabilityProvider(), RecordingDispatcher()
    thread = _thread(store)
    first = _send(store, sink, thread, durability, dispatcher, "plan it")
    _finish(durability, str(first.run_id), {"ok": True})

    declined = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="never mind",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id=None,
        durability=durability,
    )

    assert declined.disposition is TurnDisposition.DECLINED
    assert declined.context_run_ids == (first.run_id,)
