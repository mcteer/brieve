# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the sandbox seam is core, and has exactly one way out (U2).

Two properties, and the feature's whole parity claim rests on both.

**The seam is `core`, not adapter.** It imports no agent framework and no sandbox runtime.
Principle I says the core never imports a framework; FR-014c adds the reason specific to
this feature — the parity assertions must bind to platform code, so that a runtime upgrade
cannot quietly weaken them. A seam that imported its runtime would be a seam that moves when
the runtime moves.

**There is one exit, and `invoke_tool` is at it.** The loop must reach tool execution
through `invoke_tool` and through nothing else. A direct handler call, a registry lookup
followed by an invocation, or a second entry point would each be an ungoverned execution
path — the thing ADR-0041 makes an unconditional gate.

Both are asserted against the parsed AST rather than against prose. The module docstring
discusses `open` and `eval` by name, deliberately, because that is where a reader learns
why there is no blocklist — so a checker matching raw text would fail on the very passage
that explains the design. That is the prose-versus-substance mistake this repository has now
made in 006's boundary checker, 007's run-reference check, 008's read-path isolation test,
and 027's conformance-marker check.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SANDBOX = REPO / "src" / "core" / "sandbox"

#: Anything that would make the seam depend on a framework or a specific runtime.
_FORBIDDEN_IMPORTS = ("pydantic_ai", "pydantic_monty", "monty")


def _modules() -> list[tuple[pathlib.Path, ast.Module]]:
    found = []
    for path in sorted(SANDBOX.rglob("*.py")):
        found.append((path, ast.parse(path.read_text())))
    return found


def _imported_names(tree: ast.Module) -> set[str]:
    """Every module named by an import, from the AST — comments cannot reach this."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_check_covers_something() -> None:
    """Without this, a moved or emptied package makes every assertion below vacuous."""
    modules = _modules()
    assert len(modules) >= 3, f"expected the sandbox package to have modules, found {modules}"
    assert any(p.name == "seam.py" for p, _ in modules), "seam.py is missing"


def test_the_seam_imports_no_framework_and_no_runtime() -> None:
    offenders = []
    for path, tree in _modules():
        for name in _imported_names(tree):
            if name in _FORBIDDEN_IMPORTS:
                offenders.append(f"{path.relative_to(REPO)} imports {name}")
    assert offenders == [], (
        "core/sandbox must bind to no framework and no runtime — the runtime plugs in "
        f"beneath the Protocol (FR-014a/c). Found: {offenders}"
    )


def test_the_seam_reaches_execution_only_through_invoke_tool() -> None:
    """The one-exit property, read off the call graph.

    Asserts two things: `invoke_tool` is called, and nothing else that could execute a tool
    body is. The negative half is what has teeth — a seam that called `invoke_tool` *and*
    kept a second path would satisfy a naive presence check while shipping the hole.
    """
    seam = SANDBOX / "seam.py"
    tree = ast.parse(seam.read_text())

    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)

    assert "invoke_tool" in called, "the seam does not route through the governed entry"

    # Ways a tool body could be reached that are NOT the governed entry. `run_pipeline` is
    # the hook engine's own entry — calling it directly would skip invoke_tool's lease,
    # bounds and bracket handling while still looking governed.
    forbidden = {"run_pipeline", "execute", "call_handler", "handler"}
    assert not (called & forbidden), (
        f"the seam has a second route to execution: {sorted(called & forbidden)}"
    )

    # The registry is not consulted here at all: deciding whether a name is a real tool is
    # invoke_tool's job, which is what makes an invented name refuse on the ordinary path.
    imported = _imported_names(tree)
    assert "core.registry" not in imported and "registry" not in imported, (
        "the seam must not consult the registry itself — invoke_tool decides (FR-008)"
    )


def test_the_detector_can_actually_fail() -> None:
    """A checker that has never rejected anything is indistinguishable from `return []`."""
    rigged = ast.parse("import pydantic_monty\ndef f(): return run_pipeline(1)\n")
    assert "pydantic_monty" in _imported_names(rigged)
    calls = {
        n.func.id
        for n in ast.walk(rigged)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "run_pipeline" in calls
    clean = ast.parse("from core.tools.invoke import invoke_tool\n")
    assert not (_imported_names(clean) & set(_FORBIDDEN_IMPORTS))
