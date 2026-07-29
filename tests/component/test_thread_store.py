# SPDX-License-Identifier: Apache-2.0
"""The thread store's semantics, asserted where both implementations must agree.

Every row here runs against the in-memory store. The Postgres store's *own* behaviour —
the row lock, the cascade — needs the real database and is asserted in the enclave lane;
what these rows pin down is the contract both implementations sign, so a divergence shows
up as a failing row rather than as a surprise in production.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.threads.records import (
    RATE_LIMIT_WINDOW_SECONDS,
    RunInput,
    ThreadRecord,
    TurnDisposition,
    TurnRecord,
    title_from,
)
from core.threads.store import (
    InMemoryThreadStore,
    ThreadStoreError,
    decode_cursor,
    new_thread_id,
    new_turn_id,
)

TENANT = "tenant-test"
OTHER_TENANT = "tenant-other"


def _thread(
    *,
    subject: str = "alice",
    tenant: str = TENANT,
    created_at: datetime | None = None,
) -> ThreadRecord:
    thread_id = new_thread_id()
    return ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id=subject,
        tenant_id=tenant,
        created_at=created_at or datetime.now(UTC),
    )


def _turn(
    thread: ThreadRecord,
    *,
    message: str = "do the thing",
    disposition: TurnDisposition = TurnDisposition.DISPATCHED,
    created_at: datetime | None = None,
) -> TurnRecord:
    return TurnRecord(
        turn_id=new_turn_id(),
        thread_id=thread.thread_id,
        tenant_id=thread.tenant_id,
        subject_user_id=thread.subject_user_id,
        seq=-1,  # ignored; the store assigns it
        message=message,
        disposition=disposition,
        created_at=created_at or datetime.now(UTC),
    )


def test_a_thread_is_readable_by_its_owner() -> None:
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)

    assert store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT) == thread


def test_another_tenants_thread_reads_as_absent() -> None:
    """Not refused — absent. A reader that could tell them apart lets anyone probe."""
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)

    assert store.get_thread(thread_id=thread.thread_id, tenant_id=OTHER_TENANT) is None
    assert store.get_thread(thread_id="th-nonexistent", tenant_id=OTHER_TENANT) is None


def test_listing_is_newest_first_and_scoped_to_one_subject() -> None:
    store = InMemoryThreadStore()
    base = datetime.now(UTC)
    mine = [_thread(created_at=base + timedelta(seconds=i)) for i in range(3)]
    for t in mine:
        store.create_thread(t)
    store.create_thread(_thread(subject="bob"))
    store.create_thread(_thread(tenant=OTHER_TENANT))

    page = store.list_threads(tenant_id=TENANT, subject_user_id="alice")

    assert [t.thread_id for t in page.threads] == [t.thread_id for t in reversed(mine)]
    assert page.cursor is None


def test_paging_reaches_every_thread_exactly_once_and_carries_no_total() -> None:
    store = InMemoryThreadStore()
    base = datetime.now(UTC)
    for i in range(7):
        store.create_thread(_thread(created_at=base + timedelta(seconds=i)))

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        page = store.list_threads(tenant_id=TENANT, subject_user_id="alice", limit=3, cursor=cursor)
        seen.extend(t.thread_id for t in page.threads)
        cursor = page.cursor
        if cursor is None:
            break

    assert len(seen) == 7
    assert len(set(seen)) == 7
    # The cursor names a position, and nothing else. An offset-shaped cursor reads
    # identically in the happy path and leaks the size of what a caller cannot see.
    assert not hasattr(page, "total")


def test_a_malformed_cursor_refuses_rather_than_returning_an_empty_page() -> None:
    with pytest.raises(ThreadStoreError):
        decode_cursor("garbage")


def test_seq_is_dense_and_assigned_by_the_store() -> None:
    """The caller's seq is ignored — two tabs must not both claim the same number."""
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)

    stored = [store.append_turn(_turn(thread, message=f"m{i}")) for i in range(4)]

    assert [t.seq for t in stored] == [0, 1, 2, 3]
    assert [t.seq for t in store.turns_of(thread_id=thread.thread_id)] == [0, 1, 2, 3]


def test_deleting_a_thread_removes_its_turns_and_leaves_run_inputs() -> None:
    """FR-010d: the run outlives the view."""
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)
    store.append_turn(_turn(thread))
    store.put_run_input(
        RunInput(run_id="run-1", message="do the thing", created_at=datetime.now(UTC))
    )

    assert store.delete_thread(thread_id=thread.thread_id, tenant_id=TENANT) is True

    assert store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT) is None
    assert store.turns_of(thread_id=thread.thread_id) == []
    assert store.get_run_input(run_id="run-1") is not None


def test_another_tenant_cannot_delete_a_thread() -> None:
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)

    assert store.delete_thread(thread_id=thread.thread_id, tenant_id=OTHER_TENANT) is False
    assert store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT) is not None


def test_a_title_is_set_once_and_never_overwritten() -> None:
    store = InMemoryThreadStore()
    thread = _thread()
    store.create_thread(thread)

    store.set_title(thread_id=thread.thread_id, title="first")
    store.set_title(thread_id=thread.thread_id, title="second")

    stored = store.get_thread(thread_id=thread.thread_id, tenant_id=TENANT)
    assert stored is not None and stored.title == "first"


def test_the_rate_window_counts_turns_and_creations_together() -> None:
    """The pass-4 finding, as a row.

    A window counting only turns reads zero while a subject creates ten thousand empty
    threads — the bound would exist in prose and not in the query.
    """
    store = InMemoryThreadStore()
    for _ in range(4):
        store.create_thread(_thread())
    thread = _thread()
    store.create_thread(thread)
    for _ in range(3):
        store.append_turn(_turn(thread))

    # 5 creations + 3 turns
    assert store.recent_act_count(tenant_id=TENANT, subject_user_id="alice") == 8


def test_creations_alone_count_against_the_window() -> None:
    store = InMemoryThreadStore()
    for _ in range(6):
        store.create_thread(_thread())

    assert store.recent_act_count(tenant_id=TENANT, subject_user_id="alice") == 6


def test_the_rate_window_forgets_acts_outside_it() -> None:
    store = InMemoryThreadStore()
    old = datetime.now(UTC) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS + 60)
    store.create_thread(_thread(created_at=old))
    recent = _thread()
    store.create_thread(recent)

    assert store.recent_act_count(tenant_id=TENANT, subject_user_id="alice") == 1


def test_the_rate_window_is_per_subject_and_per_tenant() -> None:
    store = InMemoryThreadStore()
    store.create_thread(_thread())
    store.create_thread(_thread(subject="bob"))
    store.create_thread(_thread(tenant=OTHER_TENANT))

    assert store.recent_act_count(tenant_id=TENANT, subject_user_id="alice") == 1


def test_run_input_is_insert_only() -> None:
    """A re-dispatch under an existing run id is a resume; its input is unchanged."""
    store = InMemoryThreadStore()
    first = RunInput(run_id="run-1", message="original", created_at=datetime.now(UTC))
    store.put_run_input(first)
    store.put_run_input(RunInput(run_id="run-1", message="replaced", created_at=datetime.now(UTC)))

    stored = store.get_run_input(run_id="run-1")
    assert stored is not None and stored.message == "original"


def test_title_from_collapses_whitespace_and_cuts_at_a_word() -> None:
    assert title_from("  hello   there  ") == "hello there"
    long = "plan the migration of the workspace and then apply it carefully everywhere"
    title = title_from(long, limit=30)
    assert len(title) <= 31 and title.endswith("…") and "  " not in title
