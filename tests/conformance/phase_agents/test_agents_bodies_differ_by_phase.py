# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — AGENTS.md bodies differ by phase, not only path (049, T031, SC-001)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PHASE_ORDER

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_bodies_differ_by_phase_for_each_authoring_pack() -> None:
    for pack in ("terraform", "vault"):
        bodies = [
            (PACKS / pack / "agents" / phase.value / "AGENTS.md").read_text(encoding="utf-8")
            for phase in PHASE_ORDER
        ]
        assert all(body.strip() for body in bodies), pack
        assert len(set(bodies)) == 5, f"{pack} phase bodies are not distinct"
        # Path names alone would make a copy-paste pass; require the heading to name the phase.
        for phase, body in zip(PHASE_ORDER, bodies, strict=True):
            assert phase.value.lower() in body.lower() or phase.value.title() in body
