# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a bound phase receives the skill (051, T033-T035, A1-A3, FR-001).

This is the feature. Both HashiCorp skills have been pinned, digest-verified and named as
practice by every Terraform phase file since 049, and until now no model received either —
`content_pins` recorded a digest for each, which reads as "this governed the run" and was
true of none of them.

The rows here are deliberately about *bytes*. "The skill informed the phase" is not
assertable; "these bytes appear in the instruction between these delimiters" is.
"""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PhaseName
from core.packs.agents import SKILL_CLOSE, SKILL_OPEN, PhaseAgents, load_phase_agents
from core.packs.loader import FilesystemPackLoader
from surfaces.toolset import PACKS_ROOT
from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack

BOUND_PHASES = (PhaseName.PLAN, PhaseName.WRITE, PhaseName.JUDGE)
UNBOUND_PHASES = (PhaseName.RESEARCH, PhaseName.PROPOSE)


def _shipped(phase: PhaseName) -> PhaseAgents:
    return load_phase_agents(
        "terraform", phase, loader=FilesystemPackLoader(PACKS_ROOT), packs_root=PACKS_ROOT
    )


def test_the_write_model_receives_both_skills_in_full() -> None:
    """Row A1, US1 acceptance 1. Full bytes, not a summary and not a reference."""
    loaded = _shipped(PhaseName.WRITE)
    assert [s.name for s in loaded.skills] == [
        "terraform-style-guide",
        "terraform-style-guide-security",
    ]
    guide = (PACKS_ROOT / "terraform" / "skills" / "terraform-style-guide" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    security = (
        PACKS_ROOT / "terraform" / "skills" / "terraform-style-guide" / "SECURITY.md"
    ).read_text(encoding="utf-8")
    assert guide in loaded.body
    assert security in loaded.body


def test_every_bound_phase_receives_both_skills() -> None:
    """FR-012. Plan is bound because its output is Write's instruction."""
    for phase in BOUND_PHASES:
        loaded = _shipped(phase)
        assert len(loaded.skills) == 2, phase


def test_the_delimiters_name_the_skill_and_its_digest() -> None:
    """The only bytes the platform contributes, and what makes presence assertable."""
    loaded = _shipped(PhaseName.WRITE)
    for skill in loaded.skills:
        assert SKILL_OPEN.format(name=skill.name, digest=skill.digest) in loaded.body
        assert SKILL_CLOSE.format(name=skill.name) in loaded.body


def test_delivery_order_is_manifest_declaration_order(tmp_path: Path) -> None:
    """Row A2, FR-006. Not sorted by name — a rename would silently reorder."""
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(
            SkillSpec("zebra", body="# zebra\nfirst declared\n", phases=("write",)),
            SkillSpec("alpaca", body="# alpaca\nsecond declared\n", phases=("write",)),
        ),
    )
    loaded = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert [s.name for s in loaded.skills] == ["zebra", "alpaca"]
    assert loaded.body.index("first declared") < loaded.body.index("second declared")


def test_two_loads_of_identical_content_are_byte_identical(tmp_path: Path) -> None:
    """Row A2. Identical manifest content produces an identical instruction."""
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(
            SkillSpec("one", phases=("write",)),
            SkillSpec("two", body="# two\nother practice\n", phases=("write",)),
        ),
    )
    first = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    second = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert first.body == second.body


def test_an_unbound_phase_is_byte_identical_to_its_instruction_file() -> None:
    """Row A3, FR-011, US1 acceptance 3.

    No delimiter, no header, no trailing-byte change. A phase bound to nothing must behave
    exactly as it did before 051 — including for the Vault pack, which binds nothing at all.
    """
    for phase in UNBOUND_PHASES:
        loaded = _shipped(phase)
        source = (PACKS_ROOT / "terraform" / "agents" / phase.value / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        assert loaded.body == source, phase
        assert loaded.skills == ()


def test_the_vault_pack_binds_nothing_and_is_unchanged() -> None:
    """Vault is the live fixture for "adopted but inert", and must not acquire a binding."""
    for phase in PhaseName:
        loaded = load_phase_agents(
            "vault", phase, loader=FilesystemPackLoader(PACKS_ROOT), packs_root=PACKS_ROOT
        )
        source = (PACKS_ROOT / "vault" / "agents" / phase.value / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        assert loaded.body == source, phase
        assert loaded.skills == ()
