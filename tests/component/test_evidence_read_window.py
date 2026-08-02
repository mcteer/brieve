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


# ------------------------------------------------------------------ 029: the per-type window


def _mixed(*, common: int, rare: int) -> InMemoryEvidenceQuery:
    """The live tenant's shape: one loud type, one quiet one, interleaved in time.

    The measured composition was 383 `effect_observed` against 60 `run_start` in a window of a
    thousand. This reproduces the *ratio* rather than the counts, which is what decides whether
    the quiet type survives a bound.
    """
    sink = InMemoryAuditSink()
    index = 0
    for i in range(max(common, rare)):
        for _ in range(common // max(rare, 1)):
            sink.append_event(
                correlation_id=f"noise-{index:05d}",
                tenant_id=TENANT,
                event_type=AuditEventType.EFFECT_OBSERVED,
                payload={"index": index},
                timestamp=START + timedelta(seconds=index),
            )
            index += 1
        if i < rare:
            sink.append_event(
                correlation_id=f"run-{index:05d}",
                tenant_id=TENANT,
                event_type=AuditEventType.RUN_START,
                payload={"index": index},
                timestamp=START + timedelta(seconds=index),
            )
            index += 1
    return InMemoryEvidenceQuery(sink)


def test_a_rare_type_is_not_crowded_out_by_a_common_one() -> None:
    """SC-002, in the exact shape that failed on the deployed platform.

    Under one shared bound the quiet type gets whatever slots the loud one leaves — measured at
    60 run records in a window of 1,000. Raising the bound does not fix it, because the ratio is
    what starves the question, so this row asserts the property a bigger number cannot buy.
    """
    query = _mixed(common=600, rare=60)

    shared = query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit=100,
            event_types=frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START}),
        )
    )
    per_type = query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit_per_type=50,
            event_types=frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START}),
        )
    )

    starved = sum(1 for e in shared if e.event_type is AuditEventType.RUN_START)
    served = sum(1 for e in per_type if e.event_type is AuditEventType.RUN_START)
    assert served == 50, f"the per-type bound did not reach the quiet type: {served}"
    assert served > starved, (
        f"the per-type bound is no better than the shared one ({served} vs {starved}); the "
        f"question's own records are still competing with the estate's noisiest activity"
    )


def test_each_type_gets_its_newest_and_the_whole_stays_oldest_first() -> None:
    """The two halves that must both hold: selection per type, order overall."""
    query = _mixed(common=200, rare=40)

    result = query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit_per_type=10,
            event_types=frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START}),
        )
    )

    runs = [e for e in result if e.event_type is AuditEventType.RUN_START]
    assert len(runs) == 10
    newest_run_index = max(
        e.payload["index"]
        for e in query.search(
            EvidenceQueryRequest(
                tenant_id=TENANT, limit=10_000, event_types=frozenset({AuditEventType.RUN_START})
            )
        )
    )
    assert runs[-1].payload["index"] == newest_run_index, "the newest of the type is missing"
    timestamps = [e.timestamp for e in result]
    assert timestamps == sorted(timestamps), "the combined window is not oldest-first"


def test_the_accounting_says_what_arrived_against_what_existed() -> None:
    """FR-006's raw material: the numbers the answer's window note is built from.

    Counted per type, because that is the grain a person can act on — "the 10 most recent run
    records of 40" tells them something; "10 of 240" across mixed types tells them nothing.
    """
    query = _mixed(common=200, rare=40)

    result = query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit_per_type=10,
            event_types=frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START}),
        )
    )

    assert result.window[AuditEventType.RUN_START] == (10, 40)
    assert result.truncated, "a truncated read reported itself complete"
    assert AuditEventType.RUN_START in result.truncated


