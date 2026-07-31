# SPDX-License-Identifier: Apache-2.0
"""The named operation, against both real stores (015, SC-007/SC-008).

Reconciliation reads both copies of a stream in full — it is the most evidence-reading
thing this platform does — so ADR-0035 makes it an audited act. These rows drive
`reconcile_evidence_for` with a real evidence query, a real audit sink, and the real second
copy, because the three properties they assert each live in a different place: scope in the
query, the record in the sink, and the comparison in the destination.

The concurrency row is here rather than hermetic for a plainer reason: SC-008 is a claim
about a reconcile racing a live writer, and a double that appends when the test tells it to
has no race to lose.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.egress import ship_pass
from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile_service import PostgresReconciler
from core.audit.schema import AuditEventType
from core.identity.types import AuthenticatedSubject, SubjectKind
from surfaces.api.evidence import evidence_stream_for, reconcile_evidence_for
from tests.conformance.evidence.conftest import query

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

TENANT = "tenant-reconcile-row"


class _StaticCredentials:
    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def _operator() -> Any:
    from tests.harness.operator_credentials import OperatorCredentials

    # Typed as Any: the production classes name the production credential type, and an
    # operator-held credential is deliberately not one — the distinction the dispatch
    # harness draws for `PostgresDependencyStore`.
    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    return credentials


def _subject(user: str = "auditor", tenant: str = TENANT) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"platform"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _write_stream(sink: PostgresAuditSink, entries: int = 4, *, tenant: str = TENANT) -> str:
    correlation_id = f"recon-{uuid.uuid4().hex[:12]}"
    for i in range(entries):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id=tenant,
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )
    return correlation_id


def _parts(egress_configured: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    credentials = _operator()
    sink = PostgresAuditSink(credentials=credentials)
    evidence_query = PostgresEvidenceQuery(credentials=credentials)
    destination = PostgresAuditDestination.from_credential(egress_configured)
    reconciler = PostgresReconciler(
        connection_factory=lambda: _open(credentials),
        destination=destination,
    )
    return sink, evidence_query, reconciler, destination


def _open(credentials: Any) -> Any:
    import pg8000.dbapi

    cred = credentials.fetch()
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=5432,
        database="brieve",
        user=cred.username,
        password=cred.password,
    )
    conn.autocommit = True
    return conn


def test_row_reconciling_is_recorded_with_its_basis_and_its_caller(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """SC-007 — reading evidence is audited, and this reads all of it.

    Asserted against the real sink rather than an in-memory one because the record has to
    survive the same chain and the same append-only grant as everything else in the trail.
    A meta-audit event that only existed in a double would be a record of a record nobody
    can produce.
    """
    sink, evidence_query, reconciler, destination = _parts(egress_configured)
    correlation_id = _write_stream(sink)
    ship_pass(local=platform_admin_connection, destination=destination)

    report, _ = reconcile_evidence_for(
        correlation_id=correlation_id,
        query=evidence_query,
        audit=sink,
        subject=_subject(),
        reconciler=reconciler,
    )

    assert report.ok, f"a clean stream reported divergence: {report.findings}"

    recorded = query(
        platform_admin_connection,
        "SELECT payload FROM audit_entries WHERE correlation_id = %s "
        "AND event_type = %s ORDER BY seq DESC LIMIT 1",
        ("audit-reconcile-on_demand", str(AuditEventType.AUDIT_RECONCILED)),
    )
    assert recorded, "the comparison left no record of itself in the real trail"
    payload = recorded[0][0]
    assert payload["basis"] == "on_demand"
    assert payload["caller"] == "auditor"
    # Locations and counts, never contents (FR-019).
    assert "payload" not in str(payload.get("findings", {}))


def test_row_a_caller_outside_the_streams_tenant_is_refused_and_the_probe_recorded(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """SC-007's other half — the refusal is the event worth having.

    The caller learns nothing: an out-of-scope stream and a clean one look identical from
    the outside, which is deliberate, because telling them apart would confirm the
    existence of evidence they may not see. The trail tells them apart, which is where the
    difference is useful.
    """
    sink, evidence_query, reconciler, _destination = _parts(egress_configured)
    theirs = _write_stream(sink, tenant="tenant-somebody-else")

    report, _ = reconcile_evidence_for(
        correlation_id=theirs,
        query=evidence_query,
        audit=sink,
        subject=_subject(user="mallory"),
        reconciler=reconciler,
    )

    assert report.findings == []
    assert report.posture == "absent", (
        "a refused request returned a posture derived from a comparison that must not have run"
    )

    refusals = query(
        platform_admin_connection,
        "SELECT payload FROM audit_entries WHERE correlation_id = %s AND event_type = %s "
        "ORDER BY seq DESC LIMIT 1",
        (evidence_stream_for(TENANT), str(AuditEventType.EVIDENCE_READ_REFUSED)),
    )
    assert refusals, "reaching for another tenant's evidence went unrecorded"
    assert refusals[0][0]["subject_user_id"] == "mallory"


def test_row_reconciling_during_active_writing_reports_no_false_divergence(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """SC-008 / FR-013 — the case that decides whether anyone reads this check.

    A reconcile that ran while entries were being written would find the newest ones absent
    at the destination and, if it called that divergence, would be red during every busy
    period. A check that is always red is a check nobody reads, and this feature's whole
    value is that somebody reads it.

    So the tail is reported as backlog. Live rather than hermetic: a double that appends on
    command has no race to lose, and this row's subject is exactly the race.
    """
    sink, evidence_query, reconciler, destination = _parts(egress_configured)
    correlation_id = _write_stream(sink, 3)
    ship_pass(local=platform_admin_connection, destination=destination)

    # Written after the ship pass — legitimately at the first copy and legitimately not yet
    # at the second. This is the ordinary steady state of a busy estate, not an anomaly.
    for i in range(3, 8):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id=TENANT,
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )

    report, _ = reconcile_evidence_for(
        correlation_id=correlation_id,
        query=evidence_query,
        audit=sink,
        subject=_subject(),
        reconciler=reconciler,
    )

    assert report.findings == [], (
        f"the in-flight tail was reported as divergence rather than backlog: {report.findings}"
    )
    assert report.backlog > 0, "the undelivered tail was invisible — lag must be observable"
