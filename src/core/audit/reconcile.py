# SPDX-License-Identifier: Apache-2.0
"""Comparing the two copies, and naming what differs (ADR-0055, 015).

A second copy nobody compares is storage, not evidence. This is the comparison, and ADR-0055
requires it be a **named operation** rather than an implied capability — something an
operator invokes, an investigator points at, and the trail records.

What each mechanism catches, because they are not interchangeable and the local ones were
never enough:

- **The chain** catches modification and middle-deletion, locally. Both break the ``seq``
  sequence or the ``prev_hash`` link.
- **The local head** catches truncation, which the chain cannot — but it lives in the same
  database as the entries, so an actor who can rewrite one can rewrite both consistently.
  That is the gap this feature exists to close, and it is why the head is *shipped*.
- **The shipped head observations** catch that consistent rewrite. Each is the platform's own
  earlier claim about how long a stream was; a local head found below one is truncation
  proven by the platform's own statement, needing no inference about shipping lag.

The verdicts are deliberately narrow about what they assert. Reconciliation reports that the
copies **differ**, never which one is honest — an attacker who compromises both
administrative domains defeats this, and ADR-0055 says so itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from core.audit.chain import canonical_bytes, canonical_entry_dict, verify_chain
from core.audit.egress import PROBE_STREAM, AuditDestination, backlog_depth
from core.audit.postgres_sink import _row_to_entry
from core.audit.schema import AuditEventType

Posture = Literal["in_force", "absent", "unverified", "non_compliant"]


@dataclass
class ReconcileFinding:
    """One divergence, located.

    Carries stream and sequence and **never payload content** (FR-019). A finding that
    quoted an entry would turn the report — and the audit event summarising it — into an
    ungoverned read of tenant evidence, which is precisely what this feature is protecting.
    """

    correlation_id: str
    kind: str
    detail: str
    seq: int | None = None


@dataclass
class ReconcileReport:
    streams_checked: int = 0
    findings: list[ReconcileFinding] = field(default_factory=list)
    #: Entries owed to the destination and not yet confirmed. Lag, not divergence.
    backlog: int = 0
    #: When the second copy's attestation begins (FR-017). ``None`` when nothing has shipped.
    #: Entries written before egress was configured do ship on the first drain, but what the
    #: destination attests is the store's state at import time, not its history before that.
    coverage_since: datetime | None = None
    destination_verified: str = "unverified"
    posture: Posture = "absent"

    @property
    def ok(self) -> bool:
        return not self.findings


def reconcile(
    *,
    local: Any,
    destination: AuditDestination | None,
    only: set[str] | None = None,
) -> ReconcileReport:
    """Compare every stream's two copies and report what differs.

    ``local`` is a connection under the **run** role: the evidence role holds no grant on
    ``audit_stream_heads``, which makes it the wrong credential for a check that must read
    the local head.

    ``destination`` of ``None`` is not an error — it is the ABSENT posture (FR-009). An
    estate with no second copy has no tamper-evidence, and reporting that plainly is better
    than a default that reads as protected.
    """
    report = ReconcileReport()

    if destination is None:
        report.posture = "absent"
        report.backlog = backlog_depth(local)
        return report

    report.destination_verified = destination.probe()
    report.coverage_since = destination.coverage_start()
    report.backlog = backlog_depth(local)
    # Only a passing probe permits the claim. `unverified` and `non_compliant` each report as
    # themselves, and neither says tamper-evidence is in force (FR-020b) — a control the
    # platform has not exercised must not read as one it has.
    verification = report.destination_verified
    report.posture = "in_force" if verification == "verified" else _posture_of(verification)

    for correlation_id, local_head, watermark in _streams(local, only):
        report.streams_checked += 1
        local_entries = _local_entries(local, correlation_id)
        shipped = destination.read_entries(correlation_id)
        observations = destination.read_head_observations(correlation_id)
        shipped_by_seq = {entry.seq: entry for entry in shipped}

        # ---- the destination's copy must stand on its own (SC-002)
        if shipped:
            try:
                verify_chain(shipped)
            except ValueError as exc:
                report.findings.append(
                    ReconcileFinding(correlation_id, "destination_chain_broken", str(exc))
                )

        # ---- entry-for-entry, over what the destination has confirmed
        for entry in local_entries:
            counterpart = shipped_by_seq.get(entry.seq)
            if counterpart is None:
                # Above the watermark this is LAG, not loss: the shipper has not reached it
                # yet, and calling that divergence would cry wolf on every concurrent run
                # (FR-013, SC-008). At or below the watermark the entry was confirmed
                # delivered and is now absent, which is a different claim entirely.
                if entry.seq <= watermark:
                    report.findings.append(
                        ReconcileFinding(
                            correlation_id,
                            "missing_at_destination",
                            f"confirmed shipped to seq {watermark} but seq {entry.seq} is absent",
                            seq=entry.seq,
                        )
                    )
                continue
            if _differs(entry, counterpart):
                # One copy was rewritten. Which one is a question this cannot answer and does
                # not pretend to (SC-003).
                report.findings.append(
                    ReconcileFinding(
                        correlation_id,
                        "entry_mismatch",
                        "the two copies disagree at this position",
                        seq=entry.seq,
                    )
                )

        # ---- truncation, witnessed by the platform's own earlier claims (SC-004)
        report.findings.extend(
            _truncation_findings(correlation_id, local_head, local_entries, shipped, observations)
        )

    return report


def _differs(local: Any, shipped: Any) -> bool:
    """Do these two copies of one entry disagree, in content or in claim?

    **Not a comparison of the two ``entry_hash`` columns.** That column is an assertion made
    by whoever wrote the row, and the local writer here is the threat actor: an administrator
    who rewrites a payload and leaves the hash column alone produces two records that agree
    on their claims and disagree on their contents. Comparing the claims would have called
    that identical. A conformance row caught exactly this.

    So both are compared, because they fail differently:

    - **Content** — the canonical bytes over every hashed field. Catches a rewrite of the
      evidence itself, whatever the hash column was left saying about it.
    - **The stored claim** — catches a rewrite of the hash alone, where the content still
      matches but one copy now attests to something else.
    """
    return _content_of(local) != _content_of(shipped) or local.entry_hash != shipped.entry_hash


def _content_of(entry: Any) -> bytes:
    return canonical_bytes(
        canonical_entry_dict(
            correlation_id=entry.correlation_id,
            tenant_id=entry.tenant_id,
            seq=entry.seq,
            event_type=str(entry.event_type),
            timestamp=entry.timestamp,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
        )
    )


def _posture_of(verification: str) -> Posture:
    """A failed or absent verification reports as itself, never as protection."""
    if verification == "non_compliant":
        return "non_compliant"
    return "unverified"


def _truncation_findings(
    correlation_id: str,
    local_head: int,
    local_entries: list[Any],
    shipped: list[Any],
    observations: list[Any],
) -> list[ReconcileFinding]:
    """Detect a local trail cut short, using the destination as the witness.

    The attack this exists for is the *consistent* rewrite: delete the newest local entries
    AND lower the local head to match. Locally that verifies perfectly — the chain is intact
    and the head agrees with it — which is the whole reason the head is shipped.
    """
    findings: list[ReconcileFinding] = []
    highest_observed = max((o.highest_seq for o in observations), default=None)

    if highest_observed is not None and local_head < highest_observed:
        findings.append(
            ReconcileFinding(
                correlation_id,
                "local_truncated",
                f"the platform previously observed this stream at seq {highest_observed}; "
                f"the local head now reports {local_head}",
                seq=highest_observed,
            )
        )
        return findings

    # The same truncation seen from the entries rather than the heads. Kept as a second
    # signal because a head observation can be missing — an outage between shipping entries
    # and shipping the claim — and losing detection to that gap would be losing it exactly
    # when the store was under stress.
    highest_shipped = max((entry.seq for entry in shipped), default=None)
    local_max = max((entry.seq for entry in local_entries), default=-1)
    if highest_shipped is not None and local_max < highest_shipped:
        findings.append(
            ReconcileFinding(
                correlation_id,
                "local_truncated",
                f"the destination holds seq {highest_shipped}; the local trail ends at {local_max}",
                seq=highest_shipped,
            )
        )

    return findings


def _streams(local: Any, only: set[str] | None) -> list[tuple[str, int, int]]:
    """Every stream, with its local head and its confirmed watermark."""
    cursor = local.cursor()
    try:
        cursor.execute(
            """
            SELECT h.correlation_id, h.highest_seq, COALESCE(w.shipped_seq, -1)
            FROM audit_stream_heads h
            LEFT JOIN audit_egress_watermarks w ON w.correlation_id = h.correlation_id
            ORDER BY h.correlation_id
            """
        )
        rows = [(str(r[0]), int(r[1]), int(r[2])) for r in cursor.fetchall()]
    finally:
        cursor.close()
    # The probe stream is platform-internal scaffolding, deliberately tampered with by
    # `probe()`. Reconciling it would report the platform's own test as a finding.
    rows = [row for row in rows if row[0] != PROBE_STREAM]
    if only is not None:
        rows = [row for row in rows if row[0] in only]
    return rows


def _local_entries(local: Any, correlation_id: str) -> list[Any]:
    cursor = local.cursor()
    try:
        cursor.execute(
            "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
            "       prev_hash, entry_hash "
            "FROM audit_entries WHERE correlation_id = %s ORDER BY seq",
            (correlation_id,),
        )
        return [_row_to_entry(r) for r in cursor.fetchall()]
    finally:
        cursor.close()


def findings_by_kind(report: ReconcileReport) -> dict[str, int]:
    """Counts per kind, for the audit payload — counts, never contents."""
    counts: dict[str, int] = {}
    for finding in report.findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    return counts


__all__ = [
    "Posture",
    "emit_reconciled",
    "ReconcileFinding",
    "ReconcileReport",
    "findings_by_kind",
    "reconcile",
]


def emit_reconciled(sink: Any, report: ReconcileReport, *, basis: str, caller: str) -> None:
    """Record that the two copies were compared, and what came of it.

    ADR-0035 makes reading evidence an audited act, and reconciliation is the most
    evidence-reading thing this platform does — it reads both copies of everything. So the
    check leaves its own trace, naming who asked and on what basis.

    **Counts and locations, never contents.** The payload carries findings by kind and a
    coverage boundary; it never carries a payload from either copy. An audit event that
    quoted the evidence it had just read would be an ungoverned read path wearing an audit
    event's clothes — and this event exists precisely because reads are governed.

    Failures to emit are swallowed deliberately, and only here. Everywhere else in this
    feature an unrecorded thing is a defect; but a reconciliation that FOUND divergence and
    then could not write its own event must still have reported that divergence to stderr,
    which it has by the time this is called. Losing the summary is bad; losing the finding
    because the summary failed would be worse.
    """
    if sink is None:
        return
    try:
        sink.append_event(
            correlation_id=f"audit-reconcile-{basis}",
            tenant_id="__platform__",
            event_type=AuditEventType.AUDIT_RECONCILED,
            payload={
                "basis": basis,
                "caller": caller,
                "streams_checked": report.streams_checked,
                "findings": findings_by_kind(report),
                "finding_count": len(report.findings),
                "backlog": report.backlog,
                "coverage_since": (
                    report.coverage_since.isoformat() if report.coverage_since else None
                ),
                "destination_verified": report.destination_verified,
                "posture": report.posture,
            },
        )
    except Exception:  # noqa: BLE001 — see the docstring; the findings are already reported
        pass
