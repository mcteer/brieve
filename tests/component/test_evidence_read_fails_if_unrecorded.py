# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — FR-010b: a read whose record cannot be written is refused.

The tempting implementation logs the failure and returns the evidence anyway, because the
caller asked a legitimate question and the audit problem is not their fault. That is
exactly the case FR-010 exists to prevent: an access that happened with no record of it
having happened.

`start_governed_run` already behaves this way when its own audit write fails, so this is
consistency with the platform rather than a new severity.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from tests.harness.api_fixtures import surface_under_test


class RefusingSink(InMemoryAuditSink):
    """Accepts run entries, refuses evidence-access records."""

    def append_event(self, **kwargs: Any) -> AuditEntry:
        if str(kwargs["correlation_id"]).startswith("evidence-access:"):
            raise RuntimeError("evidence store unavailable")
        return super().append_event(**kwargs)


def test_the_read_is_refused_when_its_record_cannot_be_written() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )

    # Swap in a sink that cannot record access, leaving everything else intact.
    surface.app.state.audit_sink = RefusingSink()

    response = client.get("/evidence", headers=surface.bearer())
    assert response.status_code == 503
    # And crucially: no evidence in the body. Returning rows with a 503 would be the same
    # failure wearing a different status code.
    assert "entries" not in response.json()
