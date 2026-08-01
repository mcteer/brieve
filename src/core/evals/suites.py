# SPDX-License-Identifier: Apache-2.0
"""The four eval suites, and the discipline that a gate that cannot run FAILS.

The constitution's eval-gate row names five. Four are built here:

    must_deny          — safety refusals the agent must make
    must_decline       — requests outside declared scope, declined with a pointer elsewhere
    citation_accuracy  — claims carry citations that resolve; absent grounding produces a
                         decline rather than confabulation
    estate_state       — answers about the estate match recorded fixtures
    report_fidelity    — a compiled report mentions every material event and invents none

**Report fidelity is in force as of 021, and `OWED` is empty for the first time.** It was an
explicit skip citing ADR-0018 from 013 until then, because `RunReport` did not exist in `src/`
and a gate over it would have asserted something about a thing that is not there. Per ADR-0047
that is what a not-yet-bindable row must be — never a passing stub, and never a weaker property
asserted under its name.

**It does not share the other four's case shape**, and that is the finding rather than an
inconvenience. Those score *a model's answer to a prompt*: `expected` is a verb — deny, decline,
cited, match. Fidelity scores *a compiled report against the material events of a run*, measured
by precision and recall, so it carries `events` instead of `expected` and has no entry in
`EXPECTED_OUTCOMES`. Forcing it into `expected: str` would have reduced fidelity to a boolean —
losing exactly the signal that separates a report which omitted a denial from one that invented
a success.

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
    "report_fidelity",
)

#: Suites the constitution names that cannot yet bind. **Empty since 021** — every row in the
#: eval gate is now in force.
#:
#: Kept rather than deleted: ADR-0047 says a gate row is absent or an explicit skip citing its
#: deferring record until its feature exists, and the next row to be deferred needs somewhere to
#: be deferred *to*. A dictionary that has been empty once is easier to fill correctly than a
#: mechanism somebody has to re-invent.
OWED: Final[dict[str, str]] = {}

#: Suites scored by precision and recall against labelled material events rather than by a
#: single expected verb. See the module docstring for why fidelity could not use the other
#: shape.
MEASURED_SUITES: Final[frozenset[str]] = frozenset({"report_fidelity"})

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
    #: For `report_fidelity` only: the material events a faithful report of this run must
    #: mention. Empty for the other four, which score a verb rather than a set.
    events: tuple[str, ...] = ()


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
                expected=str(entry.get("expected", "")),
                recorded=str(entry.get("recorded", "")),
                events=tuple(str(e) for e in (entry.get("events") or ())),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"{source}: case missing required field {exc}") from exc
        if case.suite not in SUITES:
            raise UnrunnableSuite(f"{source}: case {case.id!r} names unknown suite {case.suite!r}")

        if case.suite in MEASURED_SUITES:
            # A measured suite scores a SET, not a verb, so `expected` has nothing to validate
            # against — `events` does. A fidelity case with no events is the thin corpus
            # ADR-0018 warns about wearing the schema's clothes: it would score precision and
            # recall over an empty set and pass whatever the report said.
            if not case.events:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} is a {case.suite!r} case and names no material "
                    f"events; precision and recall over an empty set pass for any report"
                )
        else:
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
    "MEASURED_SUITES",
    "OWED",
    "SUITES",
    "EvalCase",
    "UnrunnableSuite",
    "load_pack_cases",
    "parse_cases",
    "suite_listing",
]
