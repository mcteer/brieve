# SPDX-License-Identifier: Apache-2.0
"""An in-memory evidence query over an in-memory sink.

For exercising the **surface's** scoping and meta-audit logic without an enclave. It
proves nothing about storage, and deliberately cannot: the mutation defence that matters
is a database grant, tested against a real Postgres in the enclave lane.

It applies the same tenant predicate the Postgres implementation does, first and
unconditionally, because a double that scoped more loosely than production would let a
leak pass here and appear only in the enclave.
"""

from __future__ import annotations

from core.audit.query import EvidenceQueryRequest
from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink


class InMemoryEvidenceQuery:
    def __init__(self, sink: InMemoryAuditSink) -> None:
        self._sink = sink

    def search(self, request: EvidenceQueryRequest) -> list[AuditEntry]:
        entries = [e for e in self._sink.all_entries() if e.tenant_id == request.tenant_id]
        narrowed = request.correlation_id or request.run_id
        if narrowed is not None:
            entries = [e for e in entries if e.correlation_id == narrowed]
        if request.start_time is not None:
            entries = [e for e in entries if e.timestamp >= request.start_time]
        if request.end_time is not None:
            entries = [e for e in entries if e.timestamp <= request.end_time]
        # `is not None`, NEVER truthiness. An EMPTY set means "no type is visible to this
        # caller" and must match nothing; truthiness would read it as "no filter" and return
        # everything — the exact inversion of a scope bound, and the shape a scoping bug takes.
        # `None` is the absence of a filter and remains today's unnarrowed read.
        if request.event_types is not None:
            entries = [e for e in entries if e.event_type in request.event_types]
        entries.sort(key=lambda e: (e.timestamp, e.correlation_id, e.seq))
        # THE NEWEST WINDOW, RETURNED OLDEST-FIRST — and the slice is the whole fix.
        #
        # This was `entries[: request.limit]`: the OLDEST `limit` records. Measured on a real
        # tenant, 236,581 entries readable by one role against a limit of 1,000, which meant every
        # question about recent activity was answered from evidence three days stale.
        #
        # **It does not fix "which runs were denied?"** — denials are outside the `operator`
        # role's scope entirely, so that question is unanswerable for that role at any limit.
        # Noted because a wrong causal story in a comment outlives the person who wrote it.
        #
        # **The output order is unchanged.** Callers still receive ascending entries; what changed
        # is which window they receive when the limit truncates.
        return entries[-request.limit :] if request.limit else []

    def exists_outside_tenant(self, *, correlation_id: str, tenant_id: str) -> bool:
        return any(
            e.correlation_id == correlation_id and e.tenant_id != tenant_id
            for e in self._sink.all_entries()
        )
