# SPDX-License-Identifier: Apache-2.0
"""Shipping the trail to a copy the platform cannot alter (ADR-0055, 015).

**There is no spool, and that is the design rather than an omission.** ADR-0055 guessed "a
local durable spool the shipper drains" and labelled it a guess; the guess is right about
the shape and redundant about the storage. `audit_entries` is already durable, already
ordered, and already written inside the sink's transaction — a second copy of it in the same
database would be bytes rather than safety. What was actually missing is a bookmark, and
that is `audit_egress_watermarks`.

A spool on allocation disk would have been worse than redundant. Dispatched runs are
ephemeral by design (014), so an allocation-local buffer turns a scheduler kill into silent
evidence loss — the exact failure this feature exists to close.

The consequence worth stating plainly: **"durably captured for shipping" is the local
append**, so FR-014's fail-closed half is behaviour this platform already had. The hook
engine denies with `evidential_gap` when an audit append fails, and `start_governed_run`
refuses a run whose `AUTHORITY_ISSUED` could not be written. Nothing here re-implements
that; the rows assert it still holds.

The ordering that makes a crash safe is `ship → confirm → advance the watermark`, in that
order and never otherwise. A crash anywhere re-ships, and re-shipping changes nothing
because the destination's primary key lets the first write win. Advancing first would be the
classic outbox defect: the entries between the advance and the crash are never sent, and
nothing knows they are owed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from core.audit.schema import AuditEntry

#: A stream whose only purpose is to be tampered with.
#:
#: `probe()` must demonstrate that the platform's credential cannot alter what it shipped,
#: and the only honest demonstration is to *try*. Attempting that against tenant evidence
#: would mean a check that could damage the thing it protects — self-refuting, and FR-020c
#: forbids it in as many words. So the shipper seeds this stream and the probe aims there.
PROBE_STREAM = "__audit_egress_probe__"

#: What the probe concluded. Only `verified` permits a posture of "tamper-evidence in force".
DestinationVerification = Literal["verified", "non_compliant", "unverified"]


@dataclass(frozen=True)
class HeadObservation:
    """The platform's own claim about how long a stream was, at a moment.

    Shipped rather than an updatable row, so the *history* of claims survives. A local head
    later found below one of these is truncation proven by the platform's earlier statement,
    which needs no inference about shipping lag.
    """

    correlation_id: str
    highest_seq: int
    head_hash: str


@dataclass
class ShipOutcome:
    """What one pass did, so an operator sees it rather than inferring it."""

    shipped: int = 0
    streams: int = 0
    #: Entries known to be owed and not yet confirmed. FR-016 calls this observable, and it
    #: is a SECURITY signal rather than an ops nicety: the backlog is the window in which an
    #: entry exists in one place only, so a rising number is rising exposure.
    backlog: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


class AuditDestination(Protocol):
    """The second copy, from the platform's side of the administrative boundary.

    Deliberately narrow. The platform appends and reads; it cannot update or delete, and
    there is no method here that would let it — a seam that offered one would be a seam
    inviting a destination that granted it.
    """

    def ship_entries(self, entries: list[AuditEntry]) -> int:
        """Append entries. Idempotent: re-shipping an already-present position is a no-op."""
        ...

    def ship_head_observation(self, observation: HeadObservation) -> None:
        """Append the platform's claim about a stream's length."""
        ...

    def read_entries(self, correlation_id: str) -> list[AuditEntry]:
        """Read the second copy back, for reconciliation and independent verification."""
        ...

    def read_head_observations(self, correlation_id: str) -> list[HeadObservation]:
        """Every claim made about this stream, oldest first."""
        ...

    def probe(self) -> DestinationVerification:
        """Attempt to tamper, and require refusal.

        The mechanism that turns FR-020 from an assertion into an observation. An operator
        declaring the destination separately administered is a claim the platform has never
        tested — the same shape ADR-0055 rejected when it foreclosed object storage the
        enclave's own role can write, relocated into a config file.
        """
        ...

    def coverage_start(self) -> Any:
        """When the destination first received anything, or None.

        The range over which tamper-evidence actually holds (FR-017). Entries written before
        egress was configured DO ship on the first drain, but what the destination can attest
        is the store's state at import time — not its history before that. A report implying
        otherwise would be the overstated claim FR-018 forbids, one field over.
        """
        ...


def ship_pass(
    *,
    local: Any,
    destination: AuditDestination,
    limit_per_stream: int = 2000,
) -> ShipOutcome:
    """Drain every stream's unshipped tail to the destination.

    ``local`` is a connection to the platform's evidence store, held under the run role —
    the evidence role cannot read `audit_stream_heads` at all, which is deliberate and makes
    it the wrong credential for this.

    The worklist is `audit_stream_heads ⋈ audit_egress_watermarks`, and it is *exact* rather
    than approximate: the sink assigns positions under a row lock on the stream head, so
    per-stream `seq` is gapless and `seq > shipped_seq` is precisely the unshipped set. A
    global cursor over the table would race on commit order — position N+1 committing before
    N — and silently skip whatever was in flight.
    """
    outcome = ShipOutcome()
    cursor = local.cursor()
    try:
        cursor.execute(
            """
            SELECT h.correlation_id, h.highest_seq, h.head_hash,
                   COALESCE(w.shipped_seq, -1) AS shipped_seq
            FROM audit_stream_heads h
            LEFT JOIN audit_egress_watermarks w ON w.correlation_id = h.correlation_id
            WHERE h.highest_seq > COALESCE(w.shipped_seq, -1)
            ORDER BY h.correlation_id
            """
        )
        work = [(str(r[0]), int(r[1]), str(r[2]), int(r[3])) for r in cursor.fetchall()]
    finally:
        cursor.close()

    for correlation_id, highest_seq, head_hash, shipped_seq in work:
        outcome.streams += 1
        try:
            entries = _unshipped(local, correlation_id, shipped_seq, limit_per_stream)
            if entries:
                destination.ship_entries(entries)
            # The head observation goes AFTER its entries, so a crash between them leaves a
            # claim no larger than what has actually arrived. The reverse order would let the
            # destination hold a claim of length N with entries only to N-3, which reads as
            # truncation of a copy that was merely interrupted.
            destination.ship_head_observation(
                HeadObservation(
                    correlation_id=correlation_id,
                    highest_seq=highest_seq,
                    head_hash=head_hash,
                )
            )
            reached = entries[-1].seq if entries else shipped_seq
            _advance(local, correlation_id, reached)
            outcome.shipped += len(entries)
            # Anything the per-stream limit left behind is still owed, and saying so is the
            # difference between a bounded pass and a silent truncation of the worklist.
            outcome.backlog += max(0, highest_seq - reached)
        except Exception as exc:  # noqa: BLE001 — one bad stream must not strand the rest
            outcome.failures.append((correlation_id, f"{type(exc).__name__}: {exc}"))
            outcome.backlog += max(0, highest_seq - shipped_seq)

    return outcome


def backlog_depth(local: Any) -> int:
    """How many entries exist in one place only (FR-016, SC-009).

    Read independently of a ship pass, because an operator asking "how exposed am I" should
    not have to trigger shipping to find out.
    """
    cursor = local.cursor()
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(h.highest_seq - COALESCE(w.shipped_seq, -1)), 0)
            FROM audit_stream_heads h
            LEFT JOIN audit_egress_watermarks w ON w.correlation_id = h.correlation_id
            WHERE h.highest_seq > COALESCE(w.shipped_seq, -1)
            """
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        cursor.close()


