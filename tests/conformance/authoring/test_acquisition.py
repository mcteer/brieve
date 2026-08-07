# SPDX-License-Identifier: Apache-2.0
"""A10-A12 — the subject is produced, and refused before anything exists (041, US2).

**What this closes.** 038 validated the subject mount and never said where the tree came from,
while `AuthoringRequest.target_repository` named where a proposal would go. Nothing tied them
together, so a proposal could carry edits derived from a different repository than the one it
was opened against — and no check in the tier would have caught it, because each half was
individually correct.

The rows drive a fake git runner rather than the network. What they assert is the *shape* of
acquisition — shallow, single-branch, refused before producing, bounded, and never carrying a
token in a URL — none of which needs a real forge to be true or false.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from core.authoring.acquisition import (
    AcquiredSubject,
    _Completed,
    acquire_subject,
    release_subject,
)
from core.authoring.request import RequestRefused, resolve_subject_mount

REPO = "https://github.com/acme/infra"
HEAD = "9f1c2b3d4e5f60718293a4b5c6d7e8f90a1b2c3d"


@dataclass
class FakeGit:
    """Records what git was asked to do, and can be told to fail one step.

    Writes a plausible checkout on clone, because rows about the budget and about HEAD need a
    tree to measure and a repository to resolve — a runner that produced nothing would make
    every downstream assertion vacuous.
    """

    fail: str | None = None
    files: dict[str, str] | None = None
    calls: list[list[str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def __call__(self, args: list[str], *, timeout: float) -> _Completed:
        self.calls.append(list(args))
        if args[0] == "clone":
            if self.fail == "clone":
                return _Completed(returncode=128, stdout="")
            destination = Path(args[-1])
            (destination / ".git").mkdir(parents=True, exist_ok=True)
            (destination / ".git" / "config").write_text("[core]\n")
            for name, body in (self.files or {"main.tf": 'resource "null" "x" {}\n'}).items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)
            return _Completed(returncode=0, stdout="")
        if "rev-parse" in args:
            if self.fail == "rev-parse":
                return _Completed(returncode=128, stdout="")
            return _Completed(returncode=0, stdout=f"{HEAD}\n")
        return _Completed(returncode=0, stdout="")


def test_row_a10_the_subject_is_a_checkout_of_the_target_repository(tmp_path: Path) -> None:
    """A10 — the analysed tree and the published destination are one thing (FR-026)."""
    git = FakeGit()
    acquired = acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    assert isinstance(acquired, AcquiredSubject)
    assert acquired.target_repository == REPO
    assert acquired.commit == HEAD, "the base is recorded, so a repository that moves is detectable"
    assert (acquired.path / "main.tf").is_file()


def test_row_a10_the_clone_is_shallow_and_single_branch(tmp_path: Path) -> None:
    """History is not the subject; the working tree is."""
    git = FakeGit()
    acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    clone = next(c for c in git.calls if c[0] == "clone")
    assert "--depth" in clone and "1" in clone
    assert "--single-branch" in clone


def test_row_a10_the_produced_path_still_faces_the_platform_tree_refusal(tmp_path: Path) -> None:
    """The check 038 already had must survive the input changing from supplied to produced.

    Acquisition changes *where the path comes from*. It must not become a way around the one
    refusal that stops a redirected analyser being handed the platform's own tree.
    """
    git = FakeGit()
    acquired = acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    mount = resolve_subject_mount(str(acquired.path), platform_tree=Path.cwd())
    assert mount.read_only is True

    with pytest.raises(RequestRefused) as exc:
        resolve_subject_mount(str(acquired.path), platform_tree=acquired.path)
    assert exc.value.reason_code == "subject_is_platform_tree"


def test_row_a11_an_unreachable_repository_refuses_with_nothing_produced(tmp_path: Path) -> None:
    """A11 — refused before producing, which is `request.py`'s posture one step earlier."""
    git = FakeGit(fail="clone")

    with pytest.raises(RequestRefused) as exc:
        acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    assert exc.value.reason_code == "subject_unreachable"
    assert not (tmp_path / "subject").exists(), "a refusal must leave nothing on disk to leak"


