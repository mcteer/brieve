# SPDX-License-Identifier: Apache-2.0
"""R15 — the qualification can lose, and a rubber stamp fails it (043, FR-015).

**The row this file exists for is `test_an_always_affirming_candidate_fails`.** It clears the
ADR-0052 majority floor — most seed cases are fully relevant, and affirming everything gets
them right — and fails the supported-but-irrelevant number, which is the only number that
distinguishes a judge from a rubber stamp.

If that row ever passes, the relevance gate is qualified by a check that cannot fail, and every
cell it promoted is unearned.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from core.answering.relevance import RelevanceVerdict
from core.evals.relevance_qualification import (
    MAJORITY_FLOOR,
    score_relevance_judge,
)
from core.evals.relevance_seed import RelevanceSeedCase, load_relevance_seed

SEED = Path(__file__).resolve().parents[2] / "evals" / "relevance-seed" / "seed.toml"


class _AlwaysAffirms:
    """The rubber stamp. Says every claim answers the question."""

    model = "fixture/always-affirms@1"

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        return RelevanceVerdict(
            relevant=frozenset(range(len(claims))),
            model=self.model,
            raw_leading_token="RELEVANT: all",
        )


class _AlwaysRefuses:
    """The opposite failure: a judge that affirms nothing is not cautious, it is useless."""

    model = "fixture/always-refuses@1"

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        return RelevanceVerdict(
            relevant=frozenset(), model=self.model, raw_leading_token="RELEVANT: none"
        )


class _Perfect:
    """Answers from the seed's own labels — the ceiling, to prove the scorer can pass."""

    model = "fixture/perfect@1"

    def __init__(self, expectations: dict[str, frozenset[int]]) -> None:
        self._expectations = expectations

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        return RelevanceVerdict(
            relevant=self._expectations[question],
            model=self.model,
            raw_leading_token="RELEVANT: seeded",
        )


def _cases() -> tuple[RelevanceSeedCase, ...]:
    return load_relevance_seed(SEED)


def test_an_always_affirming_candidate_fails() -> None:
    """The crude rubber stamp, and it fails on BOTH numbers.

    **Measured rather than assumed**: it scores ~40%, because this seed set is balanced enough
    that affirming everything also gets every mixed case wrong. The first draft of this row
    asserted it would clear the majority floor and be caught only by the second number; that
    was a guess and it was false. Recorded here because it is the honest justification for the
    two-number design — see `test_a_nearly_right_candidate_clears_the_floor_and_still_fails`,
    which is where a single number genuinely would have passed something it should not.
    """
    report = score_relevance_judge(_AlwaysAffirms(), _cases())

    assert report.discriminating_correct == 0, (
        "an always-affirming judge gets every supported-but-irrelevant case wrong, by definition"
    )
    assert not report.qualifies
    assert "supported-but-irrelevant" in report.refusal


def test_a_nearly_right_candidate_clears_the_floor_and_still_fails() -> None:
    """R15 — the row that justifies two numbers rather than one.

    A judge agreeing with every label except ONE supported-but-irrelevant case clears the
    ADR-0052 majority floor comfortably. A single-number gate would promote it — and it is
    precisely blind to the thing the gate exists for: an answer assembled from true, cited,
    resolving claims about the wrong subject.
    """
    cases = _cases()
    blind_spot = next(case for case in cases if case.supported_but_irrelevant)
    expectations = {case.question: case.expected for case in cases}
    # It affirms the one case it should refuse, and is otherwise perfect.
    expectations[blind_spot.question] = frozenset(range(len(blind_spot.claims)))

    report = score_relevance_judge(_Perfect(expectations), cases)

    assert report.overall_rate >= MAJORITY_FLOOR, (
        f"the premise: this candidate CLEARS the floor at {report.overall_rate:.0%}, which is "
        f"what makes a single-number gate insufficient"
    )
    assert report.discriminating_correct == report.discriminating_total - 1
    assert not report.qualifies, (
        "one missed supported-but-irrelevant case is disqualifying however high the overall "
        "rate — a judge that cannot see the defect measures fluency"
    )
    assert blind_spot.id in report.refusal


def test_an_always_refusing_candidate_fails() -> None:
    """The opposite rubber stamp. Refusing everything is not caution."""
    report = score_relevance_judge(_AlwaysRefuses(), _cases())

    assert report.discriminating_correct == report.discriminating_total, (
        "it gets the irrelevant cases right for the wrong reason, which is why one number "
        "would have passed it"
    )
    assert report.overall_rate < MAJORITY_FLOOR
    assert not report.qualifies
    assert "below the" in report.refusal


def test_a_perfect_candidate_qualifies() -> None:
    """The scorer can pass, which a scorer that only ever refuses would not prove."""
    cases = _cases()
    report = score_relevance_judge(
        _Perfect({case.question: case.expected for case in cases}), cases
    )

    assert report.overall_rate == 1.0
    assert report.qualifies
    assert report.refusal == ""


def test_both_numbers_are_reported_separately() -> None:
    """038's rule, one feature over: collapsing them hides which occurred."""
    report = score_relevance_judge(_AlwaysAffirms(), _cases())

    assert report.overall_total == len(_cases())
    assert report.discriminating_total >= 3, "the seed floor guarantees at least three"
    assert report.discriminating_total < report.overall_total, (
        "the discriminating set is a SUBSET; if it were everything, the overall number would "
        "be redundant rather than complementary"
    )


def test_a_refusing_judge_scores_wrong_rather_than_aborting() -> None:
    """One unreachable moment must not hide every other result."""
    from core.answering.relevance import RelevanceRefused

    class _Unreachable:
        model = "fixture/unreachable@1"

        def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
            raise RelevanceRefused("nope", reason_code="relevance_unavailable")

    report = score_relevance_judge(_Unreachable(), _cases())

    assert report.overall_total == len(_cases()), "every case was scored, none aborted the run"
    assert not report.qualifies
    assert all("refused" in sample for outcome in report.outcomes for sample in outcome.samples)


def test_the_majority_is_taken_per_claim_not_per_verdict() -> None:
    """Three samples agreeing about claim 0 and differing elsewhere agree about claim 0.

    A whole-verdict majority would find none and report disagreement that is mostly agreement.
    """
    from core.evals.relevance_qualification import _majority

    assert _majority([frozenset({0, 1}), frozenset({0}), frozenset({0, 2})]) == frozenset({0})


def test_the_seed_set_on_disk_is_the_one_scored() -> None:
    """A qualification against a seed file nobody ships would prove nothing about the platform."""
    cases = _cases()
    assert len(cases) >= 10
    assert any(case.supported_but_irrelevant for case in cases)
    assert all(case.author.strip() for case in cases)
