# SPDX-License-Identifier: Apache-2.0
"""046 U2/U3 — sufficiency scorer fails fact-omission and passes fact inclusion."""

from __future__ import annotations

from pathlib import Path

from core.answering.corpus import load_corpus
from core.evals.scoring import AnsweringScorer, GovernedSubject, run_suite
from core.evals.suites import load_pack_cases

PACKS = Path(__file__).resolve().parents[2] / "packs"
SUBJECT = GovernedSubject(
    agent_definition_id="applier",
    pack="vault",
    tier=1,
    role="ask",
    cell="vault:anthropic/claude-opus@5:ask",
)


def test_fact_omitting_recorded_answer_fails() -> None:
    cases = load_pack_cases(PACKS / "vault", "answer_sufficiency")
    omit = next(c for c in cases if "omit" in c.id)
    result = run_suite(
        "answer_sufficiency",
        (omit,),
        subject=SUBJECT,
        scorer=AnsweringScorer(corpus=load_corpus()),
    )
    assert not result.passed
    assert result.verdicts[0].observed.startswith("missing:")


def test_fact_including_recorded_answer_passes() -> None:
    cases = load_pack_cases(PACKS / "vault", "answer_sufficiency")
    include = next(c for c in cases if "include" in c.id)
    result = run_suite(
        "answer_sufficiency",
        (include,),
        subject=SUBJECT,
        scorer=AnsweringScorer(corpus=load_corpus()),
    )
    assert result.passed
