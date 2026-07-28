# SPDX-License-Identifier: Apache-2.0
"""Append-only, hash-chained audit sink."""

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash, verify_chain
from core.audit.schema import AuditEntry, AuditEventType, EvidenceDisposition
from core.audit.sink import AuditSink, InMemoryAuditSink

__all__ = [
    "GENESIS_PREV_HASH",
    "AuditEntry",
    "AuditEventType",
    "AuditSink",
    "EvidenceDisposition",
    "InMemoryAuditSink",
    "compute_entry_hash",
    "verify_chain",
]
