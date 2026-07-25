# SPDX-License-Identifier: Apache-2.0
"""Append-only, hash-chained audit sink."""

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash, verify_chain
from core.audit.schema import AuditEntry, AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink, build_next_entry

__all__ = [
    "GENESIS_PREV_HASH",
    "AuditEntry",
    "AuditEventType",
    "AuditSink",
    "InMemoryAuditSink",
    "build_next_entry",
    "compute_entry_hash",
    "verify_chain",
]
