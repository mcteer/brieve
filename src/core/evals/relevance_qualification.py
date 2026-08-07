# SPDX-License-Identifier: Apache-2.0
"""Scoring a relevance judge against the seed set — two numbers, never one (043, FR-015).

**The second number is the one with teeth.** A candidate that clears the ADR-0052 majority floor
has shown it can agree with a person most of the time, which a judge that affirms everything
also does — because most seed cases are fully relevant and affirming them all is correct. What
separates a judge from a rubber stamp is the **supported-but-irrelevant** cases: true claims,
resolving citations, wrong subject. Those it must get *all* right.

One number would hide that. 038 made the same argument for the authoring gates —
*"collapsing them hides which occurred"* — and this is the same shape one feature over.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.answering.relevance import RelevanceJudge, RelevanceRefused
from core.evals.relevance_seed import RelevanceSeedCase

#: ADR-0052's floor for the overall agreement rate.
MAJORITY_FLOOR = 0.90

#: Samples per case. **Three, not one**, and the answering lane paid for the lesson: three
#: single-sample runs once produced three different pass/fail sets. A cell is being decided
#: here, which is exactly where that variance is unaffordable.
SAMPLES_PER_CASE = 3


@dataclass(frozen=True)
class CaseOutcome:
    """One seed case's result, at majority of three."""

    case_id: str
    expected: frozenset[int]
    observed: frozenset[int]
    supported_but_irrelevant: bool
    samples: tuple[str, ...] = ()

    @property
    def correct(self) -> bool:
        return self.expected == self.observed


@dataclass(frozen=True)
class QualificationReport:
    """Two numbers, reported separately, and the cases behind them."""

    overall_correct: int
    overall_total: int
    discriminating_correct: int
    discriminating_total: int
    outcomes: tuple[CaseOutcome, ...]

    @property
    def overall_rate(self) -> float:
        return self.overall_correct / self.overall_total if self.overall_total else 0.0

    @property
    def qualifies(self) -> bool:
        """Both numbers, and the second is absolute.

        A judge that misses one supported-but-irrelevant case is a judge that cannot see the
        defect this gate exists for, whatever its overall rate.
        """
        return (
            self.overall_rate >= MAJORITY_FLOOR
            and self.discriminating_total > 0
            and self.discriminating_correct == self.discriminating_total
        )

    @property
    def refusal(self) -> str:
        """Why it did not qualify, or empty. Names WHICH number failed."""
        if self.qualifies:
            return ""
        if self.discriminating_total == 0:
            return (
                "the seed set contains no supported-but-irrelevant cases, so this qualification "
                "measured nothing the defect presents"
            )
        if self.discriminating_correct != self.discriminating_total:
            missed = [
                o.case_id for o in self.outcomes if o.supported_but_irrelevant and not o.correct
            ]
            return (
                f"the candidate missed {missed} — supported-but-irrelevant cases are the defect "
                f"itself, and a judge that cannot see them measures fluency"
            )
        return f"overall agreement {self.overall_rate:.0%} is below the {MAJORITY_FLOOR:.0%} floor"


def _majority(observations: Sequence[frozenset[int]]) -> frozenset[int]:
    """The verdict a majority of samples agreed on, per claim index.

    Per index rather than per whole-verdict: three samples that each affirm {0,1}, {0} and {0,2}
    agree about claim 0 and disagree about the rest, and a whole-verdict majority would find no
    majority at all and report a disagreement that is mostly agreement.
    """
    if not observations:
        return frozenset()
    threshold = len(observations) / 2
    mentioned = set().union(*observations) if observations else set()
    return frozenset(
        index for index in mentioned if sum(index in obs for obs in observations) > threshold
    )


def score_relevance_judge(
    judge: RelevanceJudge,
    cases: Sequence[RelevanceSeedCase],
    *,
    samples: int = SAMPLES_PER_CASE,
) -> QualificationReport:
    """Score a candidate against the seed set at majority of ``samples``.

    A judge that refuses on a case scores that case wrong rather than aborting: a candidate
    that cannot answer some cases has failed them, and stopping would let one unreachable
    moment hide every other result.
    """
    outcomes: list[CaseOutcome] = []
    for case in cases:
        statements = [claim.statement for claim in case.claims]
        observations: list[frozenset[int]] = []
        raw: list[str] = []
        for _ in range(samples):
            try:
                verdict = judge.assess(case.question, statements)
            except RelevanceRefused as refusal:
                raw.append(f"refused:{refusal.reason_code}")
                observations.append(frozenset())
                continue
            observations.append(verdict.relevant)
            raw.append(verdict.raw_leading_token)

        outcomes.append(
            CaseOutcome(
                case_id=case.id,
                expected=case.expected,
                observed=_majority(observations),
                supported_but_irrelevant=case.supported_but_irrelevant,
                samples=tuple(raw),
            )
        )

    discriminating = [o for o in outcomes if o.supported_but_irrelevant]
    return QualificationReport(
        overall_correct=sum(1 for o in outcomes if o.correct),
        overall_total=len(outcomes),
        discriminating_correct=sum(1 for o in discriminating if o.correct),
        discriminating_total=len(discriminating),
        outcomes=tuple(outcomes),
    )


__all__ = [
    "MAJORITY_FLOOR",
    "SAMPLES_PER_CASE",
    "CaseOutcome",
    "QualificationReport",
    "score_relevance_judge",
]
