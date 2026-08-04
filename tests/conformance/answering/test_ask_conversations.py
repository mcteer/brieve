# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — asking inside a conversation, through the wired surface.

`tests/component/test_carried_context.py` tests the context builder in isolation and cannot
catch the failure that matters: the surface consulting a conversation it should not have, or
routing a question on history it should have ignored. These rows go through `POST /ask`.

Three claims, and the first is the one a caller can probe:

**A conversation that is not yours costs nothing and reveals nothing.** Absent, another
subject's, and another tenant's all answer `404 no_such_conversation`, before routing, before
governance, before the corpus is loaded and long before a vendor is called — so probing
identifiers cannot spend a model call or leave a governance record.

**An explicit signal wins; silence inherits.** A question with its own routing vocabulary is
routed on its own words wherever it is asked. A bare follow-up takes the source of the exchange
it follows, in both directions.

**History informs the question and never the answer.** A claim still ships only when its
citation resolves against the pin.
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

GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
ESTATE_QUESTION = "Which runs were denied last night?"
BARE_FOLLOW_UP = "what about multi-region?"


class _Remembers:
    """Answers from whichever material it is handed, and keeps the context it was given."""

    def __init__(self) -> None:
        self.contexts: list[str] = []
        self.corpus_calls = 0
        self.estate_calls = 0

    def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
        self.contexts.append(context)
        if isinstance(material, Corpus):
            self.corpus_calls += 1
            path, anchor = next(
                (d.path, next(iter(d.sections))) for d in material.documents.values() if d.sections
            )
            return [
                {
                    "statement": "From the corpus.",
                    "citations": [{"path": path, "anchor": anchor}],
                }
            ]
        self.estate_calls += 1
        return [
            {
                "statement": "From the records.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def _surface(provider: Any) -> Any:
    return surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )


def _arrange_records(surface: Any) -> None:
    from core.audit.schema import AuditEventType  # noqa: PLC0415

    surface.audit.append_event(
        correlation_id="estate-run-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice"},
    )


def _ask(surface: Any, question: str, conversation_id: str | None = None) -> Any:
    body: dict[str, Any] = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return TestClient(surface.app).post("/ask", json=body, headers=surface.bearer())


# ------------------------------------------------------------ [GATE:fail-closed] ownership


