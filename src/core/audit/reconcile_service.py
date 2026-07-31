# SPDX-License-Identifier: Apache-2.0
"""Reconciliation as something a caller can *ask for* (015, US3).

ADR-0055 requires the comparison be a **named operation** rather than an implied capability
— an investigator points at it, and the trail records that they did. `reconcile()` is the
comparison; this is the seam the surfaces reach it through, so neither surface has to know
about database credentials or destinations to offer it.

**Why the comparison runs under the platform's own credential, not the caller's.** It reads
`audit_stream_heads`, and the evidence role deliberately holds no grant there (008) — that
absence is what makes the read path append-only-by-grant rather than by convention, and
widening it to serve this operation would trade a structural property for a convenience.
So the operation authorizes as the caller and executes as the platform, which is the same
division `read_evidence_for` already draws: the subject decides what may be seen, the
service's credential does the seeing.
"""

from __future__ import annotations

from typing import Any, Protocol

from core.audit.egress import AuditDestination
from core.audit.reconcile import ReconcileReport, reconcile


class Reconciler(Protocol):
    """Compare one stream's two copies. One method, because that is the whole operation."""

    def reconcile_stream(self, correlation_id: str) -> ReconcileReport: ...


class PostgresReconciler:
    """The production seam: a run-role connection, and the second copy.

    ``destination`` of ``None`` is not a broken assembly — it is an estate with no second
    copy, and the report it produces says ``absent`` (FR-009). An operation that raised here
    would turn "you have no tamper-evidence" into "something went wrong", which is the less
    useful of the two answers by a wide margin.
    """

    def __init__(self, *, connection_factory: Any, destination: AuditDestination | None) -> None:
        self._connect = connection_factory
        self._destination = destination

    def reconcile_stream(self, correlation_id: str) -> ReconcileReport:
        conn = self._connect()
        try:
            return reconcile(local=conn, destination=self._destination, only={correlation_id})
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — a close failure must not mask the report
                pass


__all__ = ["PostgresReconciler", "Reconciler"]
