# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — unpromoted candidates are never executed (049, T056, A4b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from tests.conformance.phase_agents.fixtures import write_authoring_pack


def test_missing_pin_is_agents_missing_even_when_a_candidate_exists(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", omit_phase="write", plant_candidate=True)
    candidate = tmp_path / "evals" / "prompt-tune" / "candidates" / "alpha" / "write" / "AGENTS.md"
    assert candidate.is_file()
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_incomplete"


def test_load_phase_agents_never_reads_the_candidate_tree(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", plant_candidate=True)
    candidate = tmp_path / "evals" / "prompt-tune" / "candidates" / "alpha" / "write" / "AGENTS.md"
    assert candidate.is_file()
    loaded = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert "unpromoted candidate" not in loaded.body
    assert "Unique steer for this phase of alpha" in loaded.body
    assert "prompt-tune/candidates" not in loaded.provenance_path
