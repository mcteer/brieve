# SPDX-License-Identifier: Apache-2.0
"""Whether the surviving claims answer the question that was asked (043, ROADMAP gap 0g).

**A resolving citation proves a document exists, not that it answers anything.** `Corpus.resolves`
checks that a path is pinned and carries an anchor; `answer_question` keeps a claim when every
citation resolves. That was sufficient while the pin was narrow, and 035 widened it to six
product families — after which a question about *this platform's* audit retention could be
answered from HCP Terraform's and Boundary's retention pages, every citation resolving, every
claim true, and the answer wrong.

**The gap is answer-to-question, not claim-to-citation**, which is why two cheaper mechanisms
were rejected in planning: scoping a pack to its own product would decline this case and undo
035 (architecture questions are frequently cross-product), and checking that each claim's cited
section supports that claim would pass every claim here, because each one *is* supported by the
passage it cites.

**The verdict is a leading token, and that is the harness's burden rather than the model's.**
032 recorded the rule after Sonnet refused correctly and said "I can't" — semantically right and
invisible to the platform's vocabulary. A verdict the platform must *search* for is one it will
eventually misread, so the protocol asks for it first and refuses anything else.

**Malformed is a refusal, not a shrug.** A response this module cannot parse means the gate did
not run, and a gate that did not run must never read as one that passed (FR-017).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from core.errors import CoreError

#: The token a verdict must open with. Anything else is malformed — see the module docstring.
VERDICT_TOKEN = "RELEVANT:"

#: What the judge says when no claim answers the question. A distinct word rather than an empty
#: list, because "none" and "the model produced nothing" must not arrive looking identical.
NONE_TOKEN = "none"

_LEADING = re.compile(r"^\s*RELEVANT:\s*(?P<body>.*)$", re.IGNORECASE)
_INDEX = re.compile(r"\d+")


class RelevanceRefused(CoreError):
    """The judgement could not be made. Carries the reason code the decline will name."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class RelevanceVerdict:
    """Which claims the judge affirmed, and what it said to say so."""

    #: Zero-based indices into the claims the judge was shown. Empty is a real verdict.
    relevant: frozenset[int]
    #: The cell's model identity, for the `MODEL_GATE` record.
    model: str
    #: What was parsed. Kept because the verdict word IS the protocol, so a record that
    #: preserved only the interpretation would lose the evidence for it.
    raw_leading_token: str = ""


class RelevanceJudge(Protocol):
    """Asked whether the surviving claims answer the question. Fixtures and adapters implement it.

    **A separate call from the answer**, deliberately: a model grading its own output in the
    same response is the weakest form of this check, and the point of the feature is that the
    check means something.
    """

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        """Return which claims answer ``question``.

        Raises:
            RelevanceRefused: the judgement could not be made — unreachable, unqualified, or a
                response that does not carry a verdict. Every one of those declines the answer
                naming its cause; none of them may be read as an affirmation.
        """
        ...


def parse_verdict(response: str, *, claim_count: int, model: str = "") -> RelevanceVerdict:
    """Read a judge's response, or refuse.

    **Strict on the leading token, forgiving about everything after it.** A model that opens
    correctly and then explains itself has obeyed the protocol; one that explains first has not,
    because the platform would be searching prose for a verdict — and five checks in this
    repository have already matched prose instead of what they meant to match.

    Indices out of range are dropped rather than refused: a judge naming claim 7 of 3 has
    miscounted, and honouring only what exists is narrower than the alternatives (refusing the
    whole verdict would turn a miscount into a decline; keeping it would index off the end).

    Raises:
        RelevanceRefused: `malformed_verdict` — no leading token, or a body naming neither
            `none` nor any index.
    """
    match = _LEADING.match(response or "")
    if match is None:
        raise RelevanceRefused(
            "the relevance judge's response does not open with a verdict; the gate did not "
            "run, and a gate that did not run must not read as one that passed",
            reason_code="malformed_verdict",
        )

    body = match.group("body").strip()
    leading = f"{VERDICT_TOKEN} {body}".strip()

    if body.lower().startswith(NONE_TOKEN):
        return RelevanceVerdict(relevant=frozenset(), model=model, raw_leading_token=leading)

    indices = {int(found) for found in _INDEX.findall(body)}
    if not indices:
        raise RelevanceRefused(
            f"the relevance verdict {leading!r} names neither {NONE_TOKEN!r} nor any claim; "
            f"an unreadable verdict is not an affirmation",
            reason_code="malformed_verdict",
        )

    # The protocol numbers claims from 1 for the model's benefit; everything inside is 0-based.
    zero_based = frozenset(index - 1 for index in indices if 1 <= index <= claim_count)
    return RelevanceVerdict(relevant=zero_based, model=model, raw_leading_token=leading)


def render_claims(claims: Sequence[str]) -> str:
    """Number the claims for the judge, from 1. The one place that numbering is decided."""
    return "\n".join(f"{position}. {claim}" for position, claim in enumerate(claims, start=1))


__all__ = [
    "NONE_TOKEN",
    "VERDICT_TOKEN",
    "RelevanceJudge",
    "RelevanceRefused",
    "RelevanceVerdict",
    "parse_verdict",
    "render_claims",
]
