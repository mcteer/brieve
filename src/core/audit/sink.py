# SPDX-License-Identifier: Apache-2.0
"""AuditSink protocol and in-memory implementation.

The write seam **assigns** a chain position rather than accepting one.

That is a change from 002, and the reason belongs here rather than only in a spec. The
original seam was ``append(entry)``, where the caller built a fully-formed entry — ``seq``,
``prev_hash``, ``entry_hash`` — through a ``build_next_entry`` helper that read the chain
first. That shape *is* read-then-write, and it was safe only because every correlation ID
had exactly one writer: a run, holding 005's single-writer lease. Nobody ever wrote that
coupling down.

The evidence-access stream (008) broke it. One stream per tenant, one writer per reader, so
two concurrent readers would compute the same position and one would lose. A store that
assigns position inside its own transaction cannot honour ``append(entry)``: handed a
position it did not choose, it can only verify it — the race returns — or overwrite it,
stranding the caller's ``entry_hash``.

So ``append_event`` assigns and returns what it stored, and ``build_next_entry`` is gone
rather than kept alongside. A second write path computing position outside the store would
leave the race reachable through the older, more familiar function.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash
from core.audit.schema import AuditEntry, AuditEventType


class AuditSink(Protocol):
    def append_event(
        self,
        *,
        correlation_id: str,
        tenant_id: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        """Assign the next chain position, store the entry, and return what was stored."""
        ...

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEntry]: ...


class InMemoryAuditSink:
    """Append-only in-memory sink with per-correlation-id hash chaining.

    Single-process and therefore trivially serialized. The Postgres sink has to work for
    the equivalent guarantee — see :mod:`core.audit.postgres_sink`.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append_event(
        self,
        *,
        correlation_id: str,
        tenant_id: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        existing = self.list_by_correlation_id(correlation_id)
        seq = len(existing)
        prev_hash = GENESIS_PREV_HASH if seq == 0 else existing[-1].entry_hash
        ts = timestamp if timestamp is not None else datetime.now(UTC)
        entry = AuditEntry(
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            seq=seq,
            event_type=event_type,
            timestamp=ts,
            payload=payload,
            prev_hash=prev_hash,
            entry_hash=compute_entry_hash(
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                seq=seq,
                event_type=str(event_type),
                timestamp=ts,
                payload=payload,
                prev_hash=prev_hash,
            ),
        )
        self._entries.append(entry)
        return entry

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEntry]:
        matched = [e for e in self._entries if e.correlation_id == correlation_id]
        return sorted(matched, key=lambda e: e.seq)

    def correlation_ids(self) -> set[str]:
        """Correlation IDs present in this sink."""
        return {e.correlation_id for e in self._entries}

    def all_entries(self) -> list[AuditEntry]:
        """All entries in append order (read-only copy)."""
        return list(self._entries)
