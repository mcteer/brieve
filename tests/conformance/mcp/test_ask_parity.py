# SPDX-License-Identifier: Apache-2.0
"""Row: `ask` gives the same verdict on both transports — answering, declining, and failing.

**Three verdicts rather than one**, because this operation has three outcomes and they are the
ones most likely to drift apart. A surface that answered where the other declined would be the
worst available failure: two callers asking the same question of the same platform, one told the
corpus supports a claim and the other told it does not.

**The provider-failure case is here on purpose.** `answer_question` raises rather than returning a
decline, and a transport that caught that and shaped it like one would be *more* convenient and
would tell a reader the corpus was silent when the model was unreachable. Those send them to
different people, so the row checks that both surfaces keep them apart.

Both surfaces are given the **same provider instance** by `surface_under_test`. Two surfaces each
holding their own would let this row pass while the deployed pair diverged — the asymmetry the
fixture's shared collaborators exist to prevent.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus, load_corpus
from tests.harness.api_fixtures import surface_under_test
from tests.harness.parity import project

CORPUS = load_corpus()
#: A real path and anchor from the pinned corpus. Read from the corpus rather than written as a
#: literal: a hard-coded pair would rot the day the pin moves, and would rot into a row that still
#: passes because a citation that no longer resolves simply declines.
CITED_PATH, CITED_ANCHOR = next(
    (document.path, sorted(document.anchors)[0])
    for document in CORPUS.documents.values()
    if document.anchors
)


class _Answers:
    """A provider whose claim cites a section the pinned corpus really has."""

    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return [
            {
                "statement": "The pattern documents this.",
                "citations": [{"path": CITED_PATH, "anchor": CITED_ANCHOR}],
            }
        ]


class _CitesNothingReal:
    """Confident, and every citation points at a section that does not exist."""

    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return [
            {
                "statement": "Retention should be set to 400 days.",
                "citations": [{"path": "/validated-patterns/vault/retention", "anchor": "policy"}],
            }
        ]


class _Unreachable:
    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        raise ProviderUnavailable("the model could not be reached")


def _both(provider: object) -> tuple[Any, Any, Any]:
    surface = surface_under_test(ask_provider=provider, ask_model="anthropic/claude-opus@5")
    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())
    return surface, api, mcp


def test_row_an_answer_is_the_same_on_both() -> None:
    _, api, mcp = _both(_Answers())

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "answered"
    assert api.json()["claims"] == mcp.payload["claims"]
    assert api.json()["corpus_digest"] == mcp.payload["corpus_digest"] == CORPUS.digest


def test_row_a_decline_is_the_same_on_both() -> None:
    """An unresolvable citation declines — identically, and with the reason preserved.

    A transport that dropped `declined_reason` would still agree on the disposition, which is why
    the reason is compared: "the corpus does not say" and "everything you were told rested on
    nothing" are different answers to the person who asked.
    """
    _, api, mcp = _both(_CitesNothingReal())

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "declined"
    assert api.json()["declined_reason"] == mcp.payload["declined_reason"]
    assert "resolve" in api.json()["declined_reason"]


def test_row_a_provider_failure_is_the_same_on_both_and_is_not_a_decline() -> None:
    _, api, mcp = _both(_Unreachable())

    assert api.status_code == mcp.status == 503
    assert "declin" not in api.text.lower(), (
        "a provider failure delivered as a decline tells a reader the corpus was silent when "
        "the model was unreachable"
    )


def test_row_an_unconfigured_surface_refuses_the_same_on_both() -> None:
    """The default assembly. Both 503, and both record that someone asked (022's rule)."""
    surface = surface_under_test()
    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())

    assert api.status_code == mcp.status == 503
    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert len(asks) == 2, "a boundary a caller can probe without trace is what 022 removed"
    assert {a.payload["disposition"] for a in asks} == {"provider_unavailable"}


def test_row_the_ask_trail_is_equivalent_on_both() -> None:
    """Same type, subject, and decision fields — the named projection, not 'some audit'."""
    api_surface = surface_under_test(ask_provider=_Answers())
    mcp_surface = surface_under_test(ask_provider=_Answers())

    TestClient(api_surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=api_surface.bearer()
    )
    mcp_surface.mcp.call("ask", {"question": "How does this work?"}, subject=mcp_surface.subject())

    api_trail = project(api_surface.audit.all_entries())
    mcp_trail = project(mcp_surface.audit.all_entries())

    assert api_trail == mcp_trail
    assert api_trail, "an empty projection would make this row vacuous"


def test_break_fixture_a_surface_answering_where_the_other_declines_is_detected() -> None:
    """Self-verifying: constructs the divergence this row exists to catch."""
    answering = surface_under_test(ask_provider=_Answers())
    declining = surface_under_test(ask_provider=_CitesNothingReal())

    one = TestClient(answering.app).post(
        "/ask", json={"question": "How does this work?"}, headers=answering.bearer()
    )
    other = declining.mcp.call(
        "ask", {"question": "How does this work?"}, subject=declining.subject()
    )

    assert one.json()["disposition"] != other.payload["disposition"]
