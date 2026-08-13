# SPDX-License-Identifier: Apache-2.0
"""046 FR-008 — ask_answered stays content-free after the primary-answer shape change."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.answering.corpus import load_corpus
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

CORPUS = load_corpus()
CITED_PATH, CITED_ANCHOR = next(
    (document.path, sorted(document.anchors)[0])
    for document in CORPUS.documents.values()
    if document.anchors
)


class _Answers:
    def answer(self, question: str, corpus: Any) -> list[dict[str, Any]]:
        return [
            {
                "statement": "The pattern documents this distinctive prose phrase.",
                "citations": [{"path": CITED_PATH, "anchor": CITED_ANCHOR}],
            }
        ]


def test_ask_answered_omits_question_and_answer_text() -> None:
    surface = surface_under_test(
        ask_provider=_Answers(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    question = "How does this work with retention of 400 days?"
    TestClient(surface.app).post("/ask", json={"question": question}, headers=surface.bearer())

    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert len(asks) == 1
    payload = asks[0].payload
    blob = str(payload)
    assert question not in blob
    assert "distinctive prose phrase" not in blob
    assert "primary_answer" not in payload
    assert payload["disposition"] == "answered"
    assert payload["corpus_digest"]
    assert payload["cell"]
    assert payload.get("relevance_gate") in {"checked", "disabled_by_admin", ""}
