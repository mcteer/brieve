# SPDX-License-Identifier: Apache-2.0
"""The platform-owned sandbox seam (036, ADR-0041).

**The boundary is ours, and that is a measured fact rather than a preference.** The sandbox
runtime does not enforce which functions a program may call — it forwards every unresolved
name to the host, including `open`, `eval`, `__import__`, and names invented on the spot,
each arriving shaped exactly like a legitimate tool call. So the host's handler *is* the
security boundary. FR-014a makes that true by construction instead of by accident: the
governed loop lives here, in `core`, and the runtime plugs in underneath a Protocol.

Nothing in this package imports an agent framework or a sandbox runtime. `core` never
imports a framework (Principle I), and the parity assertions must bind to platform code
rather than to a `0.0.x` upstream's behaviour (FR-014c) — a runtime upgrade must not be
able to quietly weaken them.
"""

from core.sandbox.seam import (
    CallRequest,
    ProgramResult,
    SandboxRuntime,
    SandboxUnavailableError,
    run_program,
)
from core.sandbox.state import SandboxLedger

__all__ = [
    "CallRequest",
    "ProgramResult",
    "SandboxLedger",
    "SandboxRuntime",
    "SandboxUnavailableError",
    "run_program",
]
