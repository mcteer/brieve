# SPDX-License-Identifier: Apache-2.0
"""Qualifying the analyzer against human-labelled cases (037, FR-016/FR-020).

ADR-0052's mechanism, applied to a new subject: cases labelled by a person, checked into the
repository, reviewed like code — so the regress terminates somewhere a person can inspect and
revise rather than in an attestation nobody here can examine.

**The mechanism is inherited; the floor is not.** ADR-0052's floor is calibrated to the four
answering suites, and intake has no suites — it has attack classes. Inheriting "at least 20
cases spanning all four suites" would have been a category error that still passed at the
right threshold.

**And this floor has a clause ADR-0052 did not need: benign cases.** Without them the
false-positive budget has nothing to measure against, and a corpus of purely hostile content
would qualify an analyzer that flags everything — which passes every must-flag check and is
useless. An analyzer that cries wolf is not safe; it is one nobody reads.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.errors import CoreError


class SeedRefused(CoreError):
    """The corpus does not meet the floor. Raised, never warned (FR-020a)."""


class AttackClass(StrEnum):
    """What a hostile case is an example of (FR-019).

    These are intake's failure modes, and the reason the judge's suite-shaped floor does not
    transfer. `REVIEWER_TARGETED` is the one most easily forgotten: content aimed not at the
    agent but at the person reading the report.
    """

    REDIRECTION = "redirection"
    EXFILTRATION = "exfiltration"
    ENCODED_PAYLOAD = "encoded_payload"
    REVIEWER_TARGETED = "reviewer_targeted"


#: The floor, stated as numbers so "representative" is checkable at its edges — ADR-0052's
#: reason for making its own floor mechanical.
MIN_CASES = 20
MIN_PER_CLASS = 3
MIN_BENIGN = 5


@dataclass(frozen=True)
class SeedCase:
    """One labelled case: content, and what the analyzer must say about it."""

    name: str
    content: str
    #: `None` for a benign case — content the analyzer must NOT flag.
    attack_class: AttackClass | None
    must_flag: bool


def load_seed(path: Path) -> tuple[SeedCase, ...]:
    document = tomllib.loads(path.read_text())
    cases = []
    for entry in document.get("case", []):
        raw_class = entry.get("attack_class")
        cases.append(
            SeedCase(
                name=str(entry["name"]),
                content=str(entry["content"]),
                attack_class=AttackClass(raw_class) if raw_class else None,
                must_flag=bool(entry.get("must_flag", raw_class is not None)),
            )
        )
    return tuple(cases)


def assert_floor(cases: tuple[SeedCase, ...]) -> None:
    """Refuse a corpus below the floor, naming the clause that failed.

    **Each clause is checked separately.** A floor checked only in aggregate can be satisfied
    by a corpus that is wrong in one dimension and generous in another — 25 cases all of one
    attack class would clear a bare count and qualify an analyzer that has seen one trick.
    """
    if len(cases) < MIN_CASES:
        raise SeedRefused(
            f"the intake seed set holds {len(cases)} cases; the floor is {MIN_CASES}. A "
            "handful of examples qualifies an analyzer that has never seen most of what it "
            "must catch."
        )

    for attack in AttackClass:
        found = sum(1 for c in cases if c.attack_class is attack)
        if found < MIN_PER_CLASS:
            raise SeedRefused(
                f"attack class {attack.value!r} has {found} cases; the floor is "
                f"{MIN_PER_CLASS}. A class represented by one example qualifies an analyzer "
                "that may simply have memorised its wording."
            )

    benign = sum(1 for c in cases if c.attack_class is None and not c.must_flag)
    if benign < MIN_BENIGN:
        raise SeedRefused(
            f"the seed set holds {benign} benign cases; the floor is {MIN_BENIGN}. Without "
            "them the false-positive budget has nothing to measure against, and a corpus of "
            "purely hostile content would qualify an analyzer that flags everything."
        )


__all__ = [
    "MIN_BENIGN",
    "MIN_CASES",
    "MIN_PER_CLASS",
    "AttackClass",
    "SeedCase",
    "SeedRefused",
    "assert_floor",
    "load_seed",
]
