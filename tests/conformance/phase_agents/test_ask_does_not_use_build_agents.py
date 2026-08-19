# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — Ask never sets ChoiceRequest.instruction from pack agents (049, T019, A8)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASK = ROOT / "src" / "surfaces" / "api" / "ask.py"
ANSWERING = ROOT / "src" / "core" / "answering"


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_ask_module_does_not_import_phase_agents() -> None:
    names = _imported(ASK)
    offenders = [
        name
        for name in names
        if "phase_agents" in name or name.endswith("packs.agents") or "ChoiceRequest" in name
    ]
    assert not offenders, offenders
    text = ASK.read_text(encoding="utf-8")
    assert "packs/" not in text or "agents/" not in text
    assert "load_phase_agents" not in text
    assert "bind_phase_agents" not in text


def test_answering_tree_does_not_construct_choice_request() -> None:
    hits: list[str] = []
    for path in ANSWERING.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "ChoiceRequest":
                    hits.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "ChoiceRequest":
                    hits.append(str(path.relative_to(ROOT)))
    assert not hits, hits
