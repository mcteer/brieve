# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — SC-009: routing is right in BOTH directions, through the wired surface.

`tests/component/test_ask_routing.py` tests `route()` in isolation and cannot catch the failure
that actually matters: routing consulted, and the wrong read performed anyway. These rows go
through `POST /ask` and the MCP transport.

**The guidance→estate direction is the sharper check, and it is asserted by absence.** That
misroute performs a *scoped read of somebody's records* for a question that was never about them —
an act, not merely a wrong answer, and it leaves an access record to prove it. So the row does not
look for a right answer; it looks for the read that must not have happened.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.answering.corpus import Corpus
from core.audit.schema import AuditEntry
from surfaces.api.evidence import evidence_stream_for
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

ESTATE_QUESTION = "Which runs were denied last night?"
GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
NEITHER_QUESTION = "What is the weather in Denver?"


class _RecordsWhatItWasAsked:
    """Answers either shape, and remembers which material it was handed.

    One provider for both paths, so a misroute shows up as *which method was called* rather than
    as a difference in how carefully two doubles were written.
    """

    def __init__(self) -> None:
        self.corpus_calls = 0
        self.estate_calls = 0

    # Guidance seam.
    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        if isinstance(material, Corpus):
            self.corpus_calls += 1
            return [{"statement": "From the corpus.", "citations": []}]
        self.estate_calls += 1
        records: tuple[AuditEntry, ...] = material
        return [
            {
                "statement": "From the records.",
                "references": [{"entry_hash": r.entry_hash} for r in records[:1]],
            }
        ]


def _access_count(surface: Any) -> int:
    return len(surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test")))


def _arrange(surface: Any) -> None:
    from core.audit.schema import AuditEventType

    surface.audit.append_event(
        correlation_id="estate-run-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice"},
    )


def test_row_a_guidance_question_never_reads_the_records() -> None:
    """SC-009's sharper half, asserted by ABSENCE of an access record.

    If this fails, the platform read somebody's audit trail because they asked how a pattern
    works. The wrong answer would be recoverable; the read is not.
    """
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)
    before = _access_count(surface)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert _access_count(surface) == before, (
        "a guidance question performed a scoped read of the evidence plane"
    )
    assert provider.estate_calls == 0


def test_row_an_estate_question_never_consults_the_corpus() -> None:
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)

    response = TestClient(surface.app).post(
        "/ask", json={"question": ESTATE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert response.json()["source"] == "estate"
    assert provider.corpus_calls == 0, "an estate question was answered from documentation"


def test_row_the_same_routing_holds_on_mcp() -> None:
    """ADR-0033. Routing lives in the shared path, so both surfaces inherit one decision."""
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)
    before = _access_count(surface)

    guidance = surface.mcp.call("ask", {"question": GUIDANCE_QUESTION}, subject=surface.subject())
    assert guidance.status == 200
    assert _access_count(surface) == before

    estate = surface.mcp.call("ask", {"question": ESTATE_QUESTION}, subject=surface.subject())
    assert estate.status == 200
    assert estate.payload["source"] == "estate"


def test_row_a_question_matching_no_keyword_is_still_taken_to_the_corpus() -> None:
    """The edge case, rewritten around WHO IS ENTITLED TO DECLINE.

    This row used to assert a third route: a question matching neither vocabulary was declined
    by the ROUTER, before any material was read. That was wrong in the way that matters — the
    router knows which words a question contains and nothing about what the corpus holds. Asked
    *"what is the prescribed way to build a Vault cluster in AWS"* it found no keyword, declined,
    and told a maintainer the platform had no guidance on the most documented thing it ships.

    So GUIDANCE IS THE FLOOR. A question that matches nothing still reaches the corpus, and the
    decline — if there is one — comes from the model, which has read the material and is the only
    party that can say the corpus is silent.

    What the router still guarantees, and what this row now checks, is the half that was always
    load-bearing: it reads NO RECORDS on the way. An off-topic question must never become an
    excuse to open an estate a person may not see.
    """
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)
    before = _access_count(surface)

    response = TestClient(surface.app).post(
        "/ask", json={"question": NEITHER_QUESTION}, headers=surface.bearer()
    )

    body = response.json()
    assert body["source"] == "guidance"
    assert provider.corpus_calls == 1
    # The half that did not change: no records read, and no access recorded against the estate.
    assert provider.estate_calls == 0
    assert _access_count(surface) == before


def test_row_a_silent_corpus_declines_in_the_models_own_words() -> None:
    """The other half of the same decision: declining is still available, from the right party.

    Removing the router's decline did not remove declining — it moved it behind the material.
    Here the provider reads the corpus, finds nothing it can stand on, and the reason names the
    corpus rather than announcing that the question fitted no category.
    """

    class _FindsNothing:
        def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
            return []

    surface = surface_under_test(
        ask_provider=_FindsNothing(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)

    body = (
        TestClient(surface.app)
        .post("/ask", json={"question": NEITHER_QUESTION}, headers=surface.bearer())
        .json()
    )

    assert body["disposition"] == "declined"
    assert body["source"] == "guidance"
    assert "corpus" in body["declined_reason"]


def test_row_the_route_is_recorded_on_every_ask() -> None:
    """FR-010b. A route nobody can see is a decision nobody can audit."""
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    _arrange(surface)
    client = TestClient(surface.app)

    for question in (GUIDANCE_QUESTION, ESTATE_QUESTION, NEITHER_QUESTION):
        client.post("/ask", json={"question": question}, headers=surface.bearer())

    sources = [
        e.payload["source"]
        for e in surface.audit.all_entries()
        if str(e.event_type) == "ask_answered"
    ]
    # Three asks, two routes: the third question matches no keyword and takes the floor.
    assert sources == ["guidance", "estate", "guidance"]


def test_row_a_decline_never_names_the_wrong_door() -> None:
    """SC-010. Nobody who asked about their estate is told the documentation does not cover it."""
    provider = _RecordsWhatItWasAsked()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    # No records at all, so the estate question must decline.
    response = TestClient(surface.app).post(
        "/ask", json={"question": ESTATE_QUESTION}, headers=surface.bearer()
    )

    body = response.json()
    assert body["source"] == "estate"
    if body["disposition"] == "declined":
        reason = body["declined_reason"].lower()
        # The estate path has two decline reasons — "nothing you may see" and "everything rested
        # on a record you may not see". Both must speak of RECORDS and neither of documentation.
        assert "corpus" not in reason and "documentation" not in reason
        assert "record" in reason
