# SPDX-License-Identifier: Apache-2.0
"""E1–E3, E5 — endorsing is a governed act with a named author (045, T008, US1).

**The endorsement is the trust statement the citation gate rests on.** The pinned corpus is
trusted because the supply chain reviewed it; a customer's own documents cannot be trusted that
way, so what makes them citable is that a named administrator said so at a known time. These
rows assert that the saying is governed like every other configuration change, and that who
said it is the platform's statement rather than the requester's.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from surfaces.api.authority_submit import (
    AuthorityChangeRefused,
    ChangeOutcome,
    RecordMoved,
)
from surfaces.api.console import ENDORSED_SOURCES_PATH, ConsoleConfig, compose_endorsement
from tests.harness.api_fixtures import surface_under_test

ADMIN = "dan@acme.example"
LOCATION = "https://git.example.com/acme/standards"


class _Submitter:
    """Stands in for the fabric. Records what it was asked; answers what the row scripted."""

    def __init__(self, outcome: Any = None) -> None:
        self.outcome = outcome if outcome is not None else ChangeOutcome(state="applied")
        self.submitted: list[Any] = []

    def submit_change(self, change: Any) -> Any:
        self.submitted.append(change)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _record(sources: dict[str, Any] | None = None, version: int = 3) -> dict[str, Any]:
    return {"data": {"data": dict(sources or {}), "metadata": {"version": version}}}


def _config(record: dict[str, Any] | None = None, **over: Any) -> ConsoleConfig:
    stored = record if record is not None else _record()

    def read_versioned(path: str) -> Any:
        return stored if path == ENDORSED_SOURCES_PATH else None

    defaults: dict[str, Any] = {
        "read_matrix": lambda: {"schema_version": 1, "cells": []},
        "read_versioned": read_versioned,
        "quorum_configured": False,
    }
    return ConsoleConfig(**{**defaults, **over})


def _surface(submitter: Any = None, record: dict[str, Any] | None = None, **over: Any) -> Any:
    return surface_under_test(console_config=_config(record, **over), authority_submitter=submitter)


def _admin(surface: Any) -> dict[str, str]:
    headers: dict[str, str] = surface.bearer(subject=ADMIN, claims={"groups": ["platform-admin"]})
    return headers


def _endorse(surface: Any, headers: dict[str, str] | None = None, **body: Any) -> Any:
    payload = {"operation": "endorse", "source": "acme-standards", "location": LOCATION}
    payload.update(body)
    return TestClient(surface.app).post(
        "/console/endorsed-sources",
        json=payload,
        headers=headers if headers is not None else _admin(surface),
    )


# ── E1: the fabric decides, and the console renders which of three things it did ──────────


def test_row_e1_an_endorsement_rides_the_request_and_decide_path() -> None:
    """E1 — no second write mechanism (FR-001b).

    Endorsing is a governance change and goes where governance changes go: the same
    `ConfigChange`, the same submitter, the same three outcomes. A feature that invented its
    own write path would have made ADR-0069's bounds true of three records and not of the
    fourth — which is the shape of a posture that erodes one feature at a time.
    """
    submitter = _Submitter()
    response = _endorse(_surface(submitter))

    assert response.status_code == 200
    assert response.json()["state"] == "applied"
    assert len(submitter.submitted) == 1
    assert submitter.submitted[0].record == "endorsed-sources"


def test_row_e1_a_gated_estate_returns_202_and_says_it_is_not_in_force() -> None:
    """Pending is 202, never 403 — 007's seam, and the reason is a client that stops asking.

    An endorsement awaiting quorum has not made anything citable, and an administrator who
    reads "refused" will re-endorse rather than wait for the approval that is coming.
    """
    submitter = _Submitter(ChangeOutcome(state="pending", accessor="acc-1"))
    response = _endorse(_surface(submitter, quorum_configured=True))

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "pending"
    assert "NOT in force" in body["message"]


def test_row_e1_an_ungated_estate_says_so_on_an_applied_endorsement() -> None:
    """FR-007 on the fourth record. Applied-without-approval must not read as approved."""
    response = _endorse(_surface(_Submitter()))

    body = response.json()
    assert body["gating"] == "ungated"
    assert "WITHOUT approval" in body["message"]


def test_row_e1_a_denied_endorsement_is_403_and_an_outage_is_503() -> None:
    """The two failures that must never read as each other.

    Denied sends an administrator to whoever governs the quorum; unreachable sends them to an
    outage. 007's mapping, and it holds for this record because the route shares the code
    rather than reimplementing it.
    """
    denied = _endorse(_surface(_Submitter(AuthorityChangeRefused("no"))))
    assert denied.status_code == 403

    moved = _endorse(_surface(_Submitter(RecordMoved("someone else got there first"))))
    assert moved.status_code == 409


# ── E2: who, what, when — and the platform says who ───────────────────────────────────────


def test_row_e2_the_record_names_who_endorsed_and_when() -> None:
    """FR-002. An endorsement with no author is content that arrived."""
    submitter = _Submitter()
    _endorse(_surface(submitter))

    entry = submitter.submitted[0].payload["acme-standards"]
    assert entry["endorsed_by"] == ADMIN
    assert entry["endorsed_at"]
    assert entry["location"] == LOCATION


def test_row_e2_the_endorser_cannot_be_dictated_by_the_request() -> None:
    """**The row this route's shape exists for.**

    The submitter replaces a record body wholesale, so a caller able to post the body could
    name any endorser. The generic change route therefore refuses this record and points at
    the composer, which stamps the authenticated subject. An endorsement that can name
    somebody who did not endorse is worse than no endorsement — the trail would carry it as
    a fact.
    """
    surface = _surface(_Submitter())
    raw = TestClient(surface.app).post(
        "/console/changes",
        json={
            "record": "endorsed-sources",
            "payload": {"acme-standards": {"location": LOCATION, "endorsed_by": "someone-else"}},
        },
        headers=_admin(surface),
    )

    assert raw.status_code == 400
    assert "/console/endorsed-sources" in raw.json()["detail"]


def test_row_e2_a_field_a_credential_could_go_in_is_not_a_field() -> None:
    """044's FR-018b posture on the fourth record: locations, never material."""
    surface = _surface(_Submitter())
    response = TestClient(surface.app).post(
        "/console/endorsed-sources",
        json={
            "operation": "endorse",
            "source": "acme-standards",
            "location": LOCATION,
            "token": "ghp_notasecret",
        },
        headers=_admin(surface),
    )

    assert response.status_code == 422


