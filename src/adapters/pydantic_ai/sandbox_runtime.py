# SPDX-License-Identifier: Apache-2.0
"""The Monty binding — the only module in `src/` that imports the sandbox runtime (036).

Implements `core.sandbox.SandboxRuntime` against `pydantic-monty`. Everything governance
depends on lives on the other side of that Protocol, in `core`, which is what makes this
file replaceable: swapping interpreters means writing another one of these and changing no
assertion (FR-014a/c).

**The distribution is `pydantic-monty`, not `monty`.** PyPI `monty` is an unrelated
materials-science package that installs cleanly and fails only at the import. The name is
asserted by `tests/unit/test_sandbox_dependency_identity.py` rather than trusted to have
been typed correctly once — ADR-0004's identified-content discipline, applied to a runtime.

**What the runtime does and does not do.** It suspends at every external call and hands the
host a snapshot naming the function and its arguments. It does **not** enforce which
functions exist: a name that is not in `external_lookup` — including `open`, `eval`,
`__import__`, and anything the model invents — arrives here as an ordinary suspension. That
measured fact is why the seam routes *every* request through `invoke_tool` and keeps no
blocklist of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.sandbox.seam import CallRequest, SandboxUnavailableError

try:  # pragma: no cover - exercised by the absent-runtime row in a filtered environment
    import pydantic_monty as _monty
except ImportError:  # pragma: no cover - see MontyRuntime.__init__
    _monty = None  # type: ignore[assignment]


# **A program's value is its final expression**, measured rather than assumed. `MontyComplete`
# exposes exactly one thing — ``output`` — and it carries the value of the last *expression*
# the program evaluated. A program of statements only completes with ``output=None``, and a
# trailing ``result = [...]`` assignment is a statement, so it yields nothing.
#
# The first draft of this module read a module-level ``result`` binding out of a namespace
# attribute. There is no such attribute; the binding was invented, and it returned `None` for
# every program. Caught by driving the real runtime instead of trusting the shape — which is
# why the value contract is written down here, where the next person writing a program prompt
# will look.


class MontyRuntime:
    """`SandboxRuntime` over `pydantic_monty`, one session per program.

    A session owns a worker process and is a context manager upstream; this holds it open
    for the life of one program and closes it in `close()`. One program, one worker: a
    reused interpreter would carry state between programs, and two runs sharing state is a
    governance boundary nobody declared.
    """

    def __init__(self, *, limits: Any | None = None) -> None:
        if _monty is None:
            # A STATED REFUSAL, never an ImportError from three frames down (FR-013). The
            # capability is absent; the operator is told which package supplies it.
            raise SandboxUnavailableError(
                "code mode is unavailable: the sandbox runtime is not installed. "
                "Install the `sandbox` extra (pydantic-monty)."
            )
        self._pool = _monty.Monty()
        self._pool.__enter__()
        self._session = self._pool.checkout(limits=limits)
        self._session.__enter__()

    # -- SandboxRuntime -------------------------------------------------------------

    def start(self, program: str, *, externals: Sequence[str]) -> Any:
        # `external_lookup` names what the program may call *by convention*; it does not
        # restrict what it may attempt. Ellipsis marks a name the host will answer, and an
        # absent name still suspends here — which is exactly why the seam decides, not this.
        lookup = {name: ... for name in externals}
        return self._session.feed_start(program, external_lookup=lookup)

    def resume(self, suspension: Any, value: Any) -> Any:
        return suspension.resume({"return_value": value})

    def fail(self, suspension: Any, message: str) -> Any:
        """Raise inside the sandbox, so a refused call fails where it was made.

        `exc_type`/`message` rather than a return value: a denied call must not be
        distinguishable from a successful one only by inspecting the value it produced.
        """
        return suspension.resume({"exc_type": "PermissionError", "message": message})

    def is_complete(self, snapshot: Any) -> bool:
        return isinstance(snapshot, _monty.MontyComplete)

    def request_of(self, snapshot: Any) -> CallRequest:
        return CallRequest(
            name=snapshot.function_name,
            args=tuple(snapshot.args),
            kwargs=dict(snapshot.kwargs),
            call_id=str(getattr(snapshot, "call_id", "")),
        )

    def value_of(self, snapshot: Any) -> Any:
        # `output` converts the final value out of the interpreter's representation on each
        # access. See the note at the top of this module for why the value is the program's
        # trailing EXPRESSION and not a named binding.
        return snapshot.output

    # -- lifecycle ------------------------------------------------------------------

    def dump(self) -> bytes:
        """The suspended worker, serialized. Opaque — see `core.sandbox.state`.

        The credential discipline is asserted against the seam's own ledger and never
        against these bytes, so that a format change in a `0.0.x` upstream cannot silently
        stop the scanner from finding things.
        """
        return self._session.dump()

    def close(self) -> None:
        try:
            self._session.__exit__(None, None, None)
        finally:
            self._pool.__exit__(None, None, None)

    def __enter__(self) -> MontyRuntime:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def runtime_available() -> bool:
    """Whether the sandbox extra is installed, for a caller that wants to refuse early."""
    return _monty is not None


__all__ = ["MontyRuntime", "runtime_available"]
