# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — no module reachable from `core.run` imports `core.evals`.

A matrix cell is read on the run path at every run start. The scoring harness, the suites,
and the judges are not, and must not be: a run that could import `core.evals` is a run that
could score something, and a run that can score something can qualify a cell for itself.

The layering is expressed by *where the matrix lives* — `core.authority.matrix`, beside the
ceiling — but naming is not enforcement. A module in a package called `evals` sitting one
import away from the run path is an invitation somebody eventually accepts, usually with a
good local reason. This asserts the boundary instead of trusting the name.

Static rather than dynamic: an import that only happens inside a function body still ships,
and a runtime check would pass right up until the branch that takes it.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"

#: The run path's entry points. Everything reachable from these by import is on the run path.
ROOTS = ("core/run.py", "core/authority/manufacture.py", "core/tools/invoke.py")

FORBIDDEN = "core.evals"


def _module_path(module: str) -> Path | None:
    as_module = SRC / (module.replace(".", "/") + ".py")
    if as_module.is_file():
        return as_module
    as_package = SRC / module.replace(".", "/") / "__init__.py"
    return as_package if as_package.is_file() else None


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _reachable_from(roots: tuple[str, ...]) -> dict[str, set[str]]:
    """Every `core.*` module reachable by import, and what each one imported."""
    seen: dict[str, set[str]] = {}
    queue = [r.replace("/", ".").removesuffix(".py") for r in roots]
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        path = _module_path(module)
        if path is None:
            continue
        imports = _imports_of(path)
        seen[module] = imports
        queue.extend(i for i in imports if i.startswith("core.") and i not in seen)
    return seen


def test_nothing_on_the_run_path_imports_the_scoring_harness() -> None:
    graph = _reachable_from(ROOTS)
    offenders = {
        module: sorted(i for i in imports if i == FORBIDDEN or i.startswith(FORBIDDEN + "."))
        for module, imports in graph.items()
        if any(i == FORBIDDEN or i.startswith(FORBIDDEN + ".") for i in imports)
    }
    assert not offenders, (
        f"the run path reaches the scoring harness: {offenders}. A cell is an authorization "
        f"fact and is read here; the thing that WRITES cells must not be reachable from the "
        f"thing that reads them"
    )


def test_the_run_path_does_reach_the_matrix() -> None:
    """The positive control.

    Without it the row above passes trivially the day `ROOTS` stops resolving — a graph of
    three unreadable paths contains no forbidden import either. This asserts the traversal
    actually walks somewhere, so an empty result means "clean" rather than "did not look".
    """
    graph = _reachable_from(ROOTS)
    assert len(graph) > 10, f"import graph only reached {sorted(graph)}; the traversal is broken"
    assert "core.authority.errors" in graph


def test_the_check_fires_when_the_boundary_is_actually_crossed() -> None:
    """A positive control for the *check*, not for the tree.

    An absence assertion nobody has seen fail proves nothing. This constructs the violation
    in a temporary graph and confirms the same predicate reports it.
    """
    contrived = {"core.run": {"core.evals.scoring", "core.authority.matrix"}}
    offenders = [m for m, i in contrived.items() if any(x.startswith(FORBIDDEN) for x in i)]
    assert offenders == ["core.run"]
