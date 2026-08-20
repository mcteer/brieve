# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — portal does not compose phase AGENTS.md (049, T047, A13)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PORTAL = ROOT / "src" / "surfaces" / "portal"
WEB = ROOT / "portal"


def test_portal_templates_and_js_do_not_compose_phase_agents() -> None:
    forbidden = (
        "agents/research/AGENTS.md",
        "agents/plan/AGENTS.md",
        "agents/write/AGENTS.md",
        "agents/judge/AGENTS.md",
        "agents/propose/AGENTS.md",
        "load_phase_agents",
        "bind_phase_agents",
        "prompt composer",
        "prompt-tune/candidates",
    )
    hits: list[str] = []
    roots = [p for p in (PORTAL, WEB) if p.is_dir()]
    assert roots, "no portal tree to examine"
    examined = 0
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".html", ".js", ".ts", ".tsx", ".css", ".jinja2"}:
                continue
            if "node_modules" in path.parts:
                continue
            examined += 1
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                if needle in text:
                    hits.append(f"{path.relative_to(ROOT)}:{needle}")
    assert examined > 0
    assert not hits, hits
