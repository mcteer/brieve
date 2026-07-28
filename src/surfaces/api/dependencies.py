# SPDX-License-Identifier: Apache-2.0
"""Request-scoped dependencies.

The authentication dependency is the **only** way a route obtains a subject. There is no
route-level opt-out and no anonymous path: a route that forgot to depend on it would have
no subject to thread into the core, so it could not start a run or read evidence at all.
That is deliberate — an authentication check that a route can omit is one a route will
eventually omit.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status

from core.audit.query import EvidenceQuery
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from surfaces.api.verification import AuthenticationRefused, TokenVerifier
from surfaces.dispatch.types import RunDispatcher

#: Refusal reasons that are the caller's fault versus the platform's.
#:
#: `idp_unreachable` is 503 rather than 401 on purpose: the caller's credentials may be
#: perfectly good, and telling them their identity is invalid would send them to rotate a
#: token that was never the problem.
_STATUS_BY_REASON = {
    "absent_identity": status.HTTP_401_UNAUTHORIZED,
    "expired_identity": status.HTTP_401_UNAUTHORIZED,
    "unverifiable_identity": status.HTTP_401_UNAUTHORIZED,
    "no_tenant": status.HTTP_403_FORBIDDEN,
    "unmapped_claim": status.HTTP_403_FORBIDDEN,
    "idp_unreachable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _component(request: Request, name: str) -> Any:
    value = getattr(request.app.state, name, None)
    if value is None:  # pragma: no cover - assembly error
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"{name} not configured on this application"
        )
    return value


def current_subject(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedSubject:
    """Establish who is calling, or refuse with nothing executed."""
    verifier: TokenVerifier = _component(request, "token_verifier")
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return verifier.verify(token)
    except AuthenticationRefused as exc:
        raise HTTPException(
            _STATUS_BY_REASON.get(exc.reason_code, status.HTTP_401_UNAUTHORIZED),
            exc.reason_code,
        ) from exc


def run_dispatcher(request: Request) -> RunDispatcher:
    dispatcher: RunDispatcher = _component(request, "run_dispatcher")
    return dispatcher


def evidence_query(request: Request) -> EvidenceQuery:
    query: EvidenceQuery = _component(request, "evidence_query")
    return query


def authority_submitter(request: Request) -> Any:
    return _component(request, "authority_submitter")


def audit_sink(request: Request) -> AuditSink:
    sink: AuditSink = _component(request, "audit_sink")
    return sink


# Annotated aliases rather than `Depends()` in argument defaults. Both work in FastAPI;
# this form is the one that survives linting and reads as a type rather than a value.
SubjectDep = Annotated[AuthenticatedSubject, Depends(current_subject)]
DispatcherDep = Annotated[RunDispatcher, Depends(run_dispatcher)]
EvidenceDep = Annotated[EvidenceQuery, Depends(evidence_query)]
AuditDep = Annotated[AuditSink, Depends(audit_sink)]
AuthoritySubmitterDep = Annotated[Any, Depends(authority_submitter)]


# 011's collaborators, resolved the same way and for the same reason: a route that reached
# for its own handle could be stood up with different security properties than production.
def run_index(request: Request) -> Any:
    return _component(request, "run_index")


def durability(request: Request) -> Any:
    return _component(request, "durability")


def change_requests(request: Request) -> Any:
    return _component(request, "change_requests")


def change_status(request: Request) -> Any:
    return _component(request, "change_status")


def definitions(request: Request) -> Any:
    return _component(request, "definitions")


RunIndexDep = Annotated[Any, Depends(run_index)]
DurabilityDep = Annotated[Any, Depends(durability)]
ChangeRequestsDep = Annotated[Any, Depends(change_requests)]
ChangeStatusDep = Annotated[Any, Depends(change_status)]
DefinitionsDep = Annotated[Any, Depends(definitions)]

__all__ = [
    "AuditDep",
    "AuthoritySubmitterDep",
    "ChangeRequestsDep",
    "ChangeStatusDep",
    "DefinitionsDep",
    "DurabilityDep",
    "RunIndexDep",
    "DispatcherDep",
    "EvidenceDep",
    "SubjectDep",
    "audit_sink",
    "authority_submitter",
    "current_subject",
    "evidence_query",
    "run_dispatcher",
]
