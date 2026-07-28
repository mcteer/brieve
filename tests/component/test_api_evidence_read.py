# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the evidence read path's surface behaviour.

The database-enforced half (that Postgres refuses a write through the evidence role) is an
enclave row and cannot be shown here. What these cover is the part that lives in the
surface: scoping, the zero-rows distinction, and the meta-audit record.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from surfaces.api.evidence import evidence_stream_for
from tests.harness.api_fixtures import SurfaceUnderTest, surface_under_test


def _start_a_run(surface: SurfaceUnderTest, client: TestClient) -> str:
    body = client.post(
        "/runs",
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    ).json()
    return str(body["correlation_id"])


def test_evidence_is_readable_and_scoped_to_the_subjects_tenant() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    response = client.get(
        "/evidence", params={"correlation_id": correlation_id}, headers=surface.bearer()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert {e["tenant_id"] for e in body["entries"]} == {"tenant-test"}


def test_reading_evidence_is_itself_audited() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    _start_a_run(surface, client)

    client.get("/evidence", headers=surface.bearer())

    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert len(stream) == 1
    record = stream[0]
    assert record.event_type is AuditEventType.EVIDENCE_READ
    assert record.payload["subject_user_id"] == "alice"


def test_the_record_names_the_query_not_the_rows() -> None:
    """Recording results would copy evidence into the record describing it."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)
    client.get("/evidence", params={"correlation_id": correlation_id}, headers=surface.bearer())

    record = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))[0]
    assert "query_shape" in record.payload
    assert record.payload["result_count"] > 0
    # The rows themselves must not be in there — only what was read, by reference.
    serialized = str(record.payload)
    assert "entry_hash" not in serialized
    assert "prev_hash" not in serialized


def test_one_record_per_read_regardless_of_rows() -> None:
    """Termination. A read writes one record however many rows matched."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    _start_a_run(surface, client)
    _start_a_run(surface, client)

    client.get("/evidence", headers=surface.bearer())
    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert len(stream) == 1

    # Reading the meta-audit records is itself a read, and writes exactly one more.
    client.get("/evidence", headers=surface.bearer())
    assert len(surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))) == 2


def test_access_records_chain_to_each_other() -> None:
    """FR-010a. Not a fresh correlation ID per read.

    A per-read ID would make each record a chain of one — linked to nothing, and removable
    without trace, which is the opposite of what a log of who read what is for.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    for _ in range(3):
        client.get("/evidence", headers=surface.bearer())

    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert [e.seq for e in stream] == [0, 1, 2]
    assert stream[1].prev_hash == stream[0].entry_hash
    assert stream[2].prev_hash == stream[1].entry_hash


def test_reads_do_not_write_into_the_chain_they_read() -> None:
    """The other half of FR-010a, and the subtler one.

    If access records landed on the queried run's chain, a later read of that run would
    return a record the earlier read created.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)
    before = len(surface.audit.list_by_correlation_id(correlation_id))

    client.get("/evidence", params={"correlation_id": correlation_id}, headers=surface.bearer())

    assert len(surface.audit.list_by_correlation_id(correlation_id)) == before


OTHER_TENANTS_RUN = "run-belonging-to-someone-else"


def _seed_another_tenants_run(surface: SurfaceUnderTest) -> None:
    """A real stream under a different tenant.

    Necessary, and the necessity is the point. An earlier version of this test named a
    correlation ID that existed nowhere and still expected a refusal — it passed only
    because the disposition was being guessed from the shape of the ID. Constructing the
    actual situation is what makes the assertion mean anything.
    """
    surface.audit.append_event(
        correlation_id=OTHER_TENANTS_RUN,
        tenant_id="tenant-someone-else",
        event_type=AuditEventType.RUN_START,
        payload={"scope": ["echo"]},
    )


def test_cross_tenant_narrowing_returns_nothing_and_is_distinguishable() -> None:
    """FR-011, constructed the only way a caller actually could.

    There is no tenant parameter, so the reachable attempt is narrowing to a stream that
    belongs to someone else. A test written against a tenant parameter would assert
    something the surface does not expose and pass regardless of behaviour.
    """
    surface = surface_under_test()
    _seed_another_tenants_run(surface)
    client = TestClient(surface.app)

    response = client.get(
        "/evidence",
        params={"correlation_id": OTHER_TENANTS_RUN},
        headers=surface.bearer(),
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0

    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert stream[-1].event_type is AuditEventType.EVIDENCE_READ_REFUSED
    assert stream[-1].payload["disposition"] == "out_of_scope"


def test_a_stream_that_exists_nowhere_is_empty_not_refused() -> None:
    """The third case, which the two-way framing hides.

    "Not yours" and "does not exist" are different, and only the first is worth an
    investigator's attention. Recording every typo'd correlation ID as a cross-tenant
    probe would bury the real ones.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    client.get("/evidence", params={"correlation_id": "no-such-run"}, headers=surface.bearer())

    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert stream[-1].event_type is AuditEventType.EVIDENCE_READ


def test_a_legitimately_empty_query_is_recorded_differently() -> None:
    """The companion to the test above, and what makes it mean anything.

    Both return zero rows. If both recorded the same disposition, an investigator could
    not tell "nothing happened" from "you may not see it" — which is the whole of FR-011.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    response = client.get(
        "/evidence",
        params={"correlation_id": correlation_id, "start_time": "2099-01-01T00:00:00Z"},
        headers=surface.bearer(),
    )
    assert response.json()["count"] == 0

    stream = surface.audit.list_by_correlation_id(evidence_stream_for("tenant-test"))
    assert stream[-1].event_type is AuditEventType.EVIDENCE_READ
    assert stream[-1].payload["disposition"] == "scoped"


def test_the_caller_cannot_tell_the_two_apart() -> None:
    """Deliberately asserting that the response leaks nothing.

    Telling the caller which case they hit would disclose the existence of what they may
    not see, which is exactly what the boundary is for.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    correlation_id = _start_a_run(surface, client)

    _seed_another_tenants_run(surface)
    empty = client.get(
        "/evidence",
        params={"correlation_id": correlation_id, "start_time": "2099-01-01T00:00:00Z"},
        headers=surface.bearer(),
    )
    refused = client.get(
        "/evidence",
        params={"correlation_id": OTHER_TENANTS_RUN},
        headers=surface.bearer(),
    )
    assert empty.status_code == refused.status_code
    assert empty.json() == refused.json()


def test_unauthenticated_evidence_read_is_refused() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    assert client.get("/evidence").status_code == 401
