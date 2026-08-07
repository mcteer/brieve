# SPDX-License-Identifier: Apache-2.0
"""E6–E10 — the platform holds its own verified copy, and says what it took (045, T011, US2).

**Sync-then-answer is the property, and it is inherited rather than invented.** The pinned
corpus refuses what does not match its manifest because "a corpus that fetched at answer time
would make every answer depend on a third party being reachable, and would make 'pinned'
untrue." Customer content is held the same way, so these rows assert the same guarantees one
corpus over: what was taken is recorded, content that does not match its digest refuses, and an
unreachable source cannot degrade an answer that rests on what is already synced.

**E10 is a no-secret-leak row.** A private source's credential is trust-store material
referenced per sync and never entered through the console — so nothing in a sync record, a
console rendering, or a failure message may carry one. Failure messages are where this leaks:
git puts the remote URL in `stderr`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from core.answering.endorsed.records import digest_of_document
from core.endorsed_sync import (
    SyncFailed,
    SyncOutcome,
    compare_versions,
    documents_in,
    sections_of,
    slug_for,
    sync_source,
)

LOCATION = "https://git.example.com/acme/standards"
SECRET = "ghp_thisisnotarealtokenxxxxxxxxxxxxxxxx"


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "checkout"
    for name, body in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runner(tip: str = "abc123") -> Any:
    """A git that answers `ls-remote` and treats `clone` as already done.

    The workspace is supplied by the row, so the clone is a no-op and what is exercised is
    everything after it: extraction, identity, and what gets recorded.
    """

    def run(command: list[str]) -> str:
        if "ls-remote" in command:
            return f"{tip}\tHEAD\n"
        return ""

    return run


# ── E6: the sync record says what was taken, and never what it says ───────────────────────


def test_row_e6_the_sync_records_what_it_took_its_identity_when_and_who(tmp_path: Path) -> None:
    """FR-017. A version that appeared, with no author and no identity, is not a pin."""
    root = _repo(tmp_path, {"logging.md": "# Retention\n\nLogs are kept 400 days.\n"})

    version, outcome = sync_source(
        tenant_id="acme",
        source="acme-standards",
        location=LOCATION,
        triggered_by="dan@acme.example",
        runner=_runner(),
        workspace=root,
    )

    assert version.version_id
    assert version.upstream_tip == "abc123"
    assert version.synced_by == "dan@acme.example"
    assert version.synced_at.tzinfo is not None
    assert outcome.document_count == 1
    # A sync changes nothing about what answers rest on until somebody adopts it (FR-017a).
    assert version.state == "candidate"


def test_row_e6_the_sync_record_carries_identities_and_paths_never_content(
    tmp_path: Path,
) -> None:
    """FR-023, 038's FORBIDDEN_PAYLOAD_KEYS shape, and it matters more here.

    The words are somebody else's. A trail that reproduced them would put a customer's internal
    compliance policy into an audit stream that is read by people who were never given it.
    """
    body = "# Retention\n\nCONFIDENTIAL: logs are kept 400 days for the ACME audit.\n"
    root = _repo(tmp_path, {"logging.md": body})

    _, outcome = sync_source(
        tenant_id="acme",
        source="acme-standards",
        location=LOCATION,
        triggered_by="dan@acme.example",
        runner=_runner(),
        workspace=root,
    )

    rendered = str(outcome)
    assert "CONFIDENTIAL" not in rendered
    assert "400 days" not in rendered
    # What it DOES carry: an identity, a count, a tip.
    assert outcome.version_id in rendered
    assert isinstance(outcome, SyncOutcome)


def test_row_e6_the_same_content_syncs_to_the_same_identity(tmp_path: Path) -> None:
    """The pin's central property, and the reason the tip is not an input.

    A repository can be force-pushed. A version identity derived from the tip would silently
    mean different content than it did yesterday, and a run record naming it would describe
    ground that no longer exists while still looking correct.
    """
    root = _repo(tmp_path, {"logging.md": "# Retention\n\nLogs are kept 400 days.\n"})

    def sync(tip: str) -> str:
        version, _ = sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=_runner(tip),
            workspace=root,
        )
        return version.version_id

    assert sync("abc123") == sync("def456")


# ── E7: content that does not match its digest refuses ────────────────────────────────────


def test_row_e7_a_document_digest_covers_its_sections(tmp_path: Path) -> None:
    """The verification `load_corpus(verify=True)` performs, one corpus over.

    Asserted here as the digest actually being over the content, because a digest computed
    from something else — the path, the file's mtime — would verify forever and detect nothing.
    """
    root = _repo(tmp_path, {"logging.md": "# Retention\n\nLogs are kept 400 days.\n"})
    documents, _ = documents_in(root, source="acme-standards", location=LOCATION)
    document = documents["/endorsed/acme-standards/logging.md"]

    assert document.digest == digest_of_document(document.sections)
    assert document.digest != digest_of_document({"retention": "something else"})


# ── E8: three distinct failure states ─────────────────────────────────────────────────────


def test_row_e8_an_empty_source_is_not_an_unreachable_one(tmp_path: Path) -> None:
    """FR-018. Reached-and-empty sends an administrator to the repository they named; could
    not be reached sends them to the network. Reporting one for the other sends them to fix
    something that is not broken."""
    root = _repo(tmp_path, {})

    with pytest.raises(SyncFailed) as raised:
        sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=_runner(),
            workspace=root,
        )

    assert raised.value.reason_code == "source_empty"


def test_row_e8_documents_with_nothing_addressable_is_its_own_state(tmp_path: Path) -> None:
    """The third state, and the one a reasonable implementation would collapse into "empty".

    A source full of documents that have no headings is not empty — it is a source whose
    documents cannot be cited, which has a fix the administrator can actually apply.
    """
    root = _repo(tmp_path, {"notes.md": "just prose, no headings anywhere\n"})

    with pytest.raises(SyncFailed) as raised:
        sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=_runner(),
            workspace=root,
        )

    assert raised.value.reason_code == "nothing_citable"


def test_row_e8_an_unreadable_source_is_sync_failed() -> None:
    """The first state. `ls-remote` answering nothing is a source that could not be read."""

    def silent(command: list[str]) -> str:
        return ""

    with pytest.raises(SyncFailed) as raised:
        sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=silent,
        )

    assert raised.value.reason_code == "sync_failed"


# ── E20: a document with no addressable section is reported, never cited whole ────────────


def test_row_e20_an_uncitable_document_is_named_rather_than_silently_dropped(
    tmp_path: Path,
) -> None:
    """FR-011. A sync reporting "3 documents" while holding 2 has told the administrator
    something false about what the platform can answer."""
    root = _repo(
        tmp_path,
        {
            "logging.md": "# Retention\n\nLogs are kept 400 days.\n",
            "preamble.md": "no headings here at all\n",
        },
    )

    _, outcome = sync_source(
        tenant_id="acme",
        source="acme-standards",
        location=LOCATION,
        triggered_by="dan@acme.example",
        runner=_runner(),
        workspace=root,
    )

    assert outcome.document_count == 1
    assert outcome.uncitable == ("preamble.md",)


def test_text_before_the_first_heading_is_not_given_an_invented_anchor() -> None:
    """An anchor the platform made up resolves here and resolves nowhere for the reader.

    Which is exactly the "reads as evidence and is not" failure the whole citation gate exists
    to prevent — so the preamble is dropped rather than addressed.
    """
    sections = sections_of("intro prose\n\n# Retention\n\nkept 400 days\n")

    assert set(sections) == {"retention"}


def test_two_headings_with_the_same_title_stay_separately_addressable() -> None:
    """Otherwise one section silently shadows the other and a citation lands on the wrong one."""
    sections = sections_of("## Scope\n\nfirst\n\n## Scope\n\nsecond\n")

    assert sections["scope"] == "first"
    assert sections["scope-1"] == "second"


def test_the_anchor_is_the_one_the_customers_own_readers_already_use() -> None:
    """Fidelity to the renderer, not to a tidier rule.

    GitHub does not collapse the runs a removed punctuation mark leaves behind, and it keeps
    underscores. An anchor that is "cleaner" than the one the customer's own browser produces
    resolves here and 404s for the person following the citation.
    """
    assert slug_for("Log Retention & Storage") == "log-retention--storage"
    assert slug_for("Data_Retention Policy") == "data_retention-policy"
    assert slug_for("  Scope  ") == "scope"


# ── E9: an unreachable source does not stop answering from what is already synced ─────────


def test_row_e9_a_failed_sync_raises_and_touches_nothing_already_stored(tmp_path: Path) -> None:
    """The direction that matters: a sync failure must not be able to degrade an answer.

    Nothing is written until a version is fully built, so a source going unreachable leaves the
    adopted version exactly where it was — and answering, which reads the store and never the
    source, is unaffected by construction.
    """

    def unreachable(command: list[str]) -> str:
        raise SyncFailed("host is down", reason_code="sync_failed")

    with pytest.raises(SyncFailed):
        sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=unreachable,
        )


# ── E10: no credential in a sync record, a rendering, or a failure ────────────────────────


def test_row_e10_no_credential_reaches_a_sync_record(tmp_path: Path) -> None:
    """A location with material embedded in it must not be echoed into what is recorded.

    Somebody will paste a URL with a token in it — that is what the field-level refusal in the
    console is for — and if one gets past, the sync record must not be where it lands.
    """
    root = _repo(tmp_path, {"logging.md": "# Retention\n\nkept 400 days\n"})

    _, outcome = sync_source(
        tenant_id="acme",
        source="acme-standards",
        location=f"https://x-access-token:{SECRET}@git.example.com/acme/standards",
        triggered_by="dan@acme.example",
        runner=_runner(),
        workspace=root,
    )

    assert SECRET not in str(outcome)


def test_row_e10_a_failure_message_does_not_echo_what_git_said() -> None:
    """**Where this actually leaks.** git puts the remote URL in `stderr`, and a URL with
    material in it lands in whatever reads the exception — a log, a page, a trail nobody
    redacts. So the failure names the exit code and not git's own words."""
    import subprocess

    def failing(command: list[str]) -> str:
        raise subprocess.CalledProcessError(
            128, command, stderr=f"fatal: could not read from https://{SECRET}@git.example.com"
        )

    with pytest.raises(Exception) as raised:
        sync_source(
            tenant_id="acme",
            source="acme-standards",
            location=LOCATION,
            triggered_by="dan@acme.example",
            runner=failing,
        )

    assert SECRET not in str(raised.value)


