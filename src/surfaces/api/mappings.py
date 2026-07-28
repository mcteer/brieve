# SPDX-License-Identifier: Apache-2.0
"""Claim-to-role mapping changes (FR-013).

Changing which claims grant which roles is an **authority change**, gated by quorum
(ADR-0016), not an administrative edit. Without that gating, anyone with configuration
access grants themselves a role rather than being granted one — which is the escalation
path ADR-0033 closes by name.

The surface **requests** the change and reports the disposition. It does not decide it, and
there is no code path here by which it could: the decision belongs to the trust fabric's
own Control Groups, and this observes what they decided.

The status code carries the load. A pending change is **202 Accepted**, never 403. 007's
seam already names the trap in its docstring — *"The operation is queued for approval. This
is not a denial."* — and at an HTTP surface the wrong choice is sticky: a client that reads
403 stops asking, so a change approved twenty minutes later is never collected, and the
operator concludes the request was refused when it was in fact granted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.authority.changes import (
    AuthorityChangeEvent,
    BlockedPendingApprovalError,
    ChangeDisposition,
    observe_change,
)
from core.identity.claims import ClaimMapping
from core.identity.types import AuthenticatedSubject
from core.runs.changes import (
    ChangeRequestRecord,
    ChangeRequestStore,
    CollectedDisposition,
    authorize_collect,
)
from core.runs.refusals import OperationRefused
from surfaces.api.authority_submit import AuthorityChangeRefused, AuthoritySubmitUnavailable
from surfaces.api.dependencies import (
    AuditDep,
    AuthoritySubmitterDep,
    ChangeRequestsDep,
    ChangeStatusDep,
    SubjectDep,
)

CONTROLLED_PATH = "identity/claim-mappings"


class ClaimMappingChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping: ClaimMapping
    reason: str = Field(min_length=1)


class ClaimMappingChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: ChangeDisposition
    #: The trust fabric's handle for the pending request. Opaque, and not a credential —
    #: it is how the requester collects the outcome later rather than holding a connection.
    accessor: str | None = None
    controlled_path: str = CONTROLLED_PATH


def submit_mapping_change(
    *,
    submitter: Any,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    mapping: ClaimMapping,
    reason: str,
    change_requests: ChangeRequestStore | None = None,
) -> AuthorityChangeEvent:
    """Submit the change and record what the trust fabric decided.

    Transport-independent, so MCP reaches this rather than reimplementing it — the same
    reason the evidence read was extracted. Raises `AuthoritySubmitUnavailable` when the
    fabric is unreachable, which each transport turns into its own shape of 503: failing
    closed on the CHANGE, and only on the change. Runs already holding authority are
    untouched, because failing closed on the wrong thing here would halt the platform
    during a Vault blip.
    """
    correlation_id = f"authority-change:{subject.tenant_id}"
    accessor: str | None = None
    try:
        disposition = submitter.submit(requester=subject.subject_user_id, mapping=mapping)
    except BlockedPendingApprovalError as pending:
        disposition = ChangeDisposition.REQUESTED
        accessor = pending.accessor
    except AuthorityChangeRefused:
        disposition = ChangeDisposition.DENIED

    if accessor is not None and change_requests is not None:
        # Recorded the moment it exists, before it is returned. 008 handed the accessor to
        # the caller and stored nothing, which is why nothing could collect the outcome —
        # and why anyone holding an accessor could have polled anything, since the fabric
        # answers whoever presents one. This record is what makes collect tenant-scoped.
        change_requests.record(
            ChangeRequestRecord(
                accessor=accessor,
                requester=subject.subject_user_id,
                tenant_id=subject.tenant_id,
                claim_name=mapping.claim_name,
                claim_value=mapping.claim_value,
                role=mapping.role,
                submitted_at=datetime.now(UTC),
            )
        )

    event = observe_change(
        correlation_id=correlation_id,
        controlled_path=CONTROLLED_PATH,
        disposition=disposition,
        identities=[subject.subject_user_id],
        occurred_at=datetime.now(UTC),
        accessor=accessor,
    )
    audit.append_event(
        correlation_id=correlation_id,
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.AUTHORITY_CHANGE_OBSERVED,
        payload=event.public_dict() | {"reason": reason},
    )
    return event


def collect_mapping_change(
    *,
    accessor: str,
    subject: AuthenticatedSubject,
    change_requests: ChangeRequestStore,
    change_status: Any,
    audit: AuditSink,
) -> CollectedDisposition:
    """What became of a change this subject submitted.

    Transport-independent, so MCP reaches this rather than reimplementing it — and so the
    tenant check happens in exactly one place. Two lookups, in this order and not the
    reverse: **our record first**, because it decides whether this caller may ask at all,
    and only then the fabric, which would answer anyone.

    Reading a disposition never advances one. That holds because this function knows only
    how to ask `sys/control-group/request`; authorizing is a different endpoint it cannot
    call. FR-002 by absent capability rather than by discipline.
    """
    record = authorize_collect(
        change_requests.get(accessor=accessor, tenant_id=subject.tenant_id),
        subject_user_id=subject.subject_user_id,
    )
    disposition: CollectedDisposition = change_status.status_of(record.accessor)

    # Audited like every other read of governed state (FR-017). Collecting is a governance
    # decision being observed, and 008 established that observing evidence is itself
    # evidence.
    audit.append_event(
        correlation_id=f"authority-change:{subject.tenant_id}",
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.AUTHORITY_CHANGE_OBSERVED,
        payload={
            "accessor": record.accessor,
            "disposition": disposition.disposition,
            "collected_by": subject.subject_user_id,
            "outcome": "collect",
        },
    )
    return disposition


def build_router() -> APIRouter:
    router = APIRouter(tags=["authority"])

    @router.post(
        "/claim-mappings",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ClaimMappingChangeResponse,
    )
    def request_mapping_change(
        body: ClaimMappingChangeRequest,
        subject: SubjectDep,
        audit: AuditDep,
        submitter: AuthoritySubmitterDep,
    ) -> JSONResponse:
        """Submit the change for quorum and report what the trust fabric said.

        Deliberately does not wait. Quorum on an authority change is measured in hours by
        design, and holding an HTTP connection open for it would fail on every proxy in
        the path even if it were otherwise acceptable — which FR-015 says it is not.
        """
        try:
            event = submit_mapping_change(
                submitter=submitter,
                audit=audit,
                subject=subject,
                mapping=body.mapping,
                reason=body.reason,
            )
        except AuthoritySubmitUnavailable as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "the trust fabric is unreachable; the change was not submitted",
            ) from exc

        # 202 for requested AND approved; 403 only for an outright denial. A pending
        # change must never read as a refusal — a client that sees 403 stops asking, so a
        # change approved twenty minutes later is never collected.
        code = (
            status.HTTP_403_FORBIDDEN
            if event.disposition is ChangeDisposition.DENIED
            else status.HTTP_202_ACCEPTED
        )
        return JSONResponse(
            status_code=code,
            content=ClaimMappingChangeResponse(
                disposition=event.disposition,
                accessor=event.accessor,
            ).model_dump(),
        )

    @router.get("/claim-mappings/{accessor}")
    def collect_change(
        accessor: str,
        subject: SubjectDep,
        audit: AuditDep,
        changes: ChangeRequestsDep,
        status_source: ChangeStatusDep,
    ) -> JSONResponse:
        """Report what became of a change this subject submitted.

        The operation 008's own reasoning called for and did not ship: it returned 202 so
        clients would keep asking, and gave them nothing to ask.
        """
        try:
            disposition = collect_mapping_change(
                accessor=accessor,
                subject=subject,
                change_requests=changes,
                change_status=status_source,
                audit=audit,
            )
        except OperationRefused as refused:
            # `not_permitted` says why; everything else answers 404 regardless of whether
            # the record was absent or another tenant's. A response that distinguished
            # them would let anyone confirm an accessor exists somewhere else.
            code = (
                status.HTTP_403_FORBIDDEN
                if refused.is_visible_to_caller
                else status.HTTP_404_NOT_FOUND
            )
            raise HTTPException(code, "no such change request") from refused

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "accessor": disposition.accessor,
                "disposition": disposition.disposition,
                "approvals": disposition.approvals,
                "required": disposition.required,
            },
        )

    return router


__all__ = [
    "CONTROLLED_PATH",
    "ClaimMappingChangeRequest",
    "ClaimMappingChangeResponse",
    "build_router",
]
