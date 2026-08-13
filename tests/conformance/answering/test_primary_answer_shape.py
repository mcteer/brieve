# SPDX-License-Identifier: Apache-2.0
"""046 S1 — answered guidance carries primary_answer and citations."""

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
                "statement": "The pattern documents this.",
                "citations": [{"path": CITED_PATH, "anchor": CITED_ANCHOR}],
            }
        ]


def test_row_s1_answered_guidance_has_primary_answer_and_citations() -> None:
    surface = surface_under_test(
        ask_provider=_Answers(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    body = (
        TestClient(surface.app)
        .post("/ask", json={"question": "How does this work?"}, headers=surface.bearer())
        .json()
    )

    assert body["disposition"] == "answered"
    assert body["source"] == "guidance"
    assert isinstance(body["primary_answer"], str) and body["primary_answer"].strip()
    assert isinstance(body["citations"], list) and body["citations"]
    assert "claims" not in body
