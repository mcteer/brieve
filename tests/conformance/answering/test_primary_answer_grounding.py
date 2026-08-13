# SPDX-License-Identifier: Apache-2.0
"""046 S2/S3 — answered guidance never ships unresolvable citations."""

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


class _CitesNothingReal:
    def answer(self, question: str, corpus: Any) -> list[dict[str, Any]]:
        return [
            {
                "statement": "Retention should be set to 400 days.",
                "citations": [{"path": "/validated-patterns/vault/retention", "anchor": "policy"}],
            }
        ]


def _ask(provider: object) -> dict[str, Any]:
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    response = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_row_s3_unresolvable_citations_do_not_ship_answered() -> None:
    body = _ask(_CitesNothingReal())

    assert body["disposition"] == "declined"
    assert "primary_answer" not in body
    assert "citations" not in body


def test_row_s2_answered_guidance_citations_resolve() -> None:
    body = _ask(_Answers())

    assert body["disposition"] == "answered"
    assert body["primary_answer"]
    assert body["citations"]
    for citation in body["citations"]:
        assert citation["url"].startswith("https://")
        assert "#" in citation["url"]
