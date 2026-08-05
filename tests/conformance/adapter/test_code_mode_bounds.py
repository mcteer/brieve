# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a program cannot outlive the run's budget (C7, FR-010/FR-010a).

**The distinction this row exists for**: a policy deny and an exhausted bound must not be
alike. A deny is a fact about one action — the program sees it, may catch it, and keeps
running (C3). A bound is a fact about the whole run, and there is nothing left to route to,
so it propagates and terminates. Converting a bound into an in-sandbox failure would let a
program catch its own budget and keep going, which is the single most plausible way this
feature ships a hole.

The arithmetic is asserted with exact counts rather than as "the same total a structured run
would reach", because `run_program` is itself a governed step and a program of N inner calls
therefore spends N+1. Claiming parity of totals would have been claiming something false —
the correction 036's first analyze pass made before any code existed.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.pydantic_ai.sandbox_runtime import MontyRuntime
from core.bounds import BoundsTracker, ExecutionBoundExceeded, ExecutionBounds
from core.sandbox import run_program
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture
from tests.harness.frozen_clock import frozen_clock


def _bounded(max_steps: int) -> Any:
    """A run whose step budget is `max_steps`, with a tool it may call repeatedly."""
    handler = CountingHandler(result="ok")
    _agent, deps, handlers, audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"step": handler}
    )
    clock = frozen_clock()
    deps.governed_run.bounds = BoundsTracker(
        bounds=ExecutionBounds(max_steps=max_steps),
        started_at=clock.now(),
    )
    return deps, handlers


def test_each_inner_call_counts_one_step() -> None:
    """C7(a) — the bound advances per inner call, by `invoke_tool` on the existing path."""
    deps, handlers = _bounded(max_steps=10)
    program = "a = step('1')\nb = step('2')\nc = step('3')\n[a, b, c]\n"

    with MontyRuntime() as rt:
        run_program(deps.governed_run, program, rt, externals=["step"])

    assert deps.governed_run.bounds is not None
    assert deps.governed_run.bounds.steps_taken == 3, (
        f"expected one step per inner call, got {deps.governed_run.bounds.steps_taken}"
    )
    assert handlers["step"].call_count == 3


def test_a_program_cannot_exceed_the_run_budget() -> None:
    """C7(b) — the bound stops the program, at the count the budget names."""
    deps, handlers = _bounded(max_steps=2)
    program = "a = step('1')\nb = step('2')\nc = step('3')\n[a, b, c]\n"

    with MontyRuntime() as rt, pytest.raises(ExecutionBoundExceeded):
        run_program(deps.governed_run, program, rt, externals=["step"])

    assert handlers["step"].call_count == 2, (
        f"the program ran past its budget: {handlers['step'].call_count} calls"
    )


def test_a_bound_terminates_rather_than_becoming_a_program_failure() -> None:
    """C7(c) — the distinction from C3, asserted where it would actually break.

    The program tries to catch everything. A deny it may catch (C3 proves that); a bound it
    may not, because the seam lets `ExecutionBoundExceeded` propagate rather than raising it
    inside the sandbox. If this row fails, a program can swallow its own budget.
    """
    deps, handlers = _bounded(max_steps=2)
    program = (
        "out = []\n"
        "for i in range(5):\n"
        "    try:\n"
        "        out.append(step(str(i)))\n"
        "    except Exception:\n"
        "        out.append('caught')\n"
        "out\n"
    )

    with MontyRuntime() as rt, pytest.raises(ExecutionBoundExceeded):
        run_program(deps.governed_run, program, rt, externals=["step"])

    assert handlers["step"].call_count == 2, (
        "the program caught its own bound and kept calling — a bound is not catchable"
    )


def test_the_seam_sets_no_bound_of_its_own() -> None:
    """C7 — the platform owns the budget; a run without bounds is not silently bounded."""
    handler = CountingHandler(result="ok")
    _agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"step": handler}
    )
    assert deps.governed_run.bounds is None

    program = "out = [step(str(i)) for i in range(6)]\nout\n"
    with MontyRuntime() as rt:
        result = run_program(deps.governed_run, program, rt, externals=["step"])

    assert handlers["step"].call_count == 6
    assert len(result.calls) == 6
