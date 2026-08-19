# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — content_pins name pack phase AGENTS.md (049, T014, FR-012)."""

from __future__ import annotations

from pathlib import Path

from surfaces.toolset import build_registry, content_pins

PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"


def test_content_pins_include_each_phase_agents_digest() -> None:
    _, loaded = build_registry(packs=["terraform"], packs_root=PACKS_ROOT)
    pins = content_pins(loaded)
    manifest = loaded["terraform"].manifest
    for pin in manifest.agents:
        key = f"terraform/agents/{pin.phase}@{pin.version}"
        assert pins[key] == pin.digest
    assert not any(key.startswith("vault/agents/") for key in pins)
