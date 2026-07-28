# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the removed state is gone, and the constitution agrees.

Three assertions, each guarding a different way this change could be left half-done:

1. **No `PARKED` in the tree.** One missed reference leaves a state in the sealed core
   that nothing can enter, and everything still compiles.
2. **`SUSPENDED` is not terminal.** One line, and the sweeper's entire ability to resume
   anything depends on it. Terminal here and the sweeper picks up nothing, forever, while
   every other test passes.
3. **The constitution describes neither parking nor four-transport-only parity.** A
   partial amendment leaves the governing document describing behaviour that cannot
   occur, which reads as deliberate rather than as an oversight.

The third has a trap the first two do not: the constitution's **Sync Impact Report
legitimately quotes the old wording** to record what changed. A checker that matched the
whole file would fail on the very passage explaining the amendment — the same prose-versus-
substance mistake this repository has now made in 006's boundary checker, 007's
run-reference check, and 008's read-path isolation test. So the report is excluded by
structure, and a test below proves the exclusion did not swallow the body.
"""

from __future__ import annotations

import ast
import pathlib
import re

from core.run import RunState

REPO = pathlib.Path(__file__).resolve().parents[2]
CONSTITUTION = REPO / ".specify" / "memory" / "constitution.md"


def _source_files() -> list[pathlib.Path]:
    roots = (REPO / "src", REPO / "tests")
    return sorted(p for root in roots for p in root.rglob("*.py"))


def _code_without_prose(path: pathlib.Path) -> str:
    """Source with docstrings and comments removed.

    Needed here for the same reason it is needed everywhere else in this repository, and
    the first version of this file did not do it — so the check failed on the docstrings
    explaining the removal, including its own. Prose about a deleted state is not the
    deleted state.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _constitution_body() -> str:
    """The constitution without its change record.

    The Sync Impact Report is an HTML comment at the top and quotes the wording it
    replaced — necessarily, since that is what a change record is for.
    """
    text = CONSTITUTION.read_text()
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def test_the_check_covers_something() -> None:
    """Without this, moving or emptying src/ would make every assertion below pass."""
    assert len(_source_files()) >= 50
    assert len(_constitution_body()) > 2000


def test_no_parked_state_remains_in_the_tree() -> None:
    offenders = []
    for path in _source_files():
        if path.name == "test_parked_is_gone.py":
            continue
        code = _code_without_prose(path)
        if "PARKED" in code or "park_run" in code:
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"the removed state still appears in: {offenders}"


def test_suspended_is_not_terminal() -> None:
    """The one-line assertion the sweeper's existence rests on."""
    assert not RunState.SUSPENDED.is_terminal()
    assert RunState.STOPPED.is_terminal(), "a bound must stay terminal"
    assert not hasattr(RunState, "PARKED")


def test_the_constitution_describes_no_parking() -> None:
    body = _constitution_body().lower()
    assert "grant-expiry parking" not in body
    assert "the run parks" not in body


def test_the_constitution_does_not_gate_parity_on_four_transports_only() -> None:
    """The row must bind at two transports, not only once a fourth exists."""
    body = _constitution_body()
    assert "surface parity across all four transports" not in body
    assert "every pair of implemented transports" in body


def test_excluding_the_change_record_did_not_swallow_the_body() -> None:
    """The exclusion is load-bearing, so it gets a positive control.

    A stripper that removed too much would make every assertion above vacuous while
    looking like it worked — which is the failure mode of every prose-stripping check in
    this repository, and the reason they all carry one of these.
    """
    body = _constitution_body()
    assert "## Core Principles" in body
    assert "Principle X" in body
    assert "Quality Gates" in body
