# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — reconciliation as a NAMED operation (015, US3).

ADR-0055 asks for a named operation rather than an implied capability: something an
investigator points at, and something the trail records them pointing at. These cover the
surface half of that — who may ask, what comes back, and what is written down.

What they cannot cover is whether the comparison is *right*; that is the enclave's job, and
it is the enclave's job specifically because a hermetic double holds whatever second copy
the test hands it. The split is the same one `test_audit_egress.py` states.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.audit.reconcile import ReconcileFinding, ReconcileReport
from core.audit.schema import AuditEventType
from surfaces.api.evidence import evidence_stream_for
from tests.harness.api_fixtures import SurfaceUnderTest, surface_under_test


class DivergentReconciler:
    """A second copy that disagrees, so the report has something to carry."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def reconcile_stream(self, correlation_id: str) -> ReconcileReport:
        self.asked.append(correlation_id)
        return ReconcileReport(
            streams_checked=1,
            findings=[
                ReconcileFinding(
                    correlation_id, "entry_mismatch", "the two copies disagree at this position", 2
                )
            ],
            destination_verified="verified",
            posture="in_force",
        )


def _start_a_run(surface: SurfaceUnderTest, client: TestClient) -> str:
    body = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    ).json()
    return str(body["correlation_id"])


def test_the_operation_returns_the_comparison_for_a_stream_the_caller_may_read() -> None:
    reconciler = DivergentReconciler()
    surface = surface_under_test(reconciler=reconciler)
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    response = client.get(
        "/evidence/reconciliation",
        params={"correlation_id": correlation_id},
        headers=surface.bearer(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["posture"] == "in_force"
    assert body["posture_reason"], "the posture arrived without the sentence explaining it"
    assert [f["kind"] for f in body["findings"]] == ["entry_mismatch"]
    assert body["findings"][0]["seq"] == 2, "the finding did not locate the divergence"
    assert reconciler.asked == [correlation_id]


def test_a_caller_reaching_for_another_tenants_stream_is_refused_and_recorded() -> None:
    """SC-007 — and the refusal is the interesting event, not the empty result.

    Authorization here is the evidence path's, unchanged: the same query and the same
    disposition decide this that decide a read. A second answer to "who may see what" is
    exactly what Principle II forbids, and it is what a bespoke check here would be.
    """
    reconciler = DivergentReconciler()
    surface = surface_under_test(reconciler=reconciler)
    client = TestClient(surface.app)

    # A stream belonging to somebody else, in the store this caller queries. Written
    # directly rather than by running as another tenant, so the row turns on the scope
    # check rather than on token verification — a 401 here would pass while proving nothing
    # about whether the operation is bounded.
    surface.audit.append_event(
        correlation_id="someone-elses-run",
        tenant_id="tenant-other",
        event_type=AuditEventType.RUN_START,
        payload={},
    )

    response = client.get(
        "/evidence/reconciliation",
        params={"correlation_id": "someone-elses-run"},
        headers=surface.bearer(),
    )

    assert reconciler.asked == [], "a comparison ran for a caller outside the stream's tenant"
    # Indistinguishable from a clean stream to the CALLER — telling them which would leak
    # the existence of what they may not see. Distinguishable in the TRAIL, which is where
    # the difference matters.
    assert response.status_code == 200
    assert response.json()["findings"] == []

    refusals = [
        e
        for e in surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
        if e.event_type is AuditEventType.EVIDENCE_READ_REFUSED
    ]
    assert len(refusals) == 1, "the probe at another tenant's evidence went unrecorded"
    assert refusals[0].payload["subject_user_id"] == "alice"


def test_the_comparison_is_itself_audited_with_counts_and_never_contents() -> None:
    """ADR-0035 — reconciliation is the most evidence-reading thing this platform does.

    The payload carries findings by kind and a posture. It must not carry a payload from
    either copy: an audit event that quoted the evidence it had just read would be an
    ungoverned read path wearing an audit event's clothes, in the feature whose whole
    subject is that reads are governed.
    """
    surface = surface_under_test(reconciler=DivergentReconciler())
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    client.get(
        "/evidence/reconciliation",
        params={"correlation_id": correlation_id},
        headers=surface.bearer(),
    )

    reconciled = [
        e for e in surface.audit.all_entries() if e.event_type is AuditEventType.AUDIT_RECONCILED
    ]
    assert len(reconciled) == 1, "the comparison left no record of itself"
    payload: dict[str, Any] = reconciled[0].payload
    assert payload["basis"] == "on_demand", "the record does not distinguish who asked for it"
    assert payload["caller"] == "alice"
    assert payload["findings"] == {"entry_mismatch": 1}
    assert "detail" not in str(payload), "a finding's text reached the audit payload"


def test_an_estate_with_no_second_copy_answers_absent_rather_than_failing() -> None:
    """FR-009 — the route exists even when the answer is "you have no tamper-evidence".

    A route that vanished without a destination would answer the question by disappearing,
    which reads to a caller as "not supported here" rather than "not protected here".
    """
    surface = surface_under_test()  # no reconciler — an unconfigured estate
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    response = client.get(
        "/evidence/reconciliation",
        params={"correlation_id": correlation_id},
        headers=surface.bearer(),
    )

    assert response.status_code == 200
    assert response.json()["posture"] == "absent"


def test_both_transports_give_the_same_answer() -> None:
    """ADR-0033 — one authorization core, two front doors, and no third answer."""
    surface = surface_under_test(reconciler=DivergentReconciler())
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    api = client.get(
        "/evidence/reconciliation",
        params={"correlation_id": correlation_id},
        headers=surface.bearer(),
    ).json()
    mcp = surface.mcp.call(
        "reconcile_evidence", {"correlation_id": correlation_id}, subject=surface.subject()
    )

    assert mcp.payload["posture"] == api["posture"]
    assert [f["kind"] for f in mcp.payload["findings"]] == [f["kind"] for f in api["findings"]]