def _unshipped(local: Any, correlation_id: str, after_seq: int, limit: int) -> list[AuditEntry]:
    from core.audit.postgres_sink import _row_to_entry

    cursor = local.cursor()
    try:
        cursor.execute(
            "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
            "       prev_hash, entry_hash "
            "FROM audit_entries WHERE correlation_id = %s AND seq > %s "
            "ORDER BY seq LIMIT %s",
            (correlation_id, after_seq, limit),
        )
        return [_row_to_entry(r) for r in cursor.fetchall()]
    finally:
        cursor.close()


def _advance(local: Any, correlation_id: str, shipped_seq: int) -> None:
    """Record confirmed delivery — LAST, and never before.

    `GREATEST` rather than a plain assignment: a watermark must not move backwards, and two
    passes racing (or a re-ship of an older range) would otherwise reopen work already
    confirmed. Same monotonic reasoning as the revival count in 014's checkpoints.
    """
    cursor = local.cursor()
    try:
        cursor.execute(
            "INSERT INTO audit_egress_watermarks (correlation_id, shipped_seq) "
            "VALUES (%s, %s) "
            "ON CONFLICT (correlation_id) DO UPDATE "
            "SET shipped_seq = GREATEST(audit_egress_watermarks.shipped_seq, "
            "                           EXCLUDED.shipped_seq), "
            "    updated_at = now()",
            (correlation_id, shipped_seq),
        )
    finally:
        cursor.close()


__all__ = [
    "PROBE_STREAM",
    "AuditDestination",
    "DestinationVerification",
    "HeadObservation",
    "ShipOutcome",
    "backlog_depth",
    "ship_pass",
]