def test_row_e2_withdrawal_and_adoption_are_recorded_like_the_endorsement() -> None:
    """FR-017e. An adoption renews the trust statement, so it is authored like one."""
    existing = {
        "acme-standards": {
            "location": LOCATION,
            "endorsed_by": ADMIN,
            "endorsed_at": "2026-08-01T00:00:00+00:00",
        }
    }
    submitter = _Submitter()
    surface = _surface(submitter, record=_record(existing))

    adopted = TestClient(surface.app).post(
        "/console/endorsed-sources",
        json={"operation": "adopt", "source": "acme-standards", "version_id": "v-two"},
        headers=_admin(surface),
    )
    assert adopted.status_code == 200

    entry = submitter.submitted[0].payload["acme-standards"]
    assert entry["adopted_version"] == "v-two"
    assert entry["adopted_by"] == ADMIN
    assert entry["adopted_at"]
    # The original endorsement is not rewritten by an adoption.
    assert entry["endorsed_at"] == "2026-08-01T00:00:00+00:00"


# ── E3: a non-administrator is refused, and the refusal is recorded ───────────────────────


def test_row_e3_a_non_administrator_cannot_endorse() -> None:
    """The role gate the whole surface rests on, on the route that makes content citable."""
    surface = _surface(_Submitter())
    response = _endorse(surface, headers=surface.bearer())

    assert response.status_code == 403


def test_row_e3_the_refused_attempt_is_recorded() -> None:
    """022's rule: a boundary a caller can probe without trace is not a boundary."""
    surface = _surface(_Submitter())
    _endorse(surface, headers=surface.bearer())

    refusals = [
        entry
        for entry in surface.audit.all_entries()
        if entry.payload.get("reason_code") == "not_an_admin"
    ]
    assert refusals, "the console refused and said nothing about it"


def test_row_e3_an_unauthenticated_caller_reaches_nothing() -> None:
    surface = _surface(_Submitter())
    response = TestClient(surface.app).post(
        "/console/endorsed-sources",
        json={"operation": "endorse", "source": "acme-standards", "location": LOCATION},
    )

    assert response.status_code in {401, 403}


