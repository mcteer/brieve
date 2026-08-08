# SPDX-License-Identifier: Apache-2.0
"""Syncing an endorsed source — the only place the platform reaches a customer's repository.

**This is the code ADR-0070 exists for.** Principle II limits non-tool egress to enumerated
classes, and syncing an endorsed source is non-tool egress from a served process, which none of
them covers. The record adds the class with its bounds, and this module is where they hold:
only sources named in the endorsement record, only during detection / review-sync /
endorsement-sync, **never during answering**, read-only.

**Sync-then-answer, never fetch-at-answer.** The pinned corpus's reasoning, unchanged: a corpus
that fetched at answer time would make every answer depend on a third party being reachable and
would make "pinned" untrue. So this writes an immutable version into the store, and the
answering path reads that version and nothing else. `git` is the transport because it is the
transport a customer's documents already have (Principle I — build glue only; ADR-0066's
adopted-CLI posture).

**What is recorded and what is not.** The sync records what it took, its identity, when, and
who triggered it. It records **no document content** into the trail — 038's finding, and it
applies here with more force than it did there, because the content is somebody else's.

**Why this is not under `surfaces/` and not under `answering/`, both of which were tried.**
`test_the_cli_is_withdrawn.py` asserts `src/surfaces` holds exactly the three transports plus
the dispatch seam, and it caught a `surfaces/sync` package on the first run — correctly, because
a transport is how the outside reaches us and this is the one place we reach the outside.
`core/answering/` was the other candidate and is worse: the package name would say *answering*
about code whose defining bound is that it never runs during answering.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from core.answering.endorsed.corpus import endorsed_path
from core.answering.endorsed.records import (
    CANDIDATE,
    EndorsedDocument,
    SyncedVersion,
    compute_version_id,
    digest_of_document,
)

#: What is treated as a document. Not a general importer: a customer's compliance policies and
#: architecture standards are prose, and prose that a citation can address is prose with
#: headings. Widening this is a decision about what the platform will claim to have read.
DOCUMENT_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".markdown"})

#: How long a clone may take before the sync is reported as failed. Bounded because an
#: administrator is watching a page, and an unbounded fetch against an unreachable host is
#: indistinguishable to them from the platform having hung.
CLONE_TIMEOUT_SECONDS: Final[float] = 120.0

_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


class SyncFailed(RuntimeError):
    """The source could not be synced. **Four distinct states, never collapsed** (FR-018).

    `sync_failed` (it could not be reached or read), `source_empty` (it was reached and holds
    nothing), and `nothing_citable` (it holds documents and none of them can be addressed) send
    an administrator to three different places: the network, the wrong repository, and the
    documents' own structure. An interface reporting one for another sends them to fix
    something that is not broken.

    **`tooling_missing` is the fourth, and it is about us rather than about them.** The served
    API is a Python image; if it carries no `git` there is nothing to fix at the customer's end,
    and reporting that as `sync_failed` would send an administrator to check a repository that
    was never the problem. The authoring tier already draws this line — it verifies `git` and
    `gh` at task start and exits `tooling_missing` rather than failing at the last step of a run
    that had already done all its work. This is the same distinction one surface over.
    """

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class SyncOutcome:
    """What a sync did, in the shape the trail and the console both want.

    Identities and counts. **No content** — see the module note.
    """

    version_id: str
    source: str
    upstream_tip: str
    document_count: int
    #: Documents found and skipped because nothing in them can be addressed by a citation.
    #: Reported rather than silently dropped: a source whose documents have no headings is a
    #: real state with a real fix, and a sync that says "12 documents" when 5 of them are
    #: uncitable has told the administrator something false about what can be answered.
    uncitable: tuple[str, ...] = ()
    synced_at: str = ""


def slug_for(heading: str) -> str:
    """The anchor a heading is addressable by — GitHub's rule, because that is where the
    customer's readers already follow their own links.

    Deriving the anchor rather than requiring one is what makes ordinary Markdown citable
    without asking a customer to annotate their documents for us.
    """
    lowered = heading.strip().lower()
    kept = re.sub(r"[^\w\s-]", "", lowered, flags=re.UNICODE)
    # **One hyphen per space, runs NOT collapsed**, and underscores kept — which is GitHub's
    # actual behaviour rather than the tidier rule it is easy to assume. Getting this wrong
    # produces an anchor that resolves here and 404s in the customer's own browser, which is
    # the citation-that-lands-nowhere failure arriving through the back door.
    return re.sub(r"\s", "-", kept).strip("-")


def sections_of(text: str) -> dict[str, str]:
    """Split a Markdown document into addressable sections, keyed by anchor.

    Text before the first heading is deliberately **dropped**, not attached to a synthetic
    anchor. A citation must point at something a reader can find on the page; an anchor the
    platform invented would resolve here and resolve nowhere for the person following it,
    which is precisely the "reads as evidence and is not" failure the citation gate exists to
    prevent.

    A duplicated heading takes a numeric suffix, matching what a renderer does, so two sections
    with the same title stay separately addressable instead of one silently shadowing the other.
    """
    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    seen: dict[str, int] = {}

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if current is not None:
                sections[current] = "\n".join(body).strip()
            base = slug_for(match.group(2))
            if not base:
                current, body = None, []
                continue
            count = seen.get(base, 0)
            seen[base] = count + 1
            current = base if count == 0 else f"{base}-{count}"
            body = []
        elif current is not None:
            body.append(line)

    if current is not None:
        sections[current] = "\n".join(body).strip()
    return {anchor: text for anchor, text in sections.items() if text}


def documents_in(
    root: Path, *, source: str, location: str, ref: str = "HEAD"
) -> tuple[dict[str, EndorsedDocument], list[str]]:
    """Read a checkout into citable documents, and name what could not be made citable.

    Returns both, because the second is not an error and is not nothing: FR-011 says a document
    with no addressable sections is not cited whole, and E20 asserts the platform says so
    rather than quietly holding fewer documents than the administrator believes it holds.
    """
    documents: dict[str, EndorsedDocument] = {}
    uncitable: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue

        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            uncitable.append(relative)
            continue

        sections = sections_of(text)
        if not sections:
            # **Never cited whole.** A document with no heading has nothing a citation can
            # address, and pointing at the file as a unit would produce a link that lands
            # somewhere no claim was made.
            uncitable.append(relative)
            continue

        citation_path = endorsed_path(source, relative)
        documents[citation_path] = EndorsedDocument(
            path=citation_path,
            url=browse_url(location, relative, ref=ref),
            digest=digest_of_document(sections),
            anchors=frozenset(sections),
            sections=sections,
        )

    return documents, uncitable


def browse_url(location: str, relative: str, *, ref: str = "HEAD") -> str:
    """Where a person can READ this document — which is not where the platform cloned it from.

    **Found by running EL1 against a real repository.** The first version was
    `location + "/" + relative`, which produces `https://github.com/acme/standards.git/logging.md`
    — a 404. A citation that resolves inside the platform and 404s in the reader's browser is
    precisely the "reads as evidence and is not" failure the whole citation gate exists to
    prevent, arriving through the one door the gate cannot see: the gate checks that the
    *anchor exists in the content we hold*, and cannot check that the *link works*.

    Hosted forges put a blob path in between; everything else — a local path, a bare mirror, a
    server nobody here has heard of — falls back to joining, which is the honest answer for a
    location whose browse layout we do not know.
    """
    base = location.rstrip("/")
    if base.endswith(".git"):
        base = base[: -len(".git")]
    branch = "HEAD" if ref == "HEAD" else ref
    for forge in ("github.com", "gitlab.com", "bitbucket.org"):
        if forge in base:
            segment = "src" if forge == "bitbucket.org" else "blob"
            return f"{base}/{segment}/{branch}/{relative}"
    return f"{base}/{relative}"


def remote_tip(location: str, *, ref: str = "HEAD", runner: Any = None) -> str:
    """What the source says it is, **without transferring content** (FR-017a, research R5).

    A refs listing is the whole of detection. Cheap enough to ride the health checker's
    existing cadence, which is why this feature operates no scheduler of its own.
    """
    result = _run(["git", "ls-remote", "--exit-code", location, ref], runner=runner, timeout=30.0)
    line = result.strip().splitlines()[0] if result.strip() else ""
    tip = line.split()[0] if line else ""
    if not tip:
        raise SyncFailed(
            f"{location} did not report a tip for {ref}; the source could not be read",
            reason_code="sync_failed",
        )
    return tip


def sync_source(
    *,
    tenant_id: str,
    source: str,
    location: str,
    triggered_by: str,
    ref: str = "HEAD",
    state: str = CANDIDATE,
    runner: Any = None,
    workspace: Path | None = None,
) -> tuple[SyncedVersion, SyncOutcome]:
    """Fetch a source at its current tip and build an immutable version from it.

    **Lands as a `candidate` by default** — a sync changes nothing about what answers rest on.
    Adoption is a separate act by a person (FR-017a: detect is not adopt), and a sync that
    adopted what it found would make the administrator's decision by the act of looking.

    The clone is `--depth 1`: history is not what is being pinned, content is, and the version
    identity is computed over the content precisely so that a force-push cannot change what a
    pinned version means.
    """
    tip = remote_tip(location, ref=ref, runner=runner)

    temporary = workspace is None
    target = (
        Path(workspace) if workspace is not None else Path(tempfile.mkdtemp(prefix="endorsed-"))
    )
    try:
        if runner is not None or workspace is None:
            _run(
                ["git", "clone", "--depth", "1", "--branch", ref, location, str(target)]
                if ref != "HEAD"
                else ["git", "clone", "--depth", "1", location, str(target)],
                runner=runner,
                timeout=CLONE_TIMEOUT_SECONDS,
            )

        documents, uncitable = documents_in(target, source=source, location=location, ref=ref)

        if not documents and not uncitable:
            raise SyncFailed(
                f"{source} was reached and holds no documents. The source is readable and "
                f"empty — a different problem from being unreachable, and usually a different "
                f"repository than the one intended.",
                reason_code="source_empty",
            )
        if not documents:
            raise SyncFailed(
                f"{source} holds {len(uncitable)} document(s) and none of them can be cited: "
                f"nothing in them is addressable by a heading. The platform will not cite a "
                f"document whole, because a citation that lands nowhere reads as evidence.",
                reason_code="nothing_citable",
            )

        now = datetime.now(UTC)
        version = SyncedVersion(
            version_id=compute_version_id(source, documents),
            tenant_id=tenant_id,
            source=source,
            upstream_tip=tip,
            synced_at=now,
            synced_by=triggered_by,
            state=state,
            documents=documents,
        )
        outcome = SyncOutcome(
            version_id=version.version_id,
            source=source,
            upstream_tip=tip,
            document_count=len(documents),
            uncitable=tuple(sorted(uncitable)),
            synced_at=now.isoformat(),
        )
        return version, outcome
    finally:
        if temporary:
            shutil.rmtree(target, ignore_errors=True)


def compare_versions(
    adopted: Iterable[str], candidate: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """What a review shows: added, removed, and the paths present in both (FR-017c).

    Paths only. The console renders which documents moved and does not reproduce their words —
    the same line the trail draws, for the same reason.
    """
    before, after = set(adopted), set(candidate)
    return {
        "added": tuple(sorted(after - before)),
        "removed": tuple(sorted(before - after)),
        "common": tuple(sorted(before & after)),
    }


def git_available() -> bool:
    """Whether this process can reach a customer's repository at all.

    Public so an assembly can state the posture at start rather than discovering it when an
    administrator clicks Review — see `SyncFailed`'s note about which end the problem is at.
    """
    return shutil.which("git") is not None


def _run(command: list[str], *, runner: Any = None, timeout: float) -> str:
    """Run a git command, and turn every failure into one named refusal.

    `runner` is an injection seam so a row can exercise the sync without a network or a
    repository — the same shape every other outbound caller in this tree takes, and the reason
    the hermetic rows can say something about a path whose live behaviour needs a real source.
    """
    if runner is not None:
        return str(runner(command))
    if not git_available():
        raise SyncFailed(
            "this deployment has no `git`, so it cannot reach an endorsed source. Nothing is "
            "wrong with the source: the platform is missing its transport.",
            reason_code="tooling_missing",
        )
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            # A credential prompt in a served process hangs forever. Failing is the behaviour
            # a private source must produce here: its material is trust-store material
            # referenced per sync, never typed into the console (FR-018b).
            env={"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
    except (OSError, subprocess.SubprocessError) as failure:
        raise SyncFailed(
            f"the source could not be reached: {type(failure).__name__}", reason_code="sync_failed"
        ) from failure
    if completed.returncode != 0:
        # `stderr` is not echoed: it can carry a URL with material embedded in it, and a
        # failure message is exactly the place a credential leaks into a trail nobody redacts.
        raise SyncFailed(
            f"the source could not be read (git exited {completed.returncode})",
            reason_code="sync_failed",
        )
    return completed.stdout
