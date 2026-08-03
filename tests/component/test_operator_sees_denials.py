# SPDX-License-Identifier: Apache-2.0
"""031's visibility decision, pinned: an operator sees their runs' refusals — and only those.

**The decision** (029 recorded it, 030 held it open, 031 answered it): what happened to *your*
runs is yours to ask about. `AUTHORITY_DENIED` and `AUTHORITY_REFUSED` join the operator's
visible set; `AUTHORITY_ISSUED`, `AUTHORITY_EXPIRED` and the grant/change records stay
analyst-only, because who-holds-what-authority is a different sensitivity than what-was-refused.

**Why exactly two, as a row rather than a diff**: the tempting future edit is "operators keep
asking about grants, just add ISSUED" — and that flattens the role split one type at a time.
This file makes the boundary a thing somebody has to argue with, not a list that accretes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from core.answering.scope import ROLE_VISIBILITY, visible_event_types
from core.audit.schema import AuditEventType
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

MODEL = "anthropic/claude-opus@5"


def test_operators_gained_exactly_the_two_refusal_types() -> None:
    """The boundary, stated as membership so an accretion is an argument here first."""
    operator = ROLE_VISIBILITY["operator"]

    assert AuditEventType.AUTHORITY_DENIED in operator
    assert AuditEventType.AUTHORITY_REFUSED in operator
    for still_hidden in (
        AuditEventType.AUTHORITY_ISSUED,
        AuditEventType.AUTHORITY_EXPIRED,
        AuditEventType.AUTHORITY_CHANGE_OBSERVED,
        AuditEventType.MIRRORING_DECISION,
        AuditEventType.EVIDENCE_READ,
        AuditEventType.RECORD_READ,
    ):
        assert still_hidden not in operator, (
            f"{still_hidden} became operator-visible; 031 granted refusals only — grants and "
            f"reads are a different sensitivity, and widening is an argument to have here"
        )


def test_the_analyst_still_sees_everything_the_operator_does_and_more() -> None:
    """The role split survives: analyst ⊇ operator, strictly."""
    operator = visible_event_types(frozenset({"operator"}))
    analyst = visible_event_types(frozenset({"compliance-analyst"}))

    assert operator < analyst


def test_an_operator_asking_about_denials_gets_an_answer_that_cites_them() -> None:
    """US4 end to end through the full ask path — the loop the demonstration closes.

    Before 031 this exact question declined for an operator, correctly, and the person whose run
    was refused had to find an analyst to see the refusal. Now the answer rests on the denial
    record their own run produced.
    """

    class _Cites:
        def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
            from core.answering.corpus import Corpus

            if isinstance(material, Corpus):
                return [{"statement": "From the corpus.", "citations": []}]
            denials = [r for r in material if r.event_type is AuditEventType.AUTHORITY_DENIED]
            if not denials:
                return []
            return [
                {
                    "statement": "A run was denied.",
                    "references": [{"entry_hash": denials[0].entry_hash}],
                }
            ]

    surface = surface_under_test(
        ask_provider=_Cites(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )
    surface.audit.append_event(
        correlation_id="run-demo-overreach",
        tenant_id="tenant-test",
        event_type=AuditEventType.AUTHORITY_DENIED,
        payload={"subject_user_id": "alice", "tool": "apply", "reason_code": "ceiling_exceeded"},
        timestamp=datetime.now(UTC) - timedelta(minutes=5),
    )
    denial_hash = surface.audit.all_entries()[-1].entry_hash

    page = TestClient(surface.app).post(
        "/ask", json={"question": "Which runs were denied?"}, headers=surface.bearer()
    )

    assert page.status_code == 200
    body = page.json()
    assert body["disposition"] == "answered", (
        f"an operator's denial question no longer answers: {body}"
    )
    cited = {ref for claim in body["claims"] for ref in claim["references"]}
    assert denial_hash in cited, "the answer does not rest on the denial record"


def test_the_estate_suite_agreement_row_needed_no_change() -> None:
    """Research F5's measured claim, asserted: the visibility change moved no case.

    A case's `asker_role` follows its expected set; no expected set changed, so the span
    ADR-0059 names — {operator, compliance-analyst} — is untouched. This row exists so that if
    somebody later retags cases *because* operators can now see denials, they meet the
    agreement machinery deliberately rather than discovering it.
    """
    from pathlib import Path

    from core.evals.suites import ESTATE_SUITES, load_pack_cases

    packs = Path(__file__).resolve().parents[2] / "packs"
    declared = {
        case.asker_role
        for pack in ("vault", "terraform")
        for suite in ESTATE_SUITES
        for case in load_pack_cases(packs / pack, suite)
    }
    assert declared == {"operator", "compliance-analyst"}
