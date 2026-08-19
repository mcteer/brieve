# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — terraform phase pins (049, T021, A1/A3)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PHASE_ORDER
from core.packs.loader import FilesystemPackLoader
from surfaces.dispatch.phase_agents import bind_phase_agents
from surfaces.toolset import build_registry, content_pins
from tests.conformance.phase_agents.fixtures import fake_run

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_terraform_ships_five_distinct_phase_files() -> None:
    manifest = FilesystemPackLoader(PACKS).load("terraform")
    assert {pin.phase for pin in manifest.agents} == {p.value for p in PHASE_ORDER}
    bodies: dict[str, str] = {}
    run = fake_run(("terraform",), PACKS)
    for phase in PHASE_ORDER:
        loaded = bind_phase_agents(run, phase)
        bodies[phase.value] = loaded.body
        key = f"terraform/agents/{phase.value}@{loaded.version}"
        assert run.agent_content_pins[key] == loaded.digest
    assert len(set(bodies.values())) == 5
    assert not any(key.startswith("vault/agents/") for key in run.agent_content_pins)


def test_content_pins_name_only_the_bound_pack() -> None:
    _, loaded = build_registry(packs=["terraform"], packs_root=PACKS)
    pins = content_pins(loaded)
    assert any(k.startswith("terraform/agents/") for k in pins)
    assert not any(k.startswith("vault/agents/") for k in pins)


def test_propose_intake_still_names_the_terraform_pack() -> None:
    text = (Path(__file__).resolve().parents[3] / "src/surfaces/api/propose.py").read_text(
        encoding="utf-8"
    )
    assert 'pack="terraform"' in text
    assert "pack=os.environ" not in text
