# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — binding is a declaration, not a code change (051, T049/T050, A11, SC-004).

ADR-0003 keeps product knowledge in packs and out of core. A binding expressed in source
would put "Terraform's style guide belongs to the write phase" inside the platform, which is
the boundary that decision exists to hold — and it would be moved later only by somebody who
noticed it first.

Whoever adopts the next skill binds it by editing `pack.toml`, beside the pin, version and
digest that already govern it. Nothing else.

**What is checked is the skill side, not the phase side.** Source may name a phase — the
matrix's roles and the portal's progress labels both do, legitimately — and a rule banning
the literal `"plan", "write", "judge"` would flag those while catching nothing a binding
would actually look like. What source may never carry is a skill's name, a skill's
reviewer-facing text, or an association between the two.
"""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PhaseName
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
from surfaces.toolset import PACKS_ROOT
from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack

SRC = PACKS_ROOT.parent / "src"


def _shipped_skill_names() -> set[str]:
    loader = FilesystemPackLoader(PACKS_ROOT)
    return {skill.name for pack in ("terraform", "vault") for skill in loader.load(pack).skills}


def _source_files() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_source_file_names_a_shipped_skill() -> None:
    """Row A11. The names are derived from the manifests, so adopting a third is covered."""
    names = _shipped_skill_names()
    assert names, "no shipped skills; this row would assert nothing"
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for name in names:
            assert name not in text, (
                f"{path.relative_to(SRC.parent)} names the skill {name!r}. A binding belongs "
                f"in pack.toml, beside the pin that already governs it (FR-002)."
            )


def test_no_source_file_carries_a_recommendation_string() -> None:
    """The reviewer-facing text is pack content too, and must not be authored in source."""
    loader = FilesystemPackLoader(PACKS_ROOT)
    sentences = [
        item.recommendation
        for pack in ("terraform", "vault")
        for skill in loader.load(pack).skills
        for item in skill.unsatisfiable
    ]
    assert sentences, "no declared recommendations; this row would assert nothing"
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for sentence in sentences:
            assert sentence not in text, path


def test_adding_a_binding_needs_no_source_change(tmp_path: Path) -> None:
    """US3 acceptance 1, the positive case.

    The negative rows above are satisfied by a platform that ignores bindings entirely. This
    is the one that says a manifest edit alone changes what a phase receives.
    """
    write_authoring_pack(tmp_path, "alpha", skills=(SkillSpec("house-style"),))
    before = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert before.skills == ()

    manifest = tmp_path / "alpha" / "pack.toml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        text.replace('name = "house-style"', 'name = "house-style"\nphases = ["write"]'),
        encoding="utf-8",
    )

    after = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert [s.name for s in after.skills] == ["house-style"]
    assert after.body != before.body


def test_removing_a_binding_needs_no_source_change(tmp_path: Path) -> None:
    """SC-004 says *adding or removing*. A one-way door would still be a code change later."""
    write_authoring_pack(tmp_path, "alpha", skills=(SkillSpec("house-style", phases=("write",)),))
    manifest = tmp_path / "alpha" / "pack.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('phases = ["write"]\n', ""),
        encoding="utf-8",
    )
    loaded = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert loaded.skills == ()
    source = (tmp_path / "alpha" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    assert loaded.body == source
