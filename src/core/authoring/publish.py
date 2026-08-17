# SPDX-License-Identifier: Apache-2.0
"""`open_proposal`'s production handler, and the observer that resolves an interrupted one.

038 built everything a proposal needs — composition, containment, provenance, the deterministic
branch — and `register_proposal_tool` takes a `handler` no production code ever supplied. This
is that handler.

**Adopted CLIs, not an MCP server** (ADR-0066). `git` clones and pushes; `gh pr create` opens
the proposal, because a pull request is a forge concept and core git has none — `git
request-pull` drafts a maintainer email, which is the kernel workflow and not this. The
determination and its cost are recorded in the ADR rather than assumed here.

**The token is delivered per invocation and never lands anywhere.** `gh` reads `GH_TOKEN` from
the environment; `git` reaches the same token through `gh`'s credential helper, so there is one
delivery path rather than two. No `gh auth login` (which writes `hosts.yml`), no token in a
remote URL (which lands in `.git/config` and in process listings), no credential store.

**Idempotency is the branch, and the observer asks the same question the handler does.** A
publish and a revival both ask "is there already an open proposal for this head?" — one
implementation, so the two cannot disagree about what they are looking at.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.authoring.proposal import Proposal, ProposalState
from core.errors import CoreError
from core.observation.types import Observation, ObservationOutcome

#: How long any one CLI call may take before it is a hang rather than a slow forge.
DEFAULT_TIMEOUT_SECONDS = 120.0

#: The credential helper line. The empty first value CLEARS any system-configured helper, so
#: the only credential source is the one supplied — without it, a developer's global helper
#: could authenticate a push the platform believes is unauthenticated.
_HELPER_ARGS = (
    "-c",
    "credential.helper=",
    "-c",
    "credential.helper=!gh auth git-credential",
)

#: Sibling of the analyzer workspace when that directory is not itself a checkout.
#: The analyzing task writes authored bytes into `/alloc/…/workspace` with no `.git` (the
#: subject mount is read-only and separate). The publishing task must not mount the subject,
#: so it clones here, applies the composed proposal, and pushes — the checkpoint carries the
#: bytes; this directory is only the forge checkout they land on.
_PUBLISH_CHECKOUT = "publish-checkout"


class PublishRefused(CoreError):
    """A proposal that will not be opened. Carries the reason code."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class PublishResult:
    """What was opened, or what was found already open."""

    repository: str
    branch: str
    number: int
    url: str
    #: An existing open proposal for this head was found and reused rather than duplicated.
    reused: bool = False


