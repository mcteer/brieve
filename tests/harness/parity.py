# SPDX-License-Identifier: Apache-2.0
"""Drive an operation through both transports and compare what they did.

**The projection is the whole assertion.** "Equivalent audit events" left vague is the
easiest claim in this feature to satisfy dishonestly: a comparison that checks "both
produced some audit" is satisfied by two surfaces that agree about nothing. So the fields
compared are named here, and the fields deliberately *not* compared are named beside them
with the reason — a reader can then argue with the choice instead of guessing at it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from core.audit.schema import AuditEntry
from core.identity.types import AuthenticatedSubject
from surfaces.mcp.transport import McpTransport

#: Compared. Everything a caller could observe about *what was decided*.
COMPARED_FIELDS = ("event_type", "subject", "outcome", "reason_code")

#: Not compared, and each for a reason that is not "it was inconvenient":
#:
#: - timestamps and correlation IDs: two runs, legitimately different
#: - entry hashes and prev_hash: follow from the above
#: - the transport itself: the one thing that *should* differ
NOT_COMPARED = ("timestamp", "correlation_id", "entry_hash", "prev_hash", "transport")


@dataclass
class TransportOutcome:
    """What one transport did with one operation."""

    status: int
    audit: list[dict[str, Any]]


def project(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    """Reduce a trail to the parts parity is about.

    Order is preserved deliberately: two surfaces that emit the same events in a different
    sequence have not made the same decision, they have made the same decisions in a
    different order — and an investigator reconstructing a run would find one of them
    misleading.
    """
    projected = []
    for entry in entries:
        payload = entry.payload or {}
        projected.append(
            {
                "event_type": str(entry.event_type),
                "subject": payload.get("subject_user_id"),
                "outcome": payload.get("outcome"),
                "reason_code": payload.get("reason_code"),
            }
        )
    return projected


def through_api(
    client: TestClient,
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> int:
    response = client.request(method, path, headers=headers, json=json, params=params)
    return response.status_code


def through_mcp(
    transport: McpTransport,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    subject: AuthenticatedSubject,
) -> int:
    return transport.call(tool_name, arguments, subject=subject).status


__all__ = [
    "COMPARED_FIELDS",
    "NOT_COMPARED",
    "TransportOutcome",
    "project",
    "through_api",
    "through_mcp",
]
