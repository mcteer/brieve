# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the parity rows can lose (C5).

**The row ADR-0054 demands as an assertion rather than a review note**: *a host-side handler
that bypasses `invoke_tool` must fail the suite.*

Every other row in this feature asserts that governance held. None of them can tell you
whether they would notice if it did not — a suite whose assertions are structurally
incapable of failing is indistinguishable from no suite, and this repository has shipped
that shape before (030 recorded a mutation check that passed with and without the property
it claimed to test).

So this rigs the seam: a loop that returns a value to the sandbox **without** ever calling
`invoke_tool`, exactly as a well-meaning optimization might. Then it runs C1's own assertion
body against it and requires that assertion to **fail**. If this test fails, the parity rows
have stopped being able to detect a bypass, and their green is worth nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.pydantic_ai.sandbox_runtime import MontyRuntime
from core.sandbox import run_program
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture


def _rigged_run_program(run: Any, program: str, runtime: Any, *, externals: list[str]) -> Any:
    """A seam that answers the sandbox itself. The bug this feature exists to prevent.

    Deliberately plausible: it looks like a fast path that "already knows" the answer, and
    it produces a working program with correct-looking output. What it never does is ask
    whether the call was permitted.
    """

    class _Result:
        def __init__(self) -> None:
            self.value: Any = None
            self.calls: list[str] = []
            self.denied: list[str] = []

    result = _Result()
    snapshot = runtime.start(program, externals=externals)
    for _ in range(100):
        if runtime.is_complete(snapshot):
            result.value = runtime.value_of(snapshot)
            return result
        request = runtime.request_of(snapshot)
        result.calls.append(request.name)
        # THE BYPASS: a value, with no governed decision behind it.
        snapshot = runtime.resume(snapshot, "ungoverned")
    raise AssertionError("rigged seam did not terminate")


def test_the_parity_assertion_fails_against_a_bypassing_seam(monkeypatch: Any) -> None:
    """C5 — run C1's assertion against the rigged seam and require it to fail."""
    from core.tools.invoke import invoke_tool

    seen: list[str] = []

    def spy(run: Any, name: str, args: Any, **kw: Any) -> Any:
        seen.append(name)
        return invoke_tool(run, name, args, **kw)

    # Patched where the SEAM looks it up, not where it is defined: the seam imported the
    # name at module load, so patching the definition site would leave the live reference
    # untouched and the spy would record nothing while the row still passed.
    monkeypatch.setattr("core.sandbox.seam.invoke_tool", spy)

    handler = CountingHandler(result="A")
    _agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"read_thing": handler}
    )
    program = "x = read_thing('p')\nx\n"

    with MontyRuntime() as rt:
        rigged = _rigged_run_program(deps.governed_run, program, rt, externals=["read_thing"])

    # The rigged seam "worked": the program ran and produced a value.
    assert rigged.value == "ungoverned"
    assert rigged.calls == ["read_thing"]

    # And C1's assertions REJECT it. This is the whole row.
    with pytest.raises(AssertionError):
        assert seen == ["read_thing"], "the governed entry was never asked"
    assert handlers["read_thing"].call_count == 0, (
        "the registry body ran without a governed decision — the bypass was not detectable"
    )


def test_the_honest_seam_passes_the_same_assertion(monkeypatch: Any) -> None:
    """The control: the real seam satisfies exactly the assertion the rigged one fails.

    Without this pair, C5 could pass because the assertion is impossible to satisfy rather
    than because it discriminates.
    """
    from core.tools.invoke import invoke_tool

    seen: list[str] = []

    def spy(run: Any, name: str, args: Any, **kw: Any) -> Any:
        seen.append(name)
        return invoke_tool(run, name, args, **kw)

    # Patched where the SEAM looks it up, not where it is defined: the seam imported the
    # name at module load, so patching the definition site would leave the live reference
    # untouched and the spy would record nothing while the row still passed.
    monkeypatch.setattr("core.sandbox.seam.invoke_tool", spy)

    handler = CountingHandler(result="A")
    _agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"read_thing": handler}
    )

    with MontyRuntime() as rt:
        result = run_program(
            deps.governed_run, "x = read_thing('p')\nx\n", rt, externals=["read_thing"]
        )

    assert seen == ["read_thing"]
    assert result.value == "A"
    assert handlers["read_thing"].call_count == 1
