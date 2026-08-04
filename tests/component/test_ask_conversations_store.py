# SPDX-License-Identifier: Apache-2.0
"""The conversation store, and the two properties that make it safe rather than convenient.

**Owner and tenant are parameters, not a filter somebody remembers.** Every row below that
reaches for somebody else's conversation gets the same answer a row reaching for a
non-existent one gets — `None`/`False` — because a different answer for "exists but not
yours" tells the caller it exists (FR-012, FR-013, SC-004).

**Nothing here can touch the trail.** The store holds no reference to `audit_entries`, which
is why FR-023 is structural: a delete cannot alter evidence it has no way to name.

The memory twin runs here, in the fast lane. The Postgres store's SQL is exercised by
`tests/conformance/answering/test_conversation_store_enclave.py`, which runs under an attested
workload identity because that is the only place a brokered database credential exists — a
store whose SQL nobody executed is a store nobody has tested.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.answering.conversations.records import ExchangeDisposition
from core.answering.conversations.store import MemoryConversationStore

ANSWER: dict[str, Any] = {
    "disposition": "answered",
    "source": "guidance",
    "claims": [{"statement": "A Vault cluster spans availability zones.", "citations": []}],
}
DECLINE: dict[str, Any] = {
    "disposition": "declined",
    "source": "guidance",
    "declined_reason": "the pinned corpus does not support an answer to this question",
}


@pytest.fixture
def store() -> Any:
    return MemoryConversationStore()


def _start(store: Any, question: str = "How do I run a Vault cluster in AWS?") -> str:
    conversation, _ = store.start(
        conversation_id=f"c-{abs(hash(question)) % 10**8}",
        tenant_id="tenant-test",
        subject_user_id="alice",
        question=question,
        source="guidance",
        disposition=ExchangeDisposition.ANSWERED,
        outcome=ANSWER,
    )
    return str(conversation.conversation_id)


def test_a_conversation_is_born_with_its_first_exchange(store: Any) -> None:
    """FR-010. There is no empty conversation to create, list, or reopen."""
    conversation_id = _start(store)

    found = store.get(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice"
    )

    assert found is not None
    conversation, exchanges = found
    assert conversation.exchanges == 1
    assert exchanges[0].seq == 1
    assert conversation.title.startswith("How do I run a Vault cluster")


def test_exchanges_keep_the_order_they_were_accepted_in(store: Any) -> None:
    """FR-001. Dense seqs from 1, in acceptance order."""
    conversation_id = _start(store)
    for question in ("what about multi-region?", "and disaster recovery?"):
        store.append(
            conversation_id=conversation_id,
            tenant_id="tenant-test",
            subject_user_id="alice",
            question=question,
            source="guidance",
            disposition=ExchangeDisposition.ANSWERED,
            outcome=ANSWER,
        )

    _, exchanges = store.get(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice"
    )

    assert [e.seq for e in exchanges] == [1, 2, 3]
    assert exchanges[1].question == "what about multi-region?"


def test_a_declined_exchange_is_kept_as_part_of_the_conversation(store: Any) -> None:
    """FR-004. A decline is an answer and stays in the transcript."""
    conversation_id = _start(store)
    store.append(
        conversation_id=conversation_id,
        tenant_id="tenant-test",
        subject_user_id="alice",
        question="How do I rotate PKI certificates?",
        source="guidance",
        disposition=ExchangeDisposition.DECLINED,
        outcome=DECLINE,
    )

    _, exchanges = store.get(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice"
    )

    assert exchanges[1].disposition is ExchangeDisposition.DECLINED
    assert "does not support" in exchanges[1].outcome["declined_reason"]


def test_the_outcome_is_stored_verbatim_and_nothing_else_is(store: Any) -> None:
    """[GATE:no-secret-leak] What goes in is the response body; what comes out is that body.

    The store is not a place where content is composed, enriched, or re-derived — reopening a
    conversation must re-render what the person SAW, and the way to be sure of that is for the
    store to be incapable of producing anything else. A row that checked "looks similar" would
    not notice a field being invented here.
    """
    conversation_id = _start(store)

    _, exchanges = store.get(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice"
    )

    assert exchanges[0].outcome == ANSWER
    assert not any(
        key in str(exchanges[0].outcome).lower()
        for key in ("password", "api_key", "token", "secret")
    ), "the store wrote something credential-shaped that was never handed to it"


@pytest.mark.parametrize(
    ("tenant", "subject"),
    [("tenant-test", "bob"), ("tenant-other", "alice"), ("tenant-other", "bob")],
)
def test_somebody_elses_conversation_is_indistinguishable_from_no_conversation(
    store: Any, tenant: str, subject: str
) -> None:
    """FR-012, FR-013, SC-004. Every miss is the same miss, on every method."""
    conversation_id = _start(store)

    assert (
        store.get(conversation_id=conversation_id, tenant_id=tenant, subject_user_id=subject)
        is None
    )
    assert (
        store.recent(
            conversation_id=conversation_id, tenant_id=tenant, subject_user_id=subject, limit=6
        )
        == ()
    )
    assert (
        store.append(
            conversation_id=conversation_id,
            tenant_id=tenant,
            subject_user_id=subject,
            question="sneaking in",
            source="guidance",
            disposition=ExchangeDisposition.ANSWERED,
            outcome=ANSWER,
        )
        is None
    )
    assert (
        store.delete(conversation_id=conversation_id, tenant_id=tenant, subject_user_id=subject)
        is False
    )
    assert store.list_for(tenant_id=tenant, subject_user_id=subject) == ()


def test_a_conversation_that_does_not_exist_answers_the_same_way(store: Any) -> None:
    """The other half of the indistinguishability claim."""
    assert (
        store.get(conversation_id="c-nope", tenant_id="tenant-test", subject_user_id="alice")
        is None
    )
    assert (
        store.delete(conversation_id="c-nope", tenant_id="tenant-test", subject_user_id="alice")
        is False
    )


def test_listing_shows_the_conversation_just_used_first(store: Any) -> None:
    """FR-008. `last_asked_at` orders the list, so the one in hand is at the top."""
    first = _start(store, "How do I run a Vault cluster in AWS?")
    second = _start(store, "How do I back up Consul?")
    store.append(
        conversation_id=first,
        tenant_id="tenant-test",
        subject_user_id="alice",
        question="what about multi-region?",
        source="guidance",
        disposition=ExchangeDisposition.ANSWERED,
        outcome=ANSWER,
    )

    listed = store.list_for(tenant_id="tenant-test", subject_user_id="alice")

    assert [c.conversation_id for c in listed][0] == first, (
        "the conversation just added to is not at the top of the list"
    )
    assert {c.conversation_id for c in listed} == {first, second}
    assert next(c for c in listed if c.conversation_id == first).exchanges == 2


def test_deleting_removes_the_conversation_and_its_exchanges(store: Any) -> None:
    """FR-011. Hard delete; nothing left to reopen."""
    conversation_id = _start(store)

    assert store.delete(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice"
    )
    assert (
        store.get(conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice")
        is None
    )
    assert store.list_for(tenant_id="tenant-test", subject_user_id="alice") == ()


def test_recent_returns_oldest_first_for_the_context_builder(store: Any) -> None:
    """`build_context` reads a conversation in the order it happened."""
    conversation_id = _start(store)
    for question in ("second", "third", "fourth"):
        store.append(
            conversation_id=conversation_id,
            tenant_id="tenant-test",
            subject_user_id="alice",
            question=question,
            source="guidance",
            disposition=ExchangeDisposition.ANSWERED,
            outcome=ANSWER,
        )

    recent = store.recent(
        conversation_id=conversation_id, tenant_id="tenant-test", subject_user_id="alice", limit=2
    )

    assert [e.question for e in recent] == ["third", "fourth"], (
        "recent() must return the newest exchanges, oldest-first"
    )
