# SPDX-License-Identifier: Apache-2.0
"""Rows: evidence is scope-bounded, zero rows are distinguishable, access is audited.

Against the real store, because the tenant predicate is applied in SQL and a double that
scoped more loosely would let a leak pass hermetically and appear only here.
"""

from __future__ import annotations

import pytest

from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.query import EvidenceQueryRequest
from core.audit.schema import AuditEventType

pytestmark = pytest.mark.enclave

TENANT_A = "tenant-conformance-a"
TENANT_B = "tenant-conformance-b"


def test_row_evidence_is_scope_bounded(
    audit_sink: PostgresAuditSink,
    evidence_query: PostgresEvidenceQuery,
    unique_correlation_id: str,
) -> None:
    """Two identities with different scope see only their own, and neither can widen it."""
    audit_sink.append_event(
        correlation_id=f"{unique_correlation_id}-a",
        tenant_id=TENANT_A,
        event_type=AuditEventType.RUN_START,
        payload={},
    )
    audit_sink.append_event(
        correlation_id=f"{unique_correlation_id}-b",
        tenant_id=TENANT_B,
        event_type=AuditEventType.RUN_START,
        payload={},
    )

    a = evidence_query.search(EvidenceQueryRequest(tenant_id=TENANT_A))
    b = evidence_query.search(EvidenceQueryRequest(tenant_id=TENANT_B))

    assert {e.tenant_id for e in a} == {TENANT_A}
    assert {e.tenant_id for e in b} == {TENANT_B}


def test_row_narrowing_cannot_cross_the_boundary(
    audit_sink: PostgresAuditSink,
    evidence_query: PostgresEvidenceQuery,
    unique_correlation_id: str,
) -> None:
    """Naming another tenant's stream returns nothing — the tenant predicate wins."""
    other = f"{unique_correlation_id}-b"
    audit_sink.append_event(
        correlation_id=other,
        tenant_id=TENANT_B,
        event_type=AuditEventType.RUN_START,
        payload={},
    )

    got = evidence_query.search(EvidenceQueryRequest(tenant_id=TENANT_A, correlation_id=other))
    assert got == []


def test_row_zero_rows_are_distinguishable(
    audit_sink: PostgresAuditSink,
    evidence_query: PostgresEvidenceQuery,
    unique_correlation_id: str,
) -> None:
    """The distinction FR-011 turns on, at the layer that can actually determine it.

    Both cases return zero rows to the caller. Only `exists_outside_tenant` separates
    them, and without it the trail would record both as "empty".
    """
    other = f"{unique_correlation_id}-b"
    audit_sink.append_event(
        correlation_id=other,
        tenant_id=TENANT_B,
        event_type=AuditEventType.RUN_START,
        payload={},
    )

    assert evidence_query.exists_outside_tenant(correlation_id=other, tenant_id=TENANT_A)
    assert not evidence_query.exists_outside_tenant(
        correlation_id=f"{unique_correlation_id}-nowhere", tenant_id=TENANT_A
    )


def test_row_the_read_path_returns_no_verdict(evidence_query: PostgresEvidenceQuery) -> None:
    """ADR-0035: evidence with citations, never a judgment about what it means."""
    entries = evidence_query.search(EvidenceQueryRequest(tenant_id=TENANT_A, limit=1))
    for entry in entries:
        assert not hasattr(entry, "compliant")
        assert "verdict" not in entry.payload


# ------------------------------------------------------------------ 029: the per-type window


def test_row_the_per_type_window_holds_against_the_real_store(
    audit_sink: PostgresAuditSink,
    evidence_query: PostgresEvidenceQuery,
    unique_correlation_id: str,
) -> None:
    """The half of the per-type bound a hermetic lane cannot honestly claim.

    The in-memory twin is a groupby; this is a `ROW_NUMBER() OVER (PARTITION BY …)` executed by
    Postgres. Their agreeing is only evidence when they *could* have disagreed — which is exactly
    what the previous finding taught: both implementations shared the oldest-window defect, so the
    differential row between them passed while both were wrong.

    So this asserts the behaviour against the real store rather than trusting the shape: a rare
    type survives a bound that a common one would otherwise fill, and the accounting reports what
    existed rather than what arrived.
    """
    noisy, rare = 40, 4
    for i in range(noisy):
        audit_sink.append_event(
            correlation_id=f"{unique_correlation_id}-noise-{i}",
            tenant_id=TENANT_A,
            event_type=AuditEventType.EFFECT_OBSERVED,
            payload={"index": i},
        )
    for i in range(rare):
        audit_sink.append_event(
            correlation_id=f"{unique_correlation_id}-run-{i}",
            tenant_id=TENANT_A,
            event_type=AuditEventType.RUN_START,
            payload={"index": i},
        )

    types = frozenset({AuditEventType.EFFECT_OBSERVED, AuditEventType.RUN_START})
    result = evidence_query.search(
        EvidenceQueryRequest(tenant_id=TENANT_A, event_types=types, limit_per_type=5)
    )

    seen = [e.event_type for e in result]
    assert sum(1 for k in seen if k is AuditEventType.RUN_START) >= rare, (
        "the rare type was crowded out against the real store, so the SQL window is not "
        "partitioning the way the in-memory twin does"
    )
    assert sum(1 for k in seen if k is AuditEventType.EFFECT_OBSERVED) == 5, (
        "the common type was not bounded to its own limit"
    )

    timestamps = [e.timestamp for e in result]
    assert timestamps == sorted(timestamps), "the real store returned a window out of order"

    returned, matched = result.window[AuditEventType.EFFECT_OBSERVED]
    assert returned == 5
    assert matched >= noisy, (
        f"the accounting reports {matched} matched for a type with at least {noisy} rows; the "
        f"window note would understate what the answer left out"
    )


def test_row_a_read_without_a_per_type_bound_is_unchanged_against_the_real_store(
    audit_sink: PostgresAuditSink,
    evidence_query: PostgresEvidenceQuery,
    unique_correlation_id: str,
) -> None:
    """`limit_per_type=None` must be byte-for-byte today's read, including against Postgres.

    Two SQL paths exist now, and the plain one carries every pre-existing caller. A row here is
    what keeps "the default is untouched" from being a claim about the code rather than about the
    database that runs it.
    """
    for i in range(3):
        audit_sink.append_event(
            correlation_id=f"{unique_correlation_id}-plain-{i}",
            tenant_id=TENANT_A,
            event_type=AuditEventType.RUN_START,
            payload={"index": i},
        )

    result = evidence_query.search(EvidenceQueryRequest(tenant_id=TENANT_A, limit=1000))

    assert result.window == {}, "a plain read reported window accounting it was never asked for"
    timestamps = [e.timestamp for e in result]
    assert timestamps == sorted(timestamps)
