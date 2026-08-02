# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — 022's governed read is unchanged by 025's narrowing parameter.

025 needed `read_evidence_for` to accept `event_types` so estate answering can **bound the query
rather than filter the results**. That function is 022's, merged and in use, and the parameter's
default is the only thing standing between "additive" and "changed the operator read".

**So it is asserted rather than declared.** The plan says the route never passes the parameter;
these rows check that the route behaves identically with it present, and that the parameter can
only ever narrow. A default that drifted — to an empty set, say — would silently return nothing
to every operator reading the trail, and the failure would look like an empty estate.
"""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from surfaces.api.evidence import read_evidence_for
from tests.harness.api_fixtures import surface_under_test


def test_the_route_does_not_pass_the_narrowing_parameter() -> None:
    """`GET /evidence` is the operator's read and stays tenant-bounded only.

    An operator reading the trail directly is a different act from the platform assembling an
    answer on someone's behalf. Retrofitting role bounds onto 022's surface would change merged
    behaviour this feature has no mandate to change.
    """
    from surfaces.api import evidence as evidence_module

    source = inspect.getsource(evidence_module.build_router)
    assert "event_types" not in source, (
        "the /evidence route now narrows by event type — that is a change to 022's operator "
        "read, not an additive parameter for 025's estate path"
    )


def test_the_default_is_todays_read() -> None:
    """The parameter is optional and defaults to no narrowing at all."""
    signature = inspect.signature(read_evidence_for)
    assert signature.parameters["event_types"].default is None


def test_the_operator_read_returns_what_it_did_before() -> None:
    """End to end: a run is started, and the operator's unnarrowed read sees its entries."""
    surface = surface_under_test()
    client = TestClient(surface.app)

    started = client.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    correlation_id = started.json()["correlation_id"]

    read = client.get(f"/evidence?correlation_id={correlation_id}", headers=surface.bearer())
    assert read.status_code == 200
    assert read.json()["count"] > 0, "the operator read returned nothing for a run that happened"


def test_narrowing_can_only_reduce_what_is_returned() -> None:
    """The parameter narrows; it never widens, and it never reaches past the tenant bound.

    Asserted by comparison rather than by reading the query builder: the narrowed result must be a
    subset of the unnarrowed one, for the same subject and the same stream.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    started = client.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    correlation_id = started.json()["correlation_id"]
    subject = surface.subject()

    everything, _ = read_evidence_for(
        query=surface.evidence,
        audit=surface.audit,
        subject=subject,
        correlation_id=correlation_id,
    )
    narrowed, _ = read_evidence_for(
        query=surface.evidence,
        audit=surface.audit,
        subject=subject,
        correlation_id=correlation_id,
        event_types=frozenset({AuditEventType.RUN_START}),
    )

    assert everything, "the unnarrowed read found nothing, so the comparison proves nothing"
    assert len(narrowed) <= len(everything)
    assert {e.entry_hash for e in narrowed} <= {e.entry_hash for e in everything}
    assert all(str(e.event_type) == "run_start" for e in narrowed)


def test_narrowing_to_nothing_returns_nothing_rather_than_everything() -> None:
    """The fail-closed direction. An empty narrowing must not read as 'no filter'.

    This is the shape a scoping bug would take: a subject whose roles map to nothing gets an empty
    set, and if empty meant unfiltered they would see the entire tenant's trail.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    started = client.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    correlation_id = started.json()["correlation_id"]

    nothing, _ = read_evidence_for(
        query=surface.evidence,
        audit=surface.audit,
        subject=surface.subject(),
        correlation_id=correlation_id,
        event_types=frozenset(),
    )
    assert nothing == [], "an empty narrowing returned entries — empty must not mean unfiltered"
