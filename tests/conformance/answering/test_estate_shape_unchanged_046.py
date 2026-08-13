# SPDX-License-Identifier: Apache-2.0
"""046 Q2-B — estate answered payloads are not required to carry primary_answer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.answering.scope import visible_event_types
from core.audit.schema import AuditEntry, AuditEventType
from core.identity.types import AuthenticatedSubject, SubjectKind
from surfaces.api.ask import estate_answer_for
from tests.harness.api_fixtures import surface_under_test

QUESTION = "What is recorded for this estate?"


class _CitesFirst:
    def answer(self, question: str, records: tuple[AuditEntry, ...]) -> list[dict[str, Any]]:
        return [
            {
                "statement": "A run was recorded.",
                "references": [{"entry_hash": records[0].entry_hash}],
            }
        ]


def test_estate_answered_payload_keeps_claims_without_requiring_primary_answer() -> None:
    surface = surface_under_test()
    surface.audit.append_event(
        correlation_id="estate-run-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice", "outcome": "recorded"},
    )
    subject = AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id="tenant-test",
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    body = estate_answer_for(
        question=QUESTION,
        subject=subject,
        query=surface.evidence,
        audit=surface.audit,
        model="anthropic/claude-opus@5",
        provider=_CitesFirst(),
        now=datetime(2026, 8, 2, 12, tzinfo=UTC),
    )

    assert body["source"] == "estate"
    assert body["disposition"] == "answered"
    assert "claims" in body
    assert "primary_answer" not in body
    # Sanity: the claim rests on a type the operator may see.
    assert AuditEventType.RUN_START in visible_event_types(subject.roles)
