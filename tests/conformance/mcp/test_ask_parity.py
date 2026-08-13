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

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus, load_corpus
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)
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
    surface = surface_under_test(
        ask_provider=provider,
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())
    return surface, api, mcp


def test_row_an_answer_is_the_same_on_both() -> None:
    _, api, mcp = _both(_Answers())

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "answered"
    assert api.json()["primary_answer"] == mcp.payload["primary_answer"]
    assert api.json()["citations"] == mcp.payload["citations"]
    assert api.json()["primary_answer"]
    assert api.json()["citations"]
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
    """The default assembly — and since 026 it refuses on GOVERNANCE, not on wiring.

    Both surfaces answer 403 `unbound` rather than 503 `provider_unavailable`, because "nobody
    decided which model may answer" is the answer an operator needs before "nothing is wired" —
    telling them to configure a provider they are not yet permitted to use would send them one
    step too far. Both still record that someone asked (022's rule).
    """
    surface = surface_under_test()
    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())

    assert api.status_code == mcp.status == 403
    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert len(asks) == 2, "a boundary a caller can probe without trace is what 022 removed"
    assert {a.payload["disposition"] for a in asks} == {"unbound"}
    assert {a.payload["cell_disposition"] for a in asks} == {"refused:unbound"}


def test_row_the_ask_trail_is_equivalent_on_both() -> None:
    """Same type, subject, and decision fields — the named projection, not 'some audit'."""
    api_surface = surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    mcp_surface = surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )

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
    # `ask_model` must name the model the authority qualifies: `available` is exactly the
    # injected provider's model (026), so a fixture qualifying one model while the surface is
    # configured for another correctly refuses — record/actual agreement, working.
    answering = surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    declining = surface_under_test(
        ask_provider=_CitesNothingReal(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )

    one = TestClient(answering.app).post(
        "/ask", json={"question": "How does this work?"}, headers=answering.bearer()
    )
    other = declining.mcp.call(
        "ask", {"question": "How does this work?"}, subject=declining.subject()
    )

    assert one.json()["disposition"] != other.payload["disposition"]


# --------------------------------------------------------------- 025: estate verdicts

ESTATE_QUESTION = "Which runs were denied last night?"
MODEL = "anthropic/claude-opus@5"


class _AnswersFromRecords:
    """Cites the first record it is handed, whatever that is."""

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        if isinstance(material, Corpus):
            return [{"statement": "From the corpus.", "citations": []}]
        return [
            {
                "statement": "A run was recorded.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def _with_records(**kwargs: Any) -> Any:
    """A surface with one record arranged, and authority arranged **explicitly**.

    Set here rather than defaulted in the fixture: rows that answer must say so, because a
    fixture that qualified whatever provider was injected would make every refusal row an
    override rather than the behaviour (026).

    027 adds the credential the same way and for the same reason: a qualified cell is not
    authority to call a vendor, and a helper that supplied one silently would make the
    credential rows overrides rather than the behaviour.
    """
    kwargs.setdefault("ask_authority", qualified_ask_authority())
    kwargs.setdefault("credential_source", available_credential())
    from core.audit.schema import AuditEventType

    surface = surface_under_test(**kwargs)
    surface.audit.append_event(
        correlation_id="estate-run-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice"},
    )
    return surface


def test_row_an_estate_answer_is_the_same_on_both() -> None:
    """The estate half of ADR-0033's parity, through the operation that already existed.

    Parity grows by **zero operations** — asking stays one place, and what grew is the set of
    verdicts that operation can produce.
    """
    surface = _with_records(ask_provider=_AnswersFromRecords(), ask_model="anthropic/claude-opus@5")
    api = TestClient(surface.app).post(
        "/ask", json={"question": ESTATE_QUESTION}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": ESTATE_QUESTION}, subject=surface.subject())

    assert api.status_code == mcp.status == 200
    assert api.json()["source"] == mcp.payload["source"] == "estate"
    assert api.json()["disposition"] == mcp.payload["disposition"]
    assert api.json().get("claims") == mcp.payload.get("claims")


def test_row_an_estate_decline_is_the_same_on_both_including_its_reason() -> None:
    """The reason is compared, not just the disposition.

    Two surfaces agreeing that they declined while explaining it differently would send two
    callers to two different places for the same situation.
    """
    surface = surface_under_test(
        ask_provider=_AnswersFromRecords(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
    )
    api = TestClient(surface.app).post(
        "/ask", json={"question": ESTATE_QUESTION}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": ESTATE_QUESTION}, subject=surface.subject())

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "declined"
    assert api.json()["declined_reason"] == mcp.payload["declined_reason"]


def test_row_a_question_matching_no_keyword_takes_the_same_floor_on_both() -> None:
    """ADR-0033 across the change of floor.

    There is no longer an unroutable question: one that matches neither vocabulary goes to the
    corpus, because the router knows which words were used and nothing about what the corpus
    holds. The parity claim is unchanged in kind — both surfaces must reach the same source —
    and this row asserts it for the case that used to be a third route.
    """
    surface = _with_records(ask_provider=_AnswersFromRecords(), ask_model="anthropic/claude-opus@5")
    question = {"question": "What is the weather in Denver?"}

    api = TestClient(surface.app).post("/ask", json=question, headers=surface.bearer())
    mcp = surface.mcp.call("ask", question, subject=surface.subject())

    assert api.json()["source"] == mcp.payload["source"] == "guidance"
    assert api.json()["disposition"] == mcp.payload["disposition"]


def test_row_an_empty_scope_refuses_the_same_on_both() -> None:
    """SC-011 across surfaces: 403 on both, and no read attempted on either."""
    from core.identity.types import AuthenticatedSubject, SubjectKind

    surface = _with_records(ask_provider=_AnswersFromRecords(), ask_model="anthropic/claude-opus@5")
    unscoped = AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id="tenant-test",
        roles=frozenset(),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )

    api = TestClient(surface.app).post(
        "/ask",
        json={"question": ESTATE_QUESTION},
        headers=surface.bearer(claims={"groups": ["nothing-mapped"]}),
    )
    mcp = surface.mcp.call("ask", {"question": ESTATE_QUESTION}, subject=unscoped)

    assert api.status_code == mcp.status == 403


# --------------------------------------------------------------- 026: refusal parity


def _governance_surface(binding: dict[str, Any], matrix: dict[str, Any]) -> Any:
    from core.authority.ask_binding import AskAuthority

    return surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=lambda: binding, read_matrix=lambda: matrix),
        credential_source=available_credential(),
    )


def _matrix(*refs: str, **kw: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cells": [
            {
                "pack": r.split(":")[0],
                "model": r.split(":")[1],
                "role": "ask",
                "qualified_by": "fixture",
                "judge": "seed",
                "withdrawn": kw.get("withdrawn", False),
            }
            for r in refs
        ],
    }


@pytest.mark.parametrize(
    ("binding", "matrix", "expected"),
    [
        ({"schema_version": 1}, {"schema_version": 1, "cells": []}, "unbound"),
        (
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _matrix(f"vault:{MODEL}:ask", withdrawn=True),
            "unqualified_cell",
        ),
    ],
    ids=["unbound", "unqualified_cell"],
)
def test_row_a_governance_refusal_is_identical_on_both_surfaces(
    binding: dict[str, Any], matrix: dict[str, Any], expected: str
) -> None:
    """SC-007, FR-011 — same verdict AND same reason, for each governance refusal.

    Two surfaces agreeing that they refused while explaining it differently would send two callers
    to two different places for one situation. The reason is compared, not just the status.
    """
    surface = _governance_surface(binding, matrix)

    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())

    assert api.status_code == mcp.status == 403
    assert api.json()["detail"] == mcp.payload["reason"]

    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert [a.payload["disposition"] for a in asks] == [expected, expected]


def test_row_an_unreadable_fabric_refuses_identically_on_both() -> None:
    """The third refusal, and the one that must not read as a governance decision."""

    def _down() -> dict[str, Any]:
        raise ConnectionError("vault is unreachable")

    from core.authority.ask_binding import AskAuthority

    surface = surface_under_test(
        ask_provider=_Answers(),
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=_down, read_matrix=lambda: _matrix()),
    )

    api = TestClient(surface.app).post(
        "/ask", json={"question": "How does this work?"}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": "How does this work?"}, subject=surface.subject())

    assert api.status_code == mcp.status == 403
    assert api.json()["detail"] == mcp.payload["reason"]
    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert {a.payload["disposition"] for a in asks} == {"matrix_unreadable"}
