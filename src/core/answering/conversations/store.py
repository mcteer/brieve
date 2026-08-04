# SPDX-License-Identifier: Apache-2.0
"""The conversation store — its contract, and the in-memory twin the hermetic lanes use.

**Owner and tenant are parameters on every method, not a filter callers remember to apply.**
FR-012 and FR-013 say a conversation is reachable only by the person who created it, within
their tenant, and the way to make that true rather than customary is to give the store no
method that can be called without both. There is no `get(conversation_id)`.

**A miss and a refusal are the same answer here.** `get` returns `None` for "no such
conversation", "somebody else's", and "another tenant's" alike — the surface turns all three
into one 404 with one wording, because a different response for "exists but not yours" tells
the caller it exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from core.answering.conversations.records import (
    ConversationRecord,
    ExchangeDisposition,
    ExchangeRecord,
    title_from,
)


class ConversationStore(Protocol):
    """What both stores do. The surfaces hold this, never a concrete store."""

    def start(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> tuple[ConversationRecord, ExchangeRecord]:
        """Create a conversation from its first ask. Never creates an empty one."""
        ...

    def append(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> ExchangeRecord | None:
        """Add an exchange. `None` when the conversation is not this subject's."""
        ...

    def get(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str
    ) -> tuple[ConversationRecord, tuple[ExchangeRecord, ...]] | None:
        """A conversation and its exchanges in order, or `None`."""
        ...

    def recent(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str, limit: int
    ) -> tuple[ExchangeRecord, ...]:
        """The most recent exchanges, oldest-first, for context assembly."""
        ...

    def list_for(self, *, tenant_id: str, subject_user_id: str) -> tuple[ConversationRecord, ...]:
        """This subject's conversations, most recently used first."""
        ...

    def delete(self, *, conversation_id: str, tenant_id: str, subject_user_id: str) -> bool:
        """Remove a conversation and its exchanges. False when it was not theirs."""
        ...


class MemoryConversationStore:
    """The hermetic twin. Same contract, same scoping, no database.

    Used where the harness already fakes a collaborator. The Postgres store is what runs in
    conformance and in the estate, because a store tested only against a dictionary is a
    store whose SQL nobody has run.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, ConversationRecord] = {}
        self._exchanges: dict[str, list[ExchangeRecord]] = {}

    def _own(
        self, conversation_id: str, tenant_id: str, subject_user_id: str
    ) -> ConversationRecord | None:
        record = self._conversations.get(conversation_id)
        if record is None:
            return None
        if record.tenant_id != tenant_id or record.subject_user_id != subject_user_id:
            return None
        return record

    def start(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> tuple[ConversationRecord, ExchangeRecord]:
        now = datetime.now(UTC)
        conversation = ConversationRecord(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            subject_user_id=subject_user_id,
            title=title_from(question),
            created_at=now,
            last_asked_at=now,
            exchanges=1,
        )
        exchange = ExchangeRecord(
            conversation_id=conversation_id,
            seq=1,
            question=question,
            source=source,
            disposition=disposition,
            outcome=outcome,
            asked_at=now,
        )
        self._conversations[conversation_id] = conversation
        self._exchanges[conversation_id] = [exchange]
        return conversation, exchange

    def append(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> ExchangeRecord | None:
        conversation = self._own(conversation_id, tenant_id, subject_user_id)
        if conversation is None:
            return None
        now = datetime.now(UTC)
        held = self._exchanges.setdefault(conversation_id, [])
        exchange = ExchangeRecord(
            conversation_id=conversation_id,
            seq=len(held) + 1,
            question=question,
            source=source,
            disposition=disposition,
            outcome=outcome,
            asked_at=now,
        )
        held.append(exchange)
        self._conversations[conversation_id] = ConversationRecord(
            conversation_id=conversation.conversation_id,
            tenant_id=conversation.tenant_id,
            subject_user_id=conversation.subject_user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            last_asked_at=now,
            exchanges=len(held),
        )
        return exchange

    def get(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str
    ) -> tuple[ConversationRecord, tuple[ExchangeRecord, ...]] | None:
        conversation = self._own(conversation_id, tenant_id, subject_user_id)
        if conversation is None:
            return None
        return conversation, tuple(self._exchanges.get(conversation_id, ()))

    def recent(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str, limit: int
    ) -> tuple[ExchangeRecord, ...]:
        if self._own(conversation_id, tenant_id, subject_user_id) is None:
            return ()
        held = self._exchanges.get(conversation_id, [])
        return tuple(held[-limit:]) if limit > 0 else ()

    def list_for(self, *, tenant_id: str, subject_user_id: str) -> tuple[ConversationRecord, ...]:
        mine = [
            record
            for record in self._conversations.values()
            if record.tenant_id == tenant_id and record.subject_user_id == subject_user_id
        ]
        mine.sort(key=lambda r: (r.last_asked_at, r.conversation_id), reverse=True)
        return tuple(mine)

    def delete(self, *, conversation_id: str, tenant_id: str, subject_user_id: str) -> bool:
        if self._own(conversation_id, tenant_id, subject_user_id) is None:
            return False
        self._conversations.pop(conversation_id, None)
        self._exchanges.pop(conversation_id, None)
        return True


__all__ = ["ConversationStore", "MemoryConversationStore"]
