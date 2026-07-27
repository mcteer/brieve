# SPDX-License-Identifier: Apache-2.0
"""Row: evidence-access records chain, and truncation is caught (FR-010a/d, SC-009a).

Two mechanisms catching two different things, which is why both exist:

- the **chain** catches modification and middle-deletion;
- the **head** catches truncation, which the chain provably cannot.

The second is the row that would be easiest to write in a way that passes without proving
anything, so it truncates a real stream and asserts the chain still verifies — establishing
that the head is doing work the chain could not.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.audit.chain import verify_chain
from core.audit.integrity import verify_stream_integrity
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType

pytestmark = pytest.mark.enclave

TENANT = "tenant-conformance"


def _write(sink: PostgresAuditSink, stream: str, n: int) -> None:
    for i in range(n):
        sink.append_event(
            correlation_id=stream,
            tenant_id=TENANT,
            event_type=AuditEventType.EVIDENCE_READ,
            payload={"i": i},
        )


def test_records_chain_to_their_predecessor(
    audit_sink: PostgresAuditSink, unique_correlation_id: str
) -> None:
    _write(audit_sink, unique_correlation_id, 3)
    entries = audit_sink.list_by_correlation_id(unique_correlation_id)
    assert [e.seq for e in entries] == [0, 1, 2]
    verify_chain(entries)


def test_integrity_check_is_clean_on_an_untampered_store(
    audit_sink: PostgresAuditSink, unique_correlation_id: str, run_connection: Any
) -> None:
    """The false-positive half. A check that always fires gets disabled."""
    _write(audit_sink, unique_correlation_id, 3)
    report = verify_stream_integrity(lambda: run_connection())
    assert report.ok, f"clean store reported findings: {report.findings}"


def test_truncation_is_caught_by_the_head_and_not_by_the_chain(
    audit_sink: PostgresAuditSink, unique_correlation_id: str, run_connection: Any
) -> None:
    """The reason audit_stream_heads exists.

    Delete the newest entry and the remaining chain verifies perfectly — so a check built
    only on the chain would report this store as intact while the most recent record of
    who read what had been removed.
    """
    _write(audit_sink, unique_correlation_id, 3)

    conn = run_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM audit_entries WHERE correlation_id = %s AND seq = 2",
        (unique_correlation_id,),
    )
    conn.commit()
    conn.close()

    # The chain alone still passes. This assertion is the point of the row.
    verify_chain(audit_sink.list_by_correlation_id(unique_correlation_id))

    report = verify_stream_integrity(lambda: run_connection())
    truncated = [f for f in report.findings if f.correlation_id == unique_correlation_id]
    assert truncated and truncated[0].kind == "truncated"


def test_middle_deletion_is_caught_by_the_chain(
    audit_sink: PostgresAuditSink, unique_correlation_id: str, run_connection: Any
) -> None:
    _write(audit_sink, unique_correlation_id, 3)

    conn = run_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM audit_entries WHERE correlation_id = %s AND seq = 1",
        (unique_correlation_id,),
    )
    conn.commit()
    conn.close()

    report = verify_stream_integrity(lambda: run_connection())
    broken = [f for f in report.findings if f.correlation_id == unique_correlation_id]
    assert broken and broken[0].kind == "chain_broken"


def test_break_fixture_unchained_singletons_are_detectable(
    audit_sink: PostgresAuditSink, unique_correlation_id: str, run_connection: Any
) -> None:
    """The arrangement FR-010a rejects: a fresh stream per read.

    Each record satisfies "the record was written" and is still removable without trace,
    so a check that only counted records would pass against it.
    """
    for i in range(3):
        audit_sink.append_event(
            correlation_id=f"{unique_correlation_id}-{i}",
            tenant_id=TENANT,
            event_type=AuditEventType.EVIDENCE_READ,
            payload={"i": i},
        )
    for i in range(3):
        entries = audit_sink.list_by_correlation_id(f"{unique_correlation_id}-{i}")
        assert len(entries) == 1
        assert entries[0].seq == 0, "a per-read stream is a chain of one — nothing links it"
