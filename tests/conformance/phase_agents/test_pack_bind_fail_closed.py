# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — pack bind is size 1 (049, T018, A7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName
from core.packs.manifest import ManifestError
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run, write_authoring_pack


def test_zero_packs_is_pack_unbound(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha")
    run = fake_run((), tmp_path)
    with pytest.raises(ManifestError) as caught:
        bind_phase_agents(run, PhaseName.RESEARCH)
    assert caught.value.reason_code == "pack_unbound"


def test_two_packs_is_pack_ambiguous(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha")
    write_authoring_pack(tmp_path, "beta")
    run = fake_run(("alpha", "beta"), tmp_path)
    with pytest.raises(ManifestError) as caught:
        bind_phase_agents(run, PhaseName.RESEARCH)
    assert caught.value.reason_code == "pack_ambiguous"
    assert "alpha" not in (getattr(run, "phase_instruction", "") or "")