@pytest.mark.parametrize(
    "conversation_id", ["c-does-not-exist", "../../etc/passwd", "00000000-0000-0000-0000-0"]
)
def test_a_conversation_that_is_not_yours_is_refused_before_anything_happens(
    conversation_id: str,
) -> None:
    """FR-012/013. The refusal costs no model call and leaves no governance record."""
    provider = _Remembers()
    surface = _surface(provider)
    before = len(surface.audit.all_entries())

    response = _ask(surface, GUIDANCE_QUESTION, conversation_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "no_such_conversation"
    assert provider.corpus_calls == 0 and provider.estate_calls == 0, (
        "an unowned conversation id reached the model"
    )
    assert len(surface.audit.all_entries()) == before, (
        "an unowned conversation id left a record; probing ids must cost nothing"
    )


def test_another_subjects_conversation_is_indistinguishable_from_a_missing_one() -> None:
    """SC-004. A distinct response for "exists but not yours" confirms that it exists."""
    provider = _Remembers()
    surface = _surface(provider)
    mine = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    client = TestClient(surface.app)
    theirs = client.post(
        "/ask",
        json={"question": BARE_FOLLOW_UP, "conversation_id": mine},
        headers=surface.bearer(subject="bob"),
    )
    absent = client.post(
        "/ask",
        json={"question": BARE_FOLLOW_UP, "conversation_id": "c-nope"},
        headers=surface.bearer(subject="bob"),
    )

    assert theirs.status_code == absent.status_code == 404
    assert theirs.json() == absent.json(), (
        "somebody else's conversation answers differently from a missing one"
    )


# ------------------------------------------------------------------------ the conversation


def test_a_first_ask_starts_a_conversation_and_carries_nothing() -> None:
    """FR-010. The conversation is born with the ask; no history existed to carry."""
    provider = _Remembers()
    surface = _surface(provider)

    body = _ask(surface, GUIDANCE_QUESTION).json()

    assert body["conversation_id"]
    assert body["exchange_seq"] == 1
    assert provider.contexts == [""], "a first ask was given history that does not exist"


def test_a_follow_up_is_given_the_earlier_question() -> None:
    """FR-014. The subject survives, which is the whole point of the feature."""
    provider = _Remembers()
    surface = _surface(provider)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    body = _ask(surface, BARE_FOLLOW_UP, conversation_id).json()

    assert body["exchange_seq"] == 2
    assert GUIDANCE_QUESTION in provider.contexts[-1]
    assert "From the corpus." in provider.contexts[-1], "the earlier answer was not carried"


def test_history_reaches_the_question_and_never_the_citations() -> None:
    """FR-018/SC-011. Context is not material — there is nothing in it to cite through."""
    provider = _Remembers()
    surface = _surface(provider)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    _ask(surface, BARE_FOLLOW_UP, conversation_id)

    carried = provider.contexts[-1]
    assert "developer.hashicorp.com" not in carried
    assert "citations" not in carried
    assert "not corpus material" in carried.lower()


# --------------------------------------------------------------------- routing (SC-010/010a)


def test_a_signalled_question_routes_on_its_own_words_inside_a_conversation() -> None:
    """SC-010. History can never move a question that said where it belongs.

    Asked inside a DOCUMENTATION conversation, a records question still reaches the records —
    which is the half that keeps the estate reachable rather than shadowed by whatever came
    before.
    """
    provider = _Remembers()
    surface = _surface(provider)
    _arrange_records(surface)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    body = _ask(surface, ESTATE_QUESTION, conversation_id).json()

    assert body["source"] == "estate"
    assert provider.estate_calls == 1


def test_a_bare_follow_up_inherits_a_documentation_conversation() -> None:
    """SC-010a, first direction. Silence takes the source of the exchange it follows."""
    provider = _Remembers()
    surface = _surface(provider)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    body = _ask(surface, BARE_FOLLOW_UP, conversation_id).json()

    assert body["source"] == "guidance"
    assert provider.estate_calls == 0, "a documentation follow-up read somebody's records"


def test_a_bare_follow_up_inherits_a_records_conversation() -> None:
    """SC-010a, second direction — and the one that would silently answer from the wrong
    source. Without inheritance this takes the guidance floor and answers a question about
    somebody's records out of the documentation, which the routing module calls the invisible
    failure."""
    provider = _Remembers()
    surface = _surface(provider)
    _arrange_records(surface)
    conversation_id = _ask(surface, ESTATE_QUESTION).json()["conversation_id"]

    body = _ask(surface, "what about the day before?", conversation_id).json()

    assert body["source"] == "estate"


def test_the_same_question_asked_standalone_routes_the_same_way() -> None:
    """SC-010, stated as the comparison it actually is."""
    provider = _Remembers()
    surface = _surface(provider)
    _arrange_records(surface)

    standalone = _ask(surface, ESTATE_QUESTION).json()["source"]
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]
    in_conversation = _ask(surface, ESTATE_QUESTION, conversation_id).json()["source"]

    assert standalone == in_conversation == "estate"


# ------------------------------------------------------------------------- what the record says


def _asks(surface: Any) -> list[Any]:
    return [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]


def test_a_standalone_ask_carries_no_conversation_keys() -> None:
    """FR-022, first state: no conversation existed."""
    surface = _surface(_Remembers())

    _ask(surface, GUIDANCE_QUESTION)

    payload = _asks(surface)[0].payload
    assert "carried_context" not in payload, (
        "an ask that started a conversation claimed context it never had"
    )


def test_a_follow_up_records_which_exchanges_the_model_was_given() -> None:
    """FR-020/021, SC-005. The descriptor is what an auditor reconstructs from."""
    surface = _surface(_Remembers())
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    _ask(surface, BARE_FOLLOW_UP, conversation_id)

    payload = _asks(surface)[-1].payload
    assert payload["conversation_id"] == conversation_id
    assert payload["carried_context"] == {
        "exchanges": [1],
        "dropped": 0,
        "inherited_route": True,
    }


