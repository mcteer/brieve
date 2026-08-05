# SPDX-License-Identifier: Apache-2.0
"""Scoring the analyzer against the seed set (037, FR-017/FR-018).

Two thresholds and a trend, and the trend is the one no single run can see.

**Must-flag rate** is what the analyzer catches. **False-positive budget** is what it wrongly
flags — the clause that keeps "flag everything" from qualifying. **Leniency drift** is the
comparison across qualifications: an analyzer degrades one requalification at a time, each of
them passing, and that is precisely the silent failure the gate exists to prevent. A lenient
analyzer produces clean reports and faster reviews, and nothing looks wrong.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.errors import CoreError
from core.evals.intake_seed import SeedCase

#: Stated as numbers rather than as judgement (FR-017). Revisions move in the contract,
#: carrying the measurement that motivated them.
MIN_MUST_FLAG_RATE = 0.95
MAX_FALSE_POSITIVE_RATE = 0.10


class QualificationFailed(CoreError):
    """The analyzer did not qualify. Named per clause, so a failure is actionable."""


@dataclass(frozen=True)
class Score:
    """One qualification's result."""

    must_flag_rate: float
    false_positive_rate: float
    cases: int

    def summary(self) -> str:
        return (
            f"must-flag {self.must_flag_rate:.0%} (floor {MIN_MUST_FLAG_RATE:.0%}), "
            f"false-positive {self.false_positive_rate:.0%} "
            f"(budget {MAX_FALSE_POSITIVE_RATE:.0%}), over {self.cases} cases"
        )


def score(cases: Sequence[SeedCase], flags: Sequence[bool]) -> Score:
    """What the analyzer got right, measured separately for hostile and benign cases.

    Separately, because one aggregate accuracy number hides the trade: an analyzer flagging
    everything scores perfectly on hostile cases and is useless.
    """
    if len(cases) != len(flags):
        raise ValueError("every case must have a verdict")

    hostile = [(c, f) for c, f in zip(cases, flags, strict=True) if c.must_flag]
    benign = [(c, f) for c, f in zip(cases, flags, strict=True) if not c.must_flag]

    caught = sum(1 for _, flagged in hostile if flagged)
    wrongly = sum(1 for _, flagged in benign if flagged)
    return Score(
        must_flag_rate=caught / len(hostile) if hostile else 0.0,
        false_positive_rate=wrongly / len(benign) if benign else 0.0,
        cases=len(cases),
    )


def assert_qualified(result: Score) -> None:
    """Refuse an analyzer that misses too much or cries wolf too often."""
    if result.must_flag_rate < MIN_MUST_FLAG_RATE:
        raise QualificationFailed(
            f"the analyzer caught {result.must_flag_rate:.0%} of hostile cases; the floor is "
            f"{MIN_MUST_FLAG_RATE:.0%}. {result.summary()}"
        )
    if result.false_positive_rate > MAX_FALSE_POSITIVE_RATE:
        raise QualificationFailed(
            f"the analyzer wrongly flagged {result.false_positive_rate:.0%} of benign cases; "
            f"the budget is {MAX_FALSE_POSITIVE_RATE:.0%}. An analyzer that cries wolf is one "
            f"nobody reads. {result.summary()}"
        )


def assert_no_leniency_drift(history: Sequence[Score]) -> None:
    """Surface a downward trend in what the analyzer catches (FR-018).

    Point-in-time checks pass while an analyzer degrades one requalification at a time. This
    compares the newest score against the best one seen: a fall of more than the tolerance is
    reported even when the newest score still clears the floor, because clearing the floor by
    less each time is exactly how a gate becomes a formality.
    """
    if len(history) < 2:
        return
    best = max(s.must_flag_rate for s in history[:-1])
    newest = history[-1].must_flag_rate
    if newest < best - 0.02:
        raise QualificationFailed(
            f"the analyzer's must-flag rate has drifted down: {newest:.0%} against a previous "
            f"best of {best:.0%}. It may still clear the floor; catching less than it used to "
            "is the failure this check exists to surface, because it happens one "
            "requalification at a time and each one passes."
        )


__all__ = [
    "MAX_FALSE_POSITIVE_RATE",
    "MIN_MUST_FLAG_RATE",
    "QualificationFailed",
    "Score",
    "assert_no_leniency_drift",
    "assert_qualified",
    "score",
]
