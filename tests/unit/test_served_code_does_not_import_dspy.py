# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — served code does not import dspy or gepa (049, T020, A10, ADR-0071)."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
SERVED = (SRC / "core", SRC / "adapters", SRC / "surfaces")
FORBIDDEN = frozenset({"dspy", "gepa"})


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_served_packages_do_not_import_dspy_or_gepa() -> None:
    offenders: list[str] = []
    examined = 0
    for root in SERVED:
        for path in root.rglob("*.py"):
            examined += 1
            leaked = _imported_roots(path) & FORBIDDEN
            if leaked:
                offenders.append(f"{path.relative_to(SRC.parent)}:{sorted(leaked)}")
    assert examined > 50, f"only {examined} modules examined"
    assert not offenders, offenders


def test_the_detector_catches_an_import_it_should() -> None:
    tree = ast.parse("import dspy\nfrom gepa import GEPA\n")
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert FORBIDDEN <= roots
