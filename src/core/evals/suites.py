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

#: The suites in force. A tuple rather than a set so output order is stable.
SUITES: Final[tuple[str, ...]] = (
    "must_deny",
    "must_decline",
    "citation_accuracy",
    "estate_state",
    "report_fidelity",
    "answer_sufficiency",
)

#: **The intake analyzer is qualified, and deliberately NOT from `SUITES` above** (037).
#:
#: The first attempt added `intake_analysis` here and nine existing rows refused it, correctly:
#: `SUITES` is the PER-PACK list, so membership demands every pack ship
#: `evals/intake_analysis.toml` and demands the judge's seed set span it. The analyzer is not a
#: per-pack artifact — it is one platform component, qualified once against its own
#: human-labelled corpus in `evals/intake-seed/`, by `core.evals.intake_seed` and
#: `core.evals.intake_scoring`.
#:
#: Forcing it into this tuple would have created a suite every pack must satisfy for a
#: capability no pack owns, and the machinery said so through the rule that already exists:
#: *a gate with no cases must fail rather than pass vacuously*. That rule was written for a
#: different reason and caught this one exactly.
#:
#: **`OWED` stays empty and this is not a deferral.** The analyzer's qualification exists and
#: is merge-blocking; it simply is not a per-pack suite, which is a statement about shape
#: rather than about readiness.
INTAKE_QUALIFICATION = "intake_analysis"

#: **The `write` role is qualified, and deliberately NOT from `SUITES` above** (038).
#:
#: The same shape as `INTAKE_QUALIFICATION` and for the same reason — `SUITES` is the PER-PACK
#: list, so membership would demand every pack ship an integration-correctness corpus for a
#: capability most of them do not offer. 037 made that mistake and nine rows refused it.
#:
#: **Where it differs**: intake's analyzer is one platform component, qualified once. A `write`
#: cell is `(pack × model × role)`, so this is required of a pack that **declares an authoring
#: workflow** and is not asked of one that does not. Neither a global suite nor a one-off.
AUTHORING_QUALIFICATION = "authoring"

#: What `promote_model_version` checks a `write` cell's `suites_passed` against.
#:
#: **Declared beside the constant that excludes it**, so the exclusion and the requirement are
#: read together: `AUTHORING_QUALIFICATION` is outside `SUITES` precisely so nothing else
#: supplies this list, and a cell promoted against an empty required-suite set passes for any
#: evidence at all.
AUTHORING_REQUIRED_SUITES: Final[tuple[str, ...]] = (AUTHORING_QUALIFICATION,)

