# SPDX-License-Identifier: Apache-2.0
"""EL1's store half — the real Postgres and the real digest check (045, T026).

**These rows are not skippable.** A row that passes without the real store reports a
guarantee nobody tested — the durability suite's own rule, and it applies here for a sharper
reason: the endorsed store's central promise is that content which changed underneath its pin
*refuses*, and that promise lives in a `SELECT` and a comparison. An in-memory double would
assert the comparison and say nothing about whether the rows round-trip.

**The clone is exercised in `test_endorsed_clone_host.py`, not here, and the split is forced
by what each environment can do.** These rows need an attested workload identity, so they run
inside a Nomad allocation; that allocation's image is a Python image with no `git`, and the
authoring tier already settled the estate's posture on that — tooling is verified, never
`apt-get`ed at runtime inside a task that handles repository content. So the extraction and
the store are proved here against a checkout on disk, and the real `git clone` is proved on
the host where git exists. Both halves are real; neither pretends to be the other.
"""

from __future__ import annotations

import socket
import uuid
from pathlib import Path

import pytest

from core.answering.endorsed.postgres import DigestMismatch, PostgresEndorsedStore
from core.answering.endorsed.records import ADOPTED, CANDIDATE, SyncedVersion
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.endorsed_sync import SyncOutcome, sync_source

pytestmark = pytest.mark.enclave


def _enclave_reachable() -> bool:
    for host, port in (("127.0.0.1", 5432), ("127.0.0.1", 8200)):
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


@pytest.fixture
def store() -> PostgresEndorsedStore:
    if not _enclave_reachable():
        pytest.fail(
            "endorsed-store conformance requires the local enclave — run `make dev-up`. "
            "Not skippable: a row that passes without the real store reports a guarantee "
            "nobody tested."
        )
    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance")
    built = PostgresEndorsedStore(credentials=credentials)
    built.migrate()
    return built


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """What a clone leaves behind: a directory of the customer's Markdown.

    Supplied rather than cloned, because this lane runs where `git` does not exist — see the
    module note. What it exercises is everything after the transport: heading extraction,
    anchor derivation, digests, identity, and the round trip through Postgres.
    """
    work = tmp_path / "acme-standards"
    work.mkdir()
    (work / "logging.md").write_text(
        "# Log retention at Acme\n\n"
        "## Retention period\n\n"
        "Audit output is retained for exactly 400 days.\n\n"
        "## Storage location\n\n"
        "Archived to `acme-audit-archive` in eu-west-2.\n"
    )
    (work / "notes.md").write_text("prose with no headings, so nothing here can be cited\n")

    return work


def _sync(checkout: Path, source: str, *, tip: str = "abc123") -> tuple[SyncedVersion, SyncOutcome]:
    """One sync over a checkout already on disk, with the transport stubbed and nothing else.

    `runner` answers `ls-remote` and no-ops the clone. Everything the row asserts — anchors,
    digests, the version identity, the rows in Postgres — is produced by the real code.
    """

    def runner(command: list[str]) -> str:
        return f"{tip}\tHEAD\n" if "ls-remote" in command else ""

    version, outcome = sync_source(
        tenant_id="acme",
        source=source,
        location="https://git.example.com/acme/standards",
        triggered_by="dan@acme.example",
        runner=runner,
        workspace=checkout,
    )
    return version, outcome


def test_a_synced_version_round_trips_through_the_store(
    store: PostgresEndorsedStore, checkout: Path
) -> None:
    """The whole leg after the transport: the extractor addresses it, Postgres holds it, and
    what comes back resolves the same citations that went in."""
    source = f"acme-{uuid.uuid4().hex[:8]}"
    version, outcome = _sync(checkout, source)

    store.write_version(version)
    read_back = store.read_version(version.version_id)

    assert read_back is not None
    assert read_back.version_id == version.version_id
    assert read_back.synced_by == "dan@acme.example"
    assert read_back.upstream_tip == version.upstream_tip
    assert set(read_back.documents) == set(version.documents)

    document = read_back.documents[f"/endorsed/{source}/logging.md"]
    assert "retention-period" in document.anchors
    assert "400 days" in document.text_at("retention-period")
    # A document with no heading is not citable and was reported rather than dropped (FR-011).
    assert outcome.uncitable == ("notes.md",)


