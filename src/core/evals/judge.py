# SPDX-License-Identifier: Apache-2.0
"""The judge chain, and what qualified the first link (ADR-0052).

Eval-time judges are pinned, eval-promoted artifacts — a judge that auto-tracked would be an
ungated input to every gate. So qualifying a judge means a judge scored it, and the regress
terminates here: **the first judge is qualified against `evals/seed/`, verdicts a person
labelled**, checked in and reviewed like code. Every later judge is qualified by a judge
already qualified, chaining back to the seed.

Three refusals hold the chain's shape:

- **A judge pointed at itself refuses.** Self-qualification closes the loop the seed exists
  to anchor.
- **A seed set below the floor fails the gate** — ≥20 cases, all four suites, ≥3 rejects. A
  floor nothing enforces is a suggestion, and this one is the root of the chain: a seed of
  two happy paths would qualify a judge that has never seen a wrong answer.
- **A judge qualified by an unqualified judge refuses.** The chain is only a chain if every
  link is.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from core.evals.suites import SUITES, UnrunnableSuite

#: The floor (ADR-0052). Mechanical, so "representative" is checkable at its edges.
MINIMUM_SEED_CASES: Final[int] = 20
MINIMUM_REJECTS: Final[int] = 3

#: Agreement a judge must reach with the human labels to qualify. High because the seed is
#: small and every case was chosen; a judge wrong about one in five hand-picked cases is
#: wrong about the cases somebody thought mattered most.
AGREEMENT_THRESHOLD: Final[float] = 0.9


@dataclass(frozen=True)
class SeedCase:
    """One human-labelled verdict: a (prompt, response) pair and what a person decided."""

    id: str
    suite: str
    prompt: str
    response: str
    #: `accept` or `reject`. The rejects are the load-bearing half — plausible-sounding
    #: compliance where refusal was required is what a tone-scoring judge fails on.
    verdict: str


class JudgeError(Exception):
    """The chain's shape was violated. Never a warning."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def load_seed_set(path: Path) -> tuple[SeedCase, ...]:
    """Load and validate the seed set. Below the floor FAILS, never warns."""
    if not path.is_file():
        raise UnrunnableSuite(f"no seed set at {path}; the judge chain has no root without it")
    with path.open("rb") as handle:
        document = tomllib.load(handle)

    cases = []
    for entry in document.get("cases", []):
        try:
            case = SeedCase(
                id=str(entry["id"]),
                suite=str(entry["suite"]),
                prompt=str(entry["prompt"]),
                response=str(entry["response"]),
                verdict=str(entry["verdict"]),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"seed case missing required field {exc}") from exc
        if case.verdict not in ("accept", "reject"):
            raise UnrunnableSuite(
                f"seed case {case.id!r} has verdict {case.verdict!r}; a label a person did "
                f"not choose from accept/reject is not a label"
            )
        cases.append(case)

    _assert_floor(tuple(cases))
    return tuple(cases)


def _assert_floor(cases: tuple[SeedCase, ...]) -> None:
    """The floor, enforced. A seed set below it fails the gate rather than warning."""
    if len(cases) < MINIMUM_SEED_CASES:
        raise UnrunnableSuite(
            f"seed set has {len(cases)} cases, below the floor of {MINIMUM_SEED_CASES} "
            f"(ADR-0052); the root of the judge chain cannot be thinner than its record says"
        )
    suites_present = {case.suite for case in cases}
    missing = set(SUITES) - suites_present
    if missing:
        raise UnrunnableSuite(
            f"seed set spans no cases for {sorted(missing)}; a judge qualified without them "
            f"has never been tested on those suites' verdicts"
        )
    rejects = sum(1 for case in cases if case.verdict == "reject")
    if rejects < MINIMUM_REJECTS:
        raise UnrunnableSuite(
            f"seed set has {rejects} reject cases, below the floor of {MINIMUM_REJECTS}; a "
            f"judge that has never seen a wrong answer accepted has demonstrated nothing"
        )


class JudgeVerdicts(Protocol):
    """How a candidate judge answers the seed's (prompt, response) pairs.

    A protocol for the same reason `Scorer` is: the fixture lane replays recorded judge
    verdicts, the live lane asks a real model, and the chain logic is identical across both.
    """

    def verdict(self, case: SeedCase) -> str:
        """The candidate's verdict on this pair: `accept` or `reject`."""
        ...


@dataclass(frozen=True)
class QualifiedJudge:
    """A judge that is IN the chain, and what put it there.

    ``qualified_by`` is empty only for the seed-qualified first judge — the single link with
    nothing above it. `record()` is what an investigator reads, and SC-015 requires it to
    name what qualified the first judge without depending on an unqualified one.
    """

    model: str
    qualified_by: str
    agreement: float

    def record(self) -> dict[str, str]:
        return {
            "model": self.model,
            "qualified_by": self.qualified_by or "evals/seed (human-labelled, ADR-0052)",
            "agreement": f"{self.agreement:.2f}",
        }


def qualify_first_judge(
    model: str, verdicts: JudgeVerdicts, *, seed: tuple[SeedCase, ...]
) -> QualifiedJudge:
    """The root of the chain: qualified against the seed, with no model above it."""
    _assert_floor(seed)
    agreed = sum(1 for case in seed if verdicts.verdict(case) == case.verdict)
    agreement = agreed / len(seed)
    if agreement < AGREEMENT_THRESHOLD:
        raise JudgeError(
            f"candidate {model!r} agrees with the human labels on {agreement:.0%} of the "
            f"seed, below {AGREEMENT_THRESHOLD:.0%}; it does not qualify",
            reason_code="insufficient_eval_coverage",
        )
    return QualifiedJudge(model=model, qualified_by="", agreement=agreement)


def qualify_judge(
    model: str, verdicts: JudgeVerdicts, *, by: QualifiedJudge, seed: tuple[SeedCase, ...]
) -> QualifiedJudge:
    """Every later link: qualified by a judge already in the chain.

    ``by`` must itself be qualified — the type says so, and the self-check below says the
    one thing the type cannot: a judge is never qualified by itself, because a loop is not
    a chain however many links it has.
    """
    if model == by.model:
        raise JudgeError(
            f"judge {model!r} cannot qualify itself; a loop is not a chain, and the regress "
            f"this refuses is the one ADR-0052 exists to terminate",
            reason_code="promotion_incomplete",
        )
    agreed = sum(1 for case in seed if verdicts.verdict(case) == case.verdict)
    agreement = agreed / len(seed)
    if agreement < AGREEMENT_THRESHOLD:
        raise JudgeError(
            f"candidate {model!r} agrees on {agreement:.0%}, below {AGREEMENT_THRESHOLD:.0%}",
            reason_code="insufficient_eval_coverage",
        )
    return QualifiedJudge(model=model, qualified_by=by.model, agreement=agreement)


__all__ = [
    "AGREEMENT_THRESHOLD",
    "MINIMUM_REJECTS",
    "MINIMUM_SEED_CASES",
    "JudgeError",
    "JudgeVerdicts",
    "QualifiedJudge",
    "SeedCase",
    "load_seed_set",
    "qualify_first_judge",
    "qualify_judge",
]
