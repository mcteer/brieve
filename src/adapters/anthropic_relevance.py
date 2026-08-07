# SPDX-License-Identifier: Apache-2.0
"""The live relevance judge (043, T018).

**Through `client_and_model`, not `import anthropic`.** The adapter layer owns the vendor
binding (Principle I), and `tests/unit/test_no_live_dependencies.py` forbids a test module
reaching an SDK directly with no allowlist — it caught 041's authoring lane doing exactly that.
That shared factory also owns the credential check, the extra check and the model-id derivation,
each of which has been wrong here at least once.

**Sealed-core additive class**, named in the plan's Principle V row.

**The protocol is a leading token, and the burden is the harness's.** 032 recorded the rule
after Sonnet refused correctly and said "I can't" — semantically right and invisible to the
platform's vocabulary. A verdict this module had to *search* prose for is one it would
eventually misread, so it asks for the verdict first and refuses anything else.
"""

from __future__ import annotations

from collections.abc import Sequence

from adapters.anthropic_scorer import client_and_model
from core.answering.relevance import (
    RelevanceRefused,
    RelevanceVerdict,
    parse_verdict,
    render_claims,
)

#: What the judge is asked. Short on purpose: the question it answers is narrow, and a prompt
#: that explained relevance at length would be teaching the model the standard rather than
#: asking for its judgement of it.
_SYSTEM = """You decide whether statements answer a question.

You are given a QUESTION and numbered STATEMENTS. Every statement is already known to be true
and correctly cited. Your only job is to say which of them answer the question that was asked.

A statement about a different product, a different system, or a neighbouring topic does NOT
answer the question, however true and however well cited it is.

Reply with exactly one line, and nothing else:

RELEVANT: 1,3

listing the numbers of the statements that answer the question, or:

RELEVANT: none

if none of them do."""

#: Enough for one line. A budget that let the model reason at length before answering would buy
#: nothing the protocol uses, and 031's live lane recorded what a too-small budget costs — a
#: response whose reasoning consumed the tokens and returned no text at all.
_MAX_TOKENS = 256


class LiveRelevanceJudge:
    """Asks a real model whether the surviving claims answer the question."""

    def __init__(self, model: str, *, api_key: str | None = None) -> None:
        #: The cell's model. Carried onto the verdict so `MODEL_GATE` records which model
        #: judged rather than leaving it to be inferred from a binding somebody must go read.
        self.model = model
        self._api_key = api_key

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        """Return which claims answer ``question``.

        Every failure becomes `RelevanceRefused`, never a raw vendor exception: the caller
        turns a refusal into a decline naming its cause, and an exception escaping as a
        provider fault would be indistinguishable from the answering model being unreachable —
        which sends a reader to the wrong place.
        """
        try:
            client, api_model = client_and_model(self.model, api_key=self._api_key)
        except Exception as exc:  # noqa: BLE001 — an unreachable judge is a refusal
            raise RelevanceRefused(
                f"the relevance judge could not be constructed: {type(exc).__name__}",
                reason_code="relevance_unavailable",
            ) from exc

        prompt = f"QUESTION: {question}\n\nSTATEMENTS:\n{render_claims(claims)}"
        try:
            message = client.messages.create(  # type: ignore[attr-defined]
                model=api_model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 — same reason as above
            raise RelevanceRefused(
                f"the relevance judge could not be reached: {type(exc).__name__}",
                reason_code="relevance_unavailable",
            ) from exc

        response = "".join(block.text for block in message.content if block.type == "text")
        # `parse_verdict` raises `RelevanceRefused(malformed_verdict)` on anything that does
        # not open with the token — deliberately not caught here, because a malformed verdict
        # is a different cause from an unreachable judge and the record must say which.
        return parse_verdict(response, claim_count=len(claims), model=self.model)


__all__ = ["LiveRelevanceJudge"]
