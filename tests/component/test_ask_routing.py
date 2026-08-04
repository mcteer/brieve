# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — one source, decided deterministically, declining rather than guessing.

Routing exists because asking happens in **one place** (spec FR-010): a person asks, and the
platform works out what the question needs. That makes routing a component with its own failure
modes rather than a detail, so it is tested like one.

**The estate rows are the fail-closed ones.** Nothing reaches somebody's audit trail without a
positive estate signal, and that is the property the removed `NEITHER` outcome was really
protecting — a weather question must not perform a scoped read of the records. It still cannot.

**What `NEITHER` actually did was different, and it was measured.** Guidance required one of
thirteen keywords, so a question lacking them was declined with "this matches neither source" —
a claim about coverage that nothing had checked. Three plausible questions in eight failed that
way, including "best practices for Terraform module structure", which lost to the list holding
only the singular "practice". A router can tell an estate question from a guidance one; it
cannot know what the corpus covers, and now it does not pretend to.
"""

from __future__ import annotations

import pytest

from core.answering.routing import (
    ESTATE_NOUNS,
    ESTATE_TERMS,
    Route,
    route,
    route_with_signal,
    window_phrase,
)

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

#: Off-topic. These reach the corpus now and are declined BY IT — which is the difference
#: between "we looked and have nothing" and "we did not look".
OFF_TOPIC_QUESTIONS = [
    "What is the weather in Denver?",
    "Please summarise the quarterly earnings call.",
    "Who won the match?",
]

#: **The regression rows.** Every one of these was declined before the corpus was opened, and
#: every one is a question this platform exists to answer. They are listed individually rather
#: than as a property because each was a real refusal a person would have hit.
PREVIOUSLY_REFUSED = [
    "What is the prescribed way to build a Vault cluster in AWS?",
    "What are the best practices for Terraform module structure?",
    "Tell me about Vault namespaces",
    # Not refused but MIS-SENT: "secrets" is a noun both worlds own, and with no guidance marker
    # recognised, 029's tie-break sent a how-to question to somebody's audit trail. The rule is
    # unchanged and right; its vocabulary was too small to do the job.
    "Walk me through setting up dynamic secrets",
    "Vault cluster sizing guidance",
]

#: The estate side of the same change, and the reason it is safe. Widening the guidance
#: vocabulary could have pulled real estate questions toward the corpus — the asymmetric failure
#: 029 chose against. It does not: strong estate terms still win outright, and nothing here
#: contains an instructional word by accident.
STILL_ESTATE = [
    "Were any secrets read?",
    "Which tools were used?",
    "What policies were applied to my runs?",
    "Show me the records for the failed run.",
    "What changed last night?",
]


@pytest.mark.parametrize("question", ESTATE_QUESTIONS)
def test_estate_shaped_questions_route_to_the_records(question: str) -> None:
    assert route(question) is Route.ESTATE


@pytest.mark.parametrize("question", GUIDANCE_QUESTIONS)
def test_guidance_shaped_questions_route_to_the_corpus(question: str) -> None:
    assert route(question) is Route.GUIDANCE


@pytest.mark.parametrize("question", OFF_TOPIC_QUESTIONS)
def test_an_off_topic_question_reaches_the_corpus_rather_than_the_records(question: str) -> None:
    """The property the removed outcome was really protecting, kept.

    A weather question must never perform a scoped read of somebody's audit trail. It does not:
    the estate needs a positive signal, and this has none. What changed is where the question
    goes INSTEAD — to the corpus, which declines for itself. The cost is one model call to be
    told the corpus does not cover the weather; the thing bought is that no question is refused
    on the strength of a word list.
    """
    assert route(question) is not Route.ESTATE
    assert route(question) is Route.GUIDANCE


@pytest.mark.parametrize("question", PREVIOUSLY_REFUSED)
def test_a_real_question_is_never_refused_before_the_corpus_is_opened(question: str) -> None:
    """THE REGRESSION ROWS. Each was declined with "this matches neither source" while the
    corpus sat unread, or sent to the records for a noun — the defect the maintainer hit."""
    assert route(question) is Route.GUIDANCE


@pytest.mark.parametrize("question", STILL_ESTATE)
def test_widening_guidance_did_not_pull_estate_questions_away(question: str) -> None:
    """The other direction, asserted rather than assumed.

    A vocabulary change that fixed guidance by breaking the estate would be a worse trade than
    the defect it fixed: an estate question answered from generic documentation is a confident
    wrong answer about somebody's own system.
    """
    assert route(question) is Route.ESTATE


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
    for question in ESTATE_QUESTIONS + GUIDANCE_QUESTIONS + OFF_TOPIC_QUESTIONS:
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


def test_the_estate_never_becomes_the_default_destination() -> None:
    """The widening must not have made the estate a default destination (FR-002).

    This row is why removing `NEITHER` is safe. The old fallback protected the records by
    refusing everything unrecognised; the new one protects them by requiring a positive estate
    signal — which is the stronger guarantee, because it does not depend on a keyword list
    being complete.
    """
    for question in ("What is the capital of France?", "Hello there", "asdf"):
        assert route(question) is not Route.ESTATE


# ------------------------------------------- the ordinary English of operating software (036)


#: Documentation questions built from the verbs a person actually uses. Every one of these
#: routed to the ESTATE before the strong set was measured against its own rule — read the
#: asker's records, found nothing, and told them their records do not show it.
#:
#: The maintainer's own question is the first row. He asked it three times over a day and was
#: told each time that the platform had nothing, which is how a routing table becomes a report
#: that the product does not work.
ORDINARY_QUESTIONS = [
    "How do I run a Vault cluster in AWS?",
    "What's the best way to run a Vault cluster on AWS?",
    "How do I run Terraform Enterprise in a private cloud?",
    "Which ports are used by Consul?",
    "How many active nodes should a Nomad cluster have?",
    "What changed in Vault Enterprise 1.15?",
    "What happens when a Vault node has failed?",
    "How is a stopped Nomad allocation resumed?",
]


@pytest.mark.parametrize("question", ORDINARY_QUESTIONS)
def test_a_documentation_question_is_not_a_question_about_your_records(question: str) -> None:
    """The words `run`, `used`, `active`, `changed`, `failed`, `resumed`, `stopped`.

    They are how software is discussed, not how a trail is queried, and holding them as strong
    estate terms meant the most basic question this platform exists to answer performed a scoped
    read of somebody's audit records and then declined.
    """
    assert route(question) is Route.GUIDANCE, (
        f"{question!r} was routed to the estate. A documentation question must not read records"
    )


#: What-happened questions that must keep working. Removing the seven ambiguous words cost the
#: estate nothing, and this is where that is checked rather than asserted — each of these rests
#: on a word that genuinely appears only in questions about the record.
RECORD_QUESTIONS = [
    "Which runs were denied last night?",
    "What did the planner agent do?",
    "Show me the audit trail for yesterday",
    "Which workspaces violate a control?",
    "Were any secrets read?",
    "What happened to my last run?",
    "Which runs failed?",
    "Was anything refused?",
]


@pytest.mark.parametrize("question", RECORD_QUESTIONS)
def test_the_estate_is_still_reachable_without_the_ambiguous_words(question: str) -> None:
    """The other half, and the one that would make this change a regression if it failed."""
    assert route(question) is Route.ESTATE, (
        f"{question!r} no longer reaches the records — narrowing the strong set went too far"
    )


def test_no_ordinary_operating_verb_is_a_strong_estate_term() -> None:
    """The rule itself, so a future addition has to face it.

    `ESTATE_TERMS` is defined as words appearing ONLY in what-happened questions. These seven
    were measured against that definition and failed it. Re-adding one should mean re-arguing
    it here, not quietly widening a frozenset.
    """
    ordinary = {"run", "used", "active", "changed", "failed", "resumed", "stopped", "running"}

    assert not (ESTATE_TERMS & ordinary), (
        f"{sorted(ESTATE_TERMS & ordinary)} is ordinary English for operating software. A "
        f"question containing it is not evidence that somebody is asking about their records"
    )


# ------------------------------------------- the signal a follow-up inherits from (035)


#: Questions that say something the router recognises. Their route is theirs, and a
#: conversation must never move it (FR-017).
SIGNALLED = [
    ("How do I run a Vault cluster in AWS?", Route.GUIDANCE),
    ("What are the best practices for Terraform Enterprise?", Route.GUIDANCE),
    ("Which runs were denied last night?", Route.ESTATE),
    ("Show me the audit trail for yesterday", Route.ESTATE),
    ("What did the planner agent do?", Route.ESTATE),
]

#: Questions that say nothing routable. These are the ones a conversation answers for
#: (FR-017a) — asked standalone they take the guidance floor, which is unchanged.
SIGNAL_LESS = [
    "what about multi-region?",
    "and the intermediate?",
    "what about that?",
    "and after that?",
]


@pytest.mark.parametrize(("question", "expected"), SIGNALLED)
def test_a_question_with_its_own_vocabulary_reports_a_signal(
    question: str, expected: Route
) -> None:
    """The route is unchanged and the signal is reported alongside it."""
    route_taken, had_signal = route_with_signal(question)

    assert route_taken is expected
    assert had_signal is True, f"{question!r} matched vocabulary but reported no signal"


@pytest.mark.parametrize("question", SIGNAL_LESS)
def test_a_bare_follow_up_reports_no_signal(question: str) -> None:
    """The fact `route()` discards, and the whole reason this function exists.

    Both a documentation question and a bare follow-up come back GUIDANCE; only this tells
    the caller which one reached it by matching and which by falling to the floor.
    """
    route_taken, had_signal = route_with_signal(question)

    assert route_taken is Route.GUIDANCE, "the floor moved"
    assert had_signal is False, f"{question!r} reported a signal it does not carry"


@pytest.mark.parametrize("question", [q for q, _ in SIGNALLED] + SIGNAL_LESS + ["", "   ", "?"])
def test_the_signal_form_never_disagrees_with_route(question: str) -> None:
    """`route()` is the contract every existing row rests on; this must not fork it."""
    assert route_with_signal(question)[0] is route(question)


def test_the_router_still_holds_no_state() -> None:
    """FR-017b, structurally. Inheritance belongs to the caller that knows the conversation.

    If a conversation ever reaches this module, the determinism the module docstring stakes
    its argument on becomes a claim about a store rather than about a string.
    """
    import ast  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    # The DOCSTRING explains what the caller does with a conversation, which is exactly the
    # prose a naive substring check trips over — the same defect `test_containment` fixed by
    # stripping comments before checking. Read the code.
    tree = ast.parse(inspect.getsource(route_with_signal).strip())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    for held in ("conversation", "store", "previous", "history", "exchange"):
        assert not any(held in name.lower() for name in names), (
            f"route_with_signal reaches for {held!r} — the router sees a string and nothing else"
        )


def test_a_question_word_that_is_guidance_vocabulary_counts_as_a_signal() -> None:
    """An accepted edge, recorded rather than smoothed over.

    `why` is in `GUIDANCE_TERMS` — it earns its place there pulling a SHARED noun away from
    the estate ("why are secrets rotated?" is documentation). That makes a bare "why?" a
    signalled question under FR-017, so in a records conversation it goes to the corpus rather
    than inheriting.

    Left as it is, deliberately. The alternative — a second tier of "weak" guidance words —
    adds a vocabulary judgement to every future term for a follow-up nobody has yet asked in
    that shape. If somebody does, this row is where the decision gets revisited, with the
    reason already written down.
    """
    route_taken, had_signal = route_with_signal("why?")

    assert route_taken is Route.GUIDANCE
    assert had_signal is True
