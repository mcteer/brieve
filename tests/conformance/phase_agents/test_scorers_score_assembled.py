# SPDX-License-Identifier: Apache-2.0
"""GATE:eval — re-qualification looks at the bytes the model receives (051, T042, A18/A21).

SC-007 says no phase ships bound to a skill whose *combined* instruction has not passed both
suites. A scorer that reads `AGENTS.md` and stops has not looked at the change: the phase
would qualify on content that is no longer what its model is sent, and the gate would green
without asserting anything about the binding. ADR-0047 rates that worse than a missing gate.

**Row A21 is the one that would have caught the deadlock.** Assembly takes the instruction
bytes as a parameter rather than re-deriving them from a pin, so a candidate that has no
`[[agents]]` pin can be scored. Routing the scorers through `load_phase_agents` instead
would make re-qualification impossible: editing a phase file makes its pin stale, the loader
refuses `digest_mismatch`, the suites cannot run, and promotion requires them to have passed.
"""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PhaseName
from core.evals.phase_agents_corpus import (
    PhaseAgentsCase,
    load_phase_agents_cases,
    score_phase_agents_case,
)
from core.evals.phase_agents_corpus import _assembled as assembled_for
from surfaces.toolset import PACKS_ROOT

ROOT = PACKS_ROOT.parent


def test_a_bound_phase_scores_over_instruction_plus_skill() -> None:
    """Row A18. The Write case must carry the skill's bytes, not only the card's."""
    body = assembled_for("packs/terraform/agents/write/AGENTS.md", PhaseName.WRITE, repo_root=ROOT)
    guide = (PACKS_ROOT / "terraform" / "skills" / "terraform-style-guide" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert guide in body
    assert "BEGIN PINNED SKILL" in body


def test_an_unbound_phase_scores_over_its_file_alone() -> None:
    body = assembled_for(
        "packs/terraform/agents/research/AGENTS.md", PhaseName.RESEARCH, repo_root=ROOT
    )
    source = (PACKS_ROOT / "terraform" / "agents" / "research" / "AGENTS.md").read_text(
        encoding="utf-8"
    )
    assert body == source


def test_a_case_whose_bound_skill_is_missing_scores_fail(tmp_path: Path) -> None:
    """T031's falsification. Without it, T030's change could not lose.

    A copy of the shipped pack with a bound skill deleted: the instruction file is intact and
    non-empty, so the pre-051 scorer would have called this a pass.
    """
    import shutil

    packs = tmp_path / "packs"
    shutil.copytree(PACKS_ROOT / "terraform", packs / "terraform")
    (packs / "terraform" / "skills" / "terraform-style-guide" / "SKILL.md").unlink()

    case = PhaseAgentsCase(
        id="bound-skill-missing",
        suite="phase_agents",
        phase=PhaseName.WRITE,
        instruction_ref="packs/terraform/agents/write/AGENTS.md",
        expected="fail",
    )
    instruction = packs / "terraform" / "agents" / "write" / "AGENTS.md"
    assert instruction.is_file() and instruction.read_text(encoding="utf-8").strip()
    assert score_phase_agents_case(case, repo_root=tmp_path) == "fail"


def test_the_same_case_passes_with_the_skill_present() -> None:
    """The control. A row that fails whatever the tree looks like measures nothing."""
    case = PhaseAgentsCase(
        id="bound-skill-present",
        suite="phase_agents",
        phase=PhaseName.WRITE,
        instruction_ref="packs/terraform/agents/write/AGENTS.md",
        expected="pass",
    )
    assert score_phase_agents_case(case, repo_root=ROOT) == "pass"


def test_a_candidate_with_no_agents_pin_can_be_scored() -> None:
    """Row A21 — the deadlock guard.

    A candidate under `evals/prompt-tune/candidates/` has no `[[agents]]` pin by definition.
    Scoring one must not require having promoted it first, or nothing could ever be promoted.
    """
    candidate = ROOT / "evals" / "prompt-tune" / "candidates" / "terraform-051" / "write"
    if not candidate.is_dir():
        return
    body = assembled_for(
        "evals/prompt-tune/candidates/terraform-051/write/AGENTS.md",
        PhaseName.WRITE,
        repo_root=ROOT,
    )
    assert body, "a candidate with no pin could not be scored; re-qualification would deadlock"
    assert "BEGIN PINNED SKILL" in body, "the candidate scored without its bound skills"


def test_the_shipped_corpus_scores_as_declared() -> None:
    """Every shipped case still agrees with its expectation after the change."""
    cases = load_phase_agents_cases(PACKS_ROOT / "terraform")
    assert cases
    for case in cases:
        assert score_phase_agents_case(case, repo_root=ROOT) == case.expected, case.id
