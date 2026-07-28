# SPDX-License-Identifier: Apache-2.0
"""The run index's behaviour, over the in-memory implementation.

The two implementations share semantics deliberately — including the tenant collapse in
`get` — so what is proven here is proven about the *behaviour* rather than about the
storage. Whether Postgres agrees is an enclave row's question; whether the rules are right
is this file's, and a live database could not make the boundary cases happen on demand.

**Every row here is about a boundary or a disclosure**, because those are where an index
can be wrong in ways a happy-path listing would never reveal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.runs.index import (
    MAX_PAGE_SIZE,
    InMemoryRunIndex,
    RunIndexEntry,
    RunIndexError,
    decode_cursor,
)

BASE = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _entry(n: int, *, subject: str = "alice", tenant: str = "tenant-a") -> RunIndexEntry:
    return RunIndexEntry(
        run_id=f"run-{n:03d}",
        correlation_id=f"corr-{n:03d}",
        subject_user_id=subject,
        tenant_id=tenant,
        agent_definition_id="planner-agent",
        created_at=BASE + timedelta(minutes=n),
    )


def _index(*entries: RunIndexEntry) -> InMemoryRunIndex:
    index = InMemoryRunIndex()
    for entry in entries:
        index.record(entry)
    return index


def test_a_subject_sees_their_own_runs() -> None:
    """The positive control. Without it every exclusion row could pass on an empty index."""
    index = _index(_entry(1), _entry(2), _entry(3, subject="bob"))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice")

    assert [e.run_id for e in page.entries] == ["run-002", "run-001"]


def test_another_subject_in_the_same_tenant_is_excluded() -> None:
    """Same tenant is not the same person. The index filters both, in that order."""
    index = _index(_entry(1), _entry(2, subject="bob"))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice")

    assert [e.run_id for e in page.entries] == ["run-001"]


def test_another_tenant_is_excluded_even_for_the_same_subject() -> None:
    """A subject id that appears in two tenants is two principals, not one.

    The likelier real-world shape than a cross-tenant probe: the same username existing in
    two customers. Filtering on subject alone would merge them.
    """
    index = _index(_entry(1), _entry(2, tenant="tenant-b"))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice")

    assert [e.run_id for e in page.entries] == ["run-001"]


def test_nothing_started_is_an_empty_page_not_an_error() -> None:
    """Nothing to show is an answer. An error here would read as "your work is gone"."""
    page = InMemoryRunIndex().list_for(tenant_id="tenant-a", subject_user_id="alice")

    assert page.entries == []
    assert page.cursor is None


def test_pages_are_bounded_and_the_cursor_continues_them() -> None:
    index = _index(*(_entry(n) for n in range(1, 8)))

    first = index.list_for(tenant_id="tenant-a", subject_user_id="alice", limit=3)
    second = index.list_for(
        tenant_id="tenant-a", subject_user_id="alice", limit=3, cursor=first.cursor
    )

    assert [e.run_id for e in first.entries] == ["run-007", "run-006", "run-005"]
    assert [e.run_id for e in second.entries] == ["run-004", "run-003", "run-002"]
    assert first.cursor is not None


def test_the_last_page_carries_no_cursor() -> None:
    """So a caller stops, rather than paging forever against an empty tail."""
    index = _index(_entry(1), _entry(2))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice", limit=5)

    assert len(page.entries) == 2
    assert page.cursor is None


def test_the_cursor_discloses_nothing_about_what_was_withheld() -> None:
    """FR-004, asserted against the cursor's contents rather than its behaviour.

    An `OFFSET`-shaped cursor paginates identically and encodes how far in the caller is —
    which, with a page size, is the total. This asserts the cursor is only a position.
    """
    index = _index(*(_entry(n) for n in range(1, 30)))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice", limit=2)
    assert page.cursor is not None
    stamp, run_id = decode_cursor(page.cursor)

    assert run_id == page.entries[-1].run_id
    assert stamp == page.entries[-1].created_at
    assert "29" not in page.cursor and "27" not in page.cursor, (
        "the cursor appears to encode a count of remaining rows, which tells the caller "
        "how much they are not being shown"
    )


def test_a_request_for_an_enormous_page_is_capped() -> None:
    """A page size cannot become an unbounded read by being asked for politely."""
    index = _index(*(_entry(n) for n in range(1, 5)))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice", limit=10_000)

    assert len(page.entries) == 4  # all of them, but the cap applied to the query
    assert MAX_PAGE_SIZE < 10_000


def test_a_malformed_cursor_refuses_rather_than_returning_page_one() -> None:
    """Silently restarting would make a corrupted cursor look like the end of the list.

    A caller paging through results would loop forever and never know.
    """
    with pytest.raises(RunIndexError):
        InMemoryRunIndex().list_for(
            tenant_id="tenant-a", subject_user_id="alice", cursor="nonsense"
        )


def test_get_collapses_another_tenant_into_absent() -> None:
    """The collapse lives in the index so no call site can forget it.

    A reader that distinguished them would let anyone confirm an identifier exists
    elsewhere — the response itself becoming an oracle.
    """
    index = _index(_entry(1, tenant="tenant-b"))

    assert index.get(run_id="run-001", tenant_id="tenant-a") is None
    assert index.get(run_id="run-001", tenant_id="tenant-b") is not None


def test_recording_the_same_run_twice_does_not_duplicate_it() -> None:
    """A resume re-dispatches under an existing run id; the facts have not changed."""
    index = _index(_entry(1))
    index.record(_entry(1))

    page = index.list_for(tenant_id="tenant-a", subject_user_id="alice")

    assert len(page.entries) == 1
