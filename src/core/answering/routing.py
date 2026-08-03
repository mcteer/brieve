# SPDX-License-Identifier: Apache-2.0
"""Which source a question needs — decided here, deterministically, and recorded.

**A person asks in one place.** ADR-0035 says everyone asks in the same place and the answer is
bounded by who is asking; 024 built one `ask` operation. So something has to decide whether a
question wants the pinned corpus or the estate's own records, and this is that something.

**No model decides.** A model router would make Principle VIII's gates apply to routing, and
scoring it in the blocking lane would mean scoring against recordings — which is the exact defect
this lineage exists to close. Deterministic string shape is scorable with no credential, and a
misroute is a bug with a failing test rather than a judgement call.

**Ties break toward estate, and the reason is asymmetric failure.** Routing a guidance question to
the estate performs a *scoped read* — an access record for a question that was never about the
records, an act rather than a bad answer. Routing an estate question to the corpus tells someone
their own records are documentation. Both are wrong, but the estate-side failure is **visible to
the asker**: they get a decline naming the evidence plane and they rephrase. The corpus-side
failure returns a plausible answer from the wrong source, and nobody learns anything. Visible
failures get fixed, so the tie goes where the failure is visible.

**Nothing here reads anything.** The router sees a string and returns an enum member. It holds no
corpus, no query, no clock — the window vocabulary below is *recognised* here and *resolved* by
the caller against an injected clock, because ambient time inside core is how an eval lane stops
being deterministic.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final


class Route(StrEnum):
    """Where a question's answer must come from. Closed, and `NEITHER` is a real answer."""

    GUIDANCE = "guidance"
    ESTATE = "estate"
    #: Fits no source. **Declines** — the router never coerces a question into a source to avoid
    #: saying it does not know, because a coerced route produces a confident answer from material
    #: that was never about the question.
    NEITHER = "neither"


#: The estate's own nouns and verbs — the vocabulary of *what this platform did*.
#:
#: Drawn from the trail's vocabulary rather than invented: these are the words that appear in
#: `AuditEventType` and in the questions ADR-0035 names (*"which workspaces violate a control"*,
#: *"what changed last night"*).
#:
#: **This is the STRONG set: words that appear only in what-happened questions** (029).
#:
#: Measured: 4 of 12 plainly estate-shaped questions declined without reading a record, because
#: the list held the trail's verbs and not its nouns. The obvious repair — add `tool`, `agent`,
#: `secret` — captures guidance questions instead, since ties break toward estate.
#:
#: Two things had to be true at once, and one rule delivers both. **Nouns are plural-only**:
#: how-to questions name things in the singular (*read a secret*, *configure the vault agent*)
#: while what-happened questions name them in the plural (*were any secrets read*). And the
#: plurals still live in `ESTATE_NOUNS` below rather than here, because even plural they appear
#: in guidance — *"the recommended pattern for dynamic secrets"* is documentation, and an
#: existing row said so on the first run of the wider vocabulary.
#:
#: `did` is here against the instinct that it is too common: it is the *what-happened* auxiliary,
#: it routes *"What did the planner agent do?"*, and it appears in no guidance question anyone
#: has written.
ESTATE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "active",
        "audit",
        "changed",
        "did",
        "denied",
        "estate",
        "evidence",
        "failed",
        "granted",
        "happened",
        "refused",
        "resumed",
        "run",
        "runs",
        "stopped",
        "trail",
        "used",
        "violate",
        "violates",
        "violation",
        "violations",
    }
)

#: Nouns the estate and the documentation **both** own (029).
#:
#: `secrets`, `tools`, `agents` name things this platform records *and* things its documentation
#: explains. Alone they mean the estate; beside an explicit guidance marker they do not, because
#: *"the recommended pattern for dynamic secrets"* is a request for documentation that happens to
#: name a noun the trail also uses.
#:
#: **This is not a softening of the tie-break.** That rule exists for genuine ties, and a question
#: carrying two explicit guidance markers against one shared noun is not a tie — it is a guidance
#: question with a noun in it. Strong estate terms still win outright, so the asymmetric-failure
#: argument in the module docstring is untouched where it applies.
ESTATE_NOUNS: Final[frozenset[str]] = frozenset(
    {
        "agents",
        "record",
        "records",
        "secrets",
        "tools",
        "workspace",
        "workspaces",
    }
)

#: Phrases that make a question about a *window of time*, which only the records can answer.
#: Recognised here; **resolved by the caller against an injected clock** (see module docstring).
WINDOW_PHRASES: Final[tuple[str, ...]] = (
    "last night",
    "yesterday",
    "today",
    "this week",
    "last week",
    "overnight",
)

#: How something works, as opposed to what happened. The corpus's territory.
GUIDANCE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "architecture",
        "configure",
        "guide",
        "how",
        "pattern",
        "practice",
        "recommend",
        "recommended",
        "reference",
        "should",
        "supposed",
        "why",
    }
)

_WORD = re.compile(r"[a-z0-9]+")


def _words(question: str) -> set[str]:
    return set(_WORD.findall(question.lower()))


def window_phrase(question: str) -> str | None:
    """The temporal phrase this question carries, if it is one this platform recognises.

    **A closed vocabulary, deliberately.** General natural-language time parsing would put a
    guessing component on the answering path, and a question whose window was guessed wrong
    returns records from the wrong period while looking entirely correct. A phrase outside this
    list is not an error — the caller falls back to the read's own bound and says so.
    """
    lowered = question.lower()
    for phrase in WINDOW_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def route(question: str) -> Route:
    """Decide the source. Same question, same answer, always."""
    words = _words(question)
    strong = bool(words & ESTATE_TERMS) or window_phrase(question) is not None
    shared_noun = bool(words & ESTATE_NOUNS)
    guidance = bool(words & GUIDANCE_TERMS)

    if strong:
        # Including when guidance also matches — see the module docstring on asymmetric failure.
        # A what-happened word is not ambiguous, so the tie-break applies with its full force.
        return Route.ESTATE
    if shared_noun and not guidance:
        # A noun both worlds own, with nothing pulling the other way: the estate, on the same
        # asymmetric-failure reasoning.
        return Route.ESTATE
    if guidance:
        return Route.GUIDANCE
    # A shared noun cannot reach here with guidance unset — the branch above took it.
    return Route.ESTATE if shared_noun else Route.NEITHER


__all__ = [
    "ESTATE_NOUNS",
    "ESTATE_TERMS",
    "GUIDANCE_TERMS",
    "WINDOW_PHRASES",
    "Route",
    "route",
    "window_phrase",
]
