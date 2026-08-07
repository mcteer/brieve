# SPDX-License-Identifier: Apache-2.0
"""E4 — content becomes citable ONLY through an endorsement (045, T009, US1, FR-021).

**The one thing this feature must make impossible.** Everything else here is about doing a
capability well; this is about the capability not existing without the governance that
justifies it. Synced content that nobody endorsed is *present* — it is in the store, it has a
version, it has documents — and it must resolve nothing.

**The row is built to be able to lose** (044's C20 shape, third use). `test_the_gate_can_lose`
rigs the endorsement check out and asserts the content becomes citable. If that row ever
passes with the gate *in place*, the gate is not doing anything and every other row here is
green about nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.answering.endorsed.corpus import build_endorsed_corpus
from core.answering.endorsed.records import (
    ADOPTED,
    CANDIDATE,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from core.authority.endorsed_sources import citable_sources

SECTIONS = {"retention": "Logs are retained for 400 days."}
PATH = "/endorsed/acme-standards/logging.md"


def _document() -> EndorsedDocument:
    return EndorsedDocument(
        path=PATH,
        url="https://git.example.com/acme/standards/logging.md",
        digest=digest_of_document(SECTIONS),
        anchors=frozenset(SECTIONS),
        sections=dict(SECTIONS),
    )


def _version(version_id: str = "v-one", state: str = ADOPTED) -> SyncedVersion:
    return SyncedVersion(
        version_id=version_id,
        tenant_id="acme",
        source="acme-standards",
        upstream_tip="abc123",
        synced_at=datetime(2026, 8, 1, tzinfo=UTC),
        synced_by="dan@acme.example",
        state=state,
        documents={PATH: _document()},
    )


def _endorsement(**over: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "location": "https://git.example.com/acme/standards",
        "endorsed_by": "dan@acme.example",
        "endorsed_at": "2026-08-01T00:00:00+00:00",
        "adopted_version": "v-one",
    }
    entry.update(over)
    return {"acme-standards": entry}


def _resolvable(record: dict[str, Any] | None, versions: list[SyncedVersion]) -> bool:
    """What the answering path does, in miniature: the endorsement decides, the store supplies.

    Written out here rather than imported so this row asserts the *composition* — an
    implementation that read the store and forgot to consult the record would satisfy any
    check that only exercised one of them.
    """
    citable = citable_sources(record)
    admitted = [
        version
        for version in versions
        if version.source in citable
        and version.version_id == citable[version.source].adopted_version
    ]
    return build_endorsed_corpus(admitted).resolves(PATH, "retention")


# ── E4: synced and not endorsed resolves nothing ──────────────────────────────────────────


def test_row_e4_content_synced_without_any_endorsement_resolves_nothing() -> None:
    """The record is empty; the store has the document. It is not citable.

    This is the state a sync bug, a half-finished migration or a restored backup can produce,
    and in every one of them the platform must decline rather than cite material nobody
    vouched for.
    """
    assert not _resolvable(None, [_version()])
    assert not _resolvable({}, [_version()])


def test_row_e4_a_withdrawn_endorsement_resolves_nothing_though_the_content_remains() -> None:
    """Withdrawal is the operation whose failure would be silent.

    The content is still in the store — deliberately, because runs in flight pinned it — so
    "withdrawn" that failed to zero citability would leave everything working and the trust
    statement revoked. Nothing visible would be wrong.
    """
    assert not _resolvable(_endorsement(withdrawn=True), [_version()])


def test_row_e4_a_version_that_was_never_adopted_resolves_nothing() -> None:
    """Detect is not adopt (FR-017a). A candidate is synced content, not endorsed ground.

    Reviewing a change syncs a candidate; if a candidate were citable, opening the review page
    would silently change what answers rest on — the administrator's decision made by the act
    of looking at it.
    """
    assert not _resolvable(
        _endorsement(adopted_version="v-one"), [_version("v-two", state=CANDIDATE)]
    )


def test_row_e4_an_endorsement_of_a_different_source_does_not_admit_this_content() -> None:
    """Endorsement is per source, and the namespace is what keeps that meaningful."""
    record = {
        "some-other-source": {
            "location": "https://git.example.com/other",
            "endorsed_by": "dan@acme.example",
            "adopted_version": "v-one",
        }
    }
    assert not _resolvable(record, [_version()])


def test_row_e4_an_endorsed_and_adopted_source_does_resolve() -> None:
    """The positive control, and it is not decoration.

    Without it, every row above would pass on an implementation that resolved nothing at all —
    which is the way a gate row goes green while the feature is broken.
    """
    assert _resolvable(_endorsement(), [_version()])


# ── the row that must be able to lose ─────────────────────────────────────────────────────


def test_the_gate_can_lose() -> None:
    """044's C20 shape: rig the endorsement check out, and the content becomes citable.

    A safety row that cannot be made to fail proves nothing about the safety. This constructs
    the ungated composition explicitly — every synced version admitted, no record consulted —
    and asserts it resolves, so the difference between the two paths is the gate and only the
    gate.

    **If this ever fails, the check has stopped being the thing that decides**, and the rows
    above have become green about something else.
    """
    ungated = build_endorsed_corpus([_version()])

    assert ungated.resolves(PATH, "retention"), (
        "with the endorsement check removed the content resolves — that is what makes the "
        "rows above assertions about the gate rather than about an empty store"
    )
    assert not _resolvable(None, [_version()]), (
        "and with the check in place the same content resolves nothing"
    )
