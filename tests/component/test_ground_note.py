# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — every guidance answer states how old its ground is.

**The boundary days are the point.** Wording that changes at 30 and 90 days is wording nobody
notices being off by one, so 29/30/89/90/91 are asserted individually rather than "a stale pin
reads stale". A tier that silently shifted would still pass a row written at 5 and 200 days.

**Two properties matter more than the wording itself**, and both are rows here: the note is
never empty (silence must not come to mean "recent"), and an aged pin never turns an answer
into a decline (an operator who has not run a refresh has not made the platform wrong).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.answering.answer import ANSWERED, DECLINED, Answer, answer_question
from core.answering.corpus import Corpus, Document
from core.answering.ground import (
    GROUND_FRESH_DAYS,
    GROUND_STALE_DAYS,
    UNKNOWN_NOTE,
    describe_ground,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def _pinned(days_ago: int) -> datetime:
    return NOW - timedelta(days=days_ago)


def _note(days_ago: int) -> str:
    return describe_ground(_pinned(days_ago), NOW)


# ------------------------------------------------------------------ the boundaries


def test_the_fresh_tier_holds_up_to_its_last_day() -> None:
    assert GROUND_FRESH_DAYS == 30, "the boundary rows below are written against 30"
    for days in (0, 1, 7, 29):
        note = _note(days)
        assert "may have been published" not in note, f"{days} days read as aging"
        assert "overdue" not in note, f"{days} days read as stale"


def test_the_aging_tier_starts_exactly_at_the_threshold() -> None:
    """29 is fresh, 30 is aging. The off-by-one nobody would notice."""
    assert "may have been published" not in _note(29)
    assert "may have been published" in _note(30)


def test_the_stale_tier_starts_exactly_at_the_threshold() -> None:
    """89 is aging, 90 is stale — and 91 stays stale rather than wrapping."""
    assert GROUND_STALE_DAYS == 90
    assert "may have been published" in _note(89)
    assert "overdue" not in _note(89)
    assert "overdue" in _note(90)
    assert "overdue" in _note(91)
    assert "overdue" in _note(400)


def test_every_tier_states_the_pinned_date_and_the_age() -> None:
    """The tier tunes the framing; the FACT is in all of them, which is what a reader acts on."""
    for days in (0, 1, 15, 30, 89, 90, 365):
        note = _note(days)
        assert _pinned(days).date().isoformat() in note, f"{days} days: no pinned date"
        if days == 0:
            assert "today" in note
        elif days == 1:
            assert "1 day ago" in note
        else:
            assert f"{days} days ago" in note


# ------------------------------------------------------------------ unknown is a disclosure


def test_an_unknown_age_is_disclosed_rather_than_omitted() -> None:
    """The 024-era pin's case. Silence would let a reader assume recency."""
    assert describe_ground(None, NOW) == UNKNOWN_NOTE
    assert "unknown" in UNKNOWN_NOTE.lower()


def test_a_future_pin_reads_as_unknown_not_as_very_fresh() -> None:
    """`load_corpus` already maps this to None; a hand-built Corpus could still get here, and
    "in -3 days" is not a sentence anyone should read."""
    assert describe_ground(NOW + timedelta(days=3), NOW) == UNKNOWN_NOTE


def test_the_note_is_never_empty() -> None:
    """The property that keeps silence from meaning "recent" — the whole reason this exists."""
    for synced_at in (None, NOW, _pinned(1), _pinned(30), _pinned(90), _pinned(9999)):
        assert describe_ground(synced_at, NOW).strip(), f"empty note for {synced_at}"


# ------------------------------------------------------------------ FR-005's teeth


def _corpus(synced_at: datetime | None) -> Corpus:
    document = Document(
        path="/validated-patterns/vault/one",
        url="https://developer.hashicorp.com/validated-patterns/vault/one",
        digest="d" * 64,
        anchors=frozenset({"section"}),
        sections={"section": "Pinned guidance."},
    )
    return Corpus(digest="c" * 64, documents={document.path: document}, synced_at=synced_at)


class _Cites:
    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        return [
            {
                "statement": "The pinned corpus says so.",
                "citations": [{"path": "/validated-patterns/vault/one", "anchor": "section"}],
            }
        ]


def test_an_ancient_pin_still_answers() -> None:
    """FR-005. A decline here would punish the asker for an operator's omission — 024's intent
    is latest-available content, disclosed, not withheld."""
    ancient = _corpus(_pinned(3650))

    answer = answer_question(
        question="What does the guidance say?", corpus=ancient, provider=_Cites()
    )

    assert answer.disposition == ANSWERED
    note = describe_ground(ancient.synced_at, NOW)
    assert "overdue" in note, "a ten-year-old pin should read stale"


def test_the_note_rides_the_answer_object_on_both_dispositions() -> None:
    """The `window_note` shape, consumed (Principle VII): a field on the answer, set by the
    caller that owns the clock — never a second channel, never an audit payload."""
    fresh = Answer(disposition=ANSWERED, corpus_digest="c" * 64, ground_note=_note(3))
    declined = Answer(
        disposition=DECLINED,
        corpus_digest="c" * 64,
        declined_reason="nothing",
        ground_note=_note(3),
    )

    assert fresh.ground_note == declined.ground_note
    assert Answer(disposition=ANSWERED, corpus_digest="c" * 64).ground_note == ""
