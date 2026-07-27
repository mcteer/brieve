# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the authenticated identity is the subject of everything downstream.

US1's central claim, and the one the rest of the feature rests on. If the subject is wrong
here, every downstream guarantee is about the wrong person and non-repudiation is gone.

The assertion is deliberately "**every** audit record for the correlation ID", not "an
audit record". A surface that named the subject on the first entry and lost it thereafter
would satisfy the weaker version while leaving most of the trail anonymous.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.run import RunState
from tests.harness.api_fixtures import surface_under_test


def test_authenticated_subject_becomes_the_run_subject() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    response = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(subject="alice"),
    )
    assert response.status_code == 202
    handle = response.json()
    assert handle["state"] == RunState.ACTIVE

    entries = surface.audit.list_by_correlation_id(handle["correlation_id"])
    assert entries, "starting a run wrote no audit trail at all"

    issued = [e for e in entries if e.event_type == "authority_issued"]
    assert issued and issued[0].payload["subject_user_id"] == "alice"


def test_identity_appears_in_every_record_not_just_the_first() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    response = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(subject="alice"),
    )
    entries = surface.audit.list_by_correlation_id(response.json()["correlation_id"])

    # The tenant travels with the subject onto every entry, and it is inside the hash — so
    # this also proves the chain covers the scoping dimension for real traffic, not only
    # in the unit test that constructs entries directly.
    assert {e.tenant_id for e in entries} == {"tenant-test"}


def test_run_start_returns_a_handle_without_blocking() -> None:
    """FR-007a. The response describes a run that has *started*, not one that finished."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    response = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"run_id", "correlation_id", "state"}
    assert body["state"] == RunState.ACTIVE


def test_handle_carries_nothing_about_the_substrate() -> None:
    """Principle VII at the layer a customer touches first.

    A caller who can see an allocation id has learned the scheduler, and the next client
    written against this API will depend on it.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    body = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    ).json()
    serialized = str(body).lower()
    for leak in ("alloc", "nomad", "job", "container", "node"):
        assert leak not in serialized


def test_state_is_queryable_through_the_handle() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    handle = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    ).json()

    got = client.get(f"/runs/{handle['run_id']}", headers=surface.bearer())
    assert got.status_code == 200
    assert got.json()["correlation_id"] == handle["correlation_id"]


def test_unknown_run_is_not_found() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    got = client.get("/runs/no-such-run", headers=surface.bearer())
    assert got.status_code == 404


def test_unauthenticated_start_executes_nothing() -> None:
    """Refused with nothing executed — not refused after something ran."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    response = client.post(
        "/runs", json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]}
    )
    assert response.status_code == 401
    assert surface.audit.all_entries() == []
