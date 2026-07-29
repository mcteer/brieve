# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a thread never becomes a standing grant.

FR-008, and the specific way a conversational surface fails: turn one succeeds, the
person's roles narrow, and turn two rides the first turn's authority because "we already
checked". A thread that did that would be a durable, subject-owned record of permission —
which is the standing credential this platform has no other example of.

Every turn is authorized on its own terms. The rows below narrow authority *between*
turns and assert the second turn is refused, and that nothing consults the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.threads.records import ThreadRecord, TurnDisposition
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn

TENANT = "tenant-test"


@dataclass
class RecordingDispatcher:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _subject(*roles: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id=TENANT,
        roles=frozenset(roles),
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


def test_narrowed_authority_refuses_the_next_turn() -> None:
    """The scenario US2 names: same thread, same person, less authority."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    first = accept_turn(
        subject=_subject("operator"),
        thread_id=thread.thread_id,
        message="apply the change",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=True,
    )
    assert first.disposition is TurnDisposition.DISPATCHED

    # The person's roles narrow. Nothing about the thread changes.
    second = accept_turn(
        subject=_subject("reader"),
        thread_id=thread.thread_id,
        message="apply another change",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=False,
    )

    assert second.disposition is TurnDisposition.REFUSED
    assert second.reason == "not_permitted"
    assert second.run_id is None
    assert len(dispatcher.calls) == 1, "the second turn dispatched on the first's authority"


def test_the_dispatch_carries_the_current_roles_not_the_earlier_ones() -> None:
    """Even when both turns succeed, the second must be authorized as it is now."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    accept_turn(
        subject=_subject("operator", "admin"),
        thread_id=thread.thread_id,
        message="first",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
    )
    accept_turn(
        subject=_subject("operator"),
        thread_id=thread.thread_id,
        message="second",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
    )

    assert dispatcher.calls[0]["subject_roles"] == frozenset({"operator", "admin"})
    assert dispatcher.calls[1]["subject_roles"] == frozenset({"operator"})


def test_widened_authority_is_also_honoured() -> None:
    """The other direction, so the row is about freshness rather than about narrowing.

    A thread that cached the first turn's refusal would be as wrong as one that cached its
    permission — and it would be the more annoying failure, because the person would have
    been granted access and still be told no.
    """
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    refused = accept_turn(
        subject=_subject("reader"),
        thread_id=thread.thread_id,
        message="apply it",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=False,
    )
    allowed = accept_turn(
        subject=_subject("operator"),
        thread_id=thread.thread_id,
        message="apply it now",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="applier",
        startable=True,
    )

    assert refused.disposition is TurnDisposition.REFUSED
    assert allowed.disposition is TurnDisposition.DISPATCHED


def test_nothing_on_a_turn_record_carries_authority() -> None:
    """Structural: a thread stores results and dispositions, never grants.

    ADR-0042's rule — cached or precedent results never carry authority — applied to the
    record that would be the easiest place to break it.
    """
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject("operator"),
        thread_id=thread.thread_id,
        message="plan it",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner",
        startable=True,
    )

    stored = vars(turn)
    forbidden = {"roles", "grant_id", "credential_id", "token", "scope", "authority"}
    assert not (forbidden & set(stored)), (
        f"a turn record carries something authority-shaped: {forbidden & set(stored)}"
    )
