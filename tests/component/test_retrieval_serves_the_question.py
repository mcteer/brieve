# SPDX-License-Identifier: Apache-2.0
"""Retrieval must not let a person's PHRASING decide whether the platform can answer.

The maintainer asked, in his own words, how to run a Vault cluster in AWS, and was told the
pinned corpus does not support an answer. It does. The question reached the model with the
wrong material, three times, and each time the platform reported that as silence.

Two causes, both reproduced here without a model, because a row that needs a vendor is a row
that does not run in the fast lane:

  * INTENT WORDS COLLIDING WITH DOCUMENT FURNITURE. "best" scored against every "Background and
    best practices" heading in the corpus — boilerplate that appears in nearly every document —
    and the heading boost floated them to the top of a question about running a cluster.
  * TOO NARROW AN APERTURE. Ranking had to be right about the top twelve of ~2,500 sections, and
    when it was not, the answer was simply absent from what the model could see.

The second was fixed by widening rather than by ranking harder, which is the finding worth
keeping: several principled ranking improvements were measured against the live model and every
one was neutral or worse. Retrieval picks what to look at; the model is the only party that can
judge whether a section bears on the question.
"""

from __future__ import annotations

import pytest

from adapters.anthropic_answering import (
    SECTIONS_OFFERED,
    SECTIONS_PER_DOCUMENT,
    _relevant,
    _terms,
)
from core.answering.corpus import load_corpus


@pytest.fixture(scope="module")
def corpus() -> object:
    """The real pinned corpus. A fixture corpus could not show either defect."""
    return load_corpus()


@pytest.mark.parametrize(
    "word",
    ["best", "way", "prescribed", "recommended", "approach", "proper", "ideal", "guide"],
)
def test_a_word_about_wanting_is_not_a_word_about_the_subject(word: str) -> None:
    """Nobody searches for these on their own, and left in they match document furniture."""
    assert word not in _terms(f"What is the {word} thing here")


def test_topic_words_that_merely_sound_like_intent_are_kept() -> None:
    """The list must not eat the vocabulary the corpus is actually about.

    `deploy`, `install`, `size`, `upgrade`, `run` name what somebody wants DONE — they are how
    the documents are titled and they have to survive.
    """
    kept = _terms("How do I deploy install size upgrade and run Vault")

    for word in ("deploy", "install", "size", "upgrade", "run", "vault"):
        assert word in kept, f"{word} is a topic word and was dropped"


def test_asking_for_the_best_way_does_not_return_best_practice_boilerplate(
    corpus: object,
) -> None:
    """The maintainer's question, and the exact shape of what went wrong.

    Before the intent words were dropped, five of the top six sections were "…best practices"
    preambles from unrelated documents. The check is deliberately about what came back being
    ABOUT CLUSTERS rather than about a particular document winning — several would be fine.
    """
    offered = _relevant("What's the best way to run a Vault cluster on AWS?", corpus)  # type: ignore[arg-type]

    boilerplate = [f"{path}#{anchor}" for path, anchor, _ in offered if "best-practices" in anchor]
    assert boilerplate == [], (
        f"a question about running a cluster returned best-practice boilerplate: {boilerplate}"
    )
    assert any("cluster" in f"{path}#{anchor}" for path, anchor, _ in offered), (
        "nothing offered for a cluster question was even named for a cluster"
    )


def test_the_aperture_is_wide_enough_to_survive_a_wrong_ranking(corpus: object) -> None:
    """SECTIONS_OFFERED is load-bearing, and narrowing it is what caused the reported defect.

    Measured against the live model over six phrasings: twelve sections gave 3/12 empty answers,
    twenty gave 3/12, thirty gave 0/12 and 0/24 on confirmation. This row cannot re-run that —
    it needs a vendor — so it pins the number and the reason, and fails loudly if someone trims
    it back for prompt size without measuring again.
    """
    assert SECTIONS_OFFERED >= 30, (
        "the offered set was narrowed. At twelve, questions this corpus answers came back as "
        "'the pinned corpus does not support an answer' — re-measure against the live model "
        "before trimming this"
    )
    offered = _relevant("How do I run a Vault cluster in AWS?", corpus)  # type: ignore[arg-type]
    assert len(offered) == SECTIONS_OFFERED


def test_a_wider_aperture_still_spans_documents(corpus: object) -> None:
    """Widening must buy BREADTH, not thirty sections of one enthusiastic page."""
    offered = _relevant("How do I run a Vault cluster in AWS?", corpus)  # type: ignore[arg-type]

    per_document: dict[str, int] = {}
    for path, _anchor, _text in offered:
        per_document[path] = per_document.get(path, 0) + 1

    assert max(per_document.values()) <= SECTIONS_PER_DOCUMENT
    assert len(per_document) >= 8, (
        f"thirty sections came from only {len(per_document)} documents — the offered set is one "
        f"page's view of the question"
    )
