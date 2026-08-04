# SPDX-License-Identifier: Apache-2.0
"""What a conversation and an exchange are, as records.

**Deliberately not imported from `core.threads`.** The shapes rhyme and `title_from` is very
nearly the same ten lines, and copying it is the point: ADR-0039 separates asking from acting,
and a shared vocabulary module between the two surfaces is the first step toward one store,
one table, and an ask that can act. The cost of the duplication is ten lines; the cost of the
coupling is the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExchangeDisposition(StrEnum):
    """What came back. Mirrors the ask surface's own vocabulary, not the thread's.

    A thread turn is `dispatched`/`declined`/`refused` — it may have started something. An
    exchange never did, so `answered` is the positive case and there is no fourth state.
    """

    ANSWERED = "answered"
    DECLINED = "declined"
    REFUSED = "refused"


@dataclass(frozen=True)
class ConversationRecord:
    """A conversation's spine. Owned by one subject in one tenant, deletable by them."""

    conversation_id: str
    tenant_id: str
    subject_user_id: str
    #: Derived from the first question, once. No rename operation exists (035 defers it), so
    #: this cannot drift from what was actually asked.
    title: str
    created_at: datetime
    #: Bumped on every append, so the list shows the conversation just used at the top.
    last_asked_at: datetime
    #: How many exchanges it holds. Carried on the record because the list needs it and a
    #: per-row count query for a list of conversations is the classic N+1.
    exchanges: int = 0


@dataclass(frozen=True)
class ExchangeRecord:
    """One question and what came back, as the transcript remembers it."""

    conversation_id: str
    seq: int
    question: str
    #: What the ask actually consulted — `guidance` or `estate`. Stored rather than recomputed
    #: because a signal-less follow-up INHERITS it, and re-deriving it later would make
    #: routing depend on a vocabulary that has since changed.
    source: str
    disposition: ExchangeDisposition
    #: The response body the surface returned, verbatim. Reopening re-renders what the person
    #: saw rather than re-deriving it against a corpus that may since have been re-pinned.
    outcome: dict[str, Any]
    asked_at: datetime


def title_from(question: str, *, limit: int = 60) -> str:
    """A conversation's title, taken once from its first question.

    Whitespace-collapsed and cut at a word boundary where one is near enough to the limit.
    Display only — nothing reads it back, and no operation changes it.
    """
    collapsed = " ".join(question.split())
    if len(collapsed) <= limit:
        return collapsed
    cut = collapsed[:limit]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip() + "…"


__all__ = [
    "ConversationRecord",
    "ExchangeDisposition",
    "ExchangeRecord",
    "title_from",
]