def test_an_inherited_route_says_so_in_the_record() -> None:
    """The fact that would otherwise be unrecoverable: why this question went where it did."""
    surface = _surface(_Remembers())
    _arrange_records(surface)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    _ask(surface, ESTATE_QUESTION, conversation_id)

    assert _asks(surface)[-1].payload["carried_context"]["inherited_route"] is False, (
        "a question routed on its own signal was recorded as having inherited"
    )


# --------------------------------------------------------------------------- what must not change


def test_asking_in_a_conversation_reaches_no_tool() -> None:
    """FR-024. The conversation surface acquires no capability a single ask lacks.

    Asserted at the SHAPE rather than by watching one dispatcher, the way
    `test_asking_never_acts` does it: a conversation must not have handed the ask path a
    collaborator that can act, and the way to know is that no such name is reachable from it.
    """
    import inspect  # noqa: PLC0415

    from surfaces.api import ask as ask_module  # noqa: PLC0415

    reachable = inspect.getsource(ask_module._remember) + inspect.getsource(
        ask_module._resolve_conversation
    )

    for actor in ("dispatch", "registry", "run_dispatcher", "tools", "authority"):
        assert actor not in reachable, (
            f"the conversation path can reach {actor!r} — an ask must never act (ADR-0039)"
        )


def test_a_conversation_answers_a_question_asking_for_action_without_acting() -> None:
    """The behavioural half: an imperative inside a conversation is still only answered."""
    provider = _Remembers()
    surface = _surface(provider)
    conversation_id = _ask(surface, GUIDANCE_QUESTION).json()["conversation_id"]

    body = _ask(surface, "run the planner agent and deploy it", conversation_id).json()

    assert body["disposition"] in {"answered", "declined"}
    assert "run_id" not in body and "turn_id" not in body, (
        "an ask inside a conversation produced something that looks like a started run"
    )


# ------------------------------------------- [GATE:fail-closed] an unreadable store (T021)


class _Unreadable:
    """A store that cannot be reached. Every method raises the store's own error."""

    def _fail(self, *_args: Any, **_kwargs: Any) -> Any:
        from core.answering.conversations.postgres import ConversationStoreError

        raise ConversationStoreError("conversation store unavailable: simulated")

    get = list_for = delete = recent = start = append = _fail


def test_an_unreadable_store_answers_503_and_never_an_empty_list() -> None:
    """FR-008's fail-closed half, and the sharpest wording question in the feature.

    An empty list is a CLAIM: it says this person has no conversations. When the truth is that
    nobody could look, that claim is false and unrecoverable — they conclude their history is
    gone. 503 says come back.
    """
    surface = surface_under_test(ask_conversations=_Unreadable())

    response = TestClient(surface.app).get("/ask-conversations", headers=surface.bearer())

    assert response.status_code == 503
    assert response.json()["detail"] != []
    assert "try again" in response.json()["detail"].lower()


def test_an_unreadable_store_does_not_pretend_a_conversation_is_missing() -> None:
    """503, not 404. "Could not look" and "not yours" send a person to different places —
    one waits, the other goes and asks who owns it."""
    surface = surface_under_test(ask_conversations=_Unreadable())

    response = TestClient(surface.app).get("/ask-conversations/c-1", headers=surface.bearer())

    assert response.status_code == 503


def test_an_unreadable_store_refuses_the_ask_rather_than_answering_without_context() -> None:
    """The subtle one. A conversation that cannot be read must not fall through to a
    context-free answer that looks like a normal one — the person asked a follow-up and would
    get an answer to it read in isolation, with nothing saying so."""
    surface = surface_under_test(
        ask_provider=_Remembers(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
        ask_conversations=_Unreadable(),
    )

    response = _ask(surface, BARE_FOLLOW_UP, "c-1")

    assert response.status_code in (404, 503), (
        "an unreadable conversation answered the follow-up as though it had no history"
    )
