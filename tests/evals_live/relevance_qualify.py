# SPDX-License-Identifier: Apache-2.0
"""Qualifying a relevance judge against the human-labelled seed set (043, T020).

**This lane binds nothing.** It scores a candidate and prints two numbers; promotion into the
Qualified Model Matrix stays a separate human act, on ADR-0052's rule that a qualification a
machine can grant itself is not one. Nothing here writes a binding, a matrix cell, or a file.

**Two numbers, printed separately.** The overall agreement rate against the ≥90% floor, and
the supported-but-irrelevant cases, which must be *all* correct. The second is the one with
teeth: those cases are the defect itself — true claims, resolving citations, wrong subject —
and a judge that cannot see them is measuring fluency.

**A rigged candidate runs alongside the real one, every time.** `--rubber-stamp` scores an
always-affirming stub against the same seed set through the same scorer. Its purpose is to
show, in the same output, that the lane can lose: a qualification that only ever prints PASS
is indistinguishable from one that is not running (ADR-0047).

    make evals-relevance-qualify                                   # the judge at LIVE_MODEL
    make evals-relevance-qualify ARGS=--rubber-stamp                # rigged, must FAIL
    make evals-relevance-qualify ARGS=anthropic/claude-opus@5       # a named candidate

**The candidate is an argument because ADR-0067 makes it one.** A model may not judge its own
output, so the estate needs a judge qualified for a model that is NOT the one answering — and
the dev binding answers with Sonnet. Hard-coding `LIVE_MODEL` here would have qualified exactly
the one candidate the binding is forbidden to use.

Majority-of-three per case, because the answering lane already paid for the lesson: three
single-sample runs once produced three different pass/fail sets, and a cell is being decided
here.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from adapters.anthropic_relevance import LiveRelevanceJudge
from core.answering.relevance import RelevanceVerdict
from core.evals.relevance_qualification import (
    MAJORITY_FLOOR,
    SAMPLES_PER_CASE,
    QualificationReport,
    score_relevance_judge,
)
from core.evals.relevance_seed import load_relevance_seed
from core.evals.scoring import LIVE_MODEL

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "evals" / "relevance-seed" / "seed.toml"


class _RubberStamp:
    """Affirms everything. The candidate this lane must refuse."""

    model = "fixture/always-affirms@1"

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        return RelevanceVerdict(
            relevant=frozenset(range(len(claims))),
            model=self.model,
            raw_leading_token="RELEVANT: all",
        )


def _report(model: str, report: QualificationReport) -> None:
    """Print the case detail first, then the two numbers. Never a single verdict line."""
    print(f"\n--- candidate {model}, {SAMPLES_PER_CASE} samples per case, majority per claim")
    for outcome in report.outcomes:
        mark = "ok " if outcome.correct else "MISS"
        tag = " [supported-but-irrelevant]" if outcome.supported_but_irrelevant else ""
        print(f"  {mark} {outcome.case_id}{tag}")
        if not outcome.correct:
            print(f"       expected {sorted(outcome.expected)}, judged {sorted(outcome.observed)}")
            print(f"       samples: {list(outcome.samples)}")

    print("\n  TWO NUMBERS, and the second is the one with teeth:")
    print(
        f"    overall agreement          {report.overall_correct}/{report.overall_total} "
        f"= {report.overall_rate:.0%}   (floor {MAJORITY_FLOOR:.0%})"
    )
    print(
        f"    supported-but-irrelevant   {report.discriminating_correct}/"
        f"{report.discriminating_total}   (must be ALL)"
    )
    if report.qualifies:
        print(f"\n  QUALIFIES — and binds nothing. Promoting {model} is a separate human act.")
    else:
        print(f"\n  DOES NOT QUALIFY: {report.refusal}")


def main(argv: Sequence[str]) -> int:
    cases = load_relevance_seed(SEED)
    rigged = "--rubber-stamp" in argv
    named = next((arg for arg in argv if not arg.startswith("-")), LIVE_MODEL)
    candidate: object = _RubberStamp() if rigged else LiveRelevanceJudge(named)
    model = str(getattr(candidate, "model", "unknown"))

    print(f"seed set: {len(cases)} cases from {SEED.relative_to(ROOT)}")
    print(f"authors : {sorted({case.author for case in cases})}")

    report = score_relevance_judge(candidate, cases)  # type: ignore[arg-type]
    _report(model, report)

    if rigged:
        # Inverted on purpose. A rubber stamp that qualifies means the scorer is broken, and
        # every cell this lane ever promoted was promoted by a check that cannot fail.
        if report.qualifies:
            print(
                "\nLANE BROKEN: an always-affirming stub QUALIFIED. Stop — this lane is not "
                "measuring anything, and any cell it promoted is unearned.",
                file=sys.stderr,
            )
            return 1
        print("\nthe lane can lose: the rigged candidate was refused, as it must be.")
        return 0

    return 0 if report.qualifies else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
