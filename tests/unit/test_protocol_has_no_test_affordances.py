# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the identity fabric protocol declares nothing that exists for tests.

`IdentityFabric` used to declare ``issue_brokered_material`` and ``get_brokered_material``,
whose own docstrings said "(fake only)" and "never for audit/spans". A production
implementation would have been obliged to implement two methods that existed for tests,
and the honest implementation is a pair that raise — a protocol admitting it does not
describe its own production case.

**Without this row the next one arrives exactly as those did: as the shortest path at the
time.** Nobody adds a test-only method to a production protocol on purpose; they add it
because the fake needed somewhere to put something and the protocol was right there.

The check reads the AST rather than the source text, and the reason is specific to this
repository: five checks here have matched prose instead of code, twice in files whose own
docstrings warned about it. This module's docstring contains the exact strings the check
looks for, so a naive implementation would fail on itself — which is why
:func:`test_the_stripper_does_not_swallow_the_body` exists.
"""

from __future__ import annotations

import ast
import pathlib

FABRIC = pathlib.Path(__file__).resolve().parents[2] / "src" / "core" / "authority" / "fabric.py"

#: Words that mark a method as existing for tests rather than for the platform.
TEST_ONLY_MARKERS = ("fake only", "fake-only", "for tests", "test only", "test-only")


def _protocol_methods() -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(FABRIC.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "IdentityFabric":
            return [
                child
                for child in node.body
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
    raise AssertionError("IdentityFabric is not in fabric.py — did the protocol move?")


def test_the_protocol_declares_something() -> None:
    """The positive control.

    A check over an empty list passes vacuously, and a protocol that had been deleted or
    renamed would look exactly like a protocol with no test affordances.
    """
    methods = _protocol_methods()

    assert len(methods) >= 4, (
        f"IdentityFabric declares {len(methods)} method(s); the four resolutions "
        "(user scope, ceiling, policy, entitlements) are the reason it exists"
    )


def test_no_declared_method_is_marked_test_only() -> None:
    """The row itself: docstrings of protocol methods, not the module's prose."""
    offenders: list[str] = []
    for method in _protocol_methods():
        doc = (ast.get_docstring(method) or "").lower()
        if any(marker in doc for marker in TEST_ONLY_MARKERS):
            offenders.append(method.name)

    assert not offenders, (
        f"{offenders} are declared on the production protocol and documented as existing "
        "for tests. A production implementation would have to implement them, and the "
        "honest implementation is a method that raises — which is a protocol admitting it "
        "does not describe its own production case. Move the affordance to the fake."
    )


def test_the_brokered_material_methods_are_specifically_gone() -> None:
    """Named rather than implied, because these two are the reason the row exists.

    A future refactor could rename them past the marker check while keeping the shape.
    """
    names = {m.name for m in _protocol_methods()}

    assert "issue_brokered_material" not in names
    assert "get_brokered_material" not in names


def test_the_stripper_does_not_swallow_the_body() -> None:
    """Proof the check reads code rather than prose — in both directions.

    This module's own docstring contains "fake only". If the check searched the file text
    it would fail on itself; if it searched nothing it would pass on everything. Neither
    is a check. This asserts the marker is present in the file and absent from what the
    check actually examines.
    """
    assert "fake only" in __doc__.lower(), "the fixture lost the string it exists to model"

    examined = " ".join((ast.get_docstring(m) or "") for m in _protocol_methods()).lower()
    assert "fake only" not in examined, (
        "the marker appears in what the check examines, so the two assertions above are "
        "not independent — one of them is reading this file's prose"
    )