def test_writing_the_same_version_twice_is_a_no_op(
    store: PostgresEndorsedStore, checkout: Path
) -> None:
    """Immutability, asserted against the real constraint rather than against a dict.

    A repeated sync of unchanged content produces the same identity, so this must not conflict
    — "the same identity means the same content" has to hold in both directions or a pin means
    nothing.
    """
    source = f"acme-{uuid.uuid4().hex[:8]}"
    version, _ = _sync(checkout, source)

    store.write_version(version)
    store.write_version(version)

    read_back = store.read_version(version.version_id)
    assert read_back is not None
    assert len(read_back.documents) == len(version.documents)


def test_content_that_changed_underneath_its_pin_refuses(
    store: PostgresEndorsedStore, checkout: Path
) -> None:
    """**E7 against the real store, and the row this file exists for.**

    A citation into content that no longer matches what was endorsed reads as evidence for
    something nobody vouched for. `CorpusUnavailable`'s posture, one corpus over: a refusal,
    never a fallback.

    The tamper is applied through the store's own connection because that is the only way the
    failure actually happens — somebody or something writing the rows directly. Constructing a
    mismatched object in memory would assert the comparison and nothing about the read.
    """
    source = f"acme-{uuid.uuid4().hex[:8]}"
    version, _ = _sync(checkout, source)
    store.write_version(version)
    path = f"/endorsed/{source}/logging.md"

    def tamper(conn: object) -> None:
        cur = conn.cursor()  # type: ignore[attr-defined]
        cur.execute(
            "UPDATE endorsed_sections SET body = %s WHERE version_id = %s AND path = %s",
            ("Audit output is retained for 30 days.", version.version_id, path),
        )
        conn.commit()  # type: ignore[attr-defined]

    store._run(tamper)  # noqa: SLF001 — the tamper has to go through a real connection

    with pytest.raises(DigestMismatch):
        store.read_version(version.version_id)

    # And the escape hatch exists only so a row can construct the mismatch it asserts about.
    unverified = store.read_version(version.version_id, verify=False)
    assert unverified is not None
    assert "30 days" in unverified.documents[path].text_at("retention-period")


def test_adoption_supersedes_and_deletes_nothing(
    store: PostgresEndorsedStore, checkout: Path
) -> None:
    """Research R3, asserted where it matters: a run that pinned the old version must still be
    able to read it, and its record must keep naming something that exists."""
    source = f"acme-{uuid.uuid4().hex[:8]}"
    first, _ = _sync(checkout, source)
    store.write_version(first)
    store.mark_adopted(tenant_id="acme", source=source, version_id=first.version_id)

    # A second sync of DIFFERENT content, so the identities differ. The file is added to the
    # checkout rather than pushed, for the reason the module note gives.
    (checkout / "incident.md").write_text("# Incident response\n\nPage the on-call.\n")

    second, _ = _sync(checkout, source, tip="def456")
    assert second.version_id != first.version_id
    store.write_version(second)
    store.mark_adopted(tenant_id="acme", source=source, version_id=second.version_id)

    superseded = store.read_version(first.version_id)
    assert superseded is not None, (
        "the superseded version is gone, so a run that pinned it can no longer read its "
        "ground and its record names a version nobody can look at"
    )
    assert superseded.state == "superseded"
    assert store.read_version(second.version_id).state == ADOPTED  # type: ignore[union-attr]
    # Detection compares against what the ADOPTED version recorded, not the newest sync.
    assert store.adopted_tip(tenant_id="acme", source=source) == second.upstream_tip


def test_a_candidate_is_findable_and_is_not_the_adopted_one(
    store: PostgresEndorsedStore, checkout: Path
) -> None:
    """Detect is not adopt, at the storage layer: a review-sync lands as a candidate and the
    adopted tip is unmoved by it."""
    source = f"acme-{uuid.uuid4().hex[:8]}"
    version, _ = _sync(checkout, source)
    store.write_version(version)

    assert store.latest_candidate(tenant_id="acme", source=source) == version.version_id
    assert store.adopted_tip(tenant_id="acme", source=source) is None
    assert store.read_version(version.version_id).state == CANDIDATE  # type: ignore[union-attr]
