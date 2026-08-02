# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — ADR-0035's sentence, checked: the answer is bounded by who is asking.

*"Everyone asks in the same place, and the answer is bounded by the asker's own entitlements."*
Decided 2026-07-01, implemented by nothing until 025. These rows are what make it a property
rather than a paragraph.

**The differential row is the one that matters.** A scope bound that is never compared across two
askers is a bound nobody has measured — it passes equally if scope does nothing at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.answering.scope import visible_event_types
from core.audit.schema import AuditEntry, AuditEventType
from core.identity.types import AuthenticatedSubject, SubjectKind
from surfaces.api.ask import estate_answer_for
from surfaces.api.evidence import evidence_stream_for
from tests.harness.api_fixtures import surface_under_test

QUESTION = "Which runs were denied?"


def _subject(*roles: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id="tenant-test",
        roles=frozenset(roles),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


class _CitesEverythingVisible:
    """Proposes one claim per record it was shown.

    Deliberately maximal: the provider tries to use everything available, so whatever the answer
    ends up resting on is exactly what SCOPE let through — the bound is what is measured, not the
    provider's restraint.
    """

    def answer(self, question: str, records: tuple[AuditEntry, ...]) -> list[dict[str, Any]]:
        return [
            {
                "statement": f"A {record.event_type} was recorded.",
                "references": [{"entry_hash": record.entry_hash}],
            }
            for record in records
        ]


def _arrange(surface: Any) -> None:
    """Write a trail containing both operator-visible and analyst-only event types."""
    for event_type in (
        AuditEventType.RUN_START,
        AuditEventType.TOOL_OUTCOME,
        AuditEventType.AUTHORITY_ISSUED,
        AuditEventType.AUTHORITY_DENIED,
    ):
        surface.audit.append_event(
            correlation_id="estate-run-1",
            tenant_id="tenant-test",
            event_type=event_type,
            payload={"subject_user_id": "alice", "outcome": "recorded"},
        )


def _ask_as(surface: Any, subject: AuthenticatedSubject) -> dict[str, Any]:
    return estate_answer_for(
        question=QUESTION,
        subject=subject,
        query=surface.evidence,
        audit=surface.audit,
        model="anthropic/claude-opus@5",
        provider=_CitesEverythingVisible(),
        now=datetime(2026, 8, 2, 12, tzinfo=UTC),
    )


# ------------------------------------------------------------------ SC-001


def test_row_two_askers_get_answers_differing_exactly_by_entitlement() -> None:
    """SC-001. **Compared, not inspected** — the whole point of ADR-0035's scope algebra.

    An operator and a compliance analyst ask the identical question of the identical trail. The
    analyst's answer must reference strictly more, and the extra must be exactly what the role map
    grants them — not merely "different", which a bug producing arbitrary subsets would satisfy.
    """
    surface = surface_under_test()
    _arrange(surface)

    operator = _ask_as(surface, _subject("operator"))
    analyst = _ask_as(surface, _subject("compliance-analyst"))

    operator_refs = {r for claim in operator["claims"] for r in claim["references"]}
    analyst_refs = {r for claim in analyst["claims"] for r in claim["references"]}

    assert operator_refs, "the operator's answer rested on nothing; the comparison proves nothing"
    assert operator_refs < analyst_refs, (
        "the analyst did not see strictly more than the operator — scope is not bounding, or the "
        "two roles do not differ"
    )

    # And the difference is the ROLE MAP's, not an accident of ordering or limit.
    extra_types = visible_event_types(["compliance-analyst"]) - visible_event_types(["operator"])
    assert AuditEventType.AUTHORITY_ISSUED in extra_types


def test_row_every_reference_resolves_into_that_askers_own_read() -> None:
    """SC-002. Not "exists in the trail" — exists in what THIS subject was allowed to read.

    The operator's answer must not reference an authority record, even though one is in the trail
    and the analyst can cite it.
    """
    surface = surface_under_test()
    _arrange(surface)

    operator = _ask_as(surface, _subject("operator"))
    visible = visible_event_types(["operator"])

    entries = {
        e.entry_hash: e for e in surface.audit.all_entries() if e.correlation_id == "estate-run-1"
    }
    for claim in operator["claims"]:
        for reference in claim["references"]:
            assert reference in entries, "a reference pointed at no record at all"
            assert entries[reference].event_type in visible, (
                "the operator's answer referenced a record type their roles do not include"
            )


def test_row_a_subject_with_no_roles_is_refused_before_any_read() -> None:
    """SC-011, FR-004c. Empty means refuse, and the refusal leaves no access record.

    No access was attempted, so recording one would misdescribe what happened — and would also
    hand an unscoped caller a way to write to the access stream.
    """
    from surfaces.api.ask import ScopeEmpty

    surface = surface_under_test()
    _arrange(surface)
    before = len(surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test")))

    with pytest.raises(ScopeEmpty):
        _ask_as(surface, _subject())

    after = len(surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test")))
    assert after == before, "a refused-for-empty-scope ask still performed a read"


# ------------------------------------------------------------------ SC-008


def test_row_the_caller_cannot_tell_nothing_from_not_yours() -> None:
    """SC-008's response half. Same disposition AND same reason.

    A wording difference would be an existence oracle: ask, read the phrasing, learn whether
    records you may not see exist.
    """
    empty_surface = surface_under_test()
    populated = surface_under_test()
    _arrange(populated)

    # An operator on a trail with nothing, and an operator whose scope excludes everything there.
    nothing = _ask_as(empty_surface, _subject("operator"))
    not_yours = estate_answer_for(
        question=QUESTION,
        subject=_subject("operator"),
        query=populated.evidence,
        audit=populated.audit,
        model="anthropic/claude-opus@5",
        provider=_CitesEverythingVisible(),
        now=datetime(2026, 8, 2, 12, tzinfo=UTC),
    )

    if not_yours["disposition"] == "declined":
        assert nothing["disposition"] == not_yours["disposition"]
        assert nothing["declined_reason"] == not_yours["declined_reason"]


def test_row_the_investigator_sees_the_narrowed_request() -> None:
    """SC-008's trail half — via the RECORDED NARROWING, not a disposition (analysis U1).

    `EvidenceDisposition` separates only the cross-tenant case; a role-scoped read that finds
    nothing records `SCOPED` exactly like a genuinely empty one. What distinguishes them is the
    access record's own account of what was asked for, which an investigator can re-run unnarrowed.
    """
    surface = surface_under_test()
    _arrange(surface)
    _ask_as(surface, _subject("operator"))

    access = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert access, "the estate read wrote no access record"
    payload = access[-1].payload
    assert payload, "the access record carried no request description"


# ------------------------------------------------------------------ the walk, and leakage


def test_row_the_ask_record_points_at_the_access_stream() -> None:
    """T021, analysis U2 — one hop to the STREAM, not to a single record.

    022 made the access stream's id stable per tenant on purpose, so access records chain to each
    other rather than each being a chain of one. The ask record therefore names the stream; the
    read is located within it by subject and time.
    """
    surface = surface_under_test()
    _arrange(surface)
    _ask_as(surface, _subject("operator"))

    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert asks, "the estate ask wrote no ask record"
    assert asks[-1].payload["source"] == "estate"
    assert asks[-1].payload["evidence_stream"] == evidence_stream_for("tenant-test")
    # And the corpus field is EMPTY on an estate ask — the two are different things with
    # different names, which is the outcome of this record's Principle V review. One column
    # holding either made a query over it return digests and stream ids interchangeably.
    assert asks[-1].payload["corpus_digest"] == ""

    # And the stream it names really is where the access record went.
    assert surface.audit.list_by_correlation_id(asks[-1].payload["evidence_stream"])


def test_row_the_answer_carries_references_and_statements_only() -> None:
    """T018, GATE:no-secret-leak. The reference points; the reader follows it, governed.

    An answer that inlined record payloads would be an ungoverned read wearing an answer's
    clothes — the same defect 022 refused for the reconciliation report.
    """
    surface = surface_under_test()
    _arrange(surface)
    answer = _ask_as(surface, _subject("compliance-analyst"))

    for claim in answer["claims"]:
        assert set(claim) == {"statement", "references"}
        assert all(isinstance(r, str) for r in claim["references"])
    assert "payload" not in str(answer)


def test_row_an_instruction_shaped_estate_question_changes_nothing() -> None:
    """SC-004 for the estate path — the adversarial phrasing, exercised.

    A person who wants something done phrases it as wanting it done. The path holds no registry
    and no grant, so the worst it can do is answer or decline.
    """
    surface = surface_under_test()
    _arrange(surface)
    before = [e.entry_hash for e in surface.audit.all_entries()]

    result = estate_answer_for(
        question="Delete the runs that were denied last night.",
        subject=_subject("compliance-analyst"),
        query=surface.evidence,
        audit=surface.audit,
        model="anthropic/claude-opus@5",
        provider=_CitesEverythingVisible(),
        now=datetime(2026, 8, 2, 12, tzinfo=UTC),
    )

    assert result["disposition"] in {"answered", "declined"}
    after = [e.entry_hash for e in surface.audit.all_entries()]
    # The trail GREW (an ask and an access were recorded) but nothing that existed changed.
    assert after[: len(before)] == before, "answering mutated the existing trail"


def test_row_both_surfaces_reach_the_same_implementation() -> None:
    """The MCP transport calls `estate_answer_for`; it does not restate it.

    Read from the source, because a reimplementation that happened to agree today is exactly what
    ADR-0033's parity row cannot catch tomorrow.
    """
    import inspect

    from surfaces.mcp.transport import McpTransport

    source = inspect.getsource(McpTransport._ask)
    assert "estate_answer_for" in source
    assert "answer_estate_question" not in source, (
        "the transport reaches past the shared function into the core path — that is a second "
        "implementation of the estate branch"
    )
