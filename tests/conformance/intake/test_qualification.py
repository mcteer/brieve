# SPDX-License-Identifier: Apache-2.0
"""GATE:eval — the gate has a gate (Q1–Q7).

An unqualified analyzer is the ungated input to every intake decision above it. ADR-0052
settled the same problem for judges: the regress terminates in human-labelled cases in the
repository, and a floor that FAILS rather than warns, because a floor nothing enforces is a
suggestion.

**Q4 is the row that makes the others mean anything.** It weakens the analyzer deliberately
and requires qualification to fail — a qualification that cannot fail has qualified nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.evals.intake_scoring import (
    MAX_FALSE_POSITIVE_RATE,
    MIN_MUST_FLAG_RATE,
    QualificationFailed,
    Score,
    assert_no_leniency_drift,
    assert_qualified,
    score,
)
from core.evals.intake_seed import (
    MIN_BENIGN,
    MIN_CASES,
    MIN_PER_CLASS,
    AttackClass,
    SeedCase,
    SeedRefused,
    assert_floor,
    load_seed,
)

SEED = Path(__file__).resolve().parents[3] / "evals" / "intake-seed" / "seed.toml"


def _corpus() -> tuple[SeedCase, ...]:
    return load_seed(SEED)


def _case(name: str, attack: AttackClass | None, must_flag: bool) -> SeedCase:
    return SeedCase(name=name, content="x", attack_class=attack, must_flag=must_flag)


def test_the_shipped_corpus_meets_the_floor() -> None:
    """Q1 — the corpus in the repository is itself qualified."""
    cases = _corpus()
    assert_floor(cases)
    assert len(cases) >= MIN_CASES


def test_each_floor_clause_fails_on_its_own() -> None:
    """Q7 (FR-020a) — a floor checked in aggregate hides one-dimensional breaches.

    25 cases all of one attack class would clear a bare count and qualify an analyzer that
    has seen exactly one trick.
    """
    full = list(_corpus())

    # Too few cases.
    with pytest.raises(SeedRefused, match="the floor is 20"):
        assert_floor(tuple(full[: MIN_CASES - 1]))

    # A class below its minimum, with the total still comfortably above the floor.
    thinned = [c for c in full if c.attack_class is not AttackClass.EXFILTRATION]
    thinned += [_case("lone", AttackClass.EXFILTRATION, True)]
    padded = tuple(thinned + [_case(f"pad{i}", None, False) for i in range(6)])
    assert len(padded) >= MIN_CASES
    with pytest.raises(SeedRefused, match="exfiltration"):
        assert_floor(padded)

    # Benign below its minimum, everything else generous.
    hostile_only = [c for c in full if c.must_flag]
    hostile_only += [_case(f"b{i}", None, False) for i in range(MIN_BENIGN - 1)]
    hostile_only += [_case(f"extra{i}", AttackClass.REDIRECTION, True) for i in range(8)]
    with pytest.raises(SeedRefused, match="benign"):
        assert_floor(tuple(hostile_only))


def test_the_floor_is_intakes_and_not_the_judges() -> None:
    """Q2 (FR-020b) — attack classes, not answering suites.

    A corpus organised by the judge's four suites would be a category error that still
    passed at the right threshold. The floor is expressed in the failure modes intake
    actually has.
    """
    assert {a.value for a in AttackClass} == {
        "redirection",
        "exfiltration",
        "encoded_payload",
        "reviewer_targeted",
    }
    assert MIN_PER_CLASS >= 3
    # And the judge's vocabulary is absent from intake's.
    assert "citation_accuracy" not in {a.value for a in AttackClass}


def test_a_correct_analyzer_qualifies() -> None:
    """Q3 (FR-017) — the thresholds are numbers, and a good analyzer clears them."""
    cases = _corpus()
    perfect = [c.must_flag for c in cases]
    result = score(cases, perfect)
    assert_qualified(result)
    assert result.must_flag_rate == 1.0 and result.false_positive_rate == 0.0


def test_a_weakened_analyzer_fails_the_gate() -> None:
    """Q4 (SC-002) — THE ROW THAT PROVES THE OTHERS CAN LOSE.

    An analyzer that misses hostile cases must not qualify. If this ever passes trivially,
    Q1–Q3 have stopped meaning anything and the gate is decorative.
    """
    cases = _corpus()
    # Weakened: catches only half of what it should.
    hostile_seen = 0
    weakened = []
    for c in cases:
        if c.must_flag:
            hostile_seen += 1
            weakened.append(hostile_seen % 2 == 0)
        else:
            weakened.append(False)

    result = score(cases, weakened)
    assert result.must_flag_rate < MIN_MUST_FLAG_RATE
    with pytest.raises(QualificationFailed, match="hostile cases"):
        assert_qualified(result)


def test_an_analyzer_that_flags_everything_fails_the_gate() -> None:
    """Q3/Q4 — the failure the benign clause exists to catch.

    Flagging everything scores perfectly on hostile cases. Without benign cases in the
    corpus it would qualify, and it is useless: a reviewer learns to ignore it.
    """
    cases = _corpus()
    result = score(cases, [True] * len(cases))
    assert result.must_flag_rate == 1.0, "flagging everything catches everything"
    assert result.false_positive_rate > MAX_FALSE_POSITIVE_RATE
    with pytest.raises(QualificationFailed, match="cries wolf"):
        assert_qualified(result)


def test_leniency_drift_is_surfaced_even_while_the_floor_is_met() -> None:
    """Q6 (FR-018) — the failure no single run can see.

    Each score below clears the floor. The trend does not, and that is the point: an
    analyzer degrades one requalification at a time, and each one passes.
    """
    history = [
        Score(must_flag_rate=1.00, false_positive_rate=0.0, cases=20),
        Score(must_flag_rate=0.98, false_positive_rate=0.0, cases=20),
        Score(must_flag_rate=0.96, false_positive_rate=0.0, cases=20),
    ]
    for s in history:
        assert_qualified(s)  # every one of them individually passes

    with pytest.raises(QualificationFailed, match="drifted down"):
        assert_no_leniency_drift(history)


def test_a_stable_analyzer_does_not_trip_the_drift_check() -> None:
    """Q6's control — the check discriminates rather than firing on any variation."""
    steady = [Score(0.99, 0.0, 20), Score(1.00, 0.0, 20), Score(0.99, 0.0, 20)]
    assert_no_leniency_drift(steady)
