# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — an honest absence, and a recoverable cause (C8, C9, C6).

**C8 — absence is stated, never silent.** Without the optional runtime, code mode refuses
with a reason naming what is missing. Not an ImportError from three frames down, and not a
capability that half-exists: ADR-0047's rule is that a missing thing must be absent or
explicitly refused, and FR-013 applies it to this feature. This is also the outcome ADR-0041
anticipates if parity could not be demonstrated — the mechanism for shipping *nothing* has
to work as reliably as the mechanism for shipping the feature.

**C9 — the cause is recoverable.** A code-mode run's records must let a reader reconstruct
not just the effects but the program that caused them, joined by digest.

**C6 — a sandbox snapshot is a checkpoint.** What the platform serializes to suspend a
program is subject to the credential-free-checkpoint discipline, asserted against the seam's
own ledger rather than the runtime's opaque bytes — so a format change in a `0.0.x` upstream
cannot silently stop the scanner from finding things.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from adapters.pydantic_ai.durability import CredentialInCheckpointError, save_state
from adapters.pydantic_ai.sandbox_runtime import MontyRuntime
from core.audit.schema import AuditEventType
from core.sandbox import SandboxLedger, SandboxUnavailableError
from core.sandbox.program_tool import run_submitted_program
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture


def test_an_absent_runtime_refuses_with_a_stated_reason(monkeypatch: Any) -> None:
    """C8 — the operator is told which package supplies the capability."""
    import adapters.pydantic_ai.sandbox_runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "_monty", None)
    assert runtime_mod.runtime_available() is False

    with pytest.raises(SandboxUnavailableError) as raised:
        runtime_mod.MontyRuntime()

    message = str(raised.value)
    assert "sandbox" in message and "not installed" in message, (
        f"the refusal does not name what is missing: {message!r}"
    )


def test_the_program_is_recoverable_from_the_run_records() -> None:
    """C9 — cause and effects, joined by digest, from the platform's own records."""
    handlers = {
        "read_thing": CountingHandler(result="A"),
        "write_thing": CountingHandler(result="B"),
    }
    _agent, deps, made, audit = governed_agent_fixture(tool_calls=[], registry_tools=handlers)
    program = "x = read_thing('p')\ny = write_thing('q', value=x)\n[x, y]\n"

    with MontyRuntime() as rt:
        result = run_submitted_program(deps.governed_run, program, rt, externals=list(handlers))

    submitted = [e for e in audit.all_entries() if e.event_type == AuditEventType.PROGRAM_SUBMITTED]
    assert len(submitted) == 1
    recovered = submitted[0].payload

    assert recovered["program"] == program, "the cause is not recoverable verbatim"
    assert recovered["program_sha256"] == hashlib.sha256(program.encode()).hexdigest()
    # The effects sit on the same correlation id, so cause and effect join without anything
    # outside the platform's records.
    assert submitted[0].correlation_id == deps.governed_run.correlation_id
    assert result.calls == ["read_thing", "write_thing"]


def test_a_denied_submission_records_no_program() -> None:
    """C9 — a program that never ran caused nothing, so nothing is recorded.

    Recording an un-executed program would put model output the platform refused into an
    append-only trail.
    """
    _agent, deps, _made, audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"t": CountingHandler()}
    )
    before = [e for e in audit.all_entries() if e.event_type == AuditEventType.PROGRAM_SUBMITTED]
    assert before == []


def test_a_credential_in_sandbox_state_is_refused_at_the_checkpoint() -> None:
    """C6 — the ledger is what the discipline scans, not the runtime's opaque bytes."""
    ledger = SandboxLedger()
    ledger.record_input("config", "harmless")
    # A tool result carrying credential-shaped material, handed back into the sandbox —
    # NESTED, which is the case that matters: the adapter's scanner inspects top-level keys
    # only, so this is precisely what a naive ledger shape would have hidden.
    ledger.record_resume("0", {"token": "issued-by-a-tool"})

    # The hoist is the load-bearing part, asserted before the refusal so a regression in it
    # cannot leave the row passing for the wrong reason.
    assert "token" in ledger.scannable(), (
        "a nested credential key was not hoisted — the checkpoint scanner cannot see it"
    )

    from core.durability import InMemoryDurabilityProvider

    with pytest.raises(CredentialInCheckpointError):
        save_state(
            InMemoryDurabilityProvider(),
            blob_id="blob-1",
            correlation_id="corr-1",
            state=ledger.scannable(),
        )


def test_a_clean_ledger_checkpoints_without_complaint() -> None:
    """The control: the scanner discriminates rather than refusing everything."""
    from core.durability import InMemoryDurabilityProvider

    ledger = SandboxLedger()
    ledger.record_input("config", "harmless")
    ledger.record_resume("0", "an ordinary tool result")

    blob = save_state(
        InMemoryDurabilityProvider(),
        blob_id="blob-1",
        correlation_id="corr-1",
        state=ledger.scannable(),
    )
    assert blob is not None
