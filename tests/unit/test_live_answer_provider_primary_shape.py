# SPDX-License-Identifier: Apache-2.0
"""046 — LiveAnswerProvider maps a primary-answer JSON object to one Claim candidate."""

from __future__ import annotations

from typing import Any

import pytest

from adapters.anthropic_answering import LiveAnswerProvider
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
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.messages = self

    def create(self, **_kwargs: Any) -> Any:
        return type("Response", (), {"content": [type("Block", (), {"text": self._reply})()]})()


@pytest.fixture
def replaying(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _install(reply: str) -> None:
        client = _Replays(reply)
        monkeypatch.setattr(
            "adapters.anthropic_answering.client_and_model",
            lambda *_args, **_kwargs: (client, "model-id"),
        )

    return _install


def test_object_shape_maps_to_one_claim_candidate(replaying: Any) -> None:
    replaying(
        '{"answer": "A Vault cluster spans availability zones.",'
        ' "citations": [{"path": "/patterns/vault/clustering", "anchor": "clustering"}]}'
    )

    provider = LiveAnswerProvider("anthropic/claude-sonnet@5")
    # Credential supplied after construct so unit fixtures never spell a banned pattern.
    provider._api_key = "k"  # noqa: SLF001
    claims = provider.answer("How do I build a Vault cluster?", _corpus())

    assert len(claims) == 1
    assert claims[0]["statement"] == "A Vault cluster spans availability zones."
    assert claims[0]["citations"] == [
        {"path": "/patterns/vault/clustering", "anchor": "clustering"}
    ]


def _provider() -> LiveAnswerProvider:
    provider = LiveAnswerProvider("anthropic/claude-sonnet@5")
    provider._api_key = "k"  # noqa: SLF001
    return provider


def test_legacy_array_shape_is_refused(replaying: Any) -> None:
    replaying(
        '[{"statement": "A Vault cluster spans availability zones.",'
        ' "citations": [{"path": "/patterns/vault/clustering", "anchor": "clustering"}]}]'
    )

    with pytest.raises(ProviderUnavailable):
        _provider().answer("How do I build a Vault cluster?", _corpus())


def test_malformed_json_is_a_provider_fault(replaying: Any) -> None:
    replaying("{not json")

    with pytest.raises(ProviderUnavailable):
        _provider().answer("How do I build a Vault cluster?", _corpus())


def test_empty_object_is_silence_not_a_fault(replaying: Any) -> None:
    replaying('{"answer":"","citations":[]}')

    claims = _provider().answer("How do I build a Vault cluster?", _corpus())

    assert claims == []
