# SPDX-License-Identifier: Apache-2.0
"""Rows: identity-is-the-subject, fail-closed-on-identity, unmapped-claim, no-secret-leak.

Hermetic — these need no enclave, and marking them otherwise would make the fork-safe lane
weaker than it can be for no benefit.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.harness.api_fixtures import surface_under_test


def test_row_identity_is_the_subject() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    body = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    ).json()

    entries = surface.audit.list_by_correlation_id(body["correlation_id"])
    issued = [e for e in entries if e.event_type == "authority_issued"]
    assert issued and issued[0].payload["subject_user_id"] == "alice"


def test_row_fail_closed_on_identity() -> None:
    """Absent, expired, and unverifiable each refuse with ZERO executions."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    payload = {"agent_definition_id": "definition-a", "requested_tools": ["echo"]}

    attempts = [
        {},
        {"Authorization": f"Bearer {surface.idp.expired_token(claims={'groups': ['platform']})}"},
        {"Authorization": "Bearer not-a-token"},
    ]
    for headers in attempts:
        assert client.post("/runs", json=payload, headers=headers).status_code in (401, 403)

    assert surface.audit.all_entries() == [], "a refused request executed something"


def test_row_unmapped_claim_refuses() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    response = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(claims={"groups": ["not-mapped"]}),
    )
    assert response.status_code == 403
    assert surface.audit.all_entries() == []


def test_row_no_secret_leaks_into_the_trail() -> None:
    """No token material, no authorization header value, anywhere in the evidence."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    headers = surface.bearer()
    token = headers["Authorization"].split(" ", 1)[1]

    client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=headers,
    )

    serialized = " ".join(str(e.payload) for e in surface.audit.all_entries())
    assert token not in serialized
    # Not just the whole token: a prefix would be enough to correlate against a log.
    assert token[:24] not in serialized
    assert "bearer" not in serialized.lower()
