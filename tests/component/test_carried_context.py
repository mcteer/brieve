# SPDX-License-Identifier: Apache-2.0
"""What the model is told about earlier questions — and what it is never told.

Three properties, and the second is the one that keeps this feature from changing what an
answer *is*:

**A follow-up gets its subject.** Without the earlier question, "what about multi-region?" is
a sentence about nothing.

**History is structurally uncitable** (FR-018). Citations are stripped before the block is
built, so there is nothing in it to cite through. A row asserting an instruction would be a
row asserting a prompt, and prompts drift — 035 paid for that lesson with a stale
`_INSTRUCTION` that told the model it answered questions about something else.

**A decline contributes its question and never its verdict** (FR-014a). Feeding "the pinned
corpus does not support an answer" back to a model invites agreement rather than reading.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.answering.context import (
    MAX_CARRIED_EXCHANGES,
    build_context,
)
from core.answering.conversations.records import ExchangeDisposition, ExchangeRecord


def _answered(seq: int, question: str, *statements: str) -> ExchangeRecord:
    return ExchangeRecord(
        conversation_id="c-1",
        seq=seq,
        question=question,
        source="guidance",
        disposition=ExchangeDisposition.ANSWERED,
        outcome={
            "disposition": "answered",
            "source": "guidance",
            "ground_note": "Source material pinned today.",
            "claims": [
                {
                    "statement": statement,
                    "citations": [
                        "https://developer.hashicorp.com/validated-designs/vault#clustering"
                    ],
                }
                for statement in statements
            ],
        },
        asked_at=datetime.now(UTC),
    )


def _declined(seq: int, question: str) -> ExchangeRecord:
    return ExchangeRecord(
        conversation_id="c-1",
        seq=seq,
        question=question,
        source="guidance",
        disposition=ExchangeDisposition.DECLINED,
        outcome={
            "disposition": "declined",
            "source": "guidance",
            "declined_reason": "the pinned corpus does not support an answer to this question",
        },
        asked_at=datetime.now(UTC),
    )


def test_nothing_carried_is_nothing_said() -> None:
    """A first ask has no history, and the block must be empty rather than ceremonial."""
    context = build_context(())

    assert context.text == ""
    assert context.carried == ()
    assert context.dropped == 0
    assert context.note == ""


def test_a_follow_up_is_given_the_earlier_question_and_its_answer() -> None:
    """FR-014. The subject survives so "what about multi-region?" means something."""
    context = build_context(
        (_answered(1, "How do I run a Vault cluster in AWS?", "A cluster spans zones."),)
    )

    assert "How do I run a Vault cluster in AWS?" in context.text
    assert "A cluster spans zones." in context.text
    assert context.carried == (1,)


def test_no_citation_survives_into_the_history_block() -> None:
    """FR-018, structurally. There is nothing in history to cite through.

    If this fails, a model can produce a claim whose citation it read in the conversation
    rather than in the corpus — which is the laundering the pin exists to prevent.
    """
    context = build_context(
        (_answered(1, "How do I run a Vault cluster?", "A cluster spans zones."),)
    )

    assert "developer.hashicorp.com" not in context.text
    assert "#clustering" not in context.text
    assert "citations" not in context.text


def test_no_provenance_note_survives_either() -> None:
    """The ground and window notes describe THIS answer's material, not the topic.

    Carried forward they would date the wrong answer — and a note about a pin the follow-up
    never consulted is worse than no note.
    """
    context = build_context(
        (_answered(1, "How do I run a Vault cluster?", "A cluster spans zones."),)
    )

    assert "pinned today" not in context.text
    assert "ground_note" not in context.text


def test_a_decline_carries_its_question_and_not_its_verdict() -> None:
    """FR-014a. The subject survives; the verdict gets no second vote."""
    context = build_context((_declined(1, "How do I rotate PKI certificates?"),))

    assert "How do I rotate PKI certificates?" in context.text
    assert "does not support an answer" not in context.text
    assert "declined" not in context.text.lower()
    assert context.carried == (1,)


def test_the_block_says_plainly_that_it_is_not_corpus_material() -> None:
    """The instruction is belt to the stripping's braces, not a substitute for it."""
    context = build_context((_answered(1, "How do I run a Vault cluster?", "Spans zones."),))

    lowered = context.text.lower()
    assert "not corpus material" in lowered
    assert "nothing here may be cited" in lowered


