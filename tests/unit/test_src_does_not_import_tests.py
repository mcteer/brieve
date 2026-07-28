# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — no module under `src/` imports from `tests/` (FR-015, SC-008).

The rule is obvious and the reason it needed a check is not. 008 could not put a
production dispatched-run entrypoint in `src/` because a production entrypoint had no
identity fabric to resolve through — the only implementation lived under `tests/harness/`.
The choice at that moment was between a file in the wrong place and a production module
importing a test double, and 008 correctly took the first. **This check is what makes that
choice stay made**: the moment a real fabric exists, the temptation is to reach for the
fake "just for now", and "just for now" is how a test double ends up in a shipped artifact.

Imports are resolved from the AST, not by searching the text. A check that grepped for
`tests` would match this docstring, and this repository has had five checks match prose
instead of code.
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"


def _imported_roots(path: pathlib.Path) -> set[str]:
    """Every top-level package this module imports, however it phrases the import."""
    roots: set[str] = set()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `level > 0` is a relative import, which cannot reach outside the package and
            # therefore cannot reach `tests/` — skipping it avoids a false positive on a
            # sibling module that happens to be named for what it tests.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_source_module_imports_tests() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if "tests" in _imported_roots(path):
            offenders.append(str(path.relative_to(SRC.parent)))

    assert not offenders, (
        f"{offenders} import from tests/. A shipped artifact that imports a test double "
        "either ships the double or fails at import time for anyone who installed only "
        "the package — and both are worse than the file being in the wrong directory."
    )


def test_the_walk_examined_something() -> None:
    """Without this, a broken glob would report a clean tree.

    The failure mode is specific and has happened here before: a checker that examines
    nothing reports no offenders, which is indistinguishable from a healthy result.
    """
    examined = list(SRC.rglob("*.py"))

    assert len(examined) > 50, f"only {len(examined)} modules examined under {SRC}"


def test_the_detector_catches_an_import_it_should() -> None:
    """The positive control: the same function, over source that does import tests.

    Proves the AST walk finds what it is looking for rather than always returning empty —
    which every assertion above would also satisfy.
    """
    fixture = ast.parse("from tests.harness.fake_identity_fabric import fake_identity_fabric\n")
    roots = {
        node.module.split(".")[0]
        for node in ast.walk(fixture)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "tests" in roots
