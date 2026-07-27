# SPDX-License-Identifier: Apache-2.0
"""Row: both sinks write the same thing.

Two implementations that disagree about what they write are two audit schemas, and the
one everybody reasons about in tests would be the one nobody deploys.

Note what this compares. Since ``append_event`` **assigns** position rather than accepting
it, parity is no longer "both reject the same malformed input" — there is no malformed
input to supply. It is "given the same calls, both produce identical entries", which is
the property that actually matters now.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink

pytestmark = pytest.mark.enclave

CALLS: list[tuple[AuditEventType, dict[str, Any]]] = [
    (AuditEventType.RUN_START, {"scope": ["echo"]}),
    (AuditEventType.PRE_DECISION, {"outcome": "allow"}),
    (AuditEventType.TOOL_OUTCOME, {"ok": True}),
]


def test_both_sinks_produce_identical_entries(
    audit_sink: PostgresAuditSink, unique_correlation_id: str
) -> None:
    tenant = "tenant-parity"
    ts = datetime(2026, 1, 1, tzinfo=UTC)

    memory = InMemoryAuditSink()
    mem_entries = [
        memory.append_event(
            correlation_id=unique_correlation_id,
            tenant_id=tenant,
            event_type=event_type,
            payload=payload,
            timestamp=ts,
        )
        for event_type, payload in CALLS
    ]
    pg_entries = [
        audit_sink.append_event(
            correlation_id=unique_correlation_id,
            tenant_id=tenant,
            event_type=event_type,
            payload=payload,
            timestamp=ts,
        )
        for event_type, payload in CALLS
    ]

    for mem, pg in zip(mem_entries, pg_entries, strict=True):
        assert mem.seq == pg.seq
        assert mem.prev_hash == pg.prev_hash
        # The hash is the real assertion: it covers every field, so an agreement here is
        # agreement about the whole entry rather than about the fields someone remembered
        # to compare.
        assert mem.entry_hash == pg.entry_hash


def test_both_sinks_start_a_chain_at_genesis(
    audit_sink: PostgresAuditSink, unique_correlation_id: str
) -> None:
    tenant = "tenant-parity"
    memory = InMemoryAuditSink()
    mem = memory.append_event(
        correlation_id=unique_correlation_id,
        tenant_id=tenant,
        event_type=AuditEventType.RUN_START,
        payload={},
    )
    pg = audit_sink.append_event(
        correlation_id=unique_correlation_id,
        tenant_id=tenant,
        event_type=AuditEventType.RUN_START,
        payload={},
    )
    assert mem.seq == pg.seq == 0
    assert mem.prev_hash == pg.prev_hash
