# SPDX-License-Identifier: Apache-2.0
"""GATE:eval — phase_agents / build_agents can fail and are not SUITES (049, T036, A11)."""

from __future__ import annotations

from pathlib import Path

from core.evals.phase_agents_corpus import (
    load_build_agents_cases,
    load_phase_agents_cases,
    score_build_agents_case,
    score_phase_agents_case,
)
from core.evals.suites import (
    BUILD_AGENTS_QUALIFICATION,
    PHASE_AGENTS_QUALIFICATION,
    SUITES,
)

ROOT = Path(__file__).resolve().parents[3]
PACKS = ROOT / "packs"
GATES = ROOT / "tests" / "component" / "test_eval_gates.py"


def test_qualifications_are_not_members_of_suites() -> None:
    assert PHASE_AGENTS_QUALIFICATION not in SUITES
    assert BUILD_AGENTS_QUALIFICATION not in SUITES


def test_eval_gates_still_iterates_only_suites() -> None:
    text = GATES.read_text(encoding="utf-8")
    assert "for suite in SUITES" in text
    assert "load_phase_agents_cases" not in text
    assert "load_build_agents_cases" not in text
    assert "phase_agents" not in text
    assert "build_agents" not in text


def test_known_fail_fixtures_actually_fail() -> None:
    for pack in ("terraform", "vault"):
        phase_cases = load_phase_agents_cases(PACKS / pack)
        fail_hits = 0
        shipped_pass = 0
        for case in phase_cases:
            scored = score_phase_agents_case(case, repo_root=ROOT)
            if case.expected == "fail":
                assert scored == "fail", case.id
                fail_hits += 1
            if case.expected == "pass" and not case.instruction_ref.startswith("synthetic:"):
                assert scored == "pass", case.id
                assert f"packs/{pack}/agents/" in case.instruction_ref
                shipped_pass += 1
        assert fail_hits >= 5, pack
        assert shipped_pass >= 5, pack

        build_cases = load_build_agents_cases(PACKS / pack)
        fails = [c for c in build_cases if c.expected == "fail"]
        assert fails
        for build_case in fails:
            assert score_build_agents_case(build_case, repo_root=ROOT) == "fail"
        shipped = next(c for c in build_cases if c.expected == "pass")
        assert f"packs/{pack}/agents/" in shipped.set_ref
        assert score_build_agents_case(shipped, repo_root=ROOT) == "pass"
