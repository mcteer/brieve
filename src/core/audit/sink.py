# SPDX-License-Identifier: Apache-2.0
"""AuditSink protocol and in-memory implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash
from core.audit.schema import AuditEntry, AuditEventType
from core.errors import AuditChainError


class AuditSink(Protocol):
    def append(self, entry: AuditEntry) -> None: ...

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEntry]: ...


class InMemoryAuditSink:
    """Append-only in-memory sink with per-correlation-id hash chaining."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        existing = self.list_by_correlation_id(entry.correlation_id)
        expected_seq = len(existing)
        if entry.seq != expected_seq:
            raise AuditChainError(
                f"expected seq {expected_seq}, got {entry.seq}",
                correlation_id=entry.correlation_id,
            )
        expected_prev = GENESIS_PREV_HASH if expected_seq == 0 else existing[-1].entry_hash
        if entry.prev_hash != expected_prev:
            raise AuditChainError(
                "prev_hash does not match prior entry_hash",
                correlation_id=entry.correlation_id,
            )
        recomputed = compute_entry_hash(
            correlation_id=entry.correlation_id,
            seq=entry.seq,
            event_type=str(entry.event_type),
            timestamp=entry.timestamp,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
        )
        if recomputed != entry.entry_hash:
            raise AuditChainError(
                "entry_hash mismatch",
                correlation_id=entry.correlation_id,
            )
        self._entries.append(entry)

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEntry]:
        matched = [e for e in self._entries if e.correlation_id == correlation_id]
        return sorted(matched, key=lambda e: e.seq)

    def correlation_ids(self) -> set[str]:
        """Correlation IDs present in this sink."""
        return {e.correlation_id for e in self._entries}

    def all_entries(self) -> list[AuditEntry]:
        """All entries in append order (read-only copy)."""
        return list(self._entries)

    def build_entry(
        self,
        *,
        correlation_id: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        """Construct the next chained entry for a correlation ID (does not append)."""
        return build_next_entry(
            self,
            correlation_id=correlation_id,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
        )


def build_next_entry(
    sink: AuditSink,
    *,
    correlation_id: str,
    event_type: AuditEventType,
    payload: dict[str, Any],
    timestamp: datetime | None = None,
) -> AuditEntry:
    """Construct the next chained entry for a correlation ID (does not append)."""
    existing = sink.list_by_correlation_id(correlation_id)
    seq = len(existing)
    prev_hash = GENESIS_PREV_HASH if seq == 0 else existing[-1].entry_hash
    ts = timestamp if timestamp is not None else datetime.now(UTC)
    entry_hash = compute_entry_hash(
        correlation_id=correlation_id,
        seq=seq,
        event_type=str(event_type),
        timestamp=ts,
        payload=payload,
        prev_hash=prev_hash,
    )
    return AuditEntry(
        correlation_id=correlation_id,
        seq=seq,
        event_type=event_type,
        timestamp=ts,
        payload=payload,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
