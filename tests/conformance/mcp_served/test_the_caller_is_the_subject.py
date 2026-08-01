# SPDX-License-Identifier: Apache-2.0
"""US3 — the trail names the caller, not the server.

**This is the sharp edge, and it fails silently.** A server that authenticated itself and
acted on everyone's behalf would work perfectly, pass every pre-existing row, and quietly
convert a delegation chain into a shared account. Nothing above the audit entry would show it.
"""

from __future__ import annotations

import time

import pytest

from tests.conformance.mcp_served import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def _authority_subjects(correlation_id: str, token: str, *, wait: float = 90.0) -> list[str]:
    """Who the trail says acted, for one correlation id.

    The subject is not a column on an audit entry — it lives in an `authority_issued`
    record's payload, which is where the existing parity row reads it from too.

    **Waits, because against a live enclave the record is not written by the call.** The
    surface dispatches; the RUN writes its own authority record when its allocation starts.
    The existing parity row reads it synchronously because it holds an in-memory audit and a
    fake dispatcher — a difference invisible until the same assertion runs against the real
    thing, which is this feature's whole subject.

    A bounded wait, never an unbounded one: a record that never arrives is a finding, and a
    row that hung would report it as a stuck lane instead.
    """
    deadline = time.monotonic() + wait
    while True:
        evidence = surfaces.call("read_evidence", {"correlation_id": correlation_id}, token=token)
        entries = evidence.get("entries", []) if evidence.get("ok") else []
        found = [
            str(entry["payload"].get("subject_user_id", ""))
            for entry in entries
            if str(entry.get("event_type")) == "authority_issued"
            and entry.get("correlation_id") == correlation_id
        ]
        if found or time.monotonic() >= deadline:
            return found
        time.sleep(3.0)


def _start_run_as(token: str) -> str:
    started = surfaces.call(
        "start_run", {"agent_definition_id": "planner-agent", "requested_tools": []}, token=token
    )
    assert started.get("correlation_id"), f"starting a run answered no correlation id: {started}"
    return str(started["correlation_id"])


def test_the_trail_names_the_caller(caller: str) -> None:
    """FR-009, FR-010, SC-003: the subject is the person who called."""
    correlation_id = _start_run_as(caller)
    subjects = _authority_subjects(correlation_id, caller)

    assert subjects, "starting a run through the served surface wrote no authority record"
    assert "caller-1" in subjects, (
        f"the trail records {subjects} for a run started by caller-1. If this names the "
        f"service or a shared account, the delegation chain is broken — and everything else "
        f"would still work, which is why this row exists."
    )
    assert not any("mcp" in s.lower() for s in subjects), (
        f"the trail names the SERVER as the actor: {subjects}"
    )


def test_two_callers_are_distinguishable(caller: str, other_caller: str) -> None:
    """FR-011, SC-004 — and the assertion that has teeth.

    **Not "a subject was recorded."** That passes perfectly against a shared service account,
    which is the exact defect this feature exists to prevent. Two different people performing
    the same operation must leave two different records.
    """
    first = _authority_subjects(_start_run_as(caller), caller)
    second = _authority_subjects(_start_run_as(other_caller), other_caller)

    assert first and second, f"one of the two runs wrote no authority record: {first} / {second}"
    assert set(first) != set(second), (
        f"two different callers left indistinguishable records: {first} and {second}. A single "
        f"shared subject here would satisfy every other row in this suite."
    )


def test_a_session_is_bound_to_one_subject(caller: str) -> None:
    """FR-013a: the subject is fixed at the handshake and never reassigned.

    Exercised as a client would: the same session, used repeatedly, keeps answering as the
    same person. A session that drifted would be indistinguishable from one that did not,
    from any single call.
    """
    first = _authority_subjects(_start_run_as(caller), caller)
    second = _authority_subjects(_start_run_as(caller), caller)

    assert set(first) == set(second) == {"caller-1"}, (
        f"one session produced different subjects across calls: {first} then {second}"
    )


def test_no_credential_appears_in_the_surface_output(running_surface: str, caller: str) -> None:
    """[GATE:no-secret-leak] The server handles caller bearer tokens; nothing else on this
    surface ever did.

    A refusal with no diagnostic is a support ticket nobody can answer — and printing the
    token to make it answerable would put a live bearer credential in an allocation log every
    operator can read. The surface logs the REASON and never the credential.
    """
    surfaces.call("list_threads", {}, token=caller)
    output = surfaces.allocation_output(running_surface)

    assert caller not in output, (
        "a caller's bearer token appears verbatim in the surface's own output. Anyone with "
        "scheduler access could replay it."
    )
    for fragment in (caller[:24], caller.rsplit(".", 1)[-1][:24]):
        assert fragment not in output, f"part of a caller's credential is in the log: {fragment}"
