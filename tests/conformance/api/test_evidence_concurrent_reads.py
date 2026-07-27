# SPDX-License-Identifier: Apache-2.0
"""Row: concurrent readers in one tenant are all recorded (FR-010c, SC-009b).

The evidence-access stream is shared by every reader in a tenant, so it has one writer per
reader — unlike a run chain, which 005's lease guarantees has exactly one. The naive
implementation reads the chain, computes the next position, then inserts, and loses a
record whenever two reads overlap.

**A sequential test passes against that implementation every time.** This row therefore
drives real concurrent writers, which is the only arrangement that can tell the two apart.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from core.audit.chain import verify_chain
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType

pytestmark = pytest.mark.enclave

TENANT = "tenant-conformance"
WRITERS = 8


def test_row_concurrent_writes_are_all_recorded(
    run_credentials: object, unique_correlation_id: str
) -> None:
    """Each writer gets its own sink, as separate readers would have separate connections."""

    def _write(i: int) -> None:
        sink = PostgresAuditSink(credentials=run_credentials)  # type: ignore[arg-type]
        sink.append_event(
            correlation_id=unique_correlation_id,
            tenant_id=TENANT,
            event_type=AuditEventType.EVIDENCE_READ,
            payload={"writer": i},
        )

    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        list(pool.map(_write, range(WRITERS)))

    reader = PostgresAuditSink(credentials=run_credentials)  # type: ignore[arg-type]
    entries = reader.list_by_correlation_id(unique_correlation_id)

    assert len(entries) == WRITERS, "a concurrent write was lost"
    assert [e.seq for e in entries] == list(range(WRITERS)), "positions collided or gapped"
    verify_chain(entries)


def test_row_the_chain_survives_concurrency(
    run_credentials: object, unique_correlation_id: str
) -> None:
    """Not just 'all present' — correctly linked.

    A store that assigned unique positions but computed prev_hash outside the transaction
    would satisfy the count assertion and still produce a chain that does not verify.
    """

    def _write(i: int) -> None:
        sink = PostgresAuditSink(credentials=run_credentials)  # type: ignore[arg-type]
        sink.append_event(
            correlation_id=unique_correlation_id,
            tenant_id=TENANT,
            event_type=AuditEventType.EVIDENCE_READ,
            payload={"writer": i},
        )

    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        list(pool.map(_write, range(WRITERS)))

    reader = PostgresAuditSink(credentials=run_credentials)  # type: ignore[arg-type]
    verify_chain(reader.list_by_correlation_id(unique_correlation_id))
