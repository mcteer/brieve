# SPDX-License-Identifier: Apache-2.0
"""The report, as a governed read plus a compilation.

**Nothing here reads the evidence plane directly.** It calls `read_evidence_for`, which bounds by
the subject's tenant, computes the SCOPED/OUT_OF_SCOPE disposition, and fails the read if its own
meta-audit write fails. A second caller of `EvidenceQuery.search` would be a second answer to
"who may see this", arriving one layer below where the parity row looks.

**`report_for` is transport-independent** for the reason `read_evidence_for`'s docstring already
gives: ADR-0033 asks for the same verdict on every transport, and two implementations agreeing by
inspection would make that a measure of how carefully they were written.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from core.audit.schema import EvidenceDisposition
from core.reports import Claim, ReportBasis, RunReport, compile_report, validate
from surfaces.api.dependencies import AuditDep, EvidenceDep, SubjectDep
from surfaces.api.evidence import read_evidence_for

#: How many entries a report may compile from.
#:
#: **A correctness bound wearing a performance bound's clothes.** `EvidenceQueryRequest.limit`
#: defaults to 1000 and a 400-step dispatched run writes roughly seven entries per step — so a
#: report over a long run would compile from a *truncated* read and describe a run it had only
#: partly seen, in a document that reads complete. Raised well above any run this platform
#: produces, and `truncated` below is what happens when even that is not enough.
REPORT_ENTRY_LIMIT = 100_000


class ReportResponse(BaseModel):
    """A compiled report, and whether it saw the whole run."""

    model_config = ConfigDict(extra="forbid")

    report: RunReport
    #: **True means the report is incomplete and says so.** A truncated compilation is not a
    #: slow report, it is a wrong one — so it is surfaced rather than logged.
    truncated: bool = False


def report_for(
    *,
    run_id: str,
    subject: Any,
    query: Any,
    audit: Any,
    observers: frozenset[str] = frozenset(),
    terminal: bool = True,
) -> ReportResponse:
    """Compile the report for one run, through the governed read.

    **Grants no access the caller does not already have.** Every claim compiles from entries
    `read_evidence` would have returned to this same subject — the compiler holds no query, so
    there is no path by which it could see more.

    **Carries no part of the run's result payload** (FR-008a). `get_run_result` restricts that to
    the subject who started the run; a report is tenant-scoped, so including it would route
    around the restriction. Nothing here reads a checkpoint, which is how that stays true.
    """
    entries, disposition = read_evidence_for(
        query=query,
        audit=audit,
        subject=subject,
        run_id=run_id,
        limit=REPORT_ENTRY_LIMIT,
    )

    if disposition is EvidenceDisposition.OUT_OF_SCOPE or not entries:
        # A run in another tenant and a run that does not exist answer identically — the caller
        # must not learn which, because telling them leaks the existence of what they may not
        # see. An empty report rather than an error, for the same reason the evidence read
        # returns zero rows rather than a refusal.
        return ReportResponse(report=_empty(run_id))

    truncated = len(entries) >= REPORT_ENTRY_LIMIT
    report = compile_report(
        entries,
        run_id=run_id,
        observers=observers,
        terminal=terminal,
        basis=ReportBasis(chain_verified=False, reconciled=None),
    )
    report = validate(report, entries)

    if truncated:
        # Stated in the report itself, not only in a field beside it. Whoever forwards this
        # document forwards the caveat with it, which a response-envelope flag would not
        # survive.
        report = report.model_copy(
            update={
                "claims": (
                    *report.claims,
                    Claim(
                        subject="report",
                        statement=(
                            f"this report compiled from the first {REPORT_ENTRY_LIMIT} records "
                            f"of a longer run and does not describe all of it"
                        ),
                        status=report.claims[0].status.UNRECONCILED,
                        evidence=(f"{run_id}#truncated",),
                    ),
                )
            }
        )

    return ReportResponse(report=report, truncated=truncated)


def _empty(run_id: str) -> RunReport:
    """What a caller gets for a run they may not see, or one that does not exist."""
    return RunReport(run_id=run_id, disposition="unknown", claims=(), scope="")


def build_router() -> APIRouter:
    router = APIRouter(tags=["reports"])

    @router.get("/runs/{run_id}/report", response_model=ReportResponse)
    def get_run_report(
        run_id: str,
        subject: SubjectDep,
        query: EvidenceDep,
        audit: AuditDep,
    ) -> ReportResponse:
        # A thin binding onto the shared implementation, so MCP reaches the same function
        # rather than a second one that agrees by inspection.
        return report_for(run_id=run_id, subject=subject, query=query, audit=audit)

    return router


__all__ = ["REPORT_ENTRY_LIMIT", "ReportResponse", "build_router", "report_for"]
