# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — root AGENTS.md and SKILL.md are not stand-ins (049, T017, A6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from tests.conformance.phase_agents.fixtures import write_authoring_pack


def test_root_agents_and_skill_do_not_recover_a_missing_write(tmp_path: Path) -> None:
    write_authoring_pack(
        tmp_path,
        "alpha",
        omit_phase="write",
        plant_root_agents=True,
        plant_skill=True,
    )
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "alpha" / "skills" / "guide" / "SKILL.md").is_file()
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_incomplete"


def test_loaded_body_is_not_the_skill_or_root_file(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", plant_root_agents=True, plant_skill=True)
    loaded = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert "stand-in" not in loaded.body
    assert "skill is not a phase instruction" not in loaded.body
    assert loaded.body.startswith("# alpha write")
