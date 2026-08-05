# SPDX-License-Identifier: Apache-2.0
"""Code mode as a registered tool (036, ADR-0041; research R8).

**Submitting a program is itself a governed call**, because `run_program` is an ordinary
registered tool. That is the design's cheapest and most important property:

* **No new invocation class.** The model emits one tool call; the pipeline decides it like
  any other. Nothing new to intercept, no second enforcement point (Principle II).
* **The registry is the opt-in switch.** A definition whose ceiling does not include
  `run_program` has no code mode — FR-016 ("neither capability may change what a definition
  is permitted to do") holding by construction rather than by a flag somebody must remember.
* **N inner calls cost N+1 steps.** The submission is one governed step and each inner call
  is another, so a program is bounded exactly as an equivalent structured run is, one step
  earlier. That arithmetic is stated rather than discovered (FR-010, and the finding that
  came out of 036's first analyze pass).

The handler here builds nothing and decides nothing: it drives the seam, whose loop routes
every request the program makes back through `invoke_tool`.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.audit.schema import AuditEventType
from core.run import GovernedRun
from core.sandbox.seam import ProgramResult, SandboxRuntime, run_program

#: The registered name. Code mode is reachable only through this, and only for a definition
#: whose ceiling carries it.
PROGRAM_TOOL_NAME = "run_program"


def record_program(run: GovernedRun, program: str, digest: str) -> None:
    """Write the program as the recorded cause of the calls that follow (US3, FR-012).

    Written when the submission is ALLOWED. A denied submission leaves the ordinary
    `PRE_DECISION` denial and nothing here: a program that never ran caused nothing, and
    recording it would put un-executed model output into an append-only trail.

    Verbatim, on `TURN_RECORDED`'s argued precedent — this is the only durable copy of the
    cause, and a trail holding a program's effects without the program is one nobody can
    reconstruct (Principle IX).
    """
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.PROGRAM_SUBMITTED,
        payload={"program": program, "program_sha256": digest},
    )


def run_submitted_program(
    run: GovernedRun,
    program: str,
    runtime: SandboxRuntime,
    *,
    externals: Sequence[str],
) -> ProgramResult:
    """Record the cause, then execute it under the governed loop.

    Order matters: the program is recorded *before* it runs. A program that fails partway
    still caused whatever it caused, and a trail that only recorded successful programs
    would describe a different run than the one that happened.
    """
    import hashlib

    digest = hashlib.sha256(program.encode("utf-8")).hexdigest()
    record_program(run, program, digest)
    return run_program(run, program, runtime, externals=externals)


__all__ = ["PROGRAM_TOOL_NAME", "record_program", "run_submitted_program"]
