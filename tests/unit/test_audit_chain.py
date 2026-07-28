# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the sink assigns a sound chain, and tampering is detected.

An earlier version of this file asserted that ``append`` *rejected* an entry carrying a
broken link. That protection no longer exists to test, because the thing it protected
against no longer exists: ``append_event`` assigns position and linkage, so a caller has
no parameter through which to supply a wrong one. Swapping in a weaker test that still
passed would have quietly dropped the coverage, so the properties below are the ones that
still need proving.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash, verify_chain
from core.audit.schema import AuditEntry, AuditEventType
from core.audit.sink import InMemoryAuditSink

TENANT = "tenant-test"


def test_genesis_and_chain_verify() -> None:
    sink = InMemoryAuditSink()
    e0 = sink.append_event(
        correlation_id="c1",
        tenant_id=TENANT,
        event_type=AuditEventType.RUN_START,
        payload={"k": 1},
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert e0.seq == 0
    assert e0.prev_hash == GENESIS_PREV_HASH

    e1 = sink.append_event(
        correlation_id="c1",
        tenant_id=TENANT,
        event_type=AuditEventType.PRE_DECISION,
        payload={"k": 2},
        timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    assert e1.seq == 1
    assert e1.prev_hash == e0.entry_hash
    verify_chain(sink.list_by_correlation_id("c1"))


def test_position_cannot_be_supplied_by_the_caller() -> None:
    """The seam assigns; it does not accept.

    This is what replaced the old broken-link rejection test. If ``seq`` or ``prev_hash``
    ever reappear as parameters, the read-then-write shape is back, and with it the race
    that made a shared evidence stream unsafe.
    """
    params = set(inspect.signature(InMemoryAuditSink.append_event).parameters)
    assert "seq" not in params
    assert "prev_hash" not in params
    assert "entry_hash" not in params


def test_chains_are_independent_per_correlation_id() -> None:
    sink = InMemoryAuditSink()
    a = sink.append_event(
        correlation_id="c1", tenant_id=TENANT, event_type=AuditEventType.RUN_START, payload={}
    )
    b = sink.append_event(
        correlation_id="c2", tenant_id=TENANT, event_type=AuditEventType.RUN_START, payload={}
    )
    assert a.seq == b.seq == 0
    assert a.prev_hash == b.prev_hash == GENESIS_PREV_HASH


def test_verify_detects_hash_mismatch() -> None:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    good_hash = compute_entry_hash(
        correlation_id="c1",
        tenant_id=TENANT,
        seq=0,
        event_type=str(AuditEventType.RUN_START),
        timestamp=ts,
        payload={},
        prev_hash=GENESIS_PREV_HASH,
    )
    entry = AuditEntry(
        correlation_id="c1",
        tenant_id=TENANT,
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


def test_tenant_is_inside_the_hash() -> None:
    """FR-010d: the field bounding every evidence read must be covered by the chain.

    Left outside, the one field deciding who may see a record would be the one field in
    that record nobody could prove.
    """
    sink = InMemoryAuditSink()
    entry = sink.append_event(
        correlation_id="c1",
        tenant_id=TENANT,
        event_type=AuditEventType.RUN_START,
        payload={},
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    moved = entry.model_copy(update={"tenant_id": "tenant-someone-else"})
    with pytest.raises(ValueError, match="entry_hash mismatch"):
        verify_chain([moved])
