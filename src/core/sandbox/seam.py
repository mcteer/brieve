# SPDX-License-Identifier: Apache-2.0
"""The governed loop: every call a program makes goes through `invoke_tool` (036).

This module is ADR-0041's gate made structural. That record says code mode ships **only**
with verified per-call hook parity — "sandbox safety is not governance" — and the way to
make that verifiable rather than hoped-for is to leave the runtime exactly one exit and put
`invoke_tool` at it.

**The loop has no second path, and that is the whole design.** A call request from the
sandbox is routed to `invoke_tool` whether or not the name is a registered tool. There is no
blocklist, no allowlist, and no special case: `open`, `eval`, `__import__` and a name the
model invented are all *requests*, and the registry decides. This collapses FR-008 into the
path that already exists rather than adding a second place to get it wrong — and it means
the refusal an invented name receives is an ordinary `tool is not registered`, recorded like
any other denial.

**Three failures are deliberately NOT alike** (FR-010a):

* a **policy deny** becomes an in-sandbox failure the program can see and route around — it
  is a fact about one action;
* an **exhausted bound** propagates and terminates the run — it is a fact about the whole
  run, and converting it to a program-visible failure would let a program outlive its own
  budget by catching it;
* a **superseded lease** propagates for the same reason: a zombie must stop, not read a
  refusal and try the next call.

Getting that distinction backwards is the most plausible way this feature ships a hole, so
the seam states it rather than leaving it to the shape of a try/except.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.errors import CoreError
from core.run import GovernedRun
from core.sandbox.state import SandboxLedger
from core.tools.invoke import invoke_tool


class SandboxUnavailableError(CoreError):
    """No sandbox runtime is installed.

    Raised where code mode is asked for and the optional runtime is absent, so the caller
    can refuse with a stated reason rather than surfacing an ImportError from three frames
    down (FR-013). A capability that is missing must say so; silence and a stack trace are
    the two failure modes ADR-0047 calls worse than an honest absence.
    """


@dataclass(frozen=True)
class CallRequest:
    """One attempt by a program to call something by name.

    A request for a registered tool and a request for something invented are the **same
    shape** — the sandbox cannot tell them apart and neither does this. What distinguishes
    them is what the registry says when the seam asks, which is the point: there is one
    decision maker, and it is the one that already decides.
    """

    name: str
    args: Sequence[Any] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    #: The runtime's own identifier for this suspension, carried so the ledger can key a
    #: resume value to the call it answered.
    call_id: str = ""


@dataclass
class ProgramResult:
    """What a program produced, and what it did on the way.

    ``calls`` is the ordered list of names the program requested — the evidence US3 needs
    to reconstruct cause from effect. It records *requests*, including refused ones, because
    "the program tried to call something it could not" is exactly the thing a reader must
    be able to see.
    """

    value: Any = None
    calls: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    ledger: SandboxLedger = field(default_factory=SandboxLedger)


class SandboxRuntime(Protocol):
    """A sandboxed interpreter that suspends at every external call.

    The seam needs exactly this much of a runtime, which is what makes the runtime
    replaceable (FR-014a). Anything richer would tie the governance property to one
    upstream's API.
    """

    def start(self, program: str, *, externals: Sequence[str]) -> Any:
        """Begin executing ``program``; return the first suspension or completion."""
        ...

    def resume(self, suspension: Any, value: Any) -> Any:
        """Resume with a governed result; return the next suspension or completion."""
        ...

    def fail(self, suspension: Any, message: str) -> Any:
        """Resume by raising inside the sandbox; return the next suspension or completion."""
        ...

    def is_complete(self, snapshot: Any) -> bool:
        """Whether ``snapshot`` is a terminal result rather than a suspension."""
        ...

    def request_of(self, snapshot: Any) -> CallRequest:
        """The call a suspension is asking the host to perform."""
        ...

    def value_of(self, snapshot: Any) -> Any:
        """The program's result, for a snapshot that is complete."""
        ...


def run_program(
    run: GovernedRun,
    program: str,
    runtime: SandboxRuntime,
    *,
    externals: Sequence[str] | None = None,
    inputs: Mapping[str, Any] | None = None,
    max_calls: int = 1000,
) -> ProgramResult:
    """Execute ``program``, routing every call it makes through the governed entry.

    Called from inside the handler for the registered ``run_program`` tool, which means
    ``invoke_tool`` is **re-entered** here on the same run (research R11). That composes:
    the run's bounds count each inner call as a step exactly as they count a structured
    call, and the lease is re-asserted per call against the same holder. What it does *not*
    do is give the program a way to escape either — see the module docstring.

    ``max_calls`` is a loop backstop, not a governance bound. The real bound is the run's
    own ``max_steps``, enforced by ``invoke_tool``; this exists so a runtime that never
    reports completion cannot spin forever, and it is set by the platform rather than by
    anything the program can reach.
    """
    result = ProgramResult()
    for name, value in (inputs or {}).items():
        result.ledger.record_input(name, value)

    snapshot = runtime.start(program, externals=list(externals or []))

    for _ in range(max_calls):
        if runtime.is_complete(snapshot):
            result.value = runtime.value_of(snapshot)
            return result

        request = runtime.request_of(snapshot)
        result.calls.append(request.name)

        # THE ONE EXIT. Registered tool or invented name, this is the only way out of the
        # sandbox — and `invoke_tool` is the only thing that decides. A `LeaseSupersededError`
        # or `ExecutionBoundExceeded` raised in here is deliberately NOT caught: both are
        # facts about the run rather than about this call, and swallowing either would let a
        # program continue past a bound it has already exhausted.
        outcome = invoke_tool(run, request.name, dict(request.kwargs))

        if not outcome.allowed:
            # A DENY IS THE PROGRAM'S TO SEE. It is one action refused, not the end of the
            # run, so the program keeps running and may make further permitted calls. The
            # sandbox raises rather than receiving a value, because handing back a
            # fabricated result would let a refused call look like a successful one.
            result.denied.append(request.name)
            snapshot = runtime.fail(snapshot, outcome.message)
            continue

        result.ledger.record_resume(request.call_id, outcome.tool_result)
        snapshot = runtime.resume(snapshot, outcome.tool_result)

    raise CoreError(f"sandboxed program exceeded {max_calls} host round-trips without completing")


__all__ = [
    "CallRequest",
    "ProgramResult",
    "SandboxRuntime",
    "SandboxUnavailableError",
    "run_program",
]
