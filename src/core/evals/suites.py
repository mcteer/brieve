# SPDX-License-Identifier: Apache-2.0
"""The four eval suites, and the discipline that a gate that cannot run FAILS.

The constitution's eval-gate row names five. Four are built here:

    must_deny          — safety refusals the agent must make
    must_decline       — requests outside declared scope, declined with a pointer elsewhere
    citation_accuracy  — claims carry citations that resolve; absent grounding produces a
                         decline rather than confabulation
    estate_state       — answers about the estate match recorded fixtures

**Report fidelity is deliberately absent** and every suite listing says so out loud
(FR-013a): `RunReport` does not exist in `src/`, so a gate over it would assert something
about a thing that is not there. Per ADR-0047 it is an explicit skip citing ADR-0018 —
never a passing stub, and never a weaker property asserted under its name.

**A suite that cannot run raises** (FR-014, SC-005a). It never skips, never returns an empty
result set, never passes. 012 shipped the opposite twice — an accessibility lane that
skipped when playwright was missing, and an enclave lane that could pass without standing
the stack up — and both times the fix was the same: a lane that cannot run reports failure.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The four suites in force. A tuple rather than a set so output order is stable.
SUITES: Final[tuple[str, ...]] = (
    "must_deny",
    "must_decline",
    "citation_accuracy",
    "estate_state",
)

#: The fifth, recorded as owed rather than silently missing. Every function that lists
#: suites includes this in its output so the absence is a statement, not a gap.
OWED: Final[dict[str, str]] = {
    "report_fidelity": (
        "OWED against ADR-0018: RunReport does not exist in src/, so a gate over it would "
        "assert something about a thing that is not there (FR-013a, ADR-0047)"
    )
}

#: What each suite's expected outcomes may be. `deny` and `decline` are different verbs on
#: purpose — a denial is the governance boundary holding, a decline is competence about
#: scope — and a case may not blur them.
EXPECTED_OUTCOMES: Final[dict[str, frozenset[str]]] = {
    "must_deny": frozenset({"deny"}),
    "must_decline": frozenset({"decline"}),
    "citation_accuracy": frozenset({"cited", "decline"}),
    "estate_state": frozenset({"match"}),
}


class UnrunnableSuite(Exception):
    """A suite that cannot run. Raised, never skipped, never an empty pass.

    The three ways a gate goes quietly wrong are a skip that reads as green, an empty case
    set that passes vacuously, and a missing dependency that nobody notices. All three land
    here instead.
    """


@dataclass(frozen=True)
class EvalCase:
    """One case: an input, what the agent is expected to do, and the recording.

    ``recorded`` is what a previously-observed run of this case produced — the substrate the
    blocking lane scores. The live lane ignores it and asks a real model. The case is the
    same either way, which is what makes the two lanes score the same thing.
    """

    id: str
    suite: str
    prompt: str
    expected: str
    recorded: str = ""


def parse_cases(document: dict[str, object], *, source: str) -> tuple[EvalCase, ...]:
    """Parse a case file, refusing anything malformed or mis-suited."""
    raw = document.get("cases")
    if not isinstance(raw, list) or not raw:
        raise UnrunnableSuite(f"{source} declares no cases; an empty suite passes vacuously")
    cases = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise UnrunnableSuite(f"{source}: a case is not a table")
        try:
            case = EvalCase(
                id=str(entry["id"]),
                suite=str(entry["suite"]),
                prompt=str(entry["prompt"]),
                expected=str(entry["expected"]),
                recorded=str(entry.get("recorded", "")),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"{source}: case missing required field {exc}") from exc
        if case.suite not in SUITES:
            raise UnrunnableSuite(
                f"{source}: case {case.id!r} names suite {case.suite!r}, which is not one of "
                f"{list(SUITES)} — report_fidelity is {OWED['report_fidelity']}"
                if case.suite == "report_fidelity"
                else f"{source}: case {case.id!r} names unknown suite {case.suite!r}"
            )
        allowed = EXPECTED_OUTCOMES[case.suite]
        if case.expected not in allowed:
            raise UnrunnableSuite(
                f"{source}: case {case.id!r} expects {case.expected!r}; suite {case.suite!r} "
                f"permits {sorted(allowed)}"
            )
        cases.append(case)
    return tuple(cases)


def load_pack_cases(pack_dir: Path, suite: str) -> tuple[EvalCase, ...]:
    """Load one suite's cases from a pack's `evals/` directory.

    Missing is an `UnrunnableSuite`, not an empty tuple: a pack that declares a suite and
    ships no cases for it has a gate with nothing behind it, and that gate must go red
    rather than green.
    """
    path = pack_dir / "evals" / f"{suite}.toml"
    if not path.is_file():
        raise UnrunnableSuite(
            f"suite {suite!r} has no case file at {path}; a gate with no cases must fail "
            f"rather than pass vacuously (FR-014)"
        )
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    cases = parse_cases(document, source=str(path))
    wrong = [c.id for c in cases if c.suite != suite]
    if wrong:
        raise UnrunnableSuite(f"{path} contains cases for another suite: {wrong}")
    return cases


def suite_listing() -> dict[str, str]:
    """Every suite the constitution names, and its state. The skip is explicit output."""
    listing = {suite: "in force" for suite in SUITES}
    listing.update(OWED)
    return listing


__all__ = [
    "EXPECTED_OUTCOMES",
    "OWED",
    "SUITES",
    "EvalCase",
    "UnrunnableSuite",
    "load_pack_cases",
    "parse_cases",
    "suite_listing",
]
