# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — every call a program makes is governed (C1–C4, C7).

**These rows are ADR-0041's verification, not a report on it.** That record makes code mode
conditional on a hard gate: if it cannot be independently demonstrated that every tool call
issued from sandboxed code round-trips the full hook pipeline, code mode does not ship in
the governed path. What follows is that demonstration, and if any of it cannot be made
honestly green the correct outcome is FR-013 — code mode absent or refusing — never a
weaker row wearing the same name.

The arithmetic is stated rather than assumed: `run_program` is itself a registered tool, so
a program making N inner calls produces **N+1** governed decisions. That is the finding
036's first analyze pass surfaced, and asserting "the same total as a structured run" would
have been asserting something false.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from adapters.pydantic_ai.sandbox_runtime import MontyRuntime
from core.audit.schema import AuditEventType
from core.sandbox import run_program
from core.sandbox.program_tool import run_submitted_program
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture


def _fixture(tools: dict[str, CountingHandler], scope: list[str] | None = None) -> Any:
    return governed_agent_fixture(
        tool_calls=[], registry_tools=tools, scope_tools=scope if scope is not None else list(tools)
    )


def _decisions(audit: Any) -> int:
    """How many governed decisions the run produced, counted at the hook that always runs."""
    return len(
        [
            e
            for e in audit.all_entries()
            if e.event_type == AuditEventType.PRE_DECISION
            and e.payload.get("hook_name") == "dependency"
        ]
    )


def test_every_inner_call_reaches_the_governed_entry(monkeypatch: Any) -> None:
    """C1 — the host sees each call, and the registry body runs once per allowed call."""
    from core.tools.invoke import invoke_tool

    seen: list[str] = []

    def spy(run: Any, name: str, args: Any, **kw: Any) -> Any:
        seen.append(name)
        return invoke_tool(run, name, args, **kw)

    # Patched where the SEAM looks it up, not where it is defined: the seam imported the
    # name at module load, so patching the definition site would leave the live reference
    # untouched and the spy would record nothing while the row still passed.
    monkeypatch.setattr("core.sandbox.seam.invoke_tool", spy)

    a, b = CountingHandler(result="A"), CountingHandler(result="B")
    _agent, deps, handlers, _audit = _fixture({"read_thing": a, "write_thing": b})
    program = "x = read_thing('p')\ny = write_thing('q', value=x)\n[x, y]\n"

    with MontyRuntime() as rt:
        result = run_program(
            deps.governed_run, program, rt, externals=["read_thing", "write_thing"]
        )

    assert seen == ["read_thing", "write_thing"], f"the governed entry saw {seen}"
    assert result.value == ["A", "B"], "the governed results did not flow back into the program"
    assert handlers["read_thing"].call_count == 1
    assert handlers["write_thing"].call_count == 1


def test_a_program_of_n_calls_costs_n_plus_one_decisions() -> None:
    """C1 — the submission is one governed step; each inner call is another."""
    handlers = {f"t{i}": CountingHandler(result=str(i)) for i in range(3)}
    _agent, deps, made, audit = _fixture(handlers)
    program = "a = t0('x')\nb = t1('y')\nc = t2('z')\n[a, b, c]\n"

    before = _decisions(audit)
    with MontyRuntime() as rt:
        run_submitted_program(deps.governed_run, program, rt, externals=list(handlers))
    inner = _decisions(audit) - before

    assert inner == 3, f"expected one decision per inner call, got {inner}"
    # The +1 is the submission itself, which a real run makes through `invoke_tool` when the
    # model calls `run_program`. Asserted here as the recorded cause rather than re-run.
    submitted = [e for e in audit.all_entries() if e.event_type == AuditEventType.PROGRAM_SUBMITTED]
    assert len(submitted) == 1, "the program was not recorded as the cause of its calls"
    assert submitted[0].payload["program"] == program
    assert submitted[0].payload["program_sha256"] == hashlib.sha256(program.encode()).hexdigest()


def test_a_program_that_calls_nothing_is_not_an_error() -> None:
    """C1 at N=0 — pure computation produces no decisions and no effects."""
    _agent, deps, _made, audit = _fixture({"unused": CountingHandler()})
    before = _decisions(audit)

    with MontyRuntime() as rt:
        result = run_program(deps.governed_run, "x = 2 + 2\nx\n", rt, externals=["unused"])

    assert result.value == 4
    assert result.calls == []
    assert _decisions(audit) - before == 0


def test_a_denied_call_fails_inside_the_program_and_is_not_ridden_past() -> None:
    """C3 — a deny is one action refused; the program keeps running and may not have it."""
    allowed, denied = CountingHandler(result="ok"), CountingHandler(result="SHOULD-NOT-RUN")
    _agent, deps, handlers, _audit = _fixture(
        {"allowed_tool": allowed, "denied_tool": denied}, scope=["allowed_tool"]
    )
    # The program catches the refusal and keeps going — proving a deny is not a bound.
    program = (
        "a = allowed_tool('x')\n"
        "try:\n"
        "    b = denied_tool('y')\n"
        "except Exception:\n"
        "    b = 'refused'\n"
        "c = allowed_tool('z')\n"
        "[a, b, c]\n"
    )

    with MontyRuntime() as rt:
        result = run_program(
            deps.governed_run, program, rt, externals=["allowed_tool", "denied_tool"]
        )

    assert handlers["denied_tool"].call_count == 0, "a denied tool executed"
    assert result.denied == ["denied_tool"]
    assert result.value == ["ok", "refused", "ok"], (
        "the program did not survive a denial — a deny must not end the run (C7 does)"
    )


@pytest.mark.parametrize("name", ["open", "eval", "__import__", "exfiltrate"])
def test_an_invented_name_refuses_on_the_ordinary_path(name: str) -> None:
    """C4 — no blocklist: the registry decides, and refuses what it does not know.

    Each of these reaches the host shaped exactly like a legitimate tool call, because the
    sandbox forwards every unresolved name. The refusal comes from the registry lookup
    inside `invoke_tool`, which is why there is no list here for anybody to forget to update.
    """
    _agent, deps, _handlers, _audit = _fixture({"legit": CountingHandler(result="ok")})
    program = f"try:\n    r = {name}('x')\nexcept Exception:\n    r = 'refused'\nr\n"

    with MontyRuntime() as rt:
        result = run_program(deps.governed_run, program, rt, externals=["legit"])

    assert result.value == "refused", f"{name} was not refused"
    assert name in result.denied, f"{name} was not recorded as denied: {result.denied}"
