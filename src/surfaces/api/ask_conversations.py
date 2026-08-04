# SPDX-License-Identifier: Apache-2.0
"""A person's own ask conversations — listed, reopened, deleted.

**Three operations that grant nothing.** A conversation groups questions somebody already
asked and already had answered; reading one back gives them no source, no model and no scope
that the asks themselves did not. That is why this surface has no authority checks of its own
beyond identity: there is no capability here to gate.

**Owner and tenant scope every call, in the store rather than here.** The store has no method
that can be called without both, so a route cannot forget — and every miss, whether the
conversation is absent, another subject's, or another tenant's, comes back as the same 404
with the same wording. A distinct answer for "exists but not yours" tells the caller it exists.

**An unreadable store is 503, never an empty list** (FR-008's fail-closed half). Answering
`[]` when nobody could look tells a person they have no conversations, which is a claim about
their history that the platform is in no position to make.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from core.answering.conversations.postgres import ConversationStoreError
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import SubjectDep

#: One wording for every miss. See the module docstring.
NO_SUCH_CONVERSATION = "no_such_conversation"


class ConversationView(BaseModel):
    """A conversation as the list shows it. **No exchange bodies** — the list is a list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str
    title: str
    last_asked_at: str
    exchanges: int


class ConversationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversations: list[ConversationView]


class ExchangeView(BaseModel):
    """One exchange, with the outcome the person actually saw."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seq: int
    question: str
    source: str
    disposition: str
    #: The response body this ask returned, verbatim. Reopening re-renders what was seen rather
    #: than re-deriving it against a corpus that may since have been re-pinned.
    outcome: dict[str, Any]
    asked_at: str


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str
    title: str
    exchanges: list[ExchangeView]


def list_conversations(*, subject: AuthenticatedSubject, store: Any) -> ConversationListResponse:
    """Transport-independent, so MCP reaches this rather than reimplementing it (ADR-0033)."""
    if store is None:
        return ConversationListResponse(conversations=[])
    records = store.list_for(tenant_id=subject.tenant_id, subject_user_id=subject.subject_user_id)
    return ConversationListResponse(
        conversations=[
            ConversationView(
                conversation_id=record.conversation_id,
                title=record.title,
                last_asked_at=record.last_asked_at.isoformat(),
                exchanges=record.exchanges,
            )
            for record in records
        ]
    )


def read_conversation(
    *, conversation_id: str, subject: AuthenticatedSubject, store: Any
) -> ConversationDetailResponse | None:
    """One conversation and every exchange in it, or `None` for any kind of miss."""
    if store is None:
        return None
    found = store.get(
        conversation_id=conversation_id,
        tenant_id=subject.tenant_id,
        subject_user_id=subject.subject_user_id,
    )
    if found is None:
        return None
    conversation, exchanges = found
    return ConversationDetailResponse(
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        exchanges=[
            ExchangeView(
                seq=exchange.seq,
                question=exchange.question,
                source=exchange.source,
                disposition=str(exchange.disposition),
                outcome=exchange.outcome,
                asked_at=exchange.asked_at.isoformat(),
            )
            for exchange in exchanges
        ],
    )


def remove_conversation(*, conversation_id: str, subject: AuthenticatedSubject, store: Any) -> bool:
    """Delete, and **touch no evidence** (FR-023).

    The store holds no reference to the audit tables, so this cannot alter a record even by
    accident — the guarantee is structural rather than careful.
    """
    if store is None:
        return False
    removed: bool = store.delete(
        conversation_id=conversation_id,
        tenant_id=subject.tenant_id,
        subject_user_id=subject.subject_user_id,
    )
    return removed


def build_router(*, conversations: Any = None) -> APIRouter:
    router = APIRouter(tags=["ask-conversations"])

    @router.get("/ask-conversations", response_model=ConversationListResponse)
    def get_conversations(subject: SubjectDep) -> ConversationListResponse:
        """This subject's own conversations, most recently used first."""
        try:
            return list_conversations(subject=subject, store=conversations)
        except ConversationStoreError as unavailable:
            # NEVER an empty list. See the module docstring.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "your conversations could not be read just now; nothing is lost — try again in "
                "a moment.",
            ) from unavailable

    @router.get("/ask-conversations/{conversation_id}", response_model=ConversationDetailResponse)
    def get_conversation(conversation_id: str, subject: SubjectDep) -> ConversationDetailResponse:
        """One conversation, as the person left it."""
        try:
            found = read_conversation(
                conversation_id=conversation_id, subject=subject, store=conversations
            )
        except ConversationStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "that conversation could not be read just now; nothing is lost — try again in "
                "a moment.",
            ) from unavailable
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NO_SUCH_CONVERSATION)
        return found

    @router.delete("/ask-conversations/{conversation_id}", status_code=204)
    def delete_conversation(conversation_id: str, subject: SubjectDep) -> Response:
        """Remove it from this person's view. The platform's own record is untouched."""
        try:
            removed = remove_conversation(
                conversation_id=conversation_id, subject=subject, store=conversations
            )
        except ConversationStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "that conversation could not be deleted just now; nothing is lost — try again "
                "in a moment.",
            ) from unavailable
        if not removed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NO_SUCH_CONVERSATION)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


__all__ = [
    "NO_SUCH_CONVERSATION",
    "ConversationDetailResponse",
    "ConversationListResponse",
    "build_router",
    "list_conversations",
    "read_conversation",
    "remove_conversation",
]
