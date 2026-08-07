# SPDX-License-Identifier: Apache-2.0
"""The live judge's failure modes, hermetically (043).

**Written because 043's live probe hit one of them and the message named the wrong thing.**
The adapter's first budget was 256 tokens on the reasoning that the protocol only uses one
line. Three consecutive samples of the motivating case came back `stop_reason=max_tokens` with
an empty body — the model spends budget reasoning *before* the line — and the refusal said
"does not open with a verdict", which sends a reader to the prompt when the fault is in this
file.

Intermittent, which is what made it expensive: the same input answered on some samples and
returned nothing on others, so it read as model flakiness. These rows are what stop the next
occurrence from costing the same diagnosis, and they need no credential to run.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.anthropic_relevance import _MAX_TOKENS, LiveRelevanceJudge
from core.answering.relevance import RelevanceRefused


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Message:
    def __init__(self, text: str, stop_reason: str) -> None:
        self.content = [_Block(text)] if text else []
        self.stop_reason = stop_reason


class _FakeClient:
    """Stands in for the SDK client the adapter seam returns. Records what it was asked."""

    def __init__(self, message: _Message) -> None:
        self._message = message
        self.max_tokens: int | None = None

        class _Messages:
            def create(inner: Any, **kwargs: Any) -> _Message:  # noqa: N805
                self.max_tokens = kwargs.get("max_tokens")
                return self._message

        self.messages = _Messages()


def _judge(monkeypatch: pytest.MonkeyPatch, message: _Message) -> tuple[LiveRelevanceJudge, Any]:
    client = _FakeClient(message)
    # `**_` rather than naming the credential keyword: the no-secret-like-strings guard bans
    # that token in unit fixtures, and a fake has no business pinning the parameter's name.
    monkeypatch.setattr(
        "adapters.anthropic_relevance.client_and_model",
        lambda model, **_: (client, "claude-sonnet-5"),
    )
    return LiveRelevanceJudge("anthropic/claude-sonnet@5"), client


def test_a_truncated_response_names_the_budget_not_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row this file exists for. The distinction is the whole value of the message."""
    judge, _ = _judge(monkeypatch, _Message("", "max_tokens"))

    with pytest.raises(RelevanceRefused) as raised:
        judge.assess("q", ["a", "b"])

    assert raised.value.reason_code == "truncated_verdict", (
        "a budget exhaustion and a disobeyed protocol are different faults with different "
        "fixes; one reason code for both sends half the readers to the wrong file"
    )
    assert str(_MAX_TOKENS) in str(raised.value), "the message states the budget that ran out"


def test_a_disobeyed_protocol_is_still_malformed_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other side of the distinction, or the first row proves nothing."""
    judge, _ = _judge(monkeypatch, _Message("Sure! Claims 1 and 2 are relevant.", "end_turn"))

    with pytest.raises(RelevanceRefused) as raised:
        judge.assess("q", ["a", "b"])

    assert raised.value.reason_code == "malformed_verdict"


def test_a_complete_response_that_is_empty_is_not_blamed_on_the_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`stop_reason` is the discriminator, not emptiness — an empty end_turn is a bad verdict."""
    judge, _ = _judge(monkeypatch, _Message("", "end_turn"))

    with pytest.raises(RelevanceRefused) as raised:
        judge.assess("q", ["a"])

    assert raised.value.reason_code == "malformed_verdict"


def test_the_budget_covers_reasoning_the_model_never_emits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A regression guard on the constant itself, with the measurement that set it.

    256 reproduced 031's empty-response failure on real traffic. The number here is not a
    style preference — it is the difference between a gate that runs and one that intermittently
    does not, and a future "it only needs one line" edit would be exactly the reasoning that
    was already wrong once.
    """
    judge, client = _judge(monkeypatch, _Message("RELEVANT: 1", "end_turn"))

    judge.assess("q", ["a"])

    assert client.max_tokens == _MAX_TOKENS
    assert _MAX_TOKENS >= 1024, (
        "the budget must cover the reasoning the model spends before the verdict line, not "
        "the verdict line alone — 256 returned an empty body on three consecutive live samples"
    )


def test_an_unreachable_judge_refuses_rather_than_raising_a_vendor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider fault and a judge fault send a reader to different places."""

    def _explode(model: str, **_: object) -> tuple[object, str]:
        raise RuntimeError("no credential")

    monkeypatch.setattr("adapters.anthropic_relevance.client_and_model", _explode)
    judge = LiveRelevanceJudge("anthropic/claude-sonnet@5")

    with pytest.raises(RelevanceRefused) as raised:
        judge.assess("q", ["a"])

    assert raised.value.reason_code == "relevance_unavailable"


def test_the_prompt_resolves_this_platform_to_the_asker_not_a_documented_product() -> None:
    """Measured, and both halves of the measurement matter (043).

    The judge kept three claims about three *different* products as answers to "this platform's
    audit log", because nothing told it what "this platform" refers to. The first fix said
    product statements do not answer such questions, which corrected the case 3/3 and dropped
    the seed set from 10/10 to 6/10 — it taught the judge that documented products are
    generally irrelevant.

    What shipped changes deixis resolution ONLY: the live case went 3/3 and the seed stayed
    10/10. This row pins the narrow form, because the broad form is the tempting edit.
    """
    from adapters.anthropic_relevance import _SYSTEM

    assert "this platform" in _SYSTEM and "asker's own system" in _SYSTEM
    assert "does NOT answer it" not in _SYSTEM, (
        "the broad phrasing over-refuses: it cost four correct seed cases when measured"
    )
