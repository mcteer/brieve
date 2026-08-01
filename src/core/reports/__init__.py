# SPDX-License-Identifier: Apache-2.0
"""Compiling a run's records into the artifact a person reads (ADR-0018, 021).

Reports are presentation; attestation rests on records. Nothing here is a source of truth, and
nothing in this platform may read a report to decide anything.

**The compiler holds no query and no credential.** It cannot widen scope and it cannot observe a
product — both by construction rather than by rule, which is the resolution of a Constitution
Check that failed on Principle IV.
"""

from __future__ import annotations

from core.reports.compile import REFUSED, RUNNING, SCOPE, compile_report, validate
from core.reports.report import EFFECT_STATUSES, Claim, ClaimStatus, ReportBasis, RunReport

__all__ = [
    "EFFECT_STATUSES",
    "REFUSED",
    "RUNNING",
    "SCOPE",
    "Claim",
    "ClaimStatus",
    "ReportBasis",
    "RunReport",
    "compile_report",
    "validate",
]
