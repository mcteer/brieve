# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the report as a governed operation (021, FR-007/FR-008).

A report is the widest-aperture read in the platform: it compiles everything a run recorded.
These rows assert it grants **no** access beyond what the evidence path already does, and that
the one thing scoped differently — the run's result payload — never comes with it.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from surfaces.api.reports import REPORT_ENTRY_LIMIT, report_for
from tests.harness.api_fixtures import surface_under_test


def _client(surface: Any) -> TestClient:
    return TestClient(surface.app)


def test_compiling_a_report_is_itself_audited() -> None:
    """FR-007 — a report is a privileged read of the audit plane, and reads are audited.

    It reaches `read_evidence_for` rather than the query directly, so the meta-audit record comes
    for free — and, more to the point, **cannot be skipped**: that function fails the read when
    its own append fails, which a hand-built query would silently not do.
    """
    surface = surface_under_test()
    client = _client(surface)
    before = len(surface.audit._entries)

    response = client.get("/runs/whatever/report", headers=surface.bearer())
    assert response.status_code == 200

    entries = surface.audit._entries
    assert len(entries) > before, "compiling a report wrote no meta-audit record"
    assert any(
        e.event_type in {AuditEventType.EVIDENCE_READ, AuditEventType.EVIDENCE_READ_REFUSED}
        for e in entries
    ), "a report was compiled and no evidence read was recorded; the read went around the path"


def test_a_run_that_does_not_exist_answers_as_one_you_may_not_see() -> None:
    """FR-008, SC-005 — indistinguishable, including reason code and message.

    The evidence path already holds this property and the report inherits it by construction:
    both cases return the same empty report rather than an error, because an error would tell a
    caller which of the two they hit.
    """
    surface = surface_under_test()
    client = _client(surface)
    headers = surface.bearer()

    absent = client.get("/runs/no-such-run-at-all/report", headers=headers)
    other = client.get("/runs/belongs-to-another-tenant/report", headers=headers)

    assert absent.status_code == other.status_code == 200
    absent_body = absent.json()
    other_body = other.json()
    assert absent_body["report"]["claims"] == other_body["report"]["claims"] == []
    assert absent_body["report"]["disposition"] == other_body["report"]["disposition"], (
        "a nonexistent run and one in another tenant report different dispositions — that "
        "difference tells a caller which they hit, which is what FR-008 forbids"
    )


def test_a_report_carries_no_run_result_payload() -> None:
    """FR-008a, SC-005a — the leak analysis found by asking who may request a report.

    `get_run_result` is **subject-restricted**: a run's output is a work product. A report is
    **tenant-scoped**: the trail is a governance record. So a report carrying the result payload
    would route straight around the narrower rule, and it is the first artifact in this platform
    able to do that.

    Asserted structurally rather than by string search: the response model has no field for it,
    so there is nowhere for it to go.
    """
    from surfaces.api.reports import ReportResponse

    fields = set(ReportResponse.model_fields)
    assert fields == {"report", "truncated"}, (
        f"the report response grew a field: {fields}. Anything carrying run output here routes "
        f"around get_run_result's subject restriction."
    )

    from core.reports import RunReport

    report_fields = set(RunReport.model_fields)
    assert "result" not in report_fields and "payload" not in report_fields, (
        f"RunReport carries {report_fields}; a result or payload field is the subject-restricted "
        f"work product arriving under the tenant-scoped record's rules"
    )


def test_a_report_grants_no_access_the_evidence_path_would_not() -> None:
    """FR-008b — a compilation of readable records, not a new privilege.

    The compiler receives entries from `read_evidence_for` and holds no query, so it cannot see
    more by construction. This asserts the wiring actually goes that way — a `report_for` that
    reached the query directly would still pass every other row here.
    """
    import ast
    import pathlib

    source = pathlib.Path("src/surfaces/api/reports.py").read_text()
    tree = ast.parse(source)
    calls = {
        getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "read_evidence_for" in calls, (
        "the report route does not go through the governed read; it has its own path to the "
        "evidence plane, which is a second answer to who may see this"
    )
    assert "search" not in calls, (
        "the report route calls EvidenceQuery.search directly, skipping the tenant bounding, "
        "the disposition, and the meta-audit write that must not be best-effort"
    )


def test_the_entry_limit_is_above_any_run_this_platform_produces() -> None:
    """T043 — a correctness problem wearing a performance problem's clothes.

    `EvidenceQueryRequest.limit` defaults to **1000**, and a 400-step dispatched run writes
    roughly seven entries per step. A report compiled from a truncated read describes a run it
    only partly saw, **in a document that reads complete** — which is the one failure a reader
    cannot detect.

    The bound is raised well past that, and a compilation that still hits it says so in the
    report rather than in a log.
    """
    assert REPORT_ENTRY_LIMIT >= 10_000, (
        f"the report entry limit is {REPORT_ENTRY_LIMIT}; the durability fixtures alone dispatch "
        f"400-step runs at roughly seven entries per step"
    )


def test_a_truncated_report_says_so_in_the_report() -> None:
    """The caveat travels with the document, not beside it.

    A flag on the response envelope is lost the moment somebody copies the report into a change
    record — which is precisely what ADR-0018 says reports get used for. So the truncation is a
    claim inside the report, carrying the status that says it could not be reconciled.
    """
    surface = surface_under_test()
    subject = surface.subject()

    class _Truncating:
        """A query that returns exactly the limit, which is what truncation looks like."""

        def search(self, request: Any) -> list[Any]:
            from tests.harness.recorded_runs import clean_run

            entries = clean_run()
            return [entries[i % len(entries)] for i in range(REPORT_ENTRY_LIMIT)]

    response = report_for(
        run_id="long-run",
        subject=subject,
        query=_Truncating(),
        audit=surface.audit,
    )
    assert response.truncated, "a compilation at the limit did not report itself truncated"
    assert any("does not describe all of it" in c.statement for c in response.report.claims), (
        "the truncation is only on the envelope; a report copied into a change record would "
        "carry no sign that it describes part of a run"
    )
