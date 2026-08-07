# SPDX-License-Identifier: Apache-2.0
"""R1-R5, R7 — the gate declines, discloses, fails closed, and can lose (043, US1).

DECLARED_FAKE_RELEVANCE_JUDGE — see `tests/harness/fixture_relevance.py`. Every row here
constructs its own verdict rather than leaning on the fixture's affirm-by-default, because that
default is scaffolding for the *other* suites and would make these rows assert nothing.

**What these rows are about.** `Corpus.resolves` proves a document exists. Until 043 that stood
in for proving an answer was about the question, and 035's corpus widening made the difference
observable: true claims, resolving citations, wrong subject. The gate is the difference.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.answering.answer import (
    ANSWERED,
    DECLINED,
    NOT_COVERED,
    Answer,
    answer_question,
)
from core.answering.corpus import Corpus, Document
from tests.harness.fixture_relevance import FixtureRelevanceJudge

PATH = "/validated-designs/vault-operating-guides-adoption"
ANCHOR = "retention"


def _corpus() -> Corpus:
    return Corpus(
        digest="digest-043",
        documents={
            PATH: Document(
                path=PATH,
                url=f"https://developer.hashicorp.com{PATH}",
                digest="doc-digest",
                anchors=frozenset({ANCHOR}),
                sections={ANCHOR: "Retention guidance for the product."},
            )
        },
    )


class _Provider:
    """Returns fixed candidates, all citing something that resolves."""

    def __init__(self, statements: list[str], *, resolving: bool = True) -> None:
        self._statements = statements
        self._resolving = resolving

    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        anchor = ANCHOR if self._resolving else "an-anchor-nobody-pinned"
        return [
            {"statement": statement, "citations": [{"path": PATH, "anchor": anchor}]}
            for statement in self._statements
        ]


def _ask(statements: list[str], judge: Any, *, resolving: bool = True) -> Answer:
    return answer_question(
        question="What is the recommended retention period for this platform's audit log?",
        corpus=_corpus(),
        provider=_Provider(statements, resolving=resolving),
        relevance=judge,
    )


def test_row_r1_an_all_irrelevant_answer_declines_not_covered() -> None:
    """R1 — the defect, closed. True claims, resolving citations, wrong subject (FR-001)."""
    answer = _ask(
        ["Terraform keeps audit records 14 days.", "Boundary retains per policy."],
        FixtureRelevanceJudge(affirm_none=True),
    )

    assert answer.disposition == DECLINED
    assert answer.declined_reason == NOT_COVERED
    assert len(answer.irrelevant) == 2
    assert answer.dropped == (), "nothing failed to resolve; that is the whole point"


def test_row_r2_the_two_decline_grounds_are_distinguishable() -> None:
    """R2 — one reader goes to what the model invented, the other to what the corpus lacks."""
    by_relevance = _ask(
        ["A true claim about another product."], FixtureRelevanceJudge(affirm_none=True)
    )
    by_resolution = _ask(
        ["A claim citing an anchor nobody pinned."], FixtureRelevanceJudge(), resolving=False
    )

    assert by_relevance.declined_reason != by_resolution.declined_reason
    assert by_relevance.irrelevant and not by_relevance.dropped
    assert by_resolution.dropped and not by_resolution.irrelevant, (
        "a statement dropped for not resolving must never appear as irrelevant; the two "
        "buckets are the record of which check refused"
    )


def test_row_r3_partial_keep_discloses_what_it_dropped() -> None:
    """R3 — one relevant claim of three: answered, with the other two disclosed."""
    answer = _ask(
        ["Relevant one.", "Off-subject two.", "Off-subject three."],
        FixtureRelevanceJudge(affirms=[0]),
    )

    assert answer.disposition == ANSWERED
    assert [claim.statement for claim in answer.claims] == ["Relevant one."]
    assert set(answer.irrelevant) == {"Off-subject two.", "Off-subject three."}
    assert answer.relevance_note, "a reader must be told a model made this call"


@pytest.mark.parametrize(
    ("judge", "expected_cause"),
    [
        (FixtureRelevanceJudge(unreachable=True), "relevance_unavailable"),
        (FixtureRelevanceJudge(unqualified=True), "unqualified_cell"),
        (FixtureRelevanceJudge(malformed=True), "malformed_verdict"),
    ],
)
def test_row_r4_every_judge_failure_declines_naming_its_cause(
    judge: FixtureRelevanceJudge, expected_cause: str
) -> None:
    """R4 — fail closed, three ways, each distinguishable (FR-017).

    A gate that could not run must never read as one that passed — and *which* way it could not
    run is what tells an operator whether to look at a vendor, at the matrix, or at a protocol.
    """
    answer = _ask(["A claim that resolves."], judge)

    assert answer.disposition == DECLINED
    assert expected_cause in answer.declined_reason
    assert not answer.claims


def test_row_r4_the_three_causes_differ_from_each_other() -> None:
    """Distinguishable is a property of the SET, so it is asserted over the set."""
    reasons = {
        _ask(["c"], FixtureRelevanceJudge(unreachable=True)).declined_reason,
        _ask(["c"], FixtureRelevanceJudge(unqualified=True)).declined_reason,
        _ask(["c"], FixtureRelevanceJudge(malformed=True)).declined_reason,
        _ask(["c"], FixtureRelevanceJudge(affirm_none=True)).declined_reason,
    }
    assert len(reasons) == 4


def test_row_r5_a_resolution_decline_never_invokes_the_judge() -> None:
    """R5 — the cost bound, proven by counting rather than by reading the code (FR-018)."""
    judge = FixtureRelevanceJudge()
    answer = _ask(["A claim citing nothing pinned."], judge, resolving=False)

    assert answer.disposition == DECLINED
    assert judge.calls == 0, "an ask already declining must not pay for a second model call"


def test_row_r5_a_surviving_answer_invokes_the_judge_exactly_once() -> None:
    judge = FixtureRelevanceJudge()
    _ask(["one", "two", "three"], judge)

    assert judge.calls == 1, "one call per ask, not one per claim"
    assert judge.last_claims == ("one", "two", "three")


def test_row_r7_the_gate_can_lose() -> None:
    """R7 — with no judge supplied, R1's assertion FAILS (FR-009).

    A suite that cannot lose proves nothing. This runs R1's central assertion against the
    rigged construction and requires it to raise.
    """
    rigged = _ask(["Terraform keeps audit records 14 days."], None)

    assert rigged.disposition == ANSWERED, (
        "without the gate the platform answers — which is the defect, reproduced on purpose"
    )
    with pytest.raises(AssertionError):
        assert rigged.disposition == DECLINED


def test_an_answer_the_judge_fully_affirms_is_unchanged() -> None:
    """The gate narrows; it must not disturb what was already right (FR-004)."""
    judge = FixtureRelevanceJudge()
    answer = _ask(["one", "two"], judge)

    assert answer.disposition == ANSWERED
    assert len(answer.claims) == 2
    assert answer.irrelevant == ()