def test_the_bound_keeps_the_most_recent_and_says_what_it_dropped() -> None:
    """FR-015, FR-016, SC-012. Somebody follows up on what they just read."""
    exchanges = tuple(
        _answered(seq, f"question {seq}", f"statement {seq}")
        for seq in range(1, MAX_CARRIED_EXCHANGES + 3)
    )

    context = build_context(exchanges)

    assert len(context.carried) == MAX_CARRIED_EXCHANGES
    assert context.carried == tuple(range(3, MAX_CARRIED_EXCHANGES + 3)), (
        "the bound kept the oldest exchanges instead of the most recent"
    )
    assert context.dropped == 2
    assert "2 earlier exchanges were not carried" in context.note


def test_a_conversation_inside_the_bound_carries_no_note() -> None:
    """An unconditional caveat gets skipped, which costs exactly the case it exists for."""
    context = build_context(tuple(_answered(s, f"q{s}", f"s{s}") for s in range(1, 4)))

    assert context.dropped == 0
    assert context.note == ""


def test_history_is_rendered_in_the_order_it_happened() -> None:
    """Selection walks backwards; rendering walks forwards. A reversed transcript would make
    "what about multi-region?" refer to the wrong thing."""
    context = build_context(
        (
            _answered(1, "first question", "first statement"),
            _answered(2, "second question", "second statement"),
        )
    )

    assert context.text.index("first question") < context.text.index("second question")


def test_an_enormous_exchange_is_dropped_whole_rather_than_truncated() -> None:
    """Whole exchanges only. Half an exchange makes the record's descriptor a lie."""
    huge = _answered(1, "x" * 9_000, "y" * 9_000)
    small = _answered(2, "what about multi-region?", "It spans regions.")

    context = build_context((huge, small))

    assert context.carried == (2,)
    assert context.dropped == 1
    assert "x" * 100 not in context.text


def test_the_descriptor_is_what_the_record_will_carry() -> None:
    """FR-020–022. Three states, and they must be distinguishable in the payload."""
    empty = build_context(())
    carried = build_context((_answered(1, "q", "s"),), inherited_route=True)

    assert empty.descriptor == {"exchanges": [], "dropped": 0, "inherited_route": False}
    assert carried.descriptor == {"exchanges": [1], "dropped": 0, "inherited_route": True}


def test_an_answer_with_no_claims_still_carries_its_question() -> None:
    """A defensive shape: an outcome the store held that has no claims list must not crash
    context assembly, and the question is still the useful part."""
    odd = ExchangeRecord(
        conversation_id="c-1",
        seq=1,
        question="How do I run a Vault cluster?",
        source="guidance",
        disposition=ExchangeDisposition.ANSWERED,
        outcome={"disposition": "answered"},
        asked_at=datetime.now(UTC),
    )

    context = build_context((odd,))

    assert "How do I run a Vault cluster?" in context.text
    assert context.carried == (1,)


def test_context_never_reaches_for_anything_but_what_it_was_given() -> None:
    """FR-019, at the unit. `build_context` takes one conversation's exchanges and has no
    store, no subject and no way to fetch — so cross-conversation carry is not a rule it
    follows but a thing it cannot do."""
    import inspect  # noqa: PLC0415

    source = inspect.getsource(build_context)

    for reachable in ("store", "fetch", "conversation_id=", "subject"):
        assert reachable not in source, (
            f"build_context reaches for {reachable!r} — it must only see the exchanges passed in"
        )


# ------------------------------------- retrieval sees the subject, not only the model (035)


def test_the_retrieval_query_is_widened_by_the_earlier_questions() -> None:
    """The plan said retrieval should ignore context. The live check said otherwise.

    Measured: "and the clients?" carries one word, retrieved Consul DNS and Windows containers,
    and three of ten follow-ups came back empty because the model was handed material about
    neither. Widening the query with the earlier QUESTIONS took SC-002 from 6/10 to 9/10.

    Only the questions — claim statements are prose and swamp the few terms that name the
    subject. This row is what stops somebody restoring the tidier design without re-measuring.
    """
    from adapters.anthropic_answering import _retrieval_query  # noqa: PLC0415

    context = build_context(
        (_answered(1, "How should I size a Nomad cluster for production?", "Six servers."),)
    )

    widened = _retrieval_query("and the clients?", context.text)

    assert "and the clients?" in widened
    assert "Nomad" in widened, "the conversation's subject did not reach the retriever"
    assert "Six servers." not in widened, (
        "claim prose reached the retriever and will swamp the terms that name the subject"
    )


def test_a_standalone_question_retrieves_exactly_as_it_always_did() -> None:
    """No conversation, no widening — the path an ask took before 035 is byte-identical."""
    from adapters.anthropic_answering import _retrieval_query  # noqa: PLC0415

    assert _retrieval_query("How do I run a Vault cluster?", "") == "How do I run a Vault cluster?"
