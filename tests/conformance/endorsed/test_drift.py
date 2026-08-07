# SPDX-License-Identifier: Apache-2.0
"""E11–E14 — told what changed, and it stays told until somebody decides (045, T015, US3).

**Detect is not adopt, and that separation is the phase.** The cheap automatic operation
(noticing) must not be able to alter what answers rest on, and the operation that alters it
(adopting) must be a person's act with a name and a time against it. A platform where a
customer's edit silently changed what it answers — with a trail recording a version change
authored by a timer — is exactly what ADR-0070 refuses in its last alternative.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.endorsed.records import (
    ADOPTED,
    CANDIDATE,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from core.endorsed_sync import SyncFailed, SyncOutcome, compare_versions
from surfaces.api.console import ENDORSED_SOURCES_PATH, ConsoleConfig
from surfaces.mcp.health import DriftChecker, DriftFlag
from tests.harness.api_fixtures import surface_under_test

ADMIN = "dan@acme.example"
LOCATION = "https://git.example.com/acme/standards"


def _entry(**over: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "location": LOCATION,
        "endorsed_by": ADMIN,
        "endorsed_at": "2026-08-01T00:00:00+00:00",
        "adopted_version": "v-one",
    }
    entry.update(over)
    return entry


def _document(path: str, body: str = "kept 400 days") -> EndorsedDocument:
    sections = {"retention": body}
    return EndorsedDocument(
        path=path,
        url=f"https://git.example.com{path}",
        digest=digest_of_document(sections),
        anchors=frozenset(sections),
        sections=dict(sections),
    )


def _version(
    version_id: str, paths: list[str], *, tip: str, state: str = CANDIDATE
) -> SyncedVersion:
    return SyncedVersion(
        version_id=version_id,
        tenant_id="acme",
        source="acme-standards",
        upstream_tip=tip,
        synced_at=datetime(2026, 8, 5, tzinfo=UTC),
        synced_by=ADMIN,
        state=state,
        documents={path: _document(path) for path in paths},
    )


class _Store:
    """The content store, in memory. Records what it was told to label."""

    def __init__(
        self, versions: dict[str, SyncedVersion] | None = None, tip: str = "abc123"
    ) -> None:
        self.versions = dict(versions or {})
        self.tip = tip
        self.adoptions: list[tuple[str, str]] = []

    def adopted_tip(self, *, tenant_id: str, source: str) -> str:
        return self.tip

    def read_version(self, version_id: str, *, verify: bool = True) -> SyncedVersion | None:
        return self.versions.get(version_id)

    def write_version(self, version: SyncedVersion) -> None:
        self.versions[version.version_id] = version

    def mark_adopted(self, *, tenant_id: str, source: str, version_id: str) -> None:
        self.adoptions.append((source, version_id))


class _Submitter:
    def __init__(self) -> None:
        from surfaces.api.authority_submit import ChangeOutcome

        self.outcome = ChangeOutcome(state="applied")
        self.submitted: list[Any] = []

    def submit_change(self, change: Any) -> Any:
        self.submitted.append(change)
        return self.outcome


# ── E11: drift is flagged, and flagging changes nothing ───────────────────────────────────


def test_row_e11_a_moved_source_is_flagged() -> None:
    """A refs listing, no clone, no content transfer (research R5, ADR-0070's bound)."""
    flags = DriftChecker(
        read_sources=lambda: {"acme-standards": _entry()},
        store=_Store(tip="abc123"),
        list_tip=lambda location: "def456",
        now=lambda: "2026-08-07T10:00:00+00:00",
    ).sweep()

    assert len(flags) == 1
    assert flags[0].moved
    assert flags[0].upstream_tip == "def456"
    assert flags[0].adopted_tip == "abc123"
    assert flags[0].detected_at == "2026-08-07T10:00:00+00:00"


def test_row_e11_an_unmoved_source_raises_no_flag_of_change() -> None:
    flags = DriftChecker(
        read_sources=lambda: {"acme-standards": _entry()},
        store=_Store(tip="abc123"),
        list_tip=lambda location: "abc123",
    ).sweep()

    assert not flags[0].moved


def test_row_e11_noticing_changes_nothing_about_what_is_adopted() -> None:
    """FR-017a, asserted as the checker having no way to write a version.

    The store the checker is handed is asked one question — what tip the adopted version
    recorded — and is never told anything. A detection pass that could adopt would make the
    decision by the act of looking, which is the failure this whole phase is shaped around.
    """
    store = _Store(tip="abc123")
    DriftChecker(
        read_sources=lambda: {"acme-standards": _entry()},
        store=store,
        list_tip=lambda location: "def456",
    ).sweep()

    assert store.adoptions == []
    assert store.versions == {}


def test_row_e11_an_unreachable_source_is_not_an_unchanged_one() -> None:
    """**The failure with the worst consequence in this module.**

    Reporting "unchanged" when the source could not be reached tells an administrator their
    material is current at a moment when the platform has no idea. The flag carries the error
    and makes no claim either way.
    """

    def unreachable(location: str) -> str:
        raise SyncFailed("host is down", reason_code="sync_failed")

    flags = DriftChecker(
        read_sources=lambda: {"acme-standards": _entry()},
        store=_Store(tip="abc123"),
        list_tip=unreachable,
    ).sweep()

    assert flags[0].error
    assert not flags[0].moved
    assert flags[0].upstream_tip == ""


def test_row_e11_a_withdrawn_source_is_not_checked_at_all() -> None:
    """Withdrawal means the platform stops reaching out, not just stops citing.

    Continuing to probe a source somebody deliberately stopped trusting would be egress with
    no governance behind it — precisely what ADR-0070 bounds to the endorsement record.
    """
    reached: list[str] = []

    def list_tip(location: str) -> str:
        reached.append(location)
        return "def456"

    flags = DriftChecker(
        read_sources=lambda: {"acme-standards": _entry(withdrawn=True)},
        store=_Store(),
        list_tip=list_tip,
    ).sweep()

    assert flags == []
    assert reached == []


def test_row_e11_an_unreadable_endorsement_record_flags_nothing() -> None:
    """Inventing flags from a record we could not read would report drift on sources that may
    not be endorsed any more."""

    def unreadable() -> dict[str, Any]:
        raise RuntimeError("the fabric did not answer")

    assert (
        DriftChecker(read_sources=unreadable, store=_Store(), list_tip=lambda loc: "x").sweep()
        == []
    )


# ── E12: the review names added, removed, altered ─────────────────────────────────────────


def _console(
    store: _Store,
    syncer: Any,
    record: dict[str, Any] | None = None,
    submitter: Any = None,
) -> Any:
    stored = {"data": {"data": record if record is not None else {"acme-standards": _entry()}}}

    def read_versioned(path: str) -> Any:
        return stored if path == ENDORSED_SOURCES_PATH else None

    config = ConsoleConfig(
        read_matrix=lambda: {"schema_version": 1, "cells": []},
        read_versioned=read_versioned,
        endorsed_store=store,
        sync_source=syncer,
        tenant_id="acme",
    )
    return surface_under_test(console_config=config, authority_submitter=submitter or _Submitter())


def _admin(surface: Any) -> dict[str, str]:
    headers: dict[str, str] = surface.bearer(subject=ADMIN, claims={"groups": ["platform-admin"]})
    return headers


def _syncer(paths: list[str], *, tip: str = "def456", uncitable: tuple[str, ...] = ()) -> Any:
    def sync(**kwargs: Any) -> tuple[SyncedVersion, SyncOutcome]:
        version = _version("v-two", paths, tip=tip)
        return version, SyncOutcome(
            version_id="v-two",
            source=kwargs["source"],
            upstream_tip=tip,
            document_count=len(paths),
            uncitable=uncitable,
        )

    return sync


def test_row_e12_the_review_names_what_moved_and_not_what_it_says() -> None:
    """FR-017c. Paths, never words — this is somebody else's material."""
    adopted = _version(
        "v-one",
        ["/endorsed/acme-standards/a.md", "/endorsed/acme-standards/b.md"],
        tip="abc123",
        state=ADOPTED,
    )
    store = _Store({"v-one": adopted})
    surface = _console(
        store, _syncer(["/endorsed/acme-standards/b.md", "/endorsed/acme-standards/c.md"])
    )

    response = TestClient(surface.app).post(
        "/console/endorsed-sources/acme-standards/review", headers=_admin(surface)
    )

    body = response.json()
    assert response.status_code == 200
    assert body["added"] == ["/endorsed/acme-standards/c.md"]
    assert body["removed"] == ["/endorsed/acme-standards/a.md"]
    assert body["common"] == ["/endorsed/acme-standards/b.md"]
    assert "kept 400 days" not in response.text


def test_row_e12_reviewing_changes_nothing_and_says_so() -> None:
    """Opening the page must not move what answers rest on. The candidate is not citable."""
    store = _Store({"v-one": _version("v-one", ["/endorsed/acme-standards/a.md"], tip="abc123")})
    surface = _console(store, _syncer(["/endorsed/acme-standards/a.md"]))

    body = (
        TestClient(surface.app)
        .post("/console/endorsed-sources/acme-standards/review", headers=_admin(surface))
        .json()
    )

    assert body["adopted_version"] == "v-one"
    assert store.versions["v-two"].state == CANDIDATE
    assert store.adoptions == []
    assert "separate act" in body["in_force"]


def test_row_e12_an_uncitable_document_is_surfaced_in_the_review() -> None:
    """FR-011/E20 at the point a person is deciding. A review that showed 12 documents while
    3 of them cannot be cited would have the administrator adopt something other than what
    they think they are adopting."""
    store = _Store({"v-one": _version("v-one", [], tip="abc123")})
    surface = _console(
        store, _syncer(["/endorsed/acme-standards/a.md"], uncitable=("preamble.md",))
    )

    body = (
        TestClient(surface.app)
        .post("/console/endorsed-sources/acme-standards/review", headers=_admin(surface))
        .json()
    )

    assert body["uncitable"] == ["preamble.md"]


def test_row_e12_a_failed_sync_reports_which_of_the_three_states_it_was() -> None:
    """FR-018's distinction survives the route rather than collapsing into "review failed"."""

    def failing(**kwargs: Any) -> Any:
        raise SyncFailed("holds nothing", reason_code="source_empty")

    surface = _console(_Store(), failing)
    response = TestClient(surface.app).post(
        "/console/endorsed-sources/acme-standards/review", headers=_admin(surface)
    )

    assert response.status_code == 502
    assert "source_empty" in response.text


def test_row_e12_a_non_administrator_cannot_review() -> None:
    surface = _console(_Store(), _syncer([]))
    response = TestClient(surface.app).post(
        "/console/endorsed-sources/acme-standards/review", headers=surface.bearer()
    )

    assert response.status_code == 403


def test_row_e12_reviewing_a_source_that_is_not_endorsed_is_404_not_a_sync() -> None:
    """Otherwise the route is an arbitrary-URL fetcher wearing a console's clothes — the exact
    thing ADR-0070 bounds by naming the endorsement record as the reachable set."""
    reached: list[str] = []

    def sync(**kwargs: Any) -> Any:
        reached.append(kwargs["location"])
        raise AssertionError("must not be reached")

    surface = _console(_Store(), sync)
    response = TestClient(surface.app).post(
        "/console/endorsed-sources/somebody-elses-repo/review", headers=_admin(surface)
    )

    assert response.status_code == 404
    assert reached == []


# ── E13: a source that moved again is reviewed against current upstream ───────────────────


def test_row_e13_the_candidate_is_synced_at_review_time() -> None:
    """The spec's own edge case, and the only reading under which review-then-adopt is honest.

    A candidate synced when drift was *detected* would have the administrator approving a
    state of the world from days ago. Syncing at review time means what they looked at is
    what is currently upstream.
    """
    calls: list[str] = []

    def sync(**kwargs: Any) -> tuple[SyncedVersion, SyncOutcome]:
        calls.append(kwargs["source"])
        tip = f"tip-{len(calls)}"
        version = _version(f"v-{len(calls)}", ["/endorsed/acme-standards/a.md"], tip=tip)
        return version, SyncOutcome(
            version_id=version.version_id,
            source=kwargs["source"],
            upstream_tip=tip,
            document_count=1,
        )

    surface = _console(_Store(), sync)
    client = TestClient(surface.app)

    first = client.post(
        "/console/endorsed-sources/acme-standards/review", headers=_admin(surface)
    ).json()
    second = client.post(
        "/console/endorsed-sources/acme-standards/review", headers=_admin(surface)
    ).json()

    assert first["upstream_tip"] != second["upstream_tip"]
    assert len(calls) == 2


# ── E14: adoption moves the next answer and is recorded; ignoring it changes nothing ──────


def test_row_e14_adoption_labels_the_version_and_records_who_and_when() -> None:
    """FR-017e. An adoption renews the trust statement, so it is authored like one."""
    store = _Store()
    submitter = _Submitter()
    surface = _console(store, _syncer([]), submitter=submitter)

    response = TestClient(surface.app).post(
        "/console/endorsed-sources",
        json={"operation": "adopt", "source": "acme-standards", "version_id": "v-two"},
        headers=_admin(surface),
    )

    assert response.status_code == 200
    entry = submitter.submitted[0].payload["acme-standards"]
    assert entry["adopted_version"] == "v-two"
    assert entry["adopted_by"] == ADMIN
    assert store.adoptions == [("acme-standards", "v-two")]


def test_row_e14_declining_to_adopt_changes_nothing() -> None:
    """The whole point of the flag being a notification.

    An administrator who reviews and walks away leaves the estate exactly as it was: the
    adopted version unchanged, the candidate sitting in the store uncited.
    """
    adopted = _version("v-one", ["/endorsed/acme-standards/a.md"], tip="abc123", state=ADOPTED)
    store = _Store({"v-one": adopted})
    surface = _console(
        store, _syncer(["/endorsed/acme-standards/a.md", "/endorsed/acme-standards/c.md"])
    )

    TestClient(surface.app).post(
        "/console/endorsed-sources/acme-standards/review", headers=_admin(surface)
    )

    assert store.versions["v-one"].state == ADOPTED
    assert store.versions["v-two"].state == CANDIDATE
    assert store.adoptions == []


def test_row_e14_an_added_document_needs_no_fresh_endorsement() -> None:
    """FR-002a — clarify Q1's answer: the source is endorsed as a whole.

    A document added upstream becomes citable when the version containing it is adopted.
    Requiring a per-document endorsement would make the model unusable for a living
    repository and would put the administrator in the position of vouching for text they
    have not read, one file at a time.
    """
    difference = compare_versions(
        adopted=["/endorsed/acme-standards/a.md"],
        candidate=["/endorsed/acme-standards/a.md", "/endorsed/acme-standards/new.md"],
    )

    assert difference["added"] == ("/endorsed/acme-standards/new.md",)
    # The endorsement record is untouched by an adoption's content: what changes is which
    # version the record points at, never a per-document list.
    assert "documents" not in _entry()


@pytest.mark.parametrize("moved", [True, False])
def test_a_flag_reports_movement_only_when_both_tips_are_known(moved: bool) -> None:
    flag = DriftFlag(
        source="acme",
        upstream_tip="def" if moved else "abc",
        adopted_tip="abc",
        detected_at="2026-08-07T00:00:00+00:00",
    )
    assert flag.moved is moved
