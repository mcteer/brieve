# SPDX-License-Identifier: Apache-2.0
"""SHA-256 hash chain over pinned canonical UTF-8 JSON encodings.

``tenant_id`` is one of the hashed fields. It bounds every evidence read, so leaving it
outside the chain would make the field deciding who may see a record the one field in that
record nobody could prove (specs/008-northbound-api, FR-010d).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from core.audit.schema import AuditEntry

GENESIS_PREV_HASH = "0" * 64


def rfc3339_utc(dt: datetime) -> str:
    """Format timestamp as RFC 3339 UTC with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    text = dt.isoformat(timespec="microseconds")
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    if text.endswith("Z"):
        return text
    return text


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return rfc3339_utc(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def canonical_entry_dict(
    *,
    correlation_id: str,
    tenant_id: str,
    seq: int,
    event_type: str,
    timestamp: datetime,
    payload: dict[str, Any],
    prev_hash: str,
) -> dict[str, Any]:
    """Fields included in the hash (excludes entry_hash)."""
    return {
        "correlation_id": correlation_id,
        "event_type": event_type,
        "payload": _jsonable(payload),
        "prev_hash": prev_hash,
        "seq": seq,
        "tenant_id": tenant_id,
        "timestamp": rfc3339_utc(timestamp),
    }


def canonical_bytes(fields: dict[str, Any]) -> bytes:
    """UTF-8 JSON, lexicographically sorted keys, no insignificant whitespace."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_entry_hash(
    *,
    correlation_id: str,
    tenant_id: str,
    seq: int,
    event_type: str,
    timestamp: datetime,
    payload: dict[str, Any],
    prev_hash: str,
) -> str:
    fields = canonical_entry_dict(
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        seq=seq,
        event_type=event_type,
        timestamp=timestamp,
        payload=payload,
        prev_hash=prev_hash,
    )
    return hashlib.sha256(canonical_bytes(fields)).hexdigest()


def verify_chain(entries: list[AuditEntry]) -> None:
    """Raise ValueError if the chain is broken or gapped."""
    if not entries:
        return
    ordered = sorted(entries, key=lambda e: e.seq)
    for i, entry in enumerate(ordered):
        if entry.seq != i:
            raise ValueError(f"audit chain gap: expected seq {i}, got {entry.seq}")
        expected_prev = GENESIS_PREV_HASH if i == 0 else ordered[i - 1].entry_hash
        if entry.prev_hash != expected_prev:
            raise ValueError(f"audit chain link broken at seq {entry.seq}")
        recomputed = compute_entry_hash(
            correlation_id=entry.correlation_id,
            tenant_id=entry.tenant_id,
            seq=entry.seq,
            event_type=str(entry.event_type),
            timestamp=entry.timestamp,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
        )
        if recomputed != entry.entry_hash:
            raise ValueError(f"audit entry_hash mismatch at seq {entry.seq}")
