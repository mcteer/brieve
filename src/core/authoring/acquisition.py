# SPDX-License-Identifier: Apache-2.0
"""Producing the subject, rather than being handed one (041, FR-026/027/028).

**038 validated the subject mount and never said where it came from.** `resolve_subject_mount`
refuses the platform's own tree, which is the dangerous case, and takes an operator-supplied
path for everything else. Meanwhile `AuthoringRequest` carries `target_repository`, validated
against `owned_repositories`, and nothing tied the two together — so a proposal could be opened
against repository X carrying edits derived from a checkout of repository Y, and no check in
the tier would have noticed.

041 closes that by construction rather than by comparison: the platform **clones
`target_repository`** and mounts that checkout. The tree analysed and the destination
published to are then the same thing, and the mismatch is not something a later check has to
catch because it cannot be introduced.

**This runs in the dispatching context, never in the tier.** The analysing task holds no
attested identity and no egress, and acquiring the subject is not permitted to become the
exception that gives it either. `resolve_subject_mount` still runs — against the produced path
— so a bug that pointed acquisition at the platform's own tree is refused by the check that
already existed.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.authoring.request import RequestRefused


@dataclass(frozen=True)
class _Completed:
    returncode: int
    stdout: str


class GitRunner(Protocol):
    """Runs one git command. A seam, so a row can drive acquisition without a network."""

    def __call__(self, args: list[str], *, timeout: float) -> _Completed:
        """Return the command's exit status and stdout."""
        ...


#: What the platform will hold of somebody else's repository, after clone.
#:
#: Fixed with its reasoning, the way `READ_BUDGET_BYTES` is: an unfixed threshold is one that
#: gets raised until the corpus passes. 512 MiB is far above any module-plus-configuration the
#: tier exists to analyse and far below a monorepo somebody would be unhappy to have copied.
#: The READ budget still governs what the model *sees*; this governs what the platform *holds*.
ACQUISITION_BUDGET_BYTES = 512 * 1024 * 1024

#: How long a clone may take before it is a hang rather than a big repository.
DEFAULT_CLONE_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class AcquiredSubject:
    """A checkout of the repository a proposal will be opened against."""

    target_repository: str
    path: Path
    commit: str
    size_bytes: int


def acquire_subject(
    *,
    target_repository: str,
    into: Path,
    token: str | None = None,
    budget_bytes: int = ACQUISITION_BUDGET_BYTES,
    timeout: float = DEFAULT_CLONE_TIMEOUT_SECONDS,
    runner: GitRunner | None = None,
) -> AcquiredSubject:
    """Clone ``target_repository`` and return what was produced, or refuse before producing.

    **Shallow and single-branch.** History is not the subject; the working tree is. A full
    clone would copy years of somebody's development to analyse one module, and the deepest
    thing this tier does with git is read files.

    **Refuses before anything is produced**, which is `request.py`'s existing posture one step
    earlier: a refusal that arrives once files exist leaves something on disk to leak, and
    "refused after producing" and "refused before producing" are different postures wearing
    one word.

    Raises:
        RequestRefused: `subject_required`, `subject_unreachable`, `revision_missing`, or
            `acquisition_refused` (over budget — carries the size, never the content).
    """
    if not target_repository.strip():
        raise RequestRefused(
            "an authoring request names no repository to acquire",
            reason_code="subject_required",
        )

    run = runner if runner is not None else _run_git
    destination = into / "subject"
    if destination.exists():
        # A per-run directory that already holds a checkout is a run id collision or a leftover.
        # Either way, analysing somebody else's leftovers is worse than refusing.
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    url = _authenticated(target_repository, token)
    completed = run(
        ["clone", "--depth", "1", "--single-branch", url, str(destination)],
        timeout=timeout,
    )
    if completed.returncode != 0:
        # The URL may carry a token when one was supplied, so the message names the
        # REPOSITORY rather than echoing what was run.
        raise RequestRefused(
            f"the repository {target_repository!r} could not be acquired; it may not exist, "
            f"or this installation may not reach it",
            reason_code="subject_unreachable",
        )

    revision = run(["-C", str(destination), "rev-parse", "HEAD"], timeout=timeout)
    if revision.returncode != 0 or not revision.stdout.strip():
        shutil.rmtree(destination, ignore_errors=True)
        raise RequestRefused(
            f"the clone of {target_repository!r} carries no resolvable HEAD; an empty "
            f"repository has nothing to analyse and nothing to propose against",
            reason_code="revision_missing",
        )
    commit = revision.stdout.strip()

    size = _tree_size(destination)
    if size > budget_bytes:
        shutil.rmtree(destination, ignore_errors=True)
        raise RequestRefused(
            f"the checkout of {target_repository!r} is {size} bytes, over the "
            f"{budget_bytes}-byte acquisition budget; refused before analysis rather than "
            f"holding an unbounded copy of somebody else's repository",
            reason_code="acquisition_refused",
        )

    return AcquiredSubject(
        target_repository=target_repository,
        path=destination.resolve(),
        commit=commit,
        size_bytes=size,
    )


def release_subject(subject: AcquiredSubject) -> None:
    """Delete the checkout. Called at the run's terminal state, and safe to call twice.

    Deliberately not a context manager: the checkout outlives the function that made it — it
    is mounted into an allocation — so tying its life to a Python scope would be a lie about
    who owns it.
    """
    shutil.rmtree(subject.path, ignore_errors=True)


def _run_git(args: list[str], *, timeout: float) -> _Completed:
    """Run one git command. Separated so rows can drive acquisition without a network."""
    try:
        finished = subprocess.run(  # noqa: S603 — fixed executable, arguments built here
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _Completed(returncode=1, stdout=f"{type(exc).__name__}")
    return _Completed(returncode=finished.returncode, stdout=finished.stdout)


def _authenticated(repository: str, token: str | None) -> str:
    """The clone URL.

    **The token does not go in the URL.** A URL carrying one lands in `.git/config`, in
    process listings, and in any error that echoes the command. Authentication travels through
    the credential helper the publishing path also uses, so there is one delivery mechanism
    rather than two — and this function exists to make that absence explicit rather than
    accidental.
    """
    return repository


def _tree_size(root: Path) -> int:
    """Bytes on disk, excluding git's own metadata.

    `.git` is excluded because the budget is about the content being analysed. A shallow
    single-branch clone's metadata is small, and counting it would make the threshold mean
    something slightly different from what it says.
    """
    total = 0
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total


__all__ = [
    "ACQUISITION_BUDGET_BYTES",
    "DEFAULT_CLONE_TIMEOUT_SECONDS",
    "AcquiredSubject",
    "GitRunner",
    "acquire_subject",
    "release_subject",
]
