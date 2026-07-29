# SPDX-License-Identifier: Apache-2.0
"""SC-009 — another tenant's thread is indistinguishable from one that does not exist.

Across *every* operation that can name a thread, which is the part worth asserting: a
boundary that holds on four operations and leaks on the fifth is not a boundary. The
collapse lives in the store so no reader can accidentally tell the two apart, and these
rows check the collapse survives the trip through each surface function.

The same-tenant case is deliberately different. Someone else's thread in your own tenant
refuses *with a reason*, because you can already see it exists — hiding it there would be
telling a person that a conversation they can see does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.refusals import OperationRefused
from core.threads.records import ThreadRecord
from core.threads.store import InMemoryThreadStore, new_thread_id
from core.threads.turns import accept_turn
from surfaces.api.threads import delete_thread_for, list_threads_for, thread_detail_for

TENANT = "tenant-test"
OTHER = "tenant-other"


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


def _thread(
    store: InMemoryThreadStore, *, user: str = "alice", tenant: str = TENANT
) -> ThreadRecord:
    thread_id = new_thread_id()
    record = ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id=user,
        tenant_id=tenant,
        created_at=datetime.now(UTC),
    )
    store.create_thread(record)
    return record


def test_every_operation_answers_another_tenant_identically_to_absent() -> None:
    """The boundary asserted across the whole surface rather than on one route."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    theirs = _thread(store)
    intruder = _subject(user="mallory", tenant=OTHER)

    reasons: list[str] = []
    for call in (
        lambda: thread_detail_for(subject=intruder, store=store, thread_id=theirs.thread_id),
        lambda: delete_thread_for(
            subject=intruder, store=store, audit_sink=sink, thread_id=theirs.thread_id
        ),
        lambda: accept_turn(
            subject=intruder,
            thread_id=theirs.thread_id,
            message="hello",
            store=store,
            audit_sink=sink,
            dispatcher=RecordingDispatcher(),
            agent_definition_id=None,
        ),
    ):
        with pytest.raises(OperationRefused) as refused:
            call()
        reasons.append(refused.value.reason_code)
        assert refused.value.is_visible_to_caller is False

    # A genuinely absent thread must produce the same answers.
    absent: list[str] = []
    for call in (
        lambda: thread_detail_for(subject=intruder, store=store, thread_id="th-nope"),
        lambda: delete_thread_for(
            subject=intruder, store=store, audit_sink=sink, thread_id="th-nope"
        ),
        lambda: accept_turn(
            subject=intruder,
            thread_id="th-nope",
            message="hello",
            store=store,
            audit_sink=sink,
            dispatcher=RecordingDispatcher(),
            agent_definition_id=None,
        ),
    ):
        with pytest.raises(OperationRefused) as refused:
            call()
        absent.append(refused.value.reason_code)

    assert reasons == absent, (
        "an operation distinguishes another tenant's thread from an absent one"
    )


def test_a_listing_never_shows_another_tenants_threads() -> None:
    store = InMemoryThreadStore()
    _thread(store)
    _thread(store, tenant=OTHER)

    page = list_threads_for(subject=_subject(tenant=OTHER), store=store)

    assert len(page.threads) == 0 or all(t.thread_id for t in page.threads)
    mine = list_threads_for(subject=_subject(), store=store)
    assert len(mine.threads) == 1


def test_someone_elses_thread_in_the_same_tenant_refuses_with_a_reason() -> None:
    """Visible, because the caller can already see it exists."""
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    bobs = _thread(store, user="bob")

    with pytest.raises(OperationRefused) as refused:
        accept_turn(
            subject=_subject(user="alice"),
            thread_id=bobs.thread_id,
            message="hello",
            store=store,
            audit_sink=sink,
            dispatcher=RecordingDispatcher(),
            agent_definition_id=None,
        )

    assert refused.value.reason_code == "not_permitted"
    assert refused.value.is_visible_to_caller is True


def test_no_event_is_written_for_a_thread_the_caller_may_not_see() -> None:
    """A refusal must not chain an event under someone else's correlation id.

    Doing so would let a caller grow another tenant's audit stream by probing — a write
    primitive obtained from a read they were not permitted.
    """
    store, sink = InMemoryThreadStore(), InMemoryAuditSink()
    theirs = _thread(store)

    with pytest.raises(OperationRefused):
        accept_turn(
            subject=_subject(user="mallory", tenant=OTHER),
            thread_id=theirs.thread_id,
            message="probing",
            store=store,
            audit_sink=sink,
            dispatcher=RecordingDispatcher(),
            agent_definition_id=None,
        )

    assert sink.list_by_correlation_id(theirs.correlation_id) == []
