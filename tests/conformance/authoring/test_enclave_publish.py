# SPDX-License-Identifier: Apache-2.0
"""E1-E4 — the authoring path against a real forge (041, US3).

**These were run by hand before they were rows, and that is the wrong order.** A demonstration
proves a thing happened once; a row proves it keeps happening. The manual run on 2026-08-07
opened `mcteer/brieve#176` through these exact modules — real `git clone`, the real
`FileAuthor` handler, real `git push` and `gh pr create` — and its findings are what these rows
encode.

**Named runner (constitution v1.1.0): the agent harness, driven by the maintainer.** These
rows fail rather than skip when the forge, the credential, or the tooling is absent — a lane
that skips reads as green, and "validated" would then mean "not checked".

**The credential is deliberately a parameter.** `E1_TOKEN_SOURCE` selects it: the ambient `gh`
credential by default, or an ADR-0062 installation token where an App is installed. What these
rows assert is the PATH; which credential fills `token_for` is orthogonal, which is precisely
why `ProposalPublisher` takes a token source rather than reaching for one.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from core.authoring.acquisition import acquire_subject, release_subject
from core.authoring.artifact import AuthoredArtifact
from core.authoring.credential import InstallationToken
from core.authoring.proposal import branch_for, compose, scannable_text
from core.authoring.publish import ProposalObserver, ProposalPublisher
from core.authoring.tool import FileAuthor
from core.authoring.workspace import Trees
from core.observation.types import ObservationOutcome

pytestmark = pytest.mark.enclave

#: The repository these rows publish against. Row-opened proposals land on a branch derived
#: from the idempotency key, are never merged, and are closed by the runner.
TARGET = os.environ.get("E1_TARGET_REPOSITORY", "")
KEY = "e1-041-authoring-conformance"


class _AmbientToken:
    """The ambient `gh` credential, shaped like a token source."""

    def token_for(self, installation: str) -> InstallationToken:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
        if out.returncode != 0 or not out.stdout.strip():
            pytest.fail(
                "no forge credential: `gh auth token` returned nothing. This row FAILS rather "
                "than skipping — a publishing gate that skipped would read as green while "
                "nothing could publish."
            )
        return InstallationToken(
            token=out.stdout.strip(),
            installation=installation,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


@pytest.fixture(scope="module")
def target() -> str:
    _require(
        bool(TARGET),
        "E1_TARGET_REPOSITORY is unset. These rows publish a real proposal and cannot invent "
        "somewhere to publish it; they fail rather than skip (FR-016, FR-024).",
    )
    for binary in ("git", "gh"):
        found = subprocess.run(["command", "-v", binary], capture_output=True, shell=False)
        if found.returncode != 0 and not any(
            (Path(p) / binary).exists() for p in os.environ.get("PATH", "").split(":")
        ):
            pytest.fail(f"tooling_missing: {binary} is the publishing path and is not present")
    return TARGET


@pytest.fixture(scope="module")
def published(target: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """The full cycle, run once for the module: acquire -> author -> compose -> publish."""
    root = tmp_path_factory.mktemp("e1")
    acquired = acquire_subject(target_repository=f"https://github.com/{target}.git", into=root)
    trees = Trees(subject=acquired.path, workspace=acquired.path)
    artifact = AuthoredArtifact()
    author = FileAuthor(trees, artifact)
    body = (
        "# 041 conformance proof\n\nAuthored by `author_file`, composed by `compose`, "
        f"published by `ProposalPublisher`.\n\nBase: {acquired.commit}\n"
    )
    written = author({"path": "docs/authoring-conformance-proof.md", "content": body})

    proposal = compose(
        artifact=artifact,
        target_repository=target,
        branch=branch_for(KEY),
        task="041 conformance: the authoring tier opens a real proposal",
        authored_content=author.contents,
        subject_content={},
        rationale="Opened by a conformance row to prove the publishing path reaches a forge.",
        correlation_id="corr-041-e1",
        consulted=(),
        base_commit=acquired.commit,
    )
    source = _AmbientToken()
    result = ProposalPublisher(
        proposal=proposal,
        workspace=acquired.path,
        token_source=source,
        installation="ambient",
        base="main",
    )()
    yield {
        "acquired": acquired,
        "artifact": artifact,
        "written": written,
        "proposal": proposal,
        "result": result,
        "workspace": acquired.path,
        "source": source,
    }
    release_subject(acquired)


def test_row_e1_a_real_proposal_exists_and_matches_the_artifact(published, target) -> None:  # type: ignore[no-untyped-def]
    """E1 — a real PR, whose contents are the bytes the artefact recorded (SC-002, SC-009)."""
    result = published["result"]
    _require(result["number"] > 0, "no proposal number came back from the forge")

    listed = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(result["number"]),
            "--repo",
            target,
            "--json",
            "number,state,headRefName,files",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    _require(listed.returncode == 0, f"the forge does not show proposal {result['number']}")
    payload = json.loads(listed.stdout)

    assert payload["state"] == "OPEN"
    assert payload["headRefName"] == published["proposal"].branch
    assert [f["path"] for f in payload["files"]] == ["docs/authoring-conformance-proof.md"]


def test_row_e1_the_published_body_is_the_rendering_containment_scanned(published) -> None:  # type: ignore[no-untyped-def]
    """The reviewer's page and the scanned text are one string, not two that agree today."""
    proposal = published["proposal"]
    scanned = dict(scannable_text(proposal))
    assert scanned["body"] == proposal.render()
    assert "## Provenance" in proposal.render(), "FR-031 — a reviewer can trace this to a run"
    assert "corr-041-e1" in proposal.render()


