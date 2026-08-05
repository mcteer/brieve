# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — exactly one module binds the sandbox runtime (U1).

FR-014a puts the runtime *beneath* a boundary the platform owns, so it is replaceable and
the parity assertions never depend on a `0.0.x` upstream behaving as it does today. That is
only true while the binding stays in one place. A second import — a convenience in a
handler, a type annotation in `core`, a shortcut in a test helper — makes the runtime an
ambient dependency, and swapping it stops being a file rewrite and becomes an audit.

Principle I says the same thing more generally: adapters import the framework, the core does
not. The runtime is framework-shaped, so it lives with the adapters.

Read from the AST, so the module docstrings that *discuss* `pydantic_monty` — deliberately,
in `core/sandbox/` and here — do not register as imports. Prose about a dependency is not a
dependency.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "src"

#: The one module permitted to bind the runtime, relative to `src/`.
_BINDING = "adapters/pydantic_ai/sandbox_runtime.py"

_RUNTIME_MODULES = {"pydantic_monty"}


def _modules_importing_runtime() -> list[str]:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        if names & _RUNTIME_MODULES:
            offenders.append(str(path.relative_to(SRC)))
    return offenders


def test_the_check_covers_something() -> None:
    """Without this, an empty or moved src/ would make the assertion below vacuous."""
    files = list(SRC.rglob("*.py"))
    assert len(files) > 50, f"src/ did not enumerate ({len(files)} files)"
    assert (SRC / _BINDING).exists(), f"the runtime binding is missing at {_BINDING}"


def test_only_the_adapter_binding_imports_the_runtime() -> None:
    offenders = _modules_importing_runtime()
    assert offenders == [_BINDING], (
        "the sandbox runtime must be imported by exactly one module so it stays "
        f"replaceable (FR-014a). Expected [{_BINDING!r}], found {offenders}"
    )


def test_the_detector_can_actually_fail() -> None:
    """Proves the AST walk sees both import forms, and ignores prose."""
    assert "pydantic_monty" in _names(ast.parse("import pydantic_monty"))
    assert "pydantic_monty" in _names(ast.parse("from pydantic_monty import Monty"))
    assert "pydantic_monty" not in _names(ast.parse('"""A docstring naming pydantic_monty."""'))


def _names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names
