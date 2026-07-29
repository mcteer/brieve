# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — every way a turn can fail to dispatch, and none of them dispatches.

FR-017a's direction: a surface that dispatches on ambiguity is worse than one that
declines on clarity. Each row below is a different reason the platform might not act, and
the assertion is always the same one — **zero runs started** — because that is the
property a person is trusting when they type into a box.

The decline/refusal distinction is the second half. `nothing_to_dispatch` says the platform
cannot do this; `not_permitted` says this person may not. Conflating them tells someone
their access is fine when it is not, and tells another it is broken when they simply have
no access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.refusals import OperationRefused
from core.threads.records import RATE_LIMIT_ACTS, ThreadRecord, TurnDisposition
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import TurnStorageUnavailable, accept_turn

TENANT = "tenant-test"
OTHER_TENANT = "tenant-other"


@dataclass
class RecordingDispatcher:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


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


def test_no_agent_selected_declines_and_starts_nothing() -> None:
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="what can you do?",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id=None,
    )

    assert turn.disposition is TurnDisposition.DECLINED
    assert turn.reason == "nothing_to_dispatch"
    assert turn.run_id is None
    assert dispatcher.calls == []


def test_a_non_startable_agent_refuses_on_scope_and_starts_nothing() -> None:
    """A different answer from the decline above, deliberately."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="apply the change",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="apply-agent",
        startable=False,
    )

    assert turn.disposition is TurnDisposition.REFUSED
    assert turn.reason == "not_permitted"
    assert turn.run_id is None
    assert dispatcher.calls == []


def test_an_unresolvable_scope_fails_closed() -> None:
    """`startable=None` means the platform could not establish scope.

    Unresolved is not permitted. The alternative — treating "I could not tell" as "yes" —
    is the fail-open that every principle in this repository exists to prevent.
    """
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="apply the change",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="apply-agent",
        startable=None,
    )

    assert turn.disposition is TurnDisposition.REFUSED
    assert dispatcher.calls == []


def test_the_rate_window_refuses_and_starts_nothing() -> None:
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)
    for _ in range(RATE_LIMIT_ACTS):
        _thread(store)

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(),
            thread_id=thread.thread_id,
            message="one too many",
            store=store,
            audit_sink=sink,
            dispatcher=dispatcher,
            agent_definition_id="planner-agent",
            startable=True,
        )

    assert refused.value.reason_code == "rate_limited"
    assert dispatcher.calls == []


def test_an_assembly_without_a_sink_refuses_rather_than_dispatching() -> None:
    """Evidence-first means no sink, no turn.

    A typed refusal rather than a 500: an outage-shaped answer to a misassembly sends
    whoever investigates to the wrong failure entirely.
    """
    store, dispatcher = InMemoryThreadStore(), RecordingDispatcher()
    thread = _thread(store)

    with pytest.raises(TurnStorageUnavailable):
        accept_turn(
            subject=_subject(),
            thread_id=thread.thread_id,
            message="do the thing",
            store=store,
            audit_sink=None,
            dispatcher=dispatcher,
            agent_definition_id="planner-agent",
            startable=True,
        )

    assert dispatcher.calls == []


def test_another_tenants_thread_is_answered_as_absent() -> None:
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(tenant=OTHER_TENANT),
            thread_id=thread.thread_id,
            message="do the thing",
            store=store,
            audit_sink=sink,
            dispatcher=dispatcher,
            agent_definition_id="planner-agent",
            startable=True,
        )

    assert refused.value.reason_code == "no_such_record"
    assert refused.value.is_visible_to_caller is False
    assert dispatcher.calls == []


def test_someone_elses_thread_in_the_same_tenant_is_refused_with_a_reason() -> None:
    """Visible, because the caller can already see the thread exists."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store, subject="bob")

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(user="alice"),
            thread_id=thread.thread_id,
            message="do the thing",
            store=store,
            audit_sink=sink,
            dispatcher=dispatcher,
            agent_definition_id="planner-agent",
            startable=True,
        )

    assert refused.value.reason_code == "not_permitted"
    assert refused.value.is_visible_to_caller is True
    assert dispatcher.calls == []


def test_a_dispatched_turn_records_its_input_before_dispatching() -> None:
    """The input row must exist by the time the run could read it."""
    store, sink, dispatcher = InMemoryThreadStore(), InMemoryAuditSink(), RecordingDispatcher()
    thread = _thread(store)

    turn = accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="plan the migration",
        store=store,
        audit_sink=sink,
        dispatcher=dispatcher,
        agent_definition_id="planner-agent",
        startable=True,
    )

    assert turn.disposition is TurnDisposition.DISPATCHED
    assert turn.run_id is not None
    stored = store.get_run_input(run_id=turn.run_id)
    assert stored is not None and stored.message == "plan the migration"
    assert dispatcher.calls[0]["correlation_id"] == turn.run_id
    assert dispatcher.calls[0]["subject_user_id"] == "alice"


def test_the_first_accepted_turn_titles_the_thread_and_later_ones_do_not() -> None:
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    thread = _thread(store)

    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="first message",
        store=store,
        audit_sink=sink,
        agent_definition_id=None,
    )
    accept_turn(
        subject=_subject(),
        thread_id=thread.thread_id,
        message="second message",
        store=store,
        audit_sink=sink,
        agent_definition_id=None,
    )

    stored = store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT)
    assert stored is not None and stored.title == "first message"
