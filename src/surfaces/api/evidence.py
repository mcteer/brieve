# SPDX-License-Identifier: Apache-2.0
"""The governed audit read path.

A new class of access. Before this, evidence was written and never read through the
platform — so this is not an extension of an existing read, it is the first one, into the
store every other guarantee is reconciled against.

Four properties, and each is easy to implement in a way that passes a naive test:

**Scope comes from the subject, never the request.** There is no tenant parameter on the
request model, so widening is not a check that could be written wrong — it is a parameter
that does not exist. Everything a caller *can* supply narrows.

**The path cannot mutate.** ``EvidenceQuery`` names no write method, and the credential
behind it holds ``SELECT`` and nothing else, so Postgres refuses regardless of the Python.

**Reading is itself audited**, to a dedicated per-tenant stream rather than to the chain
being read. Appending to the queried run's chain would mean reading evidence writes into
the evidence being read.

**A read whose record cannot be written fails.** Returning evidence unrecorded is exactly
the case FR-010 exists to prevent.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.audit.query import EvidenceQuery, EvidenceQueryRequest, SearchResult
from core.audit.reconcile import ReconcileReport, emit_reconciled, posture_reason
from core.audit.reconcile_service import Reconciler
from core.audit.schema import AuditEntry, AuditEventType, EvidenceDisposition
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import AuditDep, EvidenceDep, ReconcilerDep, SubjectDep
from surfaces.api.record_access import RecordAccessUnavailable

#: One stream per tenant, stable across reads.
#:
#: Stable, not per-read: a fresh correlation ID each time would make every record a chain
#: of one — linked to nothing and removable without trace, which defeats the reason a
#: record of who read what exists at all.
EVIDENCE_STREAM_PREFIX = "evidence-access"


def evidence_stream_for(tenant_id: str) -> str:
    return f"{EVIDENCE_STREAM_PREFIX}:{tenant_id}"


class EvidenceReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[AuditEntry]
    count: int


def read_evidence_for(
    *,
    query: EvidenceQuery,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    correlation_id: str | None = None,
    run_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
    event_types: frozenset[AuditEventType] | None = None,
    limit_per_type: int | None = None,
) -> tuple[SearchResult, EvidenceDisposition]:
    """The governed read, independent of transport.

    Extracted from the route so MCP reaches *this* rather than reimplementing it. ADR-0033
    asks for the same verdict on every transport, and two implementations agreeing by
    inspection would make that a measure of how carefully they were written — which is
    exactly what a conformance row cannot check.

    ``event_types`` (025) narrows the read to the entry types the caller may see, and it exists so
    that **estate answering bounds the query rather than filtering the results**: out-of-scope
    entries are never read, and the access record below shows the narrowed request an investigator
    needs. Like every other field here it can only **narrow** — ``None`` is exactly today's read,
    which is what `GET /evidence` and the MCP evidence operation continue to pass.
    """
    request = EvidenceQueryRequest(
        # From the subject. Not accepted from any caller, on any transport.
        tenant_id=subject.tenant_id,
        correlation_id=correlation_id,
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        event_types=event_types,
        # 029: bounds the newest N of EACH requested type. `None` is exactly today's read, which
        # is why `GET /evidence` and the MCP evidence operation are untouched by its arrival.
        limit_per_type=limit_per_type,
    )
    entries = query.search(request)
    disposition = _disposition(entries, request, query)
    if disposition is EvidenceDisposition.OUT_OF_SCOPE:
        # Emptied, and the window accounting goes with it — a caller told nothing must not be
        # told how much they were told nothing about.
        entries = SearchResult()

    _record_access(
        audit=audit,
        subject=subject,
        request=request,
        entries=entries,
        disposition=disposition,
    )
    return entries, disposition


class ReconciliationResponse(BaseModel):
    """What the comparison found, located and never quoted.

    Findings carry stream and sequence and no payload content (FR-019). The whole point of
    this operation is that reading evidence is governed; a response that quoted the entries
    it had just compared would be an ungoverned read wearing a report's clothes.
    """

    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    posture: str
    posture_reason: str
    destination_verified: str
    findings: list[dict[str, object]]
    backlog: int
    coverage_since: datetime | None


def reconcile_evidence_for(
    *,
    correlation_id: str,
    query: EvidenceQuery,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    reconciler: Reconciler,
) -> tuple[ReconcileReport, EvidenceDisposition]:
    """Compare one stream's two copies, for a caller entitled to read that stream.

    **One stream, named.** Not an estate-wide sweep: the scheduled pass in the mcp service
    already does that under the platform's own identity, and it is the right actor for an
    estate-wide question. What a *caller* can ask is about evidence they may see, and a
    report spanning every stream would name other tenants' correlation IDs to whoever asked
    first — leaking through the report the read path exists to bound.

    **Authorization is the evidence path's, unchanged** (Principle II). Whether this stream
    is the caller's is decided by the same query and the same disposition that decide it for
    a read, so there is no second answer to the question of who may see what. A caller
    reaching for a stream outside their tenant is refused and the refusal is recorded — the
    probe is the interesting event, not the empty result.
    """
    request = EvidenceQueryRequest(
        # From the subject, on every transport. There is no tenant parameter to widen.
        tenant_id=subject.tenant_id,
        correlation_id=correlation_id,
        limit=1,
    )
    visible = query.search(request)
    disposition = _disposition(visible, request, query)

    if disposition is EvidenceDisposition.OUT_OF_SCOPE:
        _record_access(
            audit=audit, subject=subject, request=request, entries=[], disposition=disposition
        )
        return ReconcileReport(), disposition

    report = reconciler.reconcile_stream(correlation_id)
    # The comparison read both copies of this stream in full, so it is itself audited
    # (ADR-0035) — with counts and locations, never contents.
    emit_reconciled(audit, report, basis="on_demand", caller=subject.subject_user_id)
    return report, disposition


def _reconciliation_response(
    correlation_id: str, report: ReconcileReport
) -> ReconciliationResponse:
    return ReconciliationResponse(
        correlation_id=correlation_id,
        posture=report.posture,
        posture_reason=posture_reason(report),
        destination_verified=report.destination_verified,
        findings=[
            {"kind": f.kind, "seq": f.seq, "detail": f.detail, "correlation_id": f.correlation_id}
            for f in report.findings
        ],
        backlog=report.backlog,
        coverage_since=report.coverage_since,
    )


def build_router() -> APIRouter:
    router = APIRouter(tags=["evidence"])

    @router.get("/evidence", response_model=EvidenceReadResponse)
    def read_evidence(
        subject: SubjectDep,
        query: EvidenceDep,
        audit: AuditDep,
        correlation_id: str | None = None,
        run_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> EvidenceReadResponse:
        # The route is a thin binding onto the shared implementation. Zero rows either
        # way when out of scope: the caller must not learn which, because telling them
        # would leak the existence of what they may not see.
        try:
            entries, _ = read_evidence_for(
                query=query,
                audit=audit,
                subject=subject,
                correlation_id=correlation_id,
                run_id=run_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
        return EvidenceReadResponse(entries=entries, count=len(entries))

    @router.get("/evidence/reconciliation", response_model=ReconciliationResponse)
    def reconcile_evidence(
        subject: SubjectDep,
        query: EvidenceDep,
        audit: AuditDep,
        reconciler: ReconcilerDep,
        correlation_id: str,
    ) -> ReconciliationResponse:
        # Registered on the evidence router rather than its own, so it exists exactly when
        # the read path does. A route whose presence varied independently would make the
        # operation snapshot depend on assembly, which 011 already paid for once.
        try:
            report, _ = reconcile_evidence_for(
                correlation_id=correlation_id,
                query=query,
                audit=audit,
                subject=subject,
                reconciler=reconciler,
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
        # Out of scope returns the same empty shape as a clean stream, deliberately: telling
        # the caller which would leak the existence of what they may not see.
        return _reconciliation_response(correlation_id, report)

    return router


def _disposition(
    entries: list[AuditEntry],
    request: EvidenceQueryRequest,
    query: EvidenceQuery,
) -> EvidenceDisposition:
    """Distinguish "nothing happened" from "not for you" (FR-011).

    Both return zero rows, so this cannot be inferred from the count — and an earlier
    version tried to infer it from the shape of the correlation ID, which was wrong in the
    ordinary case: a run's ID carries no tenant marker, so every legitimately empty query
    over a real run was being recorded as a refusal. A disposition that is wrong in the
    common case is worse than none, because the trail then says "someone probed another
    tenant" about routine reads.

    So it is asked rather than guessed. A stream that exists under another tenant is out
    of scope; one that exists nowhere is simply empty.
    """
    if entries:
        return EvidenceDisposition.SCOPED
    narrowed = request.correlation_id or request.run_id
    if narrowed and query.exists_outside_tenant(
        correlation_id=narrowed, tenant_id=request.tenant_id
    ):
        return EvidenceDisposition.OUT_OF_SCOPE
    return EvidenceDisposition.SCOPED


def _record_access(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    request: EvidenceQueryRequest,
    entries: list[AuditEntry],
    disposition: EvidenceDisposition,
) -> None:
    """Write the meta-audit record, or fail the read (FR-010b).

    ``start_governed_run`` already behaves this way when its own audit write fails. An
    access that succeeded while its record did not is precisely what FR-010 exists to
    prevent, so this must not be a best-effort write.
    """
    event = (
        AuditEventType.EVIDENCE_READ
        if disposition is EvidenceDisposition.SCOPED
        else AuditEventType.EVIDENCE_READ_REFUSED
    )
    try:
        audit.append_event(
            correlation_id=evidence_stream_for(subject.tenant_id),
            tenant_id=subject.tenant_id,
            event_type=event,
            payload={
                "subject_user_id": subject.subject_user_id,
                "disposition": str(disposition),
                # The shape of the query, never the rows returned — recording those would
                # copy evidence into the record describing it, growing the trail in
                # proportion to reads and duplicating what it points at.
                "query_shape": {
                    "correlation_id": request.correlation_id,
                    "run_id": request.run_id,
                    "start_time": request.start_time.isoformat() if request.start_time else None,
                    "end_time": request.end_time.isoformat() if request.end_time else None,
                    "limit": request.limit,
                },
                "result_count": len(entries),
                "read_correlation_ids": sorted({e.correlation_id for e in entries}),
            },
        )
    except Exception as exc:
        # A CORE ERROR, not an HTTPException. This raised a FastAPI type from
        # transport-independent code, and `surfaces/mcp/transport.py::_read_evidence` did not
        # catch it — so an unrecordable evidence read answered 503 with a stated reason on the
        # API and escaped as something else entirely on MCP. The failure path had no parity in
        # the one operation whose docstring argues hardest for parity. Found by 022's research
        # while adopting this module's shape; fixed here rather than copied into seven new
        # call sites.
        raise RecordAccessUnavailable(
            "evidence access could not be recorded; the read is refused"
        ) from exc


__all__ = [
    "EVIDENCE_STREAM_PREFIX",
    "EvidenceReadResponse",
    "ReconciliationResponse",
    "build_router",
    "evidence_stream_for",
    "reconcile_evidence_for",
]
