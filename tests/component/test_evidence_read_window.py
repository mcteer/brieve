# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a truncated evidence read returns the NEWEST window, not the oldest.

**The defect this file exists to end was in merged code and invisible to every test.** Both
`EvidenceQuery` implementations sorted ascending and took the first `limit` entries: the *oldest*
window. On a tenant holding a handful of records that is every record and the two behaviours are
indistinguishable. On one holding 139,749 it means every read answers from the beginning of
history, and a question about what happened recently is answered honestly from evidence that has
nothing to do with it.

**Measured, after a wrong guess.** A deployed estate question declined, and the first hypothesis
was this truncation. It was not: denials sit outside the `operator` role's scope entirely, so that
question is unanswerable for that role at any limit — the decline was correct and complete.

Measuring anyway found this: **236,581 entries readable by one role against a limit of 1,000**, so
the oldest-window read answered every question from evidence three days stale. Real, independent,
and not what sent anybody looking. The distinction is kept here because a test file that tells a
false causal story is worse than one that tells none.

**Why nothing caught it.** The two implementations were wrong in the same way, so the differential
row that exists to catch divergence passed — agreement is only evidence when the implementations
could have disagreed. So the rows here assert the *property* against each implementation
separately, and only then that the two agree.

**Scope is untouched.** These rows are about which slice of an already-scoped read arrives when
the limit truncates. What a caller may see is decided by the tenant bound and the type filter
above it, and neither moves — asserted below, because a change to a read path should have to prove
that.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.query import EvidenceQueryRequest
from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from tests.harness.memory_evidence import InMemoryEvidenceQuery

TENANT = "tenant-window"
START = datetime(2026, 1, 1, tzinfo=UTC)


def _filled(count: int, *, tenant: str = TENANT) -> InMemoryEvidenceQuery:
    """`count` entries, one per minute, oldest first — so the window is unambiguous."""
    sink = InMemoryAuditSink()
    for i in range(count):
        sink.append_event(
            correlation_id=f"run-{i:05d}",
            tenant_id=tenant,
            event_type=AuditEventType.RUN_START,
            payload={"index": i},
            timestamp=START + timedelta(minutes=i),
        )
    return InMemoryEvidenceQuery(sink)


def _indices(entries: list[Any]) -> list[int]:
    return [e.payload["index"] for e in entries]


def test_a_truncated_read_returns_the_most_recent_entries() -> None:
    """The row that would have caught it.

    A hundred entries, a limit of ten. Before the fix this returned indices 0–9 — the oldest ten,
    from a tenant whose recent activity is what anybody asking is asking about.
    """
    query = _filled(100)

    entries = query.search(EvidenceQueryRequest(tenant_id=TENANT, limit=10))

    assert _indices(entries) == list(range(90, 100)), (
        "the read returned the oldest window; a question about recent activity is answered from "
        "the beginning of history"
    )


def test_the_returned_window_is_still_oldest_first() -> None:
    """Selecting the newest is not the same as reversing, and only the first was the defect.

    Callers read these in order — a report, a chain, a person scanning a page. Handing them the
    newest window in reverse would fix the selection and break every consumer, so the fix does
    exactly one thing.
    """
    entries = _filled(50).search(EvidenceQueryRequest(tenant_id=TENANT, limit=5))

    timestamps = [e.timestamp for e in entries]
    assert timestamps == sorted(timestamps), "the window is no longer oldest-first"


def test_a_read_that_does_not_truncate_is_unchanged() -> None:
    """The common case, and the one every existing row exercises.

    Below the limit there is no window to choose, and this asserts the fix did not quietly
    reorder or drop anything for the readers who never hit it.
    """
    entries = _filled(7).search(EvidenceQueryRequest(tenant_id=TENANT, limit=1000))

    assert _indices(entries) == list(range(7))


def test_the_newest_window_is_taken_after_scope_narrowing_not_before() -> None:
    """The order that matters most, and the one a fix could plausibly get backwards.

    Narrowing first and then taking the newest gives the newest *visible* entries. Taking the
    newest and then narrowing would give whatever survives from a recent slice — so a caller
    entitled to one rare type would see nothing whenever busier types crowded the window, and the
    emptiness would look like an honest "nothing happened".
    """
    sink = InMemoryAuditSink()
    for i in range(100):
        # One rare RUN_STOPPED early, then ninety-nine RUN_STARTs after it.
        kind = AuditEventType.RUN_STOPPED if i == 0 else AuditEventType.RUN_START
        sink.append_event(
            correlation_id=f"run-{i:05d}",
            tenant_id=TENANT,
            event_type=kind,
            payload={"index": i},
            timestamp=START + timedelta(minutes=i),
        )
    query = InMemoryEvidenceQuery(sink)

    entries = query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT, limit=5, event_types=frozenset({AuditEventType.RUN_STOPPED})
        )
    )

    assert _indices(entries) == [0], (
        "the newest window was taken before the type filter, so a rare entry the caller is "
        "entitled to see was crowded out by common ones"
    )


def test_the_window_does_not_reach_across_tenants() -> None:
    """The bound this change must not touch, asserted because it is a read-path change.

    Another tenant's entries are newer than every one of ours. If the window were chosen before
    the tenant predicate, they would fill it — which is not a truncation defect but a boundary
    one.
    """
    sink = InMemoryAuditSink()
    for i in range(10):
        sink.append_event(
            correlation_id=f"ours-{i}",
            tenant_id=TENANT,
            event_type=AuditEventType.RUN_START,
            payload={"index": i},
            timestamp=START + timedelta(minutes=i),
        )
    for i in range(50):
        sink.append_event(
            correlation_id=f"theirs-{i}",
            tenant_id="tenant-somebody-else",
            event_type=AuditEventType.RUN_START,
            payload={"index": 1000 + i},
            timestamp=START + timedelta(days=1, minutes=i),
        )

    entries = InMemoryEvidenceQuery(sink).search(EvidenceQueryRequest(tenant_id=TENANT, limit=5))

    assert _indices(entries) == [5, 6, 7, 8, 9]
    assert all(e.tenant_id == TENANT for e in entries)


def test_an_empty_scope_still_matches_nothing() -> None:
    """025's fail-closed rule, re-asserted here because this file changed the slicing.

    An empty type set means "no type is visible to this caller". A slice applied to an
    unfiltered list would return the newest entries to somebody entitled to none — the same
    inversion 025 found in merged code, arriving by a different route.
    """
    entries = _filled(20).search(
        EvidenceQueryRequest(tenant_id=TENANT, limit=5, event_types=frozenset())
    )

    assert entries == []


def test_a_zero_limit_returns_nothing_rather_than_everything() -> None:
    """The slice's own edge, and it is not academic.

    `entries[-0:]` is the whole list in Python — so the obvious expression of "take the last n"
    turns a limit of zero into an unbounded read. A caller asking for nothing must receive
    nothing.
    """
    assert _filled(20).search(EvidenceQueryRequest(tenant_id=TENANT, limit=0)) == []
