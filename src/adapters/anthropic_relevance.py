# SPDX-License-Identifier: Apache-2.0
"""The live relevance judge (043, T018).

**Through `client_and_model`, not `import anthropic`.** The adapter layer owns the vendor
binding (Principle I), and `tests/unit/test_no_live_dependencies.py` forbids a test module
reaching an SDK directly with no allowlist — it caught 041's authoring lane doing exactly that.
That shared factory also owns the credential check, the extra check and the model-id derivation,
each of which has been wrong here at least once.

**Sealed-core additive class**, named in the plan's Principle V row.

**Two instructions here were bought with live calls, and both are load-bearing.** The deixis
line and the subject-not-sufficiency line each fixed a real misjudgement, and each was measured
against the WHOLE seed set before shipping because the tempting version of both over-refuses.
`tests/unit/test_live_relevance_adapter.py` pins them with the numbers.

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

if none of them do.

When the question says "this platform", "this product", "our system" or "we", it refers to the
asker's own system — not to any of the products the statements are about.

Judge SUBJECT, not sufficiency. A statement that is about what was asked is relevant even if it
is partial, or general, or only says where the full answer is documented. Mark a statement
irrelevant only when it is about something else."""

#: **Not "enough for one line" — that reasoning was wrong and measured wrong.** The first draft
#: set 256 on the grounds that the protocol only uses one line, and 043's live probe hit
#: `stop_reason=max_tokens` with an EMPTY body on three consecutive samples of the motivating
#: case: the model spends budget reasoning *before* the line, so the budget must cover the
#: reasoning it never emits. 031 recorded this exact failure and this module's docstring cited
#: it as a risk while the constant reproduced it.
#:
#: Intermittent, and that is what makes it expensive: the same input answered on some samples
#: and returned nothing on others, so it reads as model flakiness rather than as a harness
#: defect. `_refused_for_budget` below is what makes it name itself next time.
_MAX_TOKENS = 2048


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
        # Truncation gets its OWN refusal, because "the model returned no verdict" and "the
        # budget ran out before the model wrote one" send a reader to entirely different places
        # — the first to the prompt, the second to this file. 043 spent live calls learning
        # that the generic message names neither.
        if getattr(message, "stop_reason", None) == "max_tokens" and not response.strip():
            raise RelevanceRefused(
                f"the relevance judge exhausted its {_MAX_TOKENS}-token budget before writing "
                f"a verdict; the gate did not run, and the budget is this adapter's to fix",
                reason_code="truncated_verdict",
            )
        # `parse_verdict` raises `RelevanceRefused(malformed_verdict)` on anything that does
        # not open with the token — deliberately not caught here, because a malformed verdict
        # is a different cause from an unreachable judge and the record must say which.
        return parse_verdict(response, claim_count=len(claims), model=self.model)


def build_relevance_judge(cell_reference: str, secret: str) -> LiveRelevanceJudge:
    """The judge for a resolved cell, holding a credential brokered for THIS ask.

    Mirrors `build_ask_provider` deliberately, and for the same reason: the surfaces call it
    once per question with material brokered for that question, and drop the result with the
    answer. A judge built at assembly would hold the credential for the life of the process —
    the standing credential Principle IV forbids, moved rather than removed.

    The cell reference is `pack:model:role`; the model is the middle field. Parsed here rather
    than in each assembly so the two surfaces cannot drift on it — which is exactly how the API
    came to emit `model_gate` while MCP did not.
    """
    parts = cell_reference.split(":")
    if len(parts) != 3:
        raise RelevanceRefused(
            f"the relevance cell reference {cell_reference!r} is not `pack:model:role`; "
            f"a judge cannot be built for a cell that cannot be read",
            reason_code="relevance_unavailable",
        )
    return LiveRelevanceJudge(parts[1], api_key=secret)


__all__ = ["LiveRelevanceJudge", "build_relevance_judge"]
