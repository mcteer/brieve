# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — parity holds across a kill (C10, FR-011a).

**The row analyze pass 2 added, because everything else here verifies parity only for runs
that never stop.** That is the wrong population: the resume path is where 014 found four
latent defects, and `run_program` is one non-repeatable bracket with inner brackets nested
inside it, so a kill mid-program lands squarely on the design's one open question.

Two properties, and they fail differently:

* **Post-resume calls are governed identically.** The run continues under its *surviving
  grant* — a resume re-observes, it does not re-authorize (ADR-0026) — so the calls made
  after the kill produce the same decisions and records as the ones before it.
* **Pre-kill calls are not re-executed.** The sandbox snapshot is the checkpoint, so
  resumption continues past what already happened rather than replaying it. Re-observe,
  never re-execute: a program whose first two calls had real effects must not repeat them
  because the third was interrupted.
"""

from __future__ import annotations

from typing import Any

from adapters.pydantic_ai.sandbox_runtime import MontyRuntime
from core.sandbox import run_program
from core.sandbox.seam import ProgramResult
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture


class _KillAfter:
    """A runtime wrapper that stops the world after N host round-trips.

    Stands in for an allocation dying mid-program. The interruption happens at the seam —
    where a real kill would leave it — rather than being simulated by rewriting state.
    """

    def __init__(self, inner: Any, *, after: int) -> None:
        self._inner = inner
        self._after = after
        self.seen = 0
        self.suspended: Any = None

    def start(self, program: str, *, externals: Any) -> Any:
        return self._inner.start(program, externals=externals)

    def resume(self, suspension: Any, value: Any) -> Any:
        self.seen += 1
        if self.seen >= self._after:
            # The kill: hand back a completed snapshot so the loop stops, and keep the
            # suspension so a resumed run could pick it up.
            self.suspended = suspension
            raise _Killed()
        return self._inner.resume(suspension, value)

    def fail(self, suspension: Any, message: str) -> Any:
        return self._inner.fail(suspension, message)

    def is_complete(self, snapshot: Any) -> bool:
        return bool(self._inner.is_complete(snapshot))

    def request_of(self, snapshot: Any) -> Any:
        return self._inner.request_of(snapshot)

    def value_of(self, snapshot: Any) -> Any:
        return self._inner.value_of(snapshot)


class _Killed(Exception):
    """The allocation died."""


def test_calls_made_before_a_kill_are_not_re_executed() -> None:
    """C10(b) — re-observe, never re-execute."""
    handler = CountingHandler(result="ok")
    _agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"step": handler}
    )
    program = "a = step('1')\nb = step('2')\nc = step('3')\n[a, b, c]\n"

    with MontyRuntime() as inner:
        killer = _KillAfter(inner, after=2)
        try:
            run_program(deps.governed_run, program, killer, externals=["step"])
        except _Killed:
            pass

        before_kill = handlers["step"].call_count
        assert before_kill == 2, f"expected two calls before the kill, got {before_kill}"

        # The resumed run continues from the SUSPENSION, not from the top. A resume that
        # restarted the program would re-execute `step('1')` and the count would climb past
        # the calls the program actually made.
        resumed = ProgramResult()
        snapshot = inner.resume(killer.suspended, "ok")
        for _ in range(10):
            if inner.is_complete(snapshot):
                resumed.value = inner.value_of(snapshot)
                break
            request = inner.request_of(snapshot)
            from core.tools.invoke import invoke_tool

            outcome = invoke_tool(deps.governed_run, request.name, dict(request.kwargs))
            resumed.calls.append(request.name)
            snapshot = inner.resume(snapshot, outcome.tool_result)

    assert handlers["step"].call_count == 3, (
        f"the program's calls were re-executed on resume: {handlers['step'].call_count} "
        "total for a three-call program"
    )


def test_calls_made_after_a_resume_are_governed_the_same_way() -> None:
    """C10(a) — the surviving grant governs the rest of the program.

    A tool the run may not use is still denied after the kill: resumption carries the run's
    authority forward unchanged rather than re-deriving it (ADR-0026).
    """
    allowed, denied = CountingHandler(result="ok"), CountingHandler(result="NO")
    _agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[],
        registry_tools={"allowed_tool": allowed, "denied_tool": denied},
        scope_tools=["allowed_tool"],
    )
    program = (
        "a = allowed_tool('1')\n"
        "try:\n"
        "    b = denied_tool('2')\n"
        "except Exception:\n"
        "    b = 'refused'\n"
        "[a, b]\n"
    )

    with MontyRuntime() as inner:
        # Killed after the FIRST call, so the denied call falls on the far side of the
        # resume — which is the only arrangement that tests what this row claims to.
        # (A denial routes through `fail`, not `resume`, so a later kill point would never
        # fire: the first draft of this row used one and silently tested nothing.)
        killer = _KillAfter(inner, after=1)
        try:
            run_program(
                deps.governed_run, program, killer, externals=["allowed_tool", "denied_tool"]
            )
        except _Killed:
            pass

        assert killer.suspended is not None, "the kill never fired — the row tests nothing"

        # Resume and finish under the same run — the denial must still be a denial.
        from core.tools.invoke import invoke_tool

        snapshot = inner.resume(killer.suspended, "ok")
        for _ in range(10):
            if inner.is_complete(snapshot):
                break
            request = inner.request_of(snapshot)
            outcome = invoke_tool(deps.governed_run, request.name, dict(request.kwargs))
            snapshot = (
                inner.resume(snapshot, outcome.tool_result)
                if outcome.allowed
                else inner.fail(snapshot, outcome.message)
            )

    assert handlers["denied_tool"].call_count == 0, (
        "a tool outside the run's scope executed after a resume — the surviving grant "
        "was not what governed the rest of the program"
    )