def test_row_a11_an_empty_repository_refuses_by_name(tmp_path: Path) -> None:
    """No resolvable HEAD is a different problem from an unreachable repository."""
    git = FakeGit(fail="rev-parse")

    with pytest.raises(RequestRefused) as exc:
        acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    assert exc.value.reason_code == "revision_missing"
    assert not (tmp_path / "subject").exists()


def test_row_a11_a_nameless_repository_refuses_before_running_git(tmp_path: Path) -> None:
    git = FakeGit()

    with pytest.raises(RequestRefused) as exc:
        acquire_subject(target_repository="   ", into=tmp_path, runner=git)

    assert exc.value.reason_code == "subject_required"
    assert git.calls == [], "nothing may run before the request is known to name something"


def test_row_a12_an_over_budget_checkout_refuses_and_names_the_size(tmp_path: Path) -> None:
    """A12 — the bound is disclosed, and the refusal carries no content (FR-028, R4)."""
    body = "x" * 4096
    git = FakeGit(files={"big.tf": body})

    with pytest.raises(RequestRefused) as exc:
        acquire_subject(target_repository=REPO, into=tmp_path, runner=git, budget_bytes=1024)

    assert exc.value.reason_code == "acquisition_refused"
    message = str(exc.value)
    assert "4096" in message and "1024" in message, "an operator needs both numbers"
    assert body not in message, "a refusal about size must never carry the content"
    assert not (tmp_path / "subject").exists()


def test_the_budget_excludes_git_metadata(tmp_path: Path) -> None:
    """The threshold means what it says: bytes of content, not bytes of clone overhead."""
    git = FakeGit(files={"a.tf": "y" * 100})
    acquired = acquire_subject(target_repository=REPO, into=tmp_path, runner=git)
    assert acquired.size_bytes == 100


def test_the_token_never_reaches_the_clone_url(tmp_path: Path) -> None:
    """A URL carrying a token lands in `.git/config` and in process listings (FR-023a)."""
    git = FakeGit()
    acquire_subject(target_repository=REPO, into=tmp_path, token="ghs_secret_value", runner=git)

    flattened = " ".join(" ".join(c) for c in git.calls)
    assert "ghs_secret_value" not in flattened
    config = (tmp_path / "subject" / ".git" / "config").read_text()
    assert "ghs_secret_value" not in config


def test_releasing_is_idempotent(tmp_path: Path) -> None:
    """Terminal state may be reached more than once; cleanup must not care."""
    git = FakeGit()
    acquired = acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    release_subject(acquired)
    release_subject(acquired)

    assert not acquired.path.exists()


def test_a_leftover_checkout_is_replaced_rather_than_analysed(tmp_path: Path) -> None:
    """A run id collision must not mean analysing somebody else's leftovers."""
    stale = tmp_path / "subject"
    stale.mkdir(parents=True)
    (stale / "stale.tf").write_text("from another run\n")

    git = FakeGit()
    acquired = acquire_subject(target_repository=REPO, into=tmp_path, runner=git)

    assert not (acquired.path / "stale.tf").exists()


def test_acquisition_writes_only_beneath_the_directory_it_was_given(tmp_path: Path) -> None:
    """The assertion `test_no_unaccounted_writes.PERMITTED` rests on (SC-002).

    Acquisition is exempt from the "author_file is the only writer" rule because it runs before
    any agent exists and prepares an input rather than producing output. That exemption is only
    honest if its writes are bounded — so this row bounds them, by watching a tree that must
    stay untouched.
    """
    guarded = tmp_path / "must-not-be-touched"
    guarded.mkdir()
    (guarded / "sentinel").write_text("intact\n")
    into = tmp_path / "run-dir"

    git = FakeGit()
    acquired = acquire_subject(target_repository=REPO, into=into, runner=git)

    assert into in acquired.path.parents, "the checkout must lie under the caller's directory"
    assert (guarded / "sentinel").read_text() == "intact\n"
    assert set(p.name for p in tmp_path.iterdir()) == {"must-not-be-touched", "run-dir"}

    release_subject(acquired)
    assert (guarded / "sentinel").exists(), "release must not reach outside its own checkout"