#: Individual then joint instruction qualifications (049). **Not** members of ``SUITES``.
PHASE_AGENTS_QUALIFICATION = "phase_agents"
BUILD_AGENTS_QUALIFICATION = "build_agents"
PHASE_AGENTS_REQUIRED_SUITES: Final[tuple[str, ...]] = (
    PHASE_AGENTS_QUALIFICATION,
    BUILD_AGENTS_QUALIFICATION,
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

#: Suites scored by driving the **product answering path** rather than replaying a recording (024).
#:
#: **This is what makes those gates mean something.** Before 024 both scorers went around the
#: product — `FixtureScorer` returns `case.recorded`, `LiveModelScorer` asks a vendor directly — so
#: nothing the product does (resolving a citation, dropping an unsupported claim, deciding to
#: decline) ever ran, and the suites were green over a capability that did not exist.
#:
#: **Declared here, beside the suite list, because both lanes must agree.** The blocking lane and
#: the live lane each pick a scorer from this set; two copies of the membership would let one lane
#: quietly revert while the other kept asserting the property. `test_eval_gates.py` asserts the
#: scorer each suite actually used, so a reversion fails a hermetic row rather than only the lane
#: that costs money to run.
ANSWERING_SUITES: Final[frozenset[str]] = frozenset({"citation_accuracy", "must_decline"})

#: Suites scored by whether the product path's **primary answer** contains required facts (046).
#:
#: **Not `ANSWERING_SUITES`.** That set routes to the `cited`/`decline` verb judge; sufficiency
#: uses non-empty `must_contain` substrings and must be able to fail a true/cited/on-subject
#: answer that omits the fact (ADR-0047). Hermetic merge gate; live SC-002 is a named-runner bar.
SUFFICIENCY_SUITES: Final[frozenset[str]] = frozenset({"answer_sufficiency"})

#: Suites scored by driving the **estate** answering path and measuring which references survived
#: (025). The last suite to stop scoring authored recordings.
#:
#: **A distinct set, never membership in `ANSWERING_SUITES`** (analysis P4-1). That set routes to
#: the corpus scorer at three call sites, whose provider parses documentation URLs out of
#: recordings — estate recordings contain none, so every case would decline and fail for a reason
#: no message would explain. Two classifications, two scorers, and the scorer-identity assertion
#: names which is which.
#:
#: **And NOT `MEASURED_SUITES`**, though both are scored by `score_fidelity`. That set's branch
#: demands `compile_for` and would refuse this suite as unrunnable — measured, not assumed.
ESTATE_SUITES: Final[frozenset[str]] = frozenset({"estate_state"})

#: What each suite's expected outcomes may be. `deny` and `decline` are different verbs on
#: purpose — a denial is the governance boundary holding, a decline is competence about
#: scope — and a case may not blur them.
EXPECTED_OUTCOMES: Final[dict[str, frozenset[str]]] = {
    "must_deny": frozenset({"deny"}),
    "must_decline": frozenset({"decline"}),
    "citation_accuracy": frozenset({"cited", "decline"}),
    # `estate_state` is deliberately ABSENT since 025. It is scored by which references survived
    # the answering path, not by a verb, so a mapping here would describe a field its cases no
    # longer carry — and the `match` verb it used could not fail an answer that reproduced the
    # record AND invented a workspace, which is why the suite moved.
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
    #: **Who could ask this** — required for estate cases, ignored by every other suite (030).
    #:
    #: An estate answer is bounded by the asker's role, and until this field existed the suite's
    #: role was implicit — which let three vault cases and three terraform cases score records no
    #: `operator` can see, and let that evidence qualify this platform's first two live cells.
    #: The tag follows the case's EXPECTED SET, not its prompt: a question can be asked by
    #: anyone, but a case expecting an `authority_denied` reference is a compliance-analyst case
    #: whatever its wording, and twice now a case's prompt read as operator-shaped while its
    #: references did not.
    #:
    #: Never defaulted. A defaulted role would be the implicit assumption 030 removes,
    #: reappearing one field over — `parse_cases` refuses instead.
    asker_role: str = ""
    #: For `answer_sufficiency` only (046): substrings the primary answer must include.
    #: Empty is refused at load — a suite that cannot fail is a governance hole (ADR-0047).
    must_contain: tuple[str, ...] = ()


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
                asker_role=str(entry.get("asker_role", "")),
                must_contain=tuple(str(m) for m in (entry.get("must_contain") or ())),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"{source}: case missing required field {exc}") from exc
        if case.suite not in SUITES:
            raise UnrunnableSuite(f"{source}: case {case.id!r} names unknown suite {case.suite!r}")

        if case.suite in SUFFICIENCY_SUITES:
            if not case.must_contain:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} is an answer_sufficiency case and names an "
                    f"empty must_contain; a suite that cannot fail is a governance hole"
                )
            if any(not item.strip() for item in case.must_contain):
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} has a blank must_contain entry; empty "
                    f"substrings pass for any answer"
                )
        elif case.suite in ESTATE_SUITES:
            # `events` is the expected REFERENCE set, and it must be non-empty for the same
            # reason a measured suite's must: precision and recall over an empty expected set
            # pass for any answer at all. Decline behaviour is asserted in component rows
            # instead — see data-model.md § Eval case shape.
            if not case.events:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} is an {case.suite!r} case and names no expected "
                    f"references; fidelity over an empty expected set passes for any answer"
                )
            # The asker's role, from the platform's OWN vocabulary — imported, never copied,
            # because a second role list is the fragmentation seam (030). Absent refuses rather
            # than defaults: a defaulted role is the implicit assumption this field exists to
            # remove, and an implicit role is how three cases scored records no operator can see.
            from core.answering.scope import ROLE_VISIBILITY

            if not case.asker_role:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} is an estate case and declares no asker_role; "
                    f"an estate answer is bounded by who is asking, and a case that does not "
                    f"say is scored under an assumption nobody wrote down"
                )
            if case.asker_role not in ROLE_VISIBILITY:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} declares asker_role {case.asker_role!r}, which "
                    f"the platform does not grant; known roles: {sorted(ROLE_VISIBILITY)}"
                )
        elif case.suite in MEASURED_SUITES:
            # A measured suite scores a SET, not a verb, so `expected` has nothing to validate
            # against — `events` does. A fidelity case with no events is the thin corpus
            # ADR-0018 warns about wearing the schema's clothes: it would score precision and
            # recall over an empty set and pass whatever the report said.
            if not case.events:
                raise UnrunnableSuite(
                    f"{source}: case {case.id!r} is a {case.suite!r} case and names no material "
                    f"events; precision and recall over an empty set pass for any report"
                )
        elif case.suite not in ESTATE_SUITES and case.suite not in SUFFICIENCY_SUITES:
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
    "AUTHORING_QUALIFICATION",
    "AUTHORING_REQUIRED_SUITES",
    "BUILD_AGENTS_QUALIFICATION",
    "EXPECTED_OUTCOMES",
    "ANSWERING_SUITES",
    "ESTATE_SUITES",
    "MEASURED_SUITES",
    "OWED",
    "PHASE_AGENTS_QUALIFICATION",
    "PHASE_AGENTS_REQUIRED_SUITES",
    "SUFFICIENCY_SUITES",
    "SUITES",
    "EvalCase",
    "UnrunnableSuite",
    "load_pack_cases",
    "parse_cases",
    "suite_listing",
]
