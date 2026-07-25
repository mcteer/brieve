# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — genesis + chained entries verify; broken link fails."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash, verify_chain
from core.audit.schema import AuditEntry, AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.errors import AuditChainError


def test_genesis_and_chain_verify() -> None:
    sink = InMemoryAuditSink()
    e0 = sink.build_entry(
        correlation_id="c1",
        event_type=AuditEventType.RUN_START,
        payload={"k": 1},
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert e0.seq == 0
    assert e0.prev_hash == GENESIS_PREV_HASH
    sink.append(e0)
    e1 = sink.build_entry(
        correlation_id="c1",
        event_type=AuditEventType.PRE_DECISION,
        payload={"k": 2},
        timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    assert e1.prev_hash == e0.entry_hash
    sink.append(e1)
    verify_chain(sink.list_by_correlation_id("c1"))


def test_broken_link_rejected_on_append() -> None:
    sink = InMemoryAuditSink()
    e0 = sink.build_entry(
        correlation_id="c1",
        event_type=AuditEventType.RUN_START,
        payload={},
    )
    sink.append(e0)
    bad = AuditEntry(
        correlation_id="c1",
        seq=1,
        event_type=AuditEventType.PRE_DECISION,
        timestamp=datetime.now(UTC),
        payload={},
        prev_hash="f" * 64,
        entry_hash="a" * 64,
    )
    with pytest.raises(AuditChainError):
        sink.append(bad)


def test_verify_detects_hash_mismatch() -> None:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    good_hash = compute_entry_hash(
        correlation_id="c1",
        seq=0,
        event_type=str(AuditEventType.RUN_START),
        timestamp=ts,
        payload={},
        prev_hash=GENESIS_PREV_HASH,
    )
    entry = AuditEntry(
        correlation_id="c1",
        seq=0,
        event_type=AuditEventType.RUN_START,
        timestamp=ts,
        payload={},
        prev_hash=GENESIS_PREV_HASH,
        entry_hash=good_hash,
    )
    tampered = entry.model_copy(update={"payload": {"x": 1}})
    with pytest.raises(ValueError, match="entry_hash mismatch"):
        verify_chain([tampered])
