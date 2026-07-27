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

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.audit.schema import AuditEventType
from core.authority.changes import (
    AuthorityChangeEvent,
    BlockedPendingApprovalError,
    ChangeDisposition,
    observe_change,
)
from core.identity.claims import ClaimMapping
from surfaces.api.dependencies import AuditDep, SubjectDep

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
    ) -> JSONResponse:
        """Submit the change for quorum and report what the trust fabric said.

        Deliberately does not wait. Quorum on an authority change is measured in hours by
        design, and holding an HTTP connection open for it would fail on every proxy in
        the path even if it were otherwise acceptable — which FR-015 says it is not.
        """
        correlation_id = f"authority-change:{subject.tenant_id}"
        try:
            event = _submit(subject.subject_user_id, body.mapping)
        except BlockedPendingApprovalError as pending:
            event = observe_change(
                correlation_id=correlation_id,
                controlled_path=CONTROLLED_PATH,
                disposition=ChangeDisposition.REQUESTED,
                identities=[subject.subject_user_id],
                occurred_at=datetime.now(UTC),
                accessor=pending.accessor,
            )

        audit.append_event(
            correlation_id=correlation_id,
            tenant_id=subject.tenant_id,
            event_type=AuditEventType.AUTHORITY_CHANGE_OBSERVED,
            payload=event.public_dict() | {"reason": body.reason},
        )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=ClaimMappingChangeResponse(
                disposition=event.disposition,
                accessor=event.accessor,
            ).model_dump(),
        )

    return router


def _submit(requester: str, mapping: ClaimMapping) -> AuthorityChangeEvent:
    """Hand the change to the trust fabric.

    Always blocked pending approval in this feature: the gate is Vault's Control Groups
    (007), and a surface that could return anything else would be a surface that could
    approve its own request.
    """
    raise BlockedPendingApprovalError(
        f"claim mapping {mapping.claim_name}={mapping.claim_value} -> {mapping.role} "
        f"requested by {requester}",
        accessor=None,
    )


__all__ = [
    "CONTROLLED_PATH",
    "ClaimMappingChangeRequest",
    "ClaimMappingChangeResponse",
    "build_router",
]
