# SPDX-License-Identifier: Apache-2.0
"""Phase and Build instruction corpora. Not members of ``SUITES`` (049)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from core.authoring.progress import PHASE_ORDER, PhaseName
from core.evals.authoring_corpus import CorpusRefused
from core.evals.suites import (
    BUILD_AGENTS_QUALIFICATION,
    PHASE_AGENTS_QUALIFICATION,
    UnrunnableSuite,
)

MIN_CASES_PER_PHASE = 5
MIN_FAIL_PER_PHASE = 1
MIN_BUILD_CASES = 5
MIN_BUILD_FAIL = 1
_SYNTHETIC_PREFIX = "synthetic:"


@dataclass(frozen=True)
class PhaseAgentsCase:
    """One individual-phase instruction case."""

    id: str
    suite: str
    phase: PhaseName
    instruction_ref: str
    expected: str


@dataclass(frozen=True)
class BuildAgentsCase:
    """One joint five-file instruction-set case."""

    id: str
    suite: str
    set_ref: str
    expected: str


def load_phase_agents_cases(pack_dir: Path) -> tuple[PhaseAgentsCase, ...]:
    """Parse ``evals/phase_agents.toml``. Refuses below the data-model floor."""
    path = pack_dir / "evals" / "phase_agents.toml"
    if not path.is_file():
        raise UnrunnableSuite(f"{path} is missing; a missing suite cannot run")
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    raw = document.get("cases")
    if not isinstance(raw, list) or not raw:
        raise UnrunnableSuite(f"{path} declares no cases; an empty suite passes vacuously")
    cases: list[PhaseAgentsCase] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise UnrunnableSuite(f"{path}: a case is not a table")
        try:
            phase = PhaseName(str(entry["phase"]))
            expected = str(entry["expected"])
            case = PhaseAgentsCase(
                id=str(entry["id"]),
                suite=str(entry["suite"]),
                phase=phase,
                instruction_ref=str(entry["instruction_ref"]),
                expected=expected,
            )
        except (KeyError, ValueError) as exc:
            raise UnrunnableSuite(f"{path}: case missing or invalid field {exc}") from exc
        if case.suite != PHASE_AGENTS_QUALIFICATION:
            raise UnrunnableSuite(f"{path}: case {case.id!r} names {case.suite!r}")
        if case.expected not in {"pass", "fail"}:
            raise UnrunnableSuite(f"{path}: case {case.id!r} expected must be pass or fail")
        cases.append(case)
    by_phase: dict[PhaseName, list[PhaseAgentsCase]] = {phase: [] for phase in PHASE_ORDER}
    for case in cases:
        by_phase[case.phase].append(case)
    for phase in PHASE_ORDER:
        group = by_phase[phase]
        if len(group) < MIN_CASES_PER_PHASE:
            raise CorpusRefused(
                f"{path}: phase {phase.value} has {len(group)} cases, below {MIN_CASES_PER_PHASE}"
            )
        if sum(1 for item in group if item.expected == "fail") < MIN_FAIL_PER_PHASE:
            raise CorpusRefused(f"{path}: phase {phase.value} has no fail case")
        if not any(
            item.expected == "pass" and not item.instruction_ref.startswith(_SYNTHETIC_PREFIX)
            for item in group
        ):
            raise CorpusRefused(
                f"{path}: phase {phase.value} has no pass case naming a shipped instruction"
            )
    return tuple(cases)


def load_build_agents_cases(pack_dir: Path) -> tuple[BuildAgentsCase, ...]:
    """Parse ``evals/build_agents.toml``. Refuses below the data-model floor."""
    path = pack_dir / "evals" / "build_agents.toml"
    if not path.is_file():
        raise UnrunnableSuite(f"{path} is missing; a missing suite cannot run")
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    raw = document.get("cases")
    if not isinstance(raw, list) or not raw:
        raise UnrunnableSuite(f"{path} declares no cases; an empty suite passes vacuously")
    cases: list[BuildAgentsCase] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise UnrunnableSuite(f"{path}: a case is not a table")
        try:
            case = BuildAgentsCase(
                id=str(entry["id"]),
                suite=str(entry["suite"]),
                set_ref=str(entry["set_ref"]),
                expected=str(entry["expected"]),
            )
        except KeyError as exc:
            raise UnrunnableSuite(f"{path}: case missing required field {exc}") from exc
        if case.suite != BUILD_AGENTS_QUALIFICATION:
            raise UnrunnableSuite(f"{path}: case {case.id!r} names {case.suite!r}")
        if case.expected not in {"pass", "fail"}:
            raise UnrunnableSuite(f"{path}: case {case.id!r} expected must be pass or fail")
        cases.append(case)
    if len(cases) < MIN_BUILD_CASES:
        raise CorpusRefused(f"{path}: {len(cases)} cases, below {MIN_BUILD_CASES}")
    if sum(1 for item in cases if item.expected == "fail") < MIN_BUILD_FAIL:
        raise CorpusRefused(f"{path}: no jointly poisonous fail case")
    if not any(
        item.expected == "pass" and not item.set_ref.startswith(_SYNTHETIC_PREFIX) for item in cases
    ):
        raise CorpusRefused(f"{path}: no pass case naming the shipped five-file set")
    return tuple(cases)


def score_phase_agents_case(case: PhaseAgentsCase, *, repo_root: Path) -> str:
    """Mechanical score: shipped paths exist and are non-empty; synthetics fail."""
    if case.instruction_ref.startswith(_SYNTHETIC_PREFIX):
        return "fail"
    path = repo_root / case.instruction_ref
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return "pass"
    return "fail"


def score_build_agents_case(case: BuildAgentsCase, *, repo_root: Path) -> str:
    """Mechanical score for the joint set."""
    if case.set_ref.startswith(_SYNTHETIC_PREFIX):
        return "fail"
    parts = [part.strip() for part in case.set_ref.split(",") if part.strip()]
    if len(parts) != 5:
        return "fail"
    if all(
        (repo_root / part).is_file() and (repo_root / part).read_text(encoding="utf-8").strip()
        for part in parts
    ):
        return "pass"
    return "fail"


__all__ = [
    "BuildAgentsCase",
    "MIN_BUILD_CASES",
    "MIN_BUILD_FAIL",
    "MIN_CASES_PER_PHASE",
    "MIN_FAIL_PER_PHASE",
    "PhaseAgentsCase",
    "load_build_agents_cases",
    "load_phase_agents_cases",
    "score_build_agents_case",
    "score_phase_agents_case",
]
