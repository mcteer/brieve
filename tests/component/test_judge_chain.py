# SPDX-License-Identifier: Apache-2.0
"""GATE:eval — the judge chain, from the seed up (ADR-0052, SC-015).

The mechanics and the **recorded answer** are different claims, and only the second is what
an investigator reads. So beyond qualifying and refusing, one row here asserts the record
itself: what qualified the first judge, with that answer depending on no unqualified judge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.evals.judge import (
    JudgeError,
    SeedCase,
    load_seed_set,
    qualify_first_judge,
    qualify_judge,
)
from core.evals.suites import UnrunnableSuite

SEED_PATH = Path(__file__).resolve().parents[2] / "evals" / "seed" / "seed.toml"


class AgreesWithHumans:
    """A candidate that answers exactly as the labels do."""

    def verdict(self, case: SeedCase) -> str:
        return case.verdict


class AlwaysAccepts:
    """The tone-scorer: everything plausible-sounding is fine. The rejects catch it."""

    def verdict(self, case: SeedCase) -> str:
        return "accept"


def _seed() -> tuple[SeedCase, ...]:
    return load_seed_set(SEED_PATH)


def test_the_shipped_seed_set_clears_its_own_floor() -> None:
    """20+, all four suites, 3+ rejects — against the real file, not a fixture of it."""
    seed = _seed()
    assert len(seed) >= 20
    assert {c.suite for c in seed} >= {
        "must_deny",
        "must_decline",
        "citation_accuracy",
        "estate_state",
    }
    assert sum(1 for c in seed if c.verdict == "reject") >= 3


def test_the_first_judge_is_qualified_against_the_seed() -> None:
    judge = qualify_first_judge("anthropic/claude-opus@5", AgreesWithHumans(), seed=_seed())
    assert judge.agreement == 1.0
    assert judge.qualified_by == ""


def test_a_judge_that_accepts_everything_fails_on_the_rejects() -> None:
    """The rejects are the load-bearing half of the seed.

    `AlwaysAccepts` agrees with every accept label — 16 of 20 — and fails, because a judge
    that has never rejected anything has demonstrated tone-matching, not judgement.
    """
    with pytest.raises(JudgeError) as caught:
        qualify_first_judge("anthropic/claude-haiku@4.5", AlwaysAccepts(), seed=_seed())
    assert caught.value.reason_code == "insufficient_eval_coverage"


def test_a_later_judge_is_qualified_by_a_qualified_judge() -> None:
    first = qualify_first_judge("anthropic/claude-opus@5", AgreesWithHumans(), seed=_seed())
    second = qualify_judge("anthropic/claude-sonnet@5", AgreesWithHumans(), by=first, seed=_seed())
    assert second.qualified_by == "anthropic/claude-opus@5"


def test_a_judge_pointed_at_itself_refuses() -> None:
    """A loop is not a chain, however many links it has."""
    first = qualify_first_judge("anthropic/claude-opus@5", AgreesWithHumans(), seed=_seed())
    with pytest.raises(JudgeError) as caught:
        qualify_judge("anthropic/claude-opus@5", AgreesWithHumans(), by=first, seed=_seed())
    assert "itself" in str(caught.value)


def test_a_seed_set_below_the_floor_fails_the_gate(tmp_path: Path) -> None:
    """Fails, never warns. A floor nothing enforces is a suggestion, and this one is the
    root of the chain."""
    thin = tmp_path / "seed.toml"
    thin.write_text(
        '[[cases]]\nid="a"\nsuite="must_deny"\nprompt="p"\nresponse="r"\nverdict="accept"\n'
    )
    with pytest.raises(UnrunnableSuite):
        load_seed_set(thin)


def test_a_seed_missing_a_suite_fails(tmp_path: Path) -> None:
    """Twenty cases of one suite is not a floor cleared — a judge qualified without a
    suite's verdicts has never been tested on them."""
    cases = "".join(
        f'[[cases]]\nid="c{i}"\nsuite="must_deny"\nprompt="p"\nresponse="r"\n'
        f'verdict="{"reject" if i < 3 else "accept"}"\n'
        for i in range(25)
    )
    single_suite = tmp_path / "seed.toml"
    single_suite.write_text(cases)
    with pytest.raises(UnrunnableSuite) as caught:
        load_seed_set(single_suite)
    assert "must_decline" in str(caught.value)


def test_a_missing_seed_set_fails_rather_than_skipping(tmp_path: Path) -> None:
    with pytest.raises(UnrunnableSuite):
        load_seed_set(tmp_path / "absent.toml")


def test_the_record_names_what_qualified_the_first_judge() -> None:
    """**SC-015 — the recorded answer, not the mechanics.**

    An investigator asks "what qualified this judge" and reads `record()`. For the first
    judge the answer must be the seed set — a human's labels — and must not name any model,
    because a model in that answer is an unqualified judge hiding in the provenance.
    """
    first = qualify_first_judge("anthropic/claude-opus@5", AgreesWithHumans(), seed=_seed())
    record = first.record()
    assert "human" in record["qualified_by"].lower()
    assert "ADR-0052" in record["qualified_by"]
    assert "anthropic" not in record["qualified_by"], (
        "the first judge's provenance names a model; the whole point of the seed is that "
        "nothing above the first link is a model"
    )

    second = qualify_judge("anthropic/claude-sonnet@5", AgreesWithHumans(), by=first, seed=_seed())
    assert second.record()["qualified_by"] == "anthropic/claude-opus@5", (
        "a later judge's provenance must name the judge that scored it"
    )


def test_a_qualified_judge_is_immutable() -> None:
    """A chain whose links can be edited after the fact is a claim, not a chain."""
    import dataclasses

    first = qualify_first_judge("anthropic/claude-opus@5", AgreesWithHumans(), seed=_seed())
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.model = "something-else"  # type: ignore[misc]


def test_a_cell_recorded_without_a_judge_is_refused_unless_it_is_the_first() -> None:
    """The chain, enforced where cells are written — promote_model_version's guard."""
    from core.evals.promotion import PromotionRefused, promote_model_version

    suites = ("must_deny", "must_decline", "citation_accuracy", "estate_state")
    with pytest.raises(PromotionRefused):
        promote_model_version(
            pack="vault",
            model="anthropic/claude-opus@5",
            role="write",
            suites_passed=suites,
            required_suites=suites,
            qualified_by="fixture",
            judge="",
        )
    # The judge role itself is the one exception: the first judge has nothing above it.
    cell = promote_model_version(
        pack="vault",
        model="anthropic/claude-opus@5",
        role="judge",
        suites_passed=suites,
        required_suites=suites,
        qualified_by="fixture",
        judge="",
    )
    assert cell["role"] == "judge"