def test_an_untruncated_per_type_read_reports_itself_complete() -> None:
    """The common case: a small estate answers wholly, and the answer says nothing about windows.

    `truncated` empty is what makes the note absent, so this is the row that keeps a complete
    answer from carrying a caveat it does not deserve.
    """
    result = _mixed(common=20, rare=5).search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit_per_type=100,
            event_types=frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START}),
        )
    )

    assert result.truncated == {}
    assert result.window[AuditEventType.RUN_START][0] == result.window[AuditEventType.RUN_START][1]


def test_the_per_type_window_never_returns_a_type_that_was_not_requested() -> None:
    """FR-005 where the new code could most easily have widened it.

    The per-type path builds buckets from whatever the scope clause returned. If it built them
    before narrowing — or ignored `event_types` — a caller would receive types their role does
    not permit, which is a boundary defect rather than a windowing one.
    """
    sink = InMemoryAuditSink()
    for i, kind in enumerate([AuditEventType.RUN_START, AuditEventType.AUTHORITY_DENIED] * 25):
        sink.append_event(
            correlation_id=f"e-{i}",
            tenant_id=TENANT,
            event_type=kind,
            payload={"index": i},
            timestamp=START + timedelta(minutes=i),
        )

    result = InMemoryEvidenceQuery(sink).search(
        EvidenceQueryRequest(
            tenant_id=TENANT,
            limit_per_type=5,
            event_types=frozenset({AuditEventType.RUN_START}),
        )
    )

    assert {e.event_type for e in result} == {AuditEventType.RUN_START}
    assert AuditEventType.AUTHORITY_DENIED not in result.window


def test_an_empty_scope_still_matches_nothing_with_a_per_type_bound() -> None:
    """025's fail-closed rule, re-asserted on the new path.

    An empty type set means "no type is visible to this caller". A per-type bucket fill over an
    unfiltered list would hand the newest of everything to somebody entitled to none — the same
    inversion 025 found in merged code, arriving by a third route.
    """
    result = _filled(20).search(
        EvidenceQueryRequest(tenant_id=TENANT, limit_per_type=5, event_types=frozenset())
    )

    assert result == []
    assert result.window == {}


def test_the_generated_sql_partitions_exactly_when_a_per_type_bound_is_set() -> None:
    """The hermetic half of a differential that cannot honestly be hermetic (029, plan).

    The Postgres implementation's *behaviour* can only be checked against a real Postgres, in the
    enclave lane. What is checkable here is that the two paths exist and are chosen correctly: a
    per-type request must partition, and a plain one must not — because a plain read that started
    partitioning would silently change what every existing caller receives.

    Asserted against the SQL the implementation builds, by capturing it at the connection seam
    rather than by re-deriving it — a row that rebuilt the query would be testing its own copy.
    """
    from core.audit.postgres_query import PostgresEvidenceQuery

    captured: list[str] = []

    class _Cursor:
        def execute(self, sql: str, params: tuple[object, ...]) -> None:
            captured.append(sql)

        def fetchall(self) -> list[object]:
            return []

    class _Conn:
        def cursor(self) -> _Cursor:
            return _Cursor()

        def close(self) -> None:
            pass

    class _Credentials:
        """Answers the one call the read makes before connecting."""

        def fetch(self) -> object:
            return type("Cred", (), {"username": "u", "password": "p"})()

    query = PostgresEvidenceQuery(
        credentials=_Credentials(),  # type: ignore[arg-type] — the seam, not the real fabric
        connect=lambda **_: _Conn(),
    )

    query.search(EvidenceQueryRequest(tenant_id=TENANT, limit=10))
    assert "PARTITION BY" not in captured[-1], (
        "a plain read partitions; every existing caller's window would change silently"
    )

    query.search(
        EvidenceQueryRequest(
            tenant_id=TENANT, limit_per_type=5, event_types=frozenset({AuditEventType.RUN_START})
        )
    )
    assert "PARTITION BY event_type" in captured[-1]
    assert "ROW_NUMBER()" in captured[-1] and "COUNT(*)" in captured[-1], (
        "the per-type query does not carry both the ranking and the accounting, so the window "
        "note would need a second round-trip"
    )
