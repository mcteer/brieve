# SPDX-License-Identifier: Apache-2.0
"""US4 — the adapter contains only the four mappings (FR-002).

Unit lane. The conformance lane owns the merge-blocking ordering assertion; this
is the fast signal that localizes a mapping break during development. The
duplication is deliberate — see specs/004-primary-adapter/research.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture

ADAPTER_DIR = Path(__file__).resolve().parents[2] / "src" / "adapters" / "pydantic_ai"


@pytest.mark.anyio
async def test_tool_mapping_delegates_to_invoke_tool() -> None:
    """Execution reaches the core registry body, never the framework's."""
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
    )

    await agent.run("go", deps=deps)

    # The framework tool bodies raise if executed; a counted core execution with no
    # AssertionError proves the call went through invoke_tool.
    assert handlers["echo"].call_count == 1


def test_adapter_holds_no_authority_or_audit_logic() -> None:
    """FR-002 review bar, mechanized: no core-owned concern reimplemented here."""
    forbidden_calls = {
        "manufacture_authority",
        "intersect_scopes",
        "live_effective",
        "append_event",
        "verify_chain",
        "run_pipeline",
    }
    offenders: list[str] = []
    for path in ADAPTER_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name in forbidden_calls:
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, (
        f"adapter reimplements core-owned logic: {offenders}. "
        "Authority, audit, and hook algebra belong in core (FR-002)."
    )


def test_adapter_modules_are_exactly_the_four_mappings() -> None:
    """A fifth behavioural module is a scope breach, not a refactor."""
    modules = {p.stem for p in ADAPTER_DIR.glob("*.py")} - {"__init__"}
    assert modules == {
        "tools",  # mapping 1
        "durability",  # mapping 2
        "approvals",  # mapping 3
        "run_context",  # mapping 4
        "agent",  # entry points binding the four together
        "governance",  # the capability that installs mapping 1
    }, f"unexpected adapter modules: {sorted(modules)}"
