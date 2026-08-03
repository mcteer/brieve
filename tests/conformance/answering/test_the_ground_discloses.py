# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — SC-001, asserted through the path rather than at the composer.

`test_ground_note.py` proves `describe_ground` words correctly. That is not the claim SC-001
makes. The claim is that **the note reaches the person reading the answer**, which is a
property of the serialized payload — and the four prior features that shipped a gate matching
prose instead of code are the reason this is asserted at the surface, over HTTP, rather than
by reading `ask.py`.

Both dispositions carry it: a decline rests on the same corpus an answer would have, and a
reader deciding whether to look elsewhere is exactly who needs the ground's age.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from core.answering.corpus import Corpus, Document
from core.answering.ground import UNKNOWN_NOTE
from surfaces.api.ask import ask_for
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

MODEL = "anthropic/claude-sonnet@5"
NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

DOCUMENT = Document(
    path="/validated-patterns/vault/one",
    url="https://developer.hashicorp.com/validated-patterns/vault/one",
    digest="d" * 64,
    anchors=frozenset({"section"}),
    sections={"section": "Pinned guidance."},
)


def _corpus(synced_at: datetime | None) -> Corpus:
    return Corpus(digest="c" * 64, documents={DOCUMENT.path: DOCUMENT}, synced_at=synced_at)


class _Cites:
    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return [
            {
                "statement": "The pinned corpus says so.",
                "citations": [{"path": DOCUMENT.path, "anchor": "section"}],
            }
        ]


class _CitesNothing:
    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return []


def _payload(provider: object, synced_at: datetime | None, now: datetime = NOW) -> dict[str, Any]:
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )
    return ask_for(
        question="What does the guidance say about this pattern?",
        subject=surface.subject(),
        corpus=_corpus(synced_at),
        provider=provider,
        audit=surface.audit,
        model=MODEL,
        now=now,
    )


def test_an_answer_states_how_old_its_ground_is() -> None:
    """SC-001, the answered half."""
    payload = _payload(_Cites(), NOW - timedelta(days=5))

    assert payload["disposition"] == "answered"
    assert payload["ground_note"], "an answer shipped without stating its ground's age"
    assert "2026-07-29" in payload["ground_note"]


def test_a_decline_states_it_too() -> None:
    """The reader deciding whether to look elsewhere is the one who most needs the age."""
    payload = _payload(_CitesNothing(), NOW - timedelta(days=5))

    assert payload["disposition"] == "declined"
    assert payload["ground_note"], "a decline shipped without stating its ground's age"


def test_the_pin_that_predates_sync_times_answers_and_says_so() -> None:
    """FR-009 — the row that lets this feature merge before the first re-sync ever runs.

    The committed corpus has no timestamp and never will. It must answer, and it must not
    imply recency by saying nothing.
    """
    payload = _payload(_Cites(), None)

    assert payload["disposition"] == "answered"
    assert payload["ground_note"] == UNKNOWN_NOTE


def test_an_ancient_pin_answers_rather_than_declining() -> None:
    """FR-005 through the path: the tier escalates the wording, never the disposition."""
    payload = _payload(_Cites(), NOW - timedelta(days=400))

    assert payload["disposition"] == "answered"
    assert "overdue" in payload["ground_note"]


def test_the_served_route_carries_the_note_over_http() -> None:
    """Over the wire, because a field the route drops is a field nobody reads.

    The route loads the committed corpus, so this asserts the deployed shape: unknown age,
    disclosed, on a real HTTP response.
    """
    surface = surface_under_test(
        ask_provider=_Cites(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )

    response = TestClient(surface.app).post(
        "/ask",
        json={"question": "What does the validated pattern say about Vault namespaces?"},
        headers=surface.bearer(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "ground_note" in body, (
        "the served guidance payload carries no ground_note — the composer working is not the "
        "same claim as the reader being told"
    )
    assert body["ground_note"].strip()


def test_the_estate_window_note_is_untouched() -> None:
    """The addition sits beside 029's disclosure rather than displacing it."""
    from core.answering.estate import describe_window

    assert describe_window({}) == ""
