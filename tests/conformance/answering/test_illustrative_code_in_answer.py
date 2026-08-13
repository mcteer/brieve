# SPDX-License-Identifier: Apache-2.0
"""046 N2 / FR-005 — illustrative code in primary_answer; uncited config never ships."""

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

_FENCE = (
    "Here is a sketch grounded in the cited section:\n\n"
    '```hcl\nresource "aws_instance" "example" {}\n```'
)


class _Coded:
    def answer(self, question: str, corpus: Any) -> list[dict[str, Any]]:
        return [
            {
                "statement": _FENCE,
                "citations": [{"path": CITED_PATH, "anchor": CITED_ANCHOR}],
            }
        ]


class _UncitedCode:
    def answer(self, question: str, corpus: Any) -> list[dict[str, Any]]:
        return [
            {
                "statement": _FENCE,
                "citations": [{"path": "/invented/module", "anchor": "main"}],
            }
        ]


def test_row_n2_fenced_code_ships_in_primary_answer_with_no_side_effects() -> None:
    surface = surface_under_test(
        ask_provider=_Coded(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    body = (
        TestClient(surface.app)
        .post(
            "/ask",
            json={"question": "Give me a terraform template for this pattern."},
            headers=surface.bearer(),
        )
        .json()
    )

    assert body["disposition"] == "answered"
    assert "```hcl" in body["primary_answer"]
    assert body["citations"]
    # Ask never dispatches authoring — no tools on the surface, no PR side channel.
    assert "author_file" not in body
    assert "pull_request" not in body


def test_row_uncited_code_does_not_ship_answered() -> None:
    surface = surface_under_test(
        ask_provider=_UncitedCode(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    body = (
        TestClient(surface.app)
        .post(
            "/ask",
            json={"question": "Give me a terraform template for this pattern."},
            headers=surface.bearer(),
        )
        .json()
    )

    assert body["disposition"] == "declined"
    assert "primary_answer" not in body