class CommandRunner(Protocol):
    """Runs one `git` or `gh` command. The seam rows drive instead of a forge."""

    def __call__(
        self, argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> _Completed:
        """Return the command's exit status, stdout and stderr."""
        ...


@dataclass(frozen=True)
class _Completed:
    returncode: int
    stdout: str
    stderr: str = ""


class ProposalPublisher:
    """`open_proposal`'s handler: push the authored tree, then open or reuse the proposal.

    Holds the token **source** rather than a token: the credential is minted per call, so a
    publisher constructed at registration time and used minutes later cannot be holding a stale
    one — and nothing that inspects this object finds a credential in it.
    """

    def __init__(
        self,
        *,
        proposal: Proposal,
        workspace: Path,
        token_source: Any,
        installation: str,
        base: str = "",
        runner: CommandRunner | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._proposal = proposal
        self._workspace = workspace
        self._token_source = token_source
        self._installation = installation
        self._base = base
        self._runner = runner or _run
        self._timeout = timeout

    def _env(self) -> dict[str, str]:
        """A per-invocation environment carrying the token and nothing inherited wholesale.

        Built fresh each call rather than mutating `os.environ`: a token placed in the process
        environment outlives the call, reaches every subsequent subprocess, and appears in any
        crash dump of the parent.
        """
        token = self._token_source.token_for(self._installation).token
        base = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG", "GIT_CONFIG_NOSYSTEM")
            if key in os.environ
        }
        return {**base, "GH_TOKEN": token, "GIT_TERMINAL_PROMPT": "0"}

    def _existing(self, env: dict[str, str]) -> PublishResult | None:
        """An open proposal for this head, or None. The observer asks this too."""
        found = self._runner(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                self._proposal.target_repository,
                "--head",
                self._proposal.branch,
                "--state",
                "open",
                "--json",
                "number,url",
            ],
            cwd=self._workspace,
            env=env,
        )
        if found.returncode != 0:
            raise PublishRefused(
                f"could not determine whether a proposal is already open on "
                f"{self._proposal.branch!r}; refusing rather than risking a second one",
                reason_code="forge_unreachable",
            )
        try:
            entries = json.loads(found.stdout or "[]")
        except json.JSONDecodeError:
            entries = []
        if not entries:
            return None
        first = entries[0]
        return PublishResult(
            repository=self._proposal.target_repository,
            branch=self._proposal.branch,
            number=int(first.get("number", 0)),
            url=str(first.get("url", "")),
            reused=True,
        )

    def __call__(self, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Publish, or return the proposal that is already there.

        Raises:
            PublishRefused: the proposal was refused before opening — an empty artefact, an
                unreachable forge, or a push that would clobber somebody's work.
        """
        if not self._proposal.files:
            raise PublishRefused(
                "the artefact is empty; a proposal with no files asks a person to review "
                "nothing and would read as work that was done",
                reason_code="empty_proposal",
            )
        if self._proposal.state is ProposalState.REFUSED:
            raise PublishRefused(
                "the proposal was refused by containment and must not be published",
                reason_code="containment_refused",
            )

        env = self._env()

        already = self._existing(env)
        if already is not None:
            return _as_payload(already)

        tree = self._tree_for_push(env)
        self._push(env, cwd=tree)

        opened = self._runner(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                self._proposal.target_repository,
                "--head",
                self._proposal.branch,
                *(["--base", self._base] if self._base else []),
                "--title",
                self._proposal.title,
                "--body",
                self._proposal.render(),
            ],
            cwd=tree,
            env=env,
        )
        if opened.returncode != 0:
            raise PublishRefused(
                f"the forge refused to open a proposal on {self._proposal.branch!r}",
                reason_code="proposal_refused",
            )

        # Re-read rather than parse the create output: `gh` prints a URL and the observer needs
        # a number, and one query answering both means the handler and the observer agree.
        landed = self._existing(env)
        if landed is None:
            raise PublishRefused(
                "the forge reported the proposal opened and does not list it; refusing to "
                "claim a proposal exists on the strength of an exit status",
                reason_code="proposal_unconfirmed",
            )
        return _as_payload(
            PublishResult(
                repository=landed.repository,
                branch=landed.branch,
                number=landed.number,
                url=landed.url,
                reused=False,
            )
        )

    def _tree_for_push(self, env: dict[str, str]) -> Path:
        """A git checkout carrying the proposal's files.

        **Two shapes, one property.** The enclave row authors into the acquired clone (subject
        and workspace are the same path), so `.git` is already here. The dispatched tier keeps
        them apart: the analyzer's workspace holds authored bytes with no history, and the
        proposer — which must not mount the subject — clones under the allocation, applies the
        composed proposal (the checkpoint is the source of truth), and pushes from that tree.
        """
        if (self._workspace / ".git").is_dir():
            return self._workspace
        return self._clone_and_materialize(env)

    def _clone_and_materialize(self, env: dict[str, str]) -> Path:
        """Fresh shallow clone, then write every proposed file into it."""
        root = self._workspace.parent / _PUBLISH_CHECKOUT
        if root.exists():
            shutil.rmtree(root)
        url = f"https://github.com/{self._proposal.target_repository}.git"
        cloned = self._runner(
            ["git", *_HELPER_ARGS, "clone", "--depth", "1", "--single-branch", url, str(root)],
            cwd=None,
            env=env,
        )
        if cloned.returncode != 0:
            raise PublishRefused(
                f"could not clone {self._proposal.target_repository!r} for publishing",
                reason_code="clone_refused",
            )
        self._materialize(root, env=env)
        return root

    def _materialize(self, root: Path, *, env: dict[str, str]) -> None:
        """Lay the composed proposal onto ``root``. Created files write; edits apply as patches."""
        for proposed in self._proposal.files:
            target = _bounded_path(root, proposed.path)
            if proposed.is_diff:
                patch = root / ".brieve-authoring.patch"
                patch.write_text(
                    proposed.body if proposed.body.endswith("\n") else proposed.body + "\n"
                )
                applied = self._runner(
                    ["git", *_HELPER_ARGS, "apply", "--whitespace=nowarn", str(patch)],
                    cwd=root,
                    env=env,
                )
                patch.unlink(missing_ok=True)
                if applied.returncode != 0:
                    raise PublishRefused(
                        f"could not apply the authored diff for {proposed.path!r}",
                        reason_code="materialize_refused",
                    )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(proposed.body)

    def _push(self, env: dict[str, str], *, cwd: Path) -> None:
        """Push the authored tree to the deterministic branch.

        `--force-with-lease` rather than `--force`: a revival must converge on the latest
        contained content, and a human's edits to the branch must make the push **refuse**
        rather than vanish. That refusal is the correct behaviour, surfaced.
        """
        for argv in (
            ["git", *_HELPER_ARGS, "checkout", "-B", self._proposal.branch],
            ["git", *_HELPER_ARGS, "add", "-A"],
            [
                "git",
                *_HELPER_ARGS,
                "-c",
                "user.name=brieve authoring",
                "-c",
                "user.email=authoring@brieve.invalid",
                "commit",
                "-m",
                self._proposal.title,
            ],
            [
                "git",
                *_HELPER_ARGS,
                "push",
                "--force-with-lease",
                "origin",
                f"HEAD:{self._proposal.branch}",
            ],
        ):
            result = self._runner(argv, cwd=cwd, env=env)
            if result.returncode != 0:
                raise PublishRefused(
                    f"could not publish the authored tree to {self._proposal.branch!r} "
                    f"(step: {argv[argv.index('--') + 1] if '--' in argv else argv[-1]})",
                    reason_code="push_refused",
                )


class ProposalObserver:
    """Did the publish land? Asked by re-reading the forge, never by assuming.

    **The same query the handler uses**, deliberately. An observer with its own idea of what
    "already open" means would eventually disagree with the handler, and the disagreement would
    surface as a duplicate proposal — which is the one outcome the non-repeatable registration
    exists to prevent.
    """

    def __init__(
        self,
        *,
        repository: str,
        token_source: Any,
        installation: str,
        workspace: Path | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self._repository = repository
        self._token_source = token_source
        self._installation = installation
        self._workspace = workspace
        self._runner = runner or _run

    def observe(self, *, idempotency_key: str) -> Observation:
        from core.authoring.proposal import branch_for

        branch = branch_for(idempotency_key)
        try:
            token = self._token_source.token_for(self._installation).token
        except Exception as exc:  # noqa: BLE001 — an observer that cannot look says so
            return Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail=f"no credential to look with: {type(exc).__name__}",
            )
        env = {
            **{k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ},
            "GH_TOKEN": token,
        }
        found = self._runner(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                self._repository,
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number",
            ],
            cwd=self._workspace,
            env=env,
        )
        if found.returncode != 0:
            return Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail="the forge could not be reached to confirm the proposal",
            )
        try:
            entries = json.loads(found.stdout or "[]")
        except json.JSONDecodeError:
            return Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail="the forge's answer could not be read",
            )
        if entries:
            return Observation(
                outcome=ObservationOutcome.HAPPENED,
                detail=f"proposal #{entries[0].get('number')} is open on {branch}",
            )
        return Observation(
            outcome=ObservationOutcome.DID_NOT_HAPPEN,
            detail=f"no open proposal on {branch}",
        )


def _bounded_path(root: Path, relative: str) -> Path:
    """A path inside ``root``, or refuse. Proposal paths are platform-composed, but the
    publish side still refuses anything that would leave the checkout — a defensive bound
    rather than trust in the earlier step alone.
    """
    if not relative.strip() or relative.startswith("/") or ".." in Path(relative).parts:
        raise PublishRefused(
            f"refusing to materialize {relative!r}: path leaves the publish checkout",
            reason_code="path_refused",
        )
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise PublishRefused(
            f"refusing to materialize {relative!r}: path leaves the publish checkout",
            reason_code="path_refused",
        ) from exc
    return target


def _as_payload(result: PublishResult) -> dict[str, Any]:
    """What the tool returns to the run — and what a record may carry.

    Repository, branch, number, url. **Never the body**: an authored proposal is a derivative
    of a private repository, and an append-only store holding a copy is one nobody can delete.
    """
    return {
        "repository": result.repository,
        "branch": result.branch,
        "number": result.number,
        "url": result.url,
        "reused": result.reused,
    }


def _run(
    argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> _Completed:
    try:
        finished = subprocess.run(  # noqa: S603 — argv built here, never from model output
            argv,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _Completed(returncode=1, stdout="", stderr=type(exc).__name__)
    return _Completed(
        returncode=finished.returncode, stdout=finished.stdout, stderr=finished.stderr
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "CommandRunner",
    "ProposalObserver",
    "ProposalPublisher",
    "PublishRefused",
    "PublishResult",
]
