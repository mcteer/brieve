# SPDX-License-Identifier: Apache-2.0
"""A model does not judge its own output (ADR-0067).

**Every live cell this platform had promoted was self-judged**, and nothing was wrong with any
of them under the rules that existed. ADR-0052 constrains how a judge earns its place; it never
said which model may judge which output, so Opus qualified Opus and Sonnet qualified Sonnet and
each record said so plainly.

The failure mode is correlated blindness. A judge sharing the generator's misconceptions is
least equipped to see the errors the generator systematically makes — and unlike 032's protocol
bleed, which announced itself by moving a number from 90% to 55%, judgement bleed moves nothing.
A cell agreeing with itself looks exactly like a cell that is right.

**The four existing cells are recorded as debt, not withdrawn.** Their evidence is real and was
gathered under a rule that did not exist. What this file enforces is that the next one cannot
repeat it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.evals.promotion import PromotionRefused, promote_model_version
from core.evals.suites import AUTHORING_REQUIRED_SUITES

ESTATE = Path(__file__).resolve().parents[2] / "infra" / "environments" / "dev" / "variables.tf"

#: Cells promoted before ADR-0067 that name themselves as their own judge.
#:
#: **Debt with a record, not a dispensation** — the shape `DELIBERATELY_UNREACHABLE` and
#: `KNOWN_UNEXECUTABLE` already use. Each entry is a `(model, role)` pair whose evidence is
#: genuine and whose judge is itself. Re-qualifying them needs a second model and a lane run,
#: which is its own piece of work; recording them keeps that visible rather than precedent.
KNOWN_SELF_JUDGED: dict[tuple[str, str], str] = {
    ("anthropic/claude-opus@5", "ask"): (
        "031 qualified Opus as the first judge in the same run that qualified it to ask. "
        "Honest under ADR-0052, non-conforming under ADR-0067."
    ),
    ("anthropic/claude-sonnet@5", "ask"): (
        "032 switched the estate to Sonnet and carried the same pattern forward."
    ),
}

_CELL = re.compile(
    r"\{\s*pack\s*=\s*\"(?P<pack>[^\"]+)\"\s*"
    r"model\s*=\s*\"(?P<model>[^\"]+)\"\s*"
    r"role\s*=\s*\"(?P<role>[^\"]+)\"\s*"
    r"qualified_by\s*=\s*\"(?P<qualified_by>[^\"]+)\"\s*"
    r"judge\s*=\s*\"(?P<judge>[^\"]*)\"",
    re.S,
)


def _estate_cells() -> list[dict[str, str]]:
    return [m.groupdict() for m in _CELL.finditer(ESTATE.read_text())]


def test_promotion_refuses_a_cell_that_judges_itself() -> None:
    """The rule, at the gate that promotes."""
    with pytest.raises(PromotionRefused) as exc:
        promote_model_version(
            pack="vault",
            model="anthropic/claude-opus@5",
            role="ask",
            suites_passed=AUTHORING_REQUIRED_SUITES,
            required_suites=AUTHORING_REQUIRED_SUITES,
            qualified_by="live",
            judge="anthropic/claude-opus@5",
        )

    assert exc.value.reason_code == "self_judged_cell"
    assert "own judge" in str(exc.value)


def test_promotion_accepts_a_different_model_as_judge() -> None:
    """The rule is about identity, not about vendor or family — Sonnet judging Opus is fine."""
    promoted = promote_model_version(
        pack="vault",
        model="anthropic/claude-opus@5",
        role="ask",
        suites_passed=AUTHORING_REQUIRED_SUITES,
        required_suites=AUTHORING_REQUIRED_SUITES,
        qualified_by="live",
        judge="anthropic/claude-sonnet@5",
    )
    assert promoted["judge"] == "anthropic/claude-sonnet@5"


def test_a_mechanical_scorer_is_unaffected() -> None:
    """ADR-0063 stands: a scorer that is not a model cannot share a model's blind spots."""
    promoted = promote_model_version(
        pack="terraform",
        model="anthropic/claude-sonnet@5",
        role="write",
        suites_passed=AUTHORING_REQUIRED_SUITES,
        required_suites=AUTHORING_REQUIRED_SUITES,
        qualified_by="fixture",
        judge="",
        scorer="authoring-reference-comparison",
    )
    assert promoted["scorer"] and not promoted["judge"]


def test_the_estate_grows_no_new_self_judged_cells() -> None:
    """The one that matters going forward.

    Every self-judged cell in the estate must be in `KNOWN_SELF_JUDGED`. A new one fails here,
    which is the whole point: the four that exist are debt, and debt that quietly grows is
    indistinguishable from a rule nobody has.
    """
    offenders = [
        f"{cell['pack']}:{cell['model']}:{cell['role']}"
        for cell in _estate_cells()
        if cell["judge"]
        and cell["judge"] == cell["model"]
        and (cell["model"], cell["role"]) not in KNOWN_SELF_JUDGED
    ]

    assert not offenders, (
        f"{offenders} name themselves as their own judge, which ADR-0067 forbids. A judge "
        f"sharing the generator's blind spots measures fluency, not correctness."
    )


def test_the_known_debt_is_real_and_only_shrinks() -> None:
    """A stale allowlist says a fixed thing is still broken.

    When somebody re-qualifies one of these against a second model, this row makes them delete
    the entry rather than leaving a record that has quietly become false.
    """
    self_judged = {
        (cell["model"], cell["role"])
        for cell in _estate_cells()
        if cell["judge"] and cell["judge"] == cell["model"]
    }
    stale = sorted(
        f"{model}:{role}" for model, role in KNOWN_SELF_JUDGED if (model, role) not in self_judged
    )

    assert not stale, f"KNOWN_SELF_JUDGED names cells that are no longer self-judged: {stale}"


def test_the_walk_examined_something() -> None:
    """A parser that finds no cells reports a clean estate — the 008 failure, one file over."""
    cells = _estate_cells()
    assert len(cells) >= 4, f"only {len(cells)} matrix cells parsed from {ESTATE}"
