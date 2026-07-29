# SPDX-License-Identifier: Apache-2.0
"""What the injection lens looks for, and why it lives in this repository.

**These patterns are an executed artifact.** The lens runs against every skill bump, and its
verdict decides whether content enters the platform — so ADR-0030's rule puts it firmly on
the *pinned* side: what the agent executes is pinned, what it consults is fetched fresh. A
lens whose patterns arrived from a feed would be an ungated input to a gate, which is the
regress this whole feature exists to terminate.

So they are here, in a file, reviewed like code.

**Pattern-based deliberately, not model-scored.** A model-scored lens would make promotion
depend on a model, which needs a qualified cell, which needs the gates to have run — a
second regress, and one with no seed set to terminate it. That is not a limitation being
tolerated; it is the only design that closes.

**The honest limit, stated where it will be read**: this catches known shapes and not novel
phrasing. It is a **floor**, not a guarantee, and ADR-0004's human review is what covers the
rest. A row in `test_injection_lens.py` asserts a phrasing this misses, so the floor is
documented by a test rather than only by this paragraph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionPattern:
    """One shape, with what it is trying to do and why that matters."""

    name: str
    pattern: re.Pattern[str]
    #: What an author is told when this fires. Names the behaviour rather than the regex —
    #: "this text instructs the agent to ignore its instructions" is actionable; "matched
    #: pattern 7" is not.
    explanation: str


def _p(name: str, expression: str, explanation: str) -> InjectionPattern:
    return InjectionPattern(
        name=name,
        pattern=re.compile(expression, re.IGNORECASE | re.MULTILINE),
        explanation=explanation,
    )


#: The three families ADR-0004 names: overriding instructions, exfiltrating context, and
#: redirecting tool use. Grouped that way rather than as a flat list because the families are
#: what a reviewer reasons about, and a new pattern should have to say which one it joins.
INJECTION_PATTERNS: tuple[InjectionPattern, ...] = (
    # --- Overriding system instructions
    _p(
        "ignore_previous_instructions",
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
        r"(previous|prior|earlier|above|system|all)\b[^.\n]{0,20}\b"
        r"(instruction|prompt|rule|direction|guideline)s?\b",
        "instructs the agent to disregard its own instructions",
    ),
    _p(
        "new_persona",
        r"\byou are (now|actually|really)\b|\bfrom now on,? you\b|\bact as if you\b",
        "attempts to replace the agent's role with a different one",
    ),
    _p(
        "developer_or_system_impersonation",
        r"^\s*(system|developer|admin(istrator)?)\s*[:>]\s*\S",
        "impersonates a system or developer turn inside content the agent reads",
    ),
    _p(
        "suppress_governance",
        r"\b(do not|don'?t|never)\b[^.\n]{0,30}\b"
        r"(log|record|audit|report|mention|tell|disclose)\b",
        "asks the agent to withhold something from the record",
    ),
    # --- Exfiltrating context
    _p(
        "reveal_context",
        r"\b(reveal|print|output|repeat|show|dump|summari[sz]e)\b[^.\n]{0,30}\b"
        r"(system prompt|your instructions|the context|conversation history|"
        r"credential|secret|token|api[_ ]?key)s?\b",
        "asks the agent to emit its context, instructions, or secret material",
    ),
    _p(
        "send_somewhere",
        r"\b(send|post|upload|transmit|exfiltrate|forward)\b[^.\n]{0,40}\b"
        r"(https?://|webhook|endpoint|external|my server)\b",
        "directs the agent to transmit content to an external destination",
    ),
    _p(
        "encode_to_evade",
        r"\b(base64|rot13|hex[- ]?encode|url[- ]?encode)\b[^.\n]{0,40}\b"
        r"(before|then|and)\b[^.\n]{0,20}\b(send|post|output|return)\b",
        "encodes content before emitting it, which defeats inspection of what was sent",
    ),
    # --- Redirecting tool use
    _p(
        "always_call",
        r"\b(always|automatically|without asking|silently)\b[^.\n]{0,30}\b"
        r"(call|invoke|run|execute|use)\b[^.\n]{0,30}\b(tool|command|script|function)\b",
        "instructs the agent to invoke tools outside the governed decision path",
    ),
    _p(
        "bypass_approval",
        r"\b(skip|bypass|avoid|without)\b[^.\n]{0,30}\b"
        r"(approval|confirmation|review|permission|authori[sz]ation)\b",
        "instructs the agent to proceed without an approval policy may require",
    ),
    _p(
        "escalate",
        r"\b(sudo|root|elevate|escalate|admin(istrator)? (access|rights|privileges))\b",
        "seeks privilege beyond what the definition was granted",
    ),
)


__all__ = ["INJECTION_PATTERNS", "InjectionPattern"]
