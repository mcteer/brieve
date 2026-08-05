# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the intake pipeline knows pins, not products (Principle I).

`core/intake/` governs a supply chain. It must not learn what Terraform or Vault are: the
moment it does, the layer that is supposed to be able to govern *anything* has acquired an
opinion about one thing, and the next adopted product needs a second code path.

Read from the AST, because the modules discuss the packs by name in their docstrings —
`packs/vault/pack.toml` is cited as the reason an absent `[upstream]` table means "authored",
and that citation is where the next reader learns the rule. A text matcher would fail on the
explanation that prevents the mistake, which is the prose-versus-substance error this
repository has made in five separate checkers.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
INTAKE = REPO / "src" / "core" / "intake"

_FORBIDDEN = {"pydantic_ai", "pydantic_monty", "packs", "adapters", "surfaces"}


def _imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_check_covers_something() -> None:
    modules = list(INTAKE.glob("*.py"))
    assert len(modules) >= 4, f"core/intake did not enumerate ({len(modules)})"


def test_intake_imports_no_product_and_no_framework() -> None:
    offenders = []
    for path in sorted(INTAKE.glob("*.py")):
        for name in _imports(ast.parse(path.read_text())):
            if name in _FORBIDDEN:
                offenders.append(f"{path.name} imports {name}")
    assert offenders == [], f"the intake pipeline is not product-blind: {offenders}"


def test_the_detector_can_actually_fail() -> None:
    assert "packs" in _imports(ast.parse("from packs.vault import thing"))
    assert not (_imports(ast.parse('"""A docstring naming packs/vault."""')) & _FORBIDDEN)
