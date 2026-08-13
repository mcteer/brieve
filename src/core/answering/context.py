# SPDX-License-Identifier: Apache-2.0
"""What a later question is told about the earlier ones.

**Context is not a source.** The model is shown earlier exchanges so that "what about
multi-region?" has a subject, and for no other reason. A claim still ships only when it cites
a section that resolves against the pinned corpus (FR-018) — and the way that is kept true
here is structural rather than instructed: **citations are stripped before the block is
built**, so there is nothing in history to cite through. An instruction not to cite history
would be a prompt, and prompts drift; 035's stale `_INSTRUCTION` cost a feature's worth of
declines proving it.

**A decline contributes its question and never its verdict** (FR-014a). "How do I rotate PKI
certificates?" is what the follow-up refers to; "the pinned corpus does not support an answer"
is a fact about the corpus, and feeding it back invites the model to agree rather than read.

**The bound is stated, not emergent** (FR-015). Whole exchanges only, oldest dropped first, so
the descriptor in the evidence record is always true: an exchange was carried or it was not,
never half of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from core.answering.conversations.records import ExchangeDisposition, ExchangeRecord

#: How many earlier exchanges may be carried.
#:
#: Six, because a person following up is following up on what they just read, and the unit
#: they reason in is exchanges ("it forgot what we said three questions ago"). Beyond six the
#: material stops being what the conversation is about and starts being its history.
MAX_CARRIED_EXCHANGES: Final[int] = 6

#: The character budget across all carried material, guarding against six enormous questions.
#:
#: 6,000 characters is roughly 1.5K tokens against the ~8.4K tokens of corpus sections the
#: model already receives — context stays a MINORITY VOICE beside the corpus, which is what
#: FR-018 requires of something that is not a source.
MAX_CARRIED_CHARS: Final[int] = 6_000

#: How a carried question is introduced in the block.
#:
#: Shared rather than spelled twice, because the RETRIEVER reads these lines back out (see
#: `_retrieval_query` in the Anthropic adapter). A follow-up like "and the clients?" carries one
#: word, and a search on that word alone returns Consul DNS and Windows containers — measured.
#: The subject has to reach the search, not only the model, so the marker is part of the
#: contract between them rather than an incidental piece of wording.
QUESTION_MARKER: Final[str] = "Earlier question: "


@dataclass(frozen=True)
class CarriedContext:
    """The block handed to the model, and what the record will say about it."""

    #: The rendered history block. Empty when nothing was carried.
    text: str = ""
    #: Which exchange seqs were carried, oldest first.
    carried: tuple[int, ...] = ()
    #: How many exchanges existed but were dropped at the bound.
    dropped: int = 0
    #: Whether the route was inherited rather than computed from the question's own words.
    inherited_route: bool = False

    @property
    def descriptor(self) -> dict[str, Any]:
        """What `record_ask` writes into the payload (FR-020–022)."""
        return {
            "exchanges": list(self.carried),
            "dropped": self.dropped,
            "inherited_route": self.inherited_route,
        }

    @property
    def note(self) -> str:
        """What the person is told when the conversation outgrew the bound (FR-016)."""
        if not self.dropped:
            return ""
        return (
            f"This answer was given the {len(self.carried)} most recent exchanges in this "
            f"conversation; {self.dropped} earlier "
            f"{'exchange was' if self.dropped == 1 else 'exchanges were'} not carried."
        )


def _statements(outcome: dict[str, Any]) -> list[str]:
    """The answer text from a stored outcome — and nothing else from it.

    Citations, notes and the source label are deliberately not read. What comes back here is
    the platform's own already-gated prose: each statement survived citation resolution when
    it shipped, so carrying it re-introduces nothing unvetted.

    **046 dual-shape:** new guidance outcomes carry `primary_answer`; pre-046 and estate
    outcomes still use `claims[].statement`. Read both so a follow-up after a new answer still
    receives the subject (T008).
    """
    primary = str(outcome.get("primary_answer", "")).strip()
    if primary:
        return [primary]
    claims = outcome.get("claims")
    if not isinstance(claims, list):
        return []
    return [
        str(claim["statement"]).strip()
        for claim in claims
        if isinstance(claim, dict) and str(claim.get("statement", "")).strip()
    ]


def _render(exchange: ExchangeRecord) -> str:
    """One exchange as history. Question always; answers as statements; verdicts never."""
    lines = [f"{QUESTION_MARKER}{exchange.question.strip()}"]
    if exchange.disposition is ExchangeDisposition.ANSWERED:
        for statement in _statements(exchange.outcome):
            lines.append(f"  - {statement}")
    return "\n".join(lines)


def build_context(
    exchanges: tuple[ExchangeRecord, ...],
    *,
    inherited_route: bool = False,
    max_exchanges: int = MAX_CARRIED_EXCHANGES,
    max_chars: int = MAX_CARRIED_CHARS,
) -> CarriedContext:
    """The bounded history block for a follow-up, oldest-first, newest kept.

    `exchanges` arrives oldest-first. Selection walks backwards from the newest so the bound
    keeps what the person is most likely referring to, then renders forwards so the model
    reads the conversation in the order it happened.
    """
    if not exchanges:
        return CarriedContext(inherited_route=inherited_route)

    kept: list[ExchangeRecord] = []
    budget = max_chars
    for exchange in reversed(exchanges):
        if len(kept) >= max_exchanges:
            break
        rendered = _render(exchange)
        # Whole exchanges only. A partial exchange would make the descriptor a lie and could
        # hand the model half a sentence.
        if len(rendered) > budget:
            break
        budget -= len(rendered)
        kept.append(exchange)

    kept.reverse()
    if not kept:
        return CarriedContext(dropped=len(exchanges), inherited_route=inherited_route)

    body = "\n\n".join(_render(exchange) for exchange in kept)
    text = (
        "Earlier in this conversation (for reference only — this is NOT corpus material, "
        "nothing here may be cited, and every claim you make still requires a citation into "
        "the sections supplied below):\n\n" + body
    )
    return CarriedContext(
        text=text,
        carried=tuple(exchange.seq for exchange in kept),
        dropped=len(exchanges) - len(kept),
        inherited_route=inherited_route,
    )


__all__ = [
    "MAX_CARRIED_CHARS",
    "MAX_CARRIED_EXCHANGES",
    "QUESTION_MARKER",
    "CarriedContext",
    "build_context",
]
