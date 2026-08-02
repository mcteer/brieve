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
ESTATE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "audit",
        "changed",
        "denied",
        "estate",
        "evidence",
        "failed",
        "granted",
        "happened",
        "record",
        "records",
        "refused",
        "resumed",
        "run",
        "runs",
        "stopped",
        "trail",
        "violate",
        "violates",
        "violation",
        "violations",
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
    estate = bool(words & ESTATE_TERMS) or window_phrase(question) is not None
    guidance = bool(words & GUIDANCE_TERMS)

    if estate:
        # Including when BOTH match — see the module docstring on asymmetric failure.
        return Route.ESTATE
    if guidance:
        return Route.GUIDANCE
    return Route.NEITHER


__all__ = ["ESTATE_TERMS", "GUIDANCE_TERMS", "WINDOW_PHRASES", "Route", "route", "window_phrase"]
