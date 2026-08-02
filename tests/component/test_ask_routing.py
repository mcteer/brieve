# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — one source, decided deterministically, declining rather than guessing.

Routing exists because asking happens in **one place** (spec FR-010): a person asks, and the
platform works out what the question needs. That makes routing a component with its own failure
modes rather than a detail, so it is tested like one.

**The `NEITHER` rows are the fail-closed ones.** A router that always returned a source would look
better in every demo and would answer questions from material that was never about them.
"""

from __future__ import annotations

import pytest

from core.answering.routing import Route, route, window_phrase

ESTATE_QUESTIONS = [
    "Which workspaces violate the control?",
    "What changed last night?",
    "Which runs were denied yesterday?",
    "Show me the records for the failed run.",
    "Who was granted access to the estate?",
]

GUIDANCE_QUESTIONS = [
    "How does an AI agent obtain an identity with Vault?",
    "What is the recommended pattern for dynamic secrets?",
    "Why should I use a validated architecture here?",
    "How do I configure the reference pattern?",
]

#: Fit neither vocabulary. **Not nonsense** — plausible questions this platform simply has no
#: source for, which is the case a coercing router answers wrongly and confidently.
NEITHER_QUESTIONS = [
    "What is the weather in Denver?",
    "Please summarise the quarterly earnings call.",
    "Who won the match?",
]


@pytest.mark.parametrize("question", ESTATE_QUESTIONS)
def test_estate_shaped_questions_route_to_the_records(question: str) -> None:
    assert route(question) is Route.ESTATE


@pytest.mark.parametrize("question", GUIDANCE_QUESTIONS)
def test_guidance_shaped_questions_route_to_the_corpus(question: str) -> None:
    assert route(question) is Route.GUIDANCE


@pytest.mark.parametrize("question", NEITHER_QUESTIONS)
def test_a_question_that_fits_no_source_is_not_coerced_into_one(question: str) -> None:
    """The spec's *"decline, not a coin flip"* edge case.

    A router that picked a source here would send a weather question to somebody's audit trail —
    performing a scoped read for a question that was never about the records.
    """
    assert route(question) is Route.NEITHER


def test_a_question_matching_both_vocabularies_goes_to_the_estate() -> None:
    """The recorded tie-break, and its reason is asymmetric failure.

    *"How should I have configured the workspace that failed last night?"* is legitimately both.
    The tie goes to the estate because that misroute **declines visibly** — the asker is told the
    records do not support it and rephrases — while the corpus misroute returns a plausible answer
    from the wrong source and nobody finds out.
    """
    both = "How should I have configured the workspace that failed last night?"
    assert route(both) is Route.ESTATE


def test_routing_is_deterministic() -> None:
    """No model, no clock, no state — asserted rather than assumed.

    A router whose answer drifted would make every downstream row flaky, and the flake would look
    like a model problem rather than a routing one.
    """
    for question in ESTATE_QUESTIONS + GUIDANCE_QUESTIONS + NEITHER_QUESTIONS:
        assert len({route(question) for _ in range(10)}) == 1


def test_window_phrases_are_recognised_but_not_resolved() -> None:
    """The router names the phrase; the caller resolves it against an injected clock.

    Resolving here would mean reading ambient time inside core, which is how an eval lane stops
    being reproducible — the same hazard the workflow runtime bans `Date.now()` for.
    """
    assert window_phrase("What changed last night?") == "last night"
    assert window_phrase("Which runs failed today?") == "today"
    assert window_phrase("Which workspaces violate the control?") is None
