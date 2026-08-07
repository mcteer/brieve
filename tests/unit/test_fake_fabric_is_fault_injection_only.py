# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — SC-001, mechanically.

"Zero conformance rows resolve an agent ceiling, a user scope, or a policy through a test
double, except rows that exist specifically to inject a resolution failure **and say so**."

The last three words are why this file exists. Every feature from 002 to 009 resolved
authority through `FakeIdentityFabric` and every one of them was right to — there was no
alternative. 010 built one, and the risk now is not that someone reaches for the fake
deliberately; it is that a row written next year uses it because the row beside it does,
and the criterion quietly stops being true.

**Two assertions, and the second exists because the first was bypassable.** A row can reach
the fake directly, which a direct-import check finds. It can also reach it *through* a
helper that imports it — which is exactly what the hybrid fabric was, and the hybrid was
introduced by the same analyze pass that wrote the direct-import check. One level of
indirection defeated it. The hybrid is deleted, and asserting that nothing imports it is
cheaper and stricter than resolving transitive imports: a module that does not exist cannot
be imported by anything.

Imports are resolved from the AST. A check that searched the text would match this
docstring, and five checks in this repository have matched prose instead of code.
"""

from __future__ import annotations

import ast
import pathlib

CONFORMANCE = pathlib.Path(__file__).resolve().parents[1] / "conformance"

#: The declaration a row must carry to use the fake legitimately.
MARKER = "FAKE_FABRIC_IS_FAULT_INJECTION"

#: The deleted scaffolding. Nothing may import it, and nothing can — it is gone.
FORBIDDEN_MODULE = "hybrid_fabric"


def _imports_fake(path: pathlib.Path) -> bool:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "fake_identity_fabric" in node.module:
                return True
            if any("fake_identity_fabric" in a.name for a in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any("fake_identity_fabric" in a.name for a in node.names):
                return True
    return False


def _declares_marker(path: pathlib.Path) -> bool:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == MARKER for target in node.targets
        ):
            return True
    return False


def test_every_conformance_row_using_the_fake_declares_why() -> None:
    offenders: list[str] = []
    for path in sorted(CONFORMANCE.rglob("*.py")):
        if _imports_fake(path) and not _declares_marker(path):
            offenders.append(str(path.relative_to(CONFORMANCE.parent)))

    assert not offenders, (
        f"{offenders} resolve authority through the identity fake without declaring "
        f"{MARKER}. Either move the row to the production fabric, or declare what failure "
        "mode it is injecting — SC-001 permits the second and nothing permits silence."
    )


def test_nothing_imports_the_deleted_hybrid() -> None:
    """The transitive loophole, closed by the module not existing.

    A row reaching the fake through the hybrid passed the check above unmarked, because the
    import it makes is of the hybrid. Asserting zero importers is stricter than following
    the chain, and it does not need maintaining: there is nothing to follow.
    """
    offenders: list[str] = []
    for path in sorted(CONFORMANCE.parent.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            module = getattr(node, "module", "") or ""
            # `ast.Global` and `ast.Nonlocal` also carry `.names`, and theirs are plain
            # strings rather than aliases — so the naive `a.name` raised AttributeError on the
            # first `global` statement anywhere in the tests tree. The scanner crashed instead
            # of reporting, which is a guard that fails open by falling over.
            names = [
                a.name if isinstance(a, ast.alias) else str(a) for a in getattr(node, "names", [])
            ]
            if FORBIDDEN_MODULE in module or any(FORBIDDEN_MODULE in n for n in names):
                offenders.append(str(path))
                break

    assert not offenders, (
        f"{offenders} import {FORBIDDEN_MODULE}, which T046a deleted. It was scaffolding "
        "for proving one resolution real while the others were faked, and every story is "
        "real now — reintroducing it would reintroduce the gap in the check above."
    )


def test_the_walk_examined_something() -> None:
    """Without this, a wrong path reports a clean tree.

    A checker that examines nothing finds no offenders, which is indistinguishable from a
    healthy result — the exact failure this repository hit in 008.
    """
    examined = list(CONFORMANCE.rglob("*.py"))

    assert len(examined) > 20, f"only {len(examined)} conformance modules found under {CONFORMANCE}"


def test_the_detector_finds_an_import_it_should() -> None:
    """Positive control for the AST walk, over source that does import the fake."""
    tree = ast.parse("from tests.harness.fake_identity_fabric import fake_identity_fabric\n")
    found = any(
        isinstance(node, ast.ImportFrom) and node.module and "fake_identity_fabric" in node.module
        for node in ast.walk(tree)
    )

    assert found


def test_at_least_one_row_legitimately_declares_the_marker() -> None:
    """The other positive control: the marker is real and reachable, not aspirational.

    If no row declared it, the first assertion would pass because no row uses the fake —
    which is a different and much less likely world than the one where the walk is broken.
    """
    declaring = [p for p in CONFORMANCE.rglob("*.py") if _declares_marker(p)]

    assert declaring, "no conformance row declares the marker, so the check may be inert"
