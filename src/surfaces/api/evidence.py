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

from core.audit.query import EvidenceQuery, EvidenceQueryRequest
from core.audit.schema import AuditEntry, AuditEventType, EvidenceDisposition
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import AuditDep, EvidenceDep, SubjectDep

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
) -> tuple[list[AuditEntry], EvidenceDisposition]:
    """The governed read, independent of transport.

    Extracted from the route so MCP reaches *this* rather than reimplementing it. ADR-0033
    asks for the same verdict on every transport, and two implementations agreeing by
    inspection would make that a measure of how carefully they were written — which is
    exactly what a conformance row cannot check.
    """
    request = EvidenceQueryRequest(
        # From the subject. Not accepted from any caller, on any transport.
        tenant_id=subject.tenant_id,
        correlation_id=correlation_id,
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    entries = query.search(request)
    disposition = _disposition(entries, request, query)
    if disposition is EvidenceDisposition.OUT_OF_SCOPE:
        entries = []

    _record_access(
        audit=audit,
        subject=subject,
        request=request,
        entries=entries,
        disposition=disposition,
    )
    return entries, disposition


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
        return EvidenceReadResponse(entries=entries, count=len(entries))

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
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "evidence access could not be recorded; the read is refused",
        ) from exc


__all__ = [
    "EVIDENCE_STREAM_PREFIX",
    "EvidenceReadResponse",
    "build_router",
    "evidence_stream_for",
]
