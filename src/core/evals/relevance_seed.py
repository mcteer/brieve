# SPDX-License-Identifier: Apache-2.0
"""The human-labelled root of the relevance judge's chain (043, FR-014/FR-015).

ADR-0052 terminates the judge regress at *cases labelled by a person, checked into the
repository, reviewed like code*. 043 adds a judge, so it adds a root — and this loader is
**deliberately separate from `judge.py`'s `SeedCase`** rather than a widening of it: that
vocabulary is accept/reject over a whole response, this one is relevant/irrelevant **per claim**,
and merging them would change the floor and the shape of a chain that is working.

**`author` is required and non-empty**, on 038's corpus precedent. The expensive clause of a
seed set is that a person writes it, and the cheap way to satisfy the letter is to generate it —
which measures the generator against itself. Recording who wrote a label makes the claim
inspectable.

**The floor names supported-but-irrelevant cases explicitly.** A seed set of easy cases qualifies
a judge on verdicts the defect never presents: the whole failure mode is claims that are true,
cited, resolving, and about something else. A corpus without them would qualify a judge that
cannot see the thing it exists to see.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from core.evals.suites import UnrunnableSuite

#: The closed verdict vocabulary. A label a person did not choose from these is not a label.
RELEVANT = "relevant"
IRRELEVANT = "irrelevant"
VERDICTS = frozenset({RELEVANT, IRRELEVANT})

#: Floors, enforced at load. Below any of them the gate goes red rather than amber.
MINIMUM_CASES = 10
MINIMUM_SUPPORTED_BUT_IRRELEVANT = 3
MINIMUM_FULLY_RELEVANT = 3
MINIMUM_MIXED = 1


@dataclass(frozen=True)
class SeedClaim:
    """One statement the judge will be shown, and what a person said about it."""

    statement: str
    #: `path#anchor` into the pinned corpus. Checked to RESOLVE by the qualification lane — a
    #: seed citing an invented anchor would qualify the judge on a world the path never produces.
    citation: str
    verdict: str

    @property
    def is_relevant(self) -> bool:
        return self.verdict == RELEVANT


@dataclass(frozen=True)
class RelevanceSeedCase:
    """One question, the claims that survived citation resolution, and the human verdicts."""

    id: str
    question: str
    claims: tuple[SeedClaim, ...]
    author: str
    note: str = ""

    @property
    def supported_but_irrelevant(self) -> bool:
        """Every claim resolves and none of them answers the question — the motivating shape."""
        return bool(self.claims) and not any(claim.is_relevant for claim in self.claims)

    @property
    def fully_relevant(self) -> bool:
        return bool(self.claims) and all(claim.is_relevant for claim in self.claims)

    @property
    def mixed(self) -> bool:
        return not self.supported_but_irrelevant and not self.fully_relevant

    @property
    def expected(self) -> frozenset[int]:
        """Zero-based indices a correct judge affirms."""
        return frozenset(i for i, claim in enumerate(self.claims) if claim.is_relevant)


def load_relevance_seed(path: Path) -> tuple[RelevanceSeedCase, ...]:
    """Load and validate, or raise. **Never warns, never returns a short set.**"""
    if not path.is_file():
        raise UnrunnableSuite(
            f"no relevance seed set at {path}; the relevance judge's chain has no root without "
            f"it, and a judge with no root is a verdict nobody can inspect"
        )
    document = tomllib.loads(path.read_text())

    cases: list[RelevanceSeedCase] = []
    for entry in document.get("cases", []):
        try:
            # `.get`, not `[...]`: a case with no claims table has no key at all, and the
            # generic missing-field error would fire before the specific one. "A case with
            # nothing to judge passes for any judge" is the actual problem and the more useful
            # thing to say, so the dedicated refusal below owns both shapes.
            raw_claims = entry.get("claims", [])
            case = RelevanceSeedCase(
                id=str(entry["id"]),
                question=str(entry["question"]),
                author=str(entry["author"]),
                note=str(entry.get("note", "")),
                claims=tuple(
                    SeedClaim(
                        statement=str(claim["statement"]),
                        citation=str(claim["citation"]),
                        verdict=str(claim["verdict"]),
                    )
                    for claim in raw_claims
                ),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"relevance seed case missing required field {exc}") from exc

        if not case.author.strip():
            raise UnrunnableSuite(
                f"relevance seed case {case.id!r} records no author. A person writes these, and "
                f"a generated label measures the generator against itself"
            )
        if not case.claims:
            raise UnrunnableSuite(
                f"relevance seed case {case.id!r} carries no claims; a case with nothing to "
                f"judge passes for any judge"
            )
        for claim in case.claims:
            if claim.verdict not in VERDICTS:
                raise UnrunnableSuite(
                    f"relevance seed case {case.id!r} has verdict {claim.verdict!r}; a label a "
                    f"person did not choose from {sorted(VERDICTS)} is not a label"
                )
        cases.append(case)

    _assert_floor(tuple(cases))
    return tuple(cases)


def _assert_floor(cases: tuple[RelevanceSeedCase, ...]) -> None:
    """The floor, enforced. A seed set below it fails rather than warning."""
    if len(cases) < MINIMUM_CASES:
        raise UnrunnableSuite(
            f"relevance seed set has {len(cases)} cases, below the floor of {MINIMUM_CASES}; "
            f"the root of a judge chain cannot be thinner than its record says"
        )

    supported_but_irrelevant = sum(1 for case in cases if case.supported_but_irrelevant)
    if supported_but_irrelevant < MINIMUM_SUPPORTED_BUT_IRRELEVANT:
        raise UnrunnableSuite(
            f"relevance seed set has {supported_but_irrelevant} supported-but-irrelevant cases, "
            f"below the floor of {MINIMUM_SUPPORTED_BUT_IRRELEVANT}. Those cases ARE the defect "
            f"— true claims, resolving citations, wrong subject — and a set without them "
            f"qualifies a judge on verdicts the failure never presents"
        )

    fully_relevant = sum(1 for case in cases if case.fully_relevant)
    if fully_relevant < MINIMUM_FULLY_RELEVANT:
        raise UnrunnableSuite(
            f"relevance seed set has {fully_relevant} fully-relevant cases, below the floor of "
            f"{MINIMUM_FULLY_RELEVANT}; a judge measured only on refusing would be qualified to "
            f"refuse everything"
        )

    mixed = sum(1 for case in cases if case.mixed)
    if mixed < MINIMUM_MIXED:
        raise UnrunnableSuite(
            f"relevance seed set has {mixed} mixed cases, below the floor of {MINIMUM_MIXED}; "
            f"partial keep is a real outcome and a judge that only answers all-or-nothing has "
            f"not been measured on it"
        )


__all__ = [
    "IRRELEVANT",
    "MINIMUM_CASES",
    "MINIMUM_FULLY_RELEVANT",
    "MINIMUM_MIXED",
    "MINIMUM_SUPPORTED_BUT_IRRELEVANT",
    "RELEVANT",
    "VERDICTS",
    "RelevanceSeedCase",
    "SeedClaim",
    "load_relevance_seed",
]
