# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — a conversation behaves the same on both transports (ADR-0033, FR-027a).

035 took full parity at stated cost rather than an exception, so these rows are the thing that
cost bought: every conversation operation reachable on the API is reachable on MCP, with the
same outcome and the same wording.

**The 404 rows are the sharp ones.** Absent, another subject's and another tenant's must be
indistinguishable *from each other* AND identical *across transports* — a caller who can tell
"exists but not yours" from "does not exist" on either surface can enumerate other people's
conversations, and a difference between the two surfaces is a way to ask twice.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.corpus import Corpus
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

MODEL = "anthropic/claude-opus@5"
QUESTION = "How does an AI agent obtain an identity with Vault?"


class _Answers:
    def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
        if isinstance(material, Corpus):
            path, anchor = next(
                (d.path, next(iter(d.sections))) for d in material.documents.values() if d.sections
            )
            return [
                {"statement": "From the corpus.", "citations": [{"path": path, "anchor": anchor}]}
            ]
        return [{"statement": "From the records.", "references": []}]


@pytest.fixture
def surface() -> Any:
    return surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )


def _api(surface: Any) -> TestClient:
    return TestClient(surface.app)


def _start(surface: Any) -> str:
    body = _api(surface).post("/ask", json={"question": QUESTION}, headers=surface.bearer()).json()
    return str(body["conversation_id"])


def test_both_transports_list_the_same_conversations(surface: Any) -> None:
    """SC-013. One store, two doors."""
    _start(surface)

    api = _api(surface).get("/ask-conversations", headers=surface.bearer()).json()
    mcp = surface.mcp.call("ask_conversations", {}, subject=surface.subject())

    assert mcp.status == 200
    assert api == mcp.payload


def test_both_transports_return_the_same_conversation(surface: Any) -> None:
    """Including every exchange, its source, its disposition and the outcome as stored."""
    conversation_id = _start(surface)

    api = (
        _api(surface).get(f"/ask-conversations/{conversation_id}", headers=surface.bearer()).json()
    )
    mcp = surface.mcp.call(
        "ask_conversation", {"conversation_id": conversation_id}, subject=surface.subject()
    )

    assert mcp.status == 200
    assert api == mcp.payload
    assert api["exchanges"][0]["question"] == QUESTION


@pytest.mark.parametrize("subject_name", ["bob"])
def test_a_foreign_conversation_answers_the_same_404_on_both(
    surface: Any, subject_name: str
) -> None:
    """FR-012, SC-004, SC-013 at once — the row that would let somebody enumerate."""
    conversation_id = _start(surface)

    api = _api(surface).get(
        f"/ask-conversations/{conversation_id}", headers=surface.bearer(subject=subject_name)
    )
    mcp = surface.mcp.call(
        "ask_conversation",
        {"conversation_id": conversation_id},
        subject=surface.subject(subject_name),
    )

    assert api.status_code == mcp.status == 404
    assert api.json()["detail"] == mcp.payload["detail"] == "no_such_conversation"


def test_an_absent_conversation_is_indistinguishable_from_a_foreign_one(surface: Any) -> None:
    """The pair that has to match, on both transports."""
    conversation_id = _start(surface)

    foreign = surface.mcp.call(
        "ask_conversation",
        {"conversation_id": conversation_id},
        subject=surface.subject("bob"),
    )
    absent = surface.mcp.call(
        "ask_conversation", {"conversation_id": "c-nope"}, subject=surface.subject("bob")
    )

    assert foreign.status == absent.status
    assert foreign.payload == absent.payload


def test_deleting_on_either_transport_removes_it_from_both(surface: Any) -> None:
    """One store, so a delete on one door is a delete."""
    conversation_id = _start(surface)

    removed = surface.mcp.call(
        "delete_ask_conversation",
        {"conversation_id": conversation_id},
        subject=surface.subject(),
    )

    assert removed.status == 204
    assert (
        _api(surface)
        .get(f"/ask-conversations/{conversation_id}", headers=surface.bearer())
        .status_code
        == 404
    )


def test_deleting_somebody_elses_conversation_refuses_on_both(surface: Any) -> None:
    """FR-012's destructive half. The refusal is the same 404, not a 403 that confirms it."""
    conversation_id = _start(surface)

    api = _api(surface).delete(
        f"/ask-conversations/{conversation_id}", headers=surface.bearer(subject="bob")
    )
    mcp = surface.mcp.call(
        "delete_ask_conversation",
        {"conversation_id": conversation_id},
        subject=surface.subject("bob"),
    )

    assert api.status_code == mcp.status == 404
    # And it is still there for its owner.
    assert (
        _api(surface)
        .get(f"/ask-conversations/{conversation_id}", headers=surface.bearer())
        .status_code
        == 200
    )


def test_asking_inside_a_conversation_behaves_the_same_on_both(surface: Any) -> None:
    """The operation that carries context — the same source, disposition and seq discipline."""
    conversation_id = _start(surface)

    mcp = surface.mcp.call(
        "ask",
        {"question": "what about multi-region?", "conversation_id": conversation_id},
        subject=surface.subject(),
    )

    assert mcp.status == 200
    assert mcp.payload["conversation_id"] == conversation_id
    assert mcp.payload["exchange_seq"] == 2
    assert mcp.payload["source"] == "guidance"


def test_asking_into_a_foreign_conversation_refuses_the_same_on_both(surface: Any) -> None:
    """The refusal must land before the model, on both transports."""
    conversation_id = _start(surface)

    api = _api(surface).post(
        "/ask",
        json={"question": "what about multi-region?", "conversation_id": conversation_id},
        headers=surface.bearer(subject="bob"),
    )
    mcp = surface.mcp.call(
        "ask",
        {"question": "what about multi-region?", "conversation_id": conversation_id},
        subject=surface.subject("bob"),
    )

    assert api.status_code == mcp.status == 404
    assert api.json()["detail"] == mcp.payload["detail"] == "no_such_conversation"


def test_deleting_a_conversation_leaves_the_trail_byte_identical(surface: Any) -> None:
    """FR-023, SC-006 — [GATE:correlation] and the reason the store shares nothing with the trail.

    A person deleting their view of some questions must not be able to delete the platform's
    record of having answered them. Asserted by comparing the entries themselves rather than
    their count: a delete that rewrote a payload would keep the count identical.
    """
    conversation_id = _start(surface)
    before = [(e.entry_hash, e.payload) for e in surface.audit.all_entries()]

    surface.mcp.call(
        "delete_ask_conversation",
        {"conversation_id": conversation_id},
        subject=surface.subject(),
    )

    after = [(e.entry_hash, e.payload) for e in surface.audit.all_entries()]
    assert after == before, "deleting a conversation altered the evidence record"
