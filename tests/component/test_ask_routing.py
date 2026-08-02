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

from core.answering.routing import ESTATE_NOUNS, ESTATE_TERMS, Route, route, window_phrase

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


# ------------------------------------------------------------------ 029: the vocabulary gap


#: The five questions a person actually asked the deployed platform on 2026-08-02, all of which
#: declined without reading a single record. This is the set, verbatim — a fixture drawn from use
#: rather than from imagination, which is the only reason it found what it found.
QUESTIONS_THAT_FAILED = (
    "Which tools were used?",
    "What did the planner agent do?",
    "Were any secrets read?",
    "Which agents are active?",
    "What ran today?",
)

#: The other half of the vocabulary decision, and the half that constrains it.
#:
#: Ties break toward estate, so every term added to reach the set above is a term that can capture
#: a how-to question. These are the shapes that would be lost — including this platform's flagship
#: guidance question, which the singular `agent` misroutes on its own.
GUIDANCE_THAT_MUST_SURVIVE = (
    "How do I read a secret?",
    "How should I configure the vault agent?",
    "How does an AI agent obtain an identity with Vault?",
    "What is the recommended pattern for tool configuration?",
)


def test_the_questions_that_failed_in_use_now_reach_the_estate() -> None:
    """US1, from the deployed platform rather than from a guess.

    A decline naming both doors is honest when a question fits neither. It is a **false negative**
    when the question was about the asker's own estate and the platform simply did not recognise
    the phrasing — and the person receives the identical page either way, which is what made this
    invisible until somebody asked out loud.
    """
    misrouted = [q for q in QUESTIONS_THAT_FAILED if route(q) is not Route.ESTATE]
    assert misrouted == [], f"questions about the asker's own estate still decline: {misrouted}"


def test_guidance_questions_survive_the_wider_estate_vocabulary() -> None:
    """The constraint that decides which terms are allowed at all.

    **A term that cannot survive both this set and the one above is a wrong term**, not a reason
    to bend the tie-break. That is the argument the next person adding vocabulary needs, so it is
    written here rather than left to be rediscovered.

    The rule that satisfies both: nouns are **plural-only**. How-to questions name things in the
    singular (*read a secret*, *configure the vault agent*); what-happened questions name them in
    the plural (*were any secrets read*, *which agents are active*). The grammar is the
    discriminator, and `routing.py` states it as a rule so the list is not mistaken for a
    coincidence.
    """
    captured = [q for q in GUIDANCE_THAT_MUST_SURVIVE if route(q) is not Route.GUIDANCE]
    assert captured == [], (
        f"the estate vocabulary captured guidance questions: {captured}. A term that cannot "
        f"survive both regression sets is the wrong term — the tie-break is not the problem"
    )


def test_the_vocabulary_keeps_shared_nouns_out_of_the_strong_set() -> None:
    """The structure, asserted directly, because two frozensets do not explain themselves.

    Two mistakes are available here and both look like tidying:

    **Adding a singular** (`agent`, `secret`, `tool`) to either set. Singular nouns belong to
    how-to questions, and `agent` alone misroutes this platform's flagship guidance question.

    **Promoting a shared noun** into `ESTATE_TERMS`. `secrets` there would win outright over the
    guidance markers in *"the recommended pattern for dynamic secrets"* — which is exactly what
    an existing row caught on the first run of the wider vocabulary, and precisely why the two
    sets exist rather than one.
    """
    for singular in ("tool", "agent", "secret"):
        assert singular not in ESTATE_TERMS and singular not in ESTATE_NOUNS, (
            f"{singular!r} is singular, and singular nouns belong to how-to questions"
        )
    for shared in ("tools", "agents", "secrets"):
        assert shared in ESTATE_NOUNS, f"{shared!r} is estate vocabulary"
        assert shared not in ESTATE_TERMS, (
            f"{shared!r} is a noun the documentation also owns; in the strong set it would beat "
            f"explicit guidance markers and route documentation questions to the evidence plane"
        )


def test_a_shared_noun_alone_still_means_the_estate() -> None:
    """The other half of the split, so it cannot collapse into "guidance always wins".

    With nothing pulling the other way, a noun both worlds own means the estate — the same
    asymmetric-failure reasoning the tie-break rests on. Only an explicit guidance marker moves it.
    """
    assert route("Were any secrets read?") is Route.ESTATE
    assert route("Which tools were used?") is Route.ESTATE
    assert route("What is the recommended pattern for dynamic secrets?") is Route.GUIDANCE


def test_an_unroutable_question_still_declines() -> None:
    """The widening must not have made the estate a default destination (FR-002)."""
    assert route("What is the capital of France?") is Route.NEITHER
    assert route("Hello there") is Route.NEITHER