def test_row_e2_republishing_the_same_key_yields_one_proposal(published, target) -> None:  # type: ignore[no-untyped-def]
    """E2 — real idempotency, against a forge that would happily open a second (SC-010)."""
    again = ProposalPublisher(
        proposal=published["proposal"],
        workspace=published["workspace"],
        token_source=published["source"],
        installation="ambient",
        base="main",
    )()

    assert again["reused"] is True
    assert again["number"] == published["result"]["number"]

    listed = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            target,
            "--head",
            published["proposal"].branch,
            "--state",
            "open",
            "--json",
            "number",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert len(json.loads(listed.stdout or "[]")) == 1, "exactly one proposal for this head"


def test_row_e3_the_analysing_task_cannot_publish(published) -> None:  # type: ignore[no-untyped-def]
    """E3 — the credential absence, observed rather than argued (FR-007, SC-004).

    Structural: the analysing task holds no attested identity, so `available()` is False and
    `token_for` raises. Asserted through the production class rather than by reading a jobspec.
    """
    from core.authoring.credential import AuthoringCredentials
    from core.durability.credentials import CredentialUnavailableError, WorkloadIdentity

    class _NoIdentity(WorkloadIdentity):
        def jwt(self) -> str:
            raise CredentialUnavailableError("the analysing task holds no attested identity")

    credentials = AuthoringCredentials(identity=_NoIdentity())
    assert credentials.available() is False
    with pytest.raises(CredentialUnavailableError):
        credentials.token_for("any-installation")


def test_row_e4_the_observer_sees_what_was_published(published, target) -> None:  # type: ignore[no-untyped-def]
    """E4's half that a host can run: an interrupted publish resolves by looking."""
    observation = ProposalObserver(
        repository=target,
        token_source=published["source"],
        installation="ambient",
        workspace=published["workspace"],
    ).observe(idempotency_key=KEY)

    assert observation.outcome is ObservationOutcome.HAPPENED
    assert str(published["result"]["number"]) in observation.detail


def test_row_e4_no_credential_is_left_on_disk(published: dict[str, Any]) -> None:
    """A15's assertion, against the real filesystem the real binaries wrote to."""
    token = published["source"].token_for("ambient").token
    workspace = published["workspace"]
    leaked = [
        str(path)
        for path in workspace.rglob("*")
        if path.is_file()
        and path.stat().st_size < 2_000_000
        and token in path.read_text(errors="ignore")
    ]
    assert not leaked, f"the forge credential was written to {leaked}"
