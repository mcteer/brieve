# SPDX-License-Identifier: Apache-2.0
"""One draw must not be allowed to say the corpus is silent.

*"The pinned corpus does not support an answer to this question"* is a claim about the platform's
own material, and a person who reads it stops asking. Measured against the 238-document corpus on
2026-08-03, that sentence was produced by a single empty sample roughly one time in six on a
question the corpus answers well — the maintainer asked once, drew the empty one, and was told the
platform had no guidance on building a Vault cluster in AWS.

These rows pin both halves of the fix, and the second half is the one worth having:

  * an empty answer is asked again, up to `ATTEMPTS_BEFORE_SILENCE`, and
  * an answer that came back with anything is NEVER asked again.

The second is what keeps this a reliability control rather than a way to shop for a better reply.
A harness that re-asks a model which already answered is one that talks itself into the answer it
wanted, and no amount of citation pinning downstream makes that honest.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.anthropic_answering import (
    ATTEMPTS_BEFORE_SILENCE,
    LiveAnswerProvider,
    LiveEstateProvider,
)
from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus, Document


def _corpus() -> Corpus:
    return Corpus(
        documents={
            "/patterns/vault/clustering": Document(
                path="/patterns/vault/clustering",
                url="https://developer.hashicorp.com/patterns/vault/clustering",
                digest="upstream-digest",
                anchors=frozenset({"clustering"}),
                sections={"clustering": "A Vault cluster spans availability zones in AWS."},
            )
        },
        digest="digest",
        synced_at=None,
    )


class _Replays:
    """A client that returns a scripted sequence of model replies, counting the calls."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls = 0
        self.messages = self

    def create(self, **_kwargs: Any) -> Any:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return type("Response", (), {"content": [type("Block", (), {"text": reply})()]})()


@pytest.fixture
def replaying(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Swap the vendor client for a scripted one, at the single seam both providers use."""

    def _install(*replies: str) -> _Replays:
        client = _Replays(*replies)
        monkeypatch.setattr(
            "adapters.anthropic_answering.client_and_model",
            lambda *_args, **_kwargs: (client, "model-id"),
        )
        return client

    return _install


_CLAIM = (
    '[{"statement": "A Vault cluster spans availability zones.",'
    ' "citations": [{"path": "/patterns/vault/clustering", "anchor": "clustering"}]}]'
)


def test_an_empty_draw_is_asked_again_rather_than_reported_as_silence(replaying: Any) -> None:
    """The maintainer's failure, made impossible: empty then answered returns the answer."""
    client = replaying("[]", _CLAIM)

    claims = LiveAnswerProvider("anthropic/claude-sonnet@5", api_key="k").answer(
        "How do I build a Vault cluster in AWS?", _corpus()
    )

    assert claims, "an empty first draw was reported as silence instead of being asked again"
    assert client.calls == 2, "the retry did not happen, or happened more than once"


def test_a_model_that_answered_is_never_asked_twice(replaying: Any) -> None:
    """The half that keeps this honest.

    If this ever fails, the harness has become something that re-rolls until it likes the reply.
    A single thin claim is still an answer, and the platform's job is to report it, not improve it.
    """
    client = replaying(_CLAIM, _CLAIM)

    LiveAnswerProvider("anthropic/claude-sonnet@5", api_key="k").answer(
        "How do I build a Vault cluster in AWS?", _corpus()
    )

    assert client.calls == 1, "a model that answered was asked again — this is answer-shopping"


def test_a_corpus_that_really_is_silent_still_declines(replaying: Any) -> None:
    """Retrying must not remove declining. Every attempt empty means the platform says so."""
    client = replaying("[]")

    claims = LiveAnswerProvider("anthropic/claude-sonnet@5", api_key="k").answer(
        "How do I build a Vault cluster in AWS?", _corpus()
    )

    assert claims == []
    assert client.calls == ATTEMPTS_BEFORE_SILENCE, (
        f"a genuinely silent corpus should be confirmed {ATTEMPTS_BEFORE_SILENCE} times, "
        f"not {client.calls}"
    )


def test_nothing_to_read_costs_no_model_call_at_all(replaying: Any) -> None:
    """Retrieval finding nothing is not a question for the model, and never was."""
    client = replaying("[]")

    claims = LiveAnswerProvider("anthropic/claude-sonnet@5", api_key="k").answer(
        "zzz", Corpus(documents={}, digest="d", synced_at=None)
    )

    assert claims == []
    assert client.calls == 0


def test_a_provider_fault_is_not_retried_into_a_decline(replaying: Any) -> None:
    """A fault and a decline must keep different shapes (`core.answering.answer`).

    Retrying on empty must not quietly start swallowing faults: "the model would not answer in
    the required shape" and "the corpus does not say" send a reader to different people.
    """
    replaying("not json at all")

    with pytest.raises(ProviderUnavailable):
        LiveAnswerProvider("anthropic/claude-sonnet@5", api_key="k").answer(
            "How do I build a Vault cluster in AWS?", _corpus()
        )


class _Record:
    entry_hash = "abc123"
    event_type = "run_start"
    correlation_id = "run-1"
    payload: dict[str, Any] = {"subject_user_id": "alice"}


def test_the_estate_path_takes_the_same_care(replaying: Any) -> None:
    """A decline about somebody's own records is the heavier claim, not the lighter one.

    Told the platform found nothing in their records, a person concludes something did not
    happen. Records read and not understood on one draw must not become "there is nothing there".
    """
    client = replaying("[]", '[{"statement": "A run started.", "references": [{"id": "abc123"}]}]')

    claims = LiveEstateProvider(model="anthropic/claude-sonnet@5", api_key="k").answer(
        "What ran last night?", (_Record(),)
    )

    assert claims, "the estate path reported silence on a single empty draw"
    assert client.calls == 2