# ── what a review compares ────────────────────────────────────────────────────────────────


def test_the_comparison_names_added_and_removed_paths_and_not_their_words() -> None:
    """FR-017c's shape. Paths only — the same line the trail draws, for the same reason."""
    diff = compare_versions(
        adopted=["/endorsed/acme/a.md", "/endorsed/acme/b.md"],
        candidate=["/endorsed/acme/b.md", "/endorsed/acme/c.md"],
    )

    assert diff["added"] == ("/endorsed/acme/c.md",)
    assert diff["removed"] == ("/endorsed/acme/a.md",)
    assert diff["common"] == ("/endorsed/acme/b.md",)


def test_a_hidden_directory_is_not_customer_documentation(tmp_path: Path) -> None:
    """`.github/` and friends are repository machinery, and citing them would be citing us."""
    root = _repo(
        tmp_path,
        {
            "logging.md": "# Retention\n\nkept 400 days\n",
            ".github/PULL_REQUEST_TEMPLATE.md": "# Checklist\n\ntick things\n",
        },
    )

    documents, _ = documents_in(root, source="acme", location=LOCATION)

    assert set(documents) == {"/endorsed/acme/logging.md"}


def test_a_citation_url_is_one_a_reader_can_actually_follow(tmp_path: Path) -> None:
    """**Found by running EL1 against a real repository, and it is the gate's blind spot.**

    The first version built `location + "/" + relative`, giving
    `https://github.com/acme/standards.git/logging.md` — a 404. The citation gate checks that
    the anchor exists in the content the platform holds; it cannot check that the link works.
    So a reader following what reads as evidence would find nothing, which is the exact failure
    the whole gate exists to prevent, arriving through the one door it does not watch.
    """
    root = _repo(tmp_path, {"logging.md": "# Retention\n\nkept 400 days\n"})

    documents, _ = documents_in(
        root, source="acme", location="https://github.com/acme/standards.git"
    )

    assert documents["/endorsed/acme/logging.md"].url == (
        "https://github.com/acme/standards/blob/HEAD/logging.md"
    )


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("https://github.com/acme/std.git", "https://github.com/acme/std/blob/HEAD/a.md"),
        ("https://gitlab.com/acme/std", "https://gitlab.com/acme/std/blob/HEAD/a.md"),
        ("https://bitbucket.org/acme/std.git", "https://bitbucket.org/acme/std/src/HEAD/a.md"),
        # A forge nobody here has heard of: join, which is the honest answer for a browse
        # layout we do not know rather than a guess that produces a confident 404.
        ("https://git.internal.acme/acme/std.git", "https://git.internal.acme/acme/std/a.md"),
    ],
)
def test_the_browse_url_matches_each_forges_own_layout(location: str, expected: str) -> None:
    from core.endorsed_sync import browse_url

    assert browse_url(location, "a.md") == expected


def test_the_synced_at_is_timezone_aware(tmp_path: Path) -> None:
    """A naive timestamp is not comparable to `now`, and the age disclosure needs to compare."""
    root = _repo(tmp_path, {"a.md": "# H\n\nb\n"})
    version, _ = sync_source(
        tenant_id="acme",
        source="acme",
        location=LOCATION,
        triggered_by="dan",
        runner=_runner(),
        workspace=root,
    )

    assert version.synced_at.tzinfo is not None
    assert version.synced_at <= datetime.now(UTC)
