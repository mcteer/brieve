# SPDX-License-Identifier: Apache-2.0
"""EL1's transport half — a real `git clone`, on the host (045, T026).

**This is the only place the transport is actually exercised.** Everywhere else in this
feature the clone is stubbed so the row can be about extraction, identity or the store — which
is right, and leaves exactly one thing unasserted: that the argument construction, the depth
flag, the branch selection and the terminal-prompt suppression produce a working checkout. A
feature whose only outbound operation is never performed is 041's "correct, tested, wired to
nothing" in the one place it would be hardest to notice, because everything downstream of it
is proved.

**`host_enclave`, and the split is forced.** The store rows need an attested workload identity,
so they run inside a Nomad allocation — whose image is a Python image with no `git`, and the
authoring tier already settled that a runtime `apt-get` inside a task handling repository
content is refused. So the transport is proved here, where git exists, and needs no database.

These rows fail rather than skip when git is absent: a transport row that quietly did not run
is the same as not having one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from core.endorsed_sync import SyncFailed, remote_tip, sync_source

pytestmark = pytest.mark.host_enclave


@pytest.fixture
def origin(tmp_path: Path) -> str:
    """A real bare repository, made by real `git`, holding real Markdown."""
    if shutil.which("git") is None:
        pytest.fail(
            "the endorsed-content transport cannot be exercised without `git`. This row is "
            "not skippable: a transport nobody performed is a transport nobody has tested."
        )

    work = tmp_path / "acme-standards"
    work.mkdir()
    (work / "logging.md").write_text(
        "# Log retention at Acme\n\n"
        "## Retention period\n\n"
        "Audit output is retained for exactly 400 days.\n"
    )
    (work / "README").write_text("not markdown, so not a document at all\n")

    def git(*args: str, cwd: Path = work) -> None:
        subprocess.run(  # noqa: S603
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git(
        "-c",
        "user.email=dan@acme.example",
        "-c",
        "user.name=Dan",
        "commit",
        "-qm",
        "acme standards",
    )

    bare = tmp_path / "acme-standards.git"
    subprocess.run(  # noqa: S603
        ["git", "clone", "-q", "--bare", str(work), str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(bare)


def test_el1_a_real_repository_syncs_into_a_citable_version(origin: str) -> None:
    """The transport, end to end: clone, extract, address, identify.

    Everything here comes from the real code path — `git clone --depth 1` into a temporary
    directory that is then removed, headings turned into the anchors a reader's own browser
    would produce, and an identity computed over the content.
    """
    version, outcome = sync_source(
        tenant_id="acme",
        source="acme-standards",
        location=origin,
        triggered_by="dan@acme.example",
    )

    path = "/endorsed/acme-standards/logging.md"
    assert set(version.documents) == {path}
    # `# Log retention at Acme` is followed immediately by the next heading, so it holds no
    # text and is NOT an anchor. That is the rule working rather than a gap: a citation
    # pointing at a heading the platform holds no words for could never support a claim, and
    # would resolve while proving nothing.
    assert version.documents[path].anchors == {"retention-period"}
    assert "400 days" in version.documents[path].text_at("retention-period")
    assert version.upstream_tip == remote_tip(origin)
    assert outcome.document_count == 1
    # `README` has no `.md` suffix, so it is not a document at all — distinct from a Markdown
    # file with no headings, which IS a document and is reported as uncitable.
    assert outcome.uncitable == ()


def test_el1_the_same_upstream_syncs_to_the_same_identity_twice(origin: str) -> None:
    """Two real clones of unchanged content produce one identity.

    The property every pin rests on, asserted against the transport rather than against a
    dictionary: if a clone introduced any per-run variation — a timestamp, an ordering, a line
    ending — the identity would differ each time and "this run read what that run read" would
    be unanswerable.
    """
    first, _ = sync_source(
        tenant_id="acme", source="acme-standards", location=origin, triggered_by="dan"
    )
    second, _ = sync_source(
        tenant_id="acme", source="acme-standards", location=origin, triggered_by="dan"
    )

    assert first.version_id == second.version_id


def test_el1_the_working_directory_does_not_outlive_the_sync(origin: str) -> None:
    """The clone is temporary, and nothing of the customer's content is left on the disk.

    An allocation filesystem does not survive rescheduling anyway; what matters is that a
    sync does not accumulate copies of somebody else's documents in a directory nobody
    watches.
    """
    before = {p.name for p in Path("/tmp").glob("endorsed-*")}  # noqa: S108

    sync_source(tenant_id="acme", source="acme-standards", location=origin, triggered_by="dan")

    after = {p.name for p in Path("/tmp").glob("endorsed-*")}  # noqa: S108
    assert after <= before, f"the sync left {after - before} behind"


def test_el1_an_unreachable_source_fails_without_echoing_what_git_said(tmp_path: Path) -> None:
    """The failure path, against real `git` rather than a scripted one.

    git puts the remote URL in `stderr`, and a URL can carry material in it — so the refusal
    names an exit code and not git's own words. Asserted here because a hermetic row can only
    check what a stub was told to say.
    """
    missing = str(tmp_path / "there-is-no-repository-here")

    with pytest.raises(SyncFailed) as raised:
        sync_source(tenant_id="acme", source="acme-standards", location=missing, triggered_by="dan")

    assert raised.value.reason_code == "sync_failed"
    assert "fatal" not in str(raised.value).lower()


def test_el1_a_source_holding_no_markdown_is_empty_rather_than_unreachable(
    tmp_path: Path,
) -> None:
    """FR-018's distinction, against a real repository that really has nothing to cite."""
    if shutil.which("git") is None:
        pytest.fail("git is required; see the fixture")

    work = tmp_path / "empty-standards"
    work.mkdir()
    (work / "notes.txt").write_text("nothing citable here\n")
    subprocess.run(  # noqa: S603
        ["git", "init", "-q", "-b", "main"], cwd=work, check=True, capture_output=True, text=True
    )
    subprocess.run(  # noqa: S603
        ["git", "add", "-A"], cwd=work, check=True, capture_output=True, text=True
    )
    subprocess.run(  # noqa: S603
        [
            "git",
            "-c",
            "user.email=dan@acme.example",
            "-c",
            "user.name=Dan",
            "commit",
            "-qm",
            "nothing",
        ],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(SyncFailed) as raised:
        sync_source(tenant_id="acme", source="empty", location=str(work), triggered_by="dan")

    assert raised.value.reason_code == "source_empty"
