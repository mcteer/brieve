# SPDX-License-Identifier: Apache-2.0
"""The surface may not describe governance it does not perform.

**This file is the one that would have failed on 2026-08-01.** The MCP surface told every
connecting client that *"every operation executes as the calling user and is recorded in a
tamper-evident trail"* while nine of seventeen operations wrote nothing at all. Nothing in the
857-test suite compared what the platform *says* to what it *does*.

The rows below drive every operation the catalogue claims records, through the real transport,
and check the trail. A catalogue entry is a claim; these make it a checkable one.
"""

from __future__ import annotations

from typing import Any

import pytest

from surfaces.api.record_access import record_stream_for
from surfaces.mcp.operations import (
    AUDIT_DISPOSITIONS,
    NO_RECORD,
    RECORDS,
    RECORDS_ELSEWHERE,
    McpOperation,
    governance_sentence,
    operations,
)
from tests.harness.api_fixtures import surface_under_test

#: How to drive each `records` operation far enough to observe whether it records.
#:
#: **Every one of the seven is here, and the row below fails if one is missing** — a coverage
#: table that silently omits an operation is how this gap reached seventeen in the first place.
DRIVERS: dict[str, Any] = {
    "list_runs": lambda s, subj: s.mcp.call("list_runs", {}, subject=subj),
    "get_run": lambda s, subj: s.mcp.call("get_run", {"run_id": "nope"}, subject=subj),
    "get_run_result": lambda s, subj: s.mcp.call(
        "get_run_result", {"run_id": "nope"}, subject=subj
    ),
    "list_threads": lambda s, subj: s.mcp.call("list_threads", {}, subject=subj),
    "get_thread": lambda s, subj: s.mcp.call("get_thread", {"thread_id": "nope"}, subject=subj),
    "create_thread": lambda s, subj: s.mcp.call("create_thread", {}, subject=subj),
    "stop_run": lambda s, subj: s.mcp.call("stop_run", {"run_id": "nope"}, subject=subj),
}


def _subject(surface: Any) -> Any:
    return surface.subject()


def _recorded_names() -> set[str]:
    return {o.tool_name for o in operations() if o.audit_disposition == RECORDS}


def test_every_operation_carries_a_disposition() -> None:
    """SC-004. A required field makes omission a constructor error; this names the operation.

    `McpOperation` rejects a missing disposition at construction — but a `TypeError` names an
    *argument*, not the thing a person has to fix. This row is what makes the failure legible,
    and it is the standing check FR-009 asks for.
    """
    for op in operations():
        assert op.audit_disposition in AUDIT_DISPOSITIONS, (
            f"{op.tool_name} carries no valid audit disposition — decide whether it touches a "
            "run or a thread, and say so in the catalogue"
        )


def test_a_records_elsewhere_operation_must_name_where() -> None:
    """The rule that found the `stop_run` gap before implementation began.

    An earlier draft classified `stop_run` as `records_elsewhere`. Applying this rule — name
    where — is what revealed there was no where: it wrote nothing at all.
    """
    for op in operations():
        if op.audit_disposition == RECORDS_ELSEWHERE:
            assert op.audit_note.strip(), f"{op.tool_name} claims to be recorded but not where"

    with pytest.raises(ValueError, match="must name where"):
        McpOperation(
            tool_name="invented",
            method="GET",
            path="/invented",
            description="",
            input_schema={},
            audit_disposition=RECORDS_ELSEWHERE,
        )


def test_the_drivers_cover_every_recording_operation() -> None:
    """Guards the row below against the catalogue growing past it.

    Without this, an eighth `records` operation would ship uncovered and the coverage row would
    keep passing — which is precisely how `test_operations_audited.py` came to look like it
    covered this question while covering a different one.
    """
    assert set(DRIVERS) == _recorded_names()


def test_every_operation_claiming_to_record_actually_does() -> None:
    """**SC-003 / FR-011 — the row that would have failed before this feature.**

    Each operation the catalogue says records is driven through the real transport, and the
    trail is checked. Refusals count: FR-007 requires a refused read to record, so driving these
    against absent records still produces an entry — and an operation that produced none would
    be claiming coverage it does not have, which is the exact defect 022 exists to close.
    """
    for name in sorted(DRIVERS):
        surface = surface_under_test()
        subject = _subject(surface)
        before = {e.entry_hash for e in surface.audit.all_entries()}
        DRIVERS[name](surface, subject)
        written = [e for e in surface.audit.all_entries() if e.entry_hash not in before]

        # A read lands in the reader stream; an act on a run or thread lands on that object's
        # own stream (FR-005a). Either satisfies the claim; neither being present does not.
        assert any(
            e.event_type.value
            in {"record_read", "record_read_refused", "thread_created", "run_stopped"}
            for e in written
        ), (
            f"{name} is declared `records` and wrote nothing — the surface tells every client "
            "it is recorded, and it is not"
        )


def test_the_two_catalogue_operations_stay_unrecorded() -> None:
    """SC-011, a deliberate negative. **Do not delete this for looking like dead weight.**

    Agent definitions are configuration: reading one discloses how the platform is set up, not
    what anyone did with it. They are also the highest-frequency reads a connected client
    makes — an editor fetches them on every connect — and the trail is never sampled, so
    recording them would be a permanent cost for the least informative entries.

    Pinned so that widening coverage later is a decision someone makes rather than a drift.
    """
    assert {o.tool_name for o in operations() if o.audit_disposition == NO_RECORD} == {
        "list_agent_definitions",
        "get_agent_definition",
    }

    surface = surface_under_test()
    subject = _subject(surface)
    before = len(surface.audit.list_by_correlation_id(record_stream_for(subject.tenant_id)))
    surface.mcp.call("list_agent_definitions", {}, subject=subject)
    surface.mcp.call(
        "get_agent_definition", {"agent_definition_id": "planner-agent"}, subject=subject
    )
    after = len(surface.audit.list_by_correlation_id(record_stream_for(subject.tenant_id)))
    assert after == before


def test_the_governance_sentence_is_derived_from_the_dispositions() -> None:
    """FR-011. A sentence that could drift is a sentence that will.

    The surface's claim is generated from the catalogue, so it cannot assert coverage the
    catalogue does not declare. A row comparing the sentence to a second hand-written
    expectation would have passed every day the original gap existed — keeping the two in sync
    is the thing that failed.
    """
    sentence = governance_sentence()
    for name in _recorded_names():
        assert name in sentence
    for op in operations():
        if op.audit_disposition == NO_RECORD:
            assert op.tool_name in sentence, "the sentence must state what it does NOT record"
    assert str(len(_recorded_names())) in sentence
    assert str(len(operations())) in sentence
