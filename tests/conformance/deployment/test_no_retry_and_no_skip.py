# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — this package neither retries nor skips (017, FR-006/FR-014).

**Why retrying is forbidden here specifically.** This gate exists because a defect hid for
months behind gates that passed. An assembly that fails one start in three would go green on
the second attempt and nobody would learn — which is the failure mode returning under a
different name. A process that reached a working state on the second attempt did not reach
it on the first, and that difference is the defect.

**Why the check is scoped to modules rather than to loop syntax.** A readiness poll and an
assertion retry are textually identical. There is exactly one wait in this package, in
`conftest.py`, and it is what makes generous per-process waits possible; a row keyed on
`while` or `for` would either flag it or be relaxed until it asserted nothing. So the rule is
structural: **one module may wait, and no other module may loop over an assertion.**
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

HERE = Path(__file__).parent

#: The one module permitted to wait. Named, so adding a second is a visible decision.
MAY_WAIT = "conftest.py"


def modules() -> list[Path]:
    return sorted(p for p in HERE.glob("*.py") if p.name != "__init__.py")


def test_nothing_in_this_package_skips() -> None:
    """A gate that skips when the thing it guards is missing reports green for the one
    state it exists to catch (FR-006)."""
    offenders = {
        p.name: [
            node.lineno
            for node in ast.walk(ast.parse(p.read_text()))
            if isinstance(node, ast.Attribute) and node.attr in {"skip", "skipif", "xfail"}
        ]
        for p in modules()
    }
    offenders = {name: lines for name, lines in offenders.items() if lines}

    assert not offenders, (
        f"skips in a merge-blocking deployment gate: {offenders}. An absent process is a "
        f"failure, never a skip — FR-006."
    )


def test_no_module_loops_over_an_assertion() -> None:
    """FR-014, stated as the property it actually is.

    Not "no loops" — `surfaces.py` iterates job definitions and the coverage rows iterate
    sets, and neither retries anything. What a retry looks like structurally is a **loop
    whose body contains an assertion**: attempt, check, go round again. That is the shape
    forbidden, and stating it this way needs no exemption list to be maintained.
    """
    offenders: dict[str, list[int]] = {}
    for path in modules():
        if path.name == MAY_WAIT:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.While, ast.For)):
                continue
            if any(isinstance(inner, ast.Assert) for inner in ast.walk(node)):
                offenders.setdefault(path.name, []).append(node.lineno)

    assert not offenders, (
        f"assertions inside loops: {offenders}. A loop around an attempt is a retry, and a "
        f"retry is how this class of defect returns to invisibility — an assembly failing "
        f"one start in three goes green on the second pass and nobody learns. Assert once; "
        f"if the surface needs time, that is {MAY_WAIT}'s single bounded wait."
    )


def test_the_single_wait_is_bounded() -> None:
    """A wait that could not expire would hang the lane rather than failing it (FR-002)."""
    source = (HERE / MAY_WAIT).read_text()
    assert "deadline" in source and "time.monotonic" in source, (
        "the wait is not bounded by a deadline, so a hung surface would hold the lane until "
        "the surrounding job's own timeout — which reports as the gate overrunning rather "
        "than as that surface failing"
    )
    assert "WAITS" in source, "waits are not stated per process (SC-004)"
