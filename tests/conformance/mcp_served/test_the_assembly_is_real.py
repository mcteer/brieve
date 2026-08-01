# SPDX-License-Identifier: Apache-2.0
"""The assembly, and the rule that keeps these rows meaning what they say.

**Assembly is the one path no unit test covers.** ROADMAP gap 0d named that shape and 017 was
built for it; this feature exists because the MCP transport was correct, tested, and wired to
nothing. So the row that proves the assembly must drive the running process, and the rule that
forbids shortcuts must be checked rather than trusted.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.conformance.mcp_served import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

HERE = Path(__file__).resolve().parent


def test_the_served_process_is_assembled_from_real_parts(running_surface: str) -> None:
    """FR-002, FR-004: real collaborators, said out loud by the process itself.

    `McpTransport` defaults several collaborators to in-memory implementations. That is right
    for the class rows and wrong here — an in-memory thread store would serve a client
    happily, lose everything, and leave every pre-existing row passing.
    """
    output = surfaces.allocation_output(running_surface)

    assert "mcp surface ready" in output, (
        f"the surface never announced readiness, so nothing here can claim it assembled.\n"
        f"--- its own output ---\n{output[-2000:]}"
    )
    assert "db=" in output, "the readiness line does not name where its database is"


def test_no_row_here_constructs_the_transport() -> None:
    """FR-016, and the rule this whole directory rests on.

    A row that built `McpTransport` in a fixture would assert exactly what fifty-six class
    rows already assert, while sitting in a directory whose name promises a served process.
    **That is this feature's own defect, reintroduced inside the fix** — and nothing else
    would catch it, because such a row passes.

    Checked structurally rather than by grep, so a mention in prose is not a violation and an
    aliased import is.
    """
    offences: list[str] = []

    for module in sorted(HERE.glob("*.py")):
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "surfaces.mcp.transport":
                offences.append(f"{module.name}:{node.lineno} imports from the transport module")
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "McpTransport":
                    offences.append(f"{module.name}:{node.lineno} constructs McpTransport")

    assert not offences, (
        "a row in this directory reaches the transport directly instead of the served "
        "process:\n" + "\n".join(f"  {o}" for o in offences)
    )