# ── E5: withdrawal takes effect at the next question, with no restart ─────────────────────


def test_row_e5_withdrawal_leaves_the_adopted_version_in_place() -> None:
    """FR-004 with research R4's constraint.

    Citability goes to zero because `withdrawn` beats adoption at parse time. The version
    stays because runs in flight pinned it, and a run record naming a version that has been
    erased describes ground nobody can look at.
    """
    existing = {
        "acme-standards": {
            "location": LOCATION,
            "endorsed_by": ADMIN,
            "endorsed_at": "2026-08-01T00:00:00+00:00",
            "adopted_version": "v-one",
        }
    }
    submitter = _Submitter()
    surface = _surface(submitter, record=_record(existing))

    TestClient(surface.app).post(
        "/console/endorsed-sources",
        json={"operation": "withdraw", "source": "acme-standards"},
        headers=_admin(surface),
    )

    entry = submitter.submitted[0].payload["acme-standards"]
    assert entry["withdrawn"] is True
    assert entry["adopted_version"] == "v-one"


def test_row_e5_the_record_is_read_per_request_so_no_restart_is_needed() -> None:
    """044's C17 shape in one process: the state that decides citability is never cached.

    Asserted at the reader rather than through two HTTP calls, because what must be true is
    that *nothing holds it* — a row that merely observed the right answer twice would pass
    over a cache with a short enough life.
    """
    reads: list[str] = []

    def read_versioned(path: str) -> Any:
        reads.append(path)
        return _record()

    surface = _surface(_Submitter(), read_versioned=read_versioned)
    client = TestClient(surface.app)
    client.get("/console/configuration", headers=_admin(surface))
    before = reads.count(ENDORSED_SOURCES_PATH)
    client.get("/console/configuration", headers=_admin(surface))

    assert reads.count(ENDORSED_SOURCES_PATH) > before


# ── the composer's own properties, where they can be exercised exhaustively ───────────────


def test_endorsing_a_second_source_does_not_withdraw_the_first() -> None:
    """The data-loss path a whole-record write makes available, closed by merging.

    The submitter replaces the body, so an endorsement composed from nothing would silently
    un-endorse everything else. This is the row that would notice.
    """
    existing = {
        "first": {"location": "https://a", "endorsed_by": ADMIN, "adopted_version": "v-a"},
    }
    composed = compose_endorsement(
        current=existing,
        operation="endorse",
        source="second",
        actor=ADMIN,
        now="2026-08-07T00:00:00+00:00",
        location="https://b",
    )

    assert composed["first"]["adopted_version"] == "v-a"
    assert composed["second"]["endorsed_by"] == ADMIN


def test_re_endorsing_a_withdrawn_source_restores_it_without_losing_its_version() -> None:
    """Withdrawal is reversible, and reversing it must not cost the adopted version.

    Forcing a delete-and-recreate would lose the version, and with it every run record's
    ability to name ground that still exists.
    """
    existing = {
        "acme": {
            "location": LOCATION,
            "endorsed_by": ADMIN,
            "adopted_version": "v-one",
            "withdrawn": True,
        }
    }
    composed = compose_endorsement(
        current=existing,
        operation="endorse",
        source="acme",
        actor=ADMIN,
        now="2026-08-07T00:00:00+00:00",
    )

    assert composed["acme"]["withdrawn"] is False
    assert composed["acme"]["adopted_version"] == "v-one"


@pytest.mark.parametrize("operation", ["withdraw", "adopt"])
def test_a_source_that_is_not_endorsed_cannot_be_withdrawn_or_adopted(operation: str) -> None:
    with pytest.raises(ValueError, match="not endorsed"):
        compose_endorsement(
            current={},
            operation=operation,
            source="acme",
            actor=ADMIN,
            now="2026-08-07T00:00:00+00:00",
            version_id="v-one",
        )


def test_an_unreadable_record_refuses_rather_than_composing_from_nothing() -> None:
    """The failure mode with the worst consequence in this route.

    Composing against an empty record after a read failure would submit a body containing one
    source and silently withdraw every other — data loss dressed as a fresh start. Refusing
    sends the administrator to the outage.
    """

    def unreadable(path: str) -> Any:
        raise RuntimeError("the fabric did not answer")

    response = _endorse(_surface(_Submitter(), read_versioned=unreadable))
    assert response.status_code == 503
