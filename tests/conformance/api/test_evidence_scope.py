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
