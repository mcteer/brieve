# SPDX-License-Identifier: Apache-2.0
"""PL2 — the whole thing, against a real repository and a real Vault (042, T020).

read the estate → author a change → **measure it with Vault** → open a real pull request.

**Every component is the production one.** `acquire_subject`, `FileAuthor`, `compose` and
`ProposalPublisher` are 041's, unedited; `vault_policy_impact` is the handler the pack
declares; `compose_policy_evidence` is what the dispatch surface uses. A script that
reimplemented any of them would prove the script works.

**SC-001 is the assertion**: a reviewer reading only the pull request can say what changed,
what it now permits, and on what basis. That is checked here by building the body and
requiring all three to be present — and then by a person reading the PR, which is what the
named-runner obligation is for.

    make dev-up
    E2E_TARGET_REPOSITORY=owner/repo E2E_POLICY_PATH=path/to/policy.hcl \\
      VAULT_TOKEN=... python tests/evals_live/policy_authoring_e2e.py

Fails rather than skips on anything missing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core.authoring.acquisition import acquire_subject  # noqa: E402
from core.authoring.artifact import AuthoredArtifact  # noqa: E402
from core.authoring.credential import InstallationToken  # noqa: E402
from core.authoring.proposal import branch_for, compose  # noqa: E402
from core.authoring.publish import ProposalPublisher  # noqa: E402
from core.authoring.tool import FileAuthor  # noqa: E402
from core.authoring.workspace import Trees  # noqa: E402
from core.durability.credentials import VaultDatabaseCredentials  # noqa: E402
from surfaces import handlers  # noqa: E402
from surfaces.dispatch.policy_authoring import compose_policy_evidence  # noqa: E402

RUN = "pl2-042"

#: The guidance this change rests on. Resolved against the pinned corpus at composition — an
#: invented anchor gets the FR-012 disclosure rather than being passed off as grounding.
CITATION = (
    "/validated-designs/vault-operating-guides-adoption/static-secrets"
    "#configure-policies-for-kv-secrets"
)

RATIONALE = (
    "The policy grants create, read, update, delete and list across the whole of `secret/*`, "
    "which is every path in the KV store rather than the ones this workload uses. The Vault "
    f"operating guides recommend scoping KV policies to the prefix a workload owns "
    f"({CITATION}), so this narrows the grant to `secret/data/loadtest/*` and its metadata, "
    "and drops `delete` — a load test writes and reads its own fixtures and has no reason to "
    "remove anybody else's.\n\n"
    "The measured impact below is Vault's own answer, not this agent's opinion of the change."
)


class _AmbientToken:
    """The ambient `gh` credential, shaped like a token source (041's own live-row pattern)."""

    def token_for(self, installation: str) -> InstallationToken:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
        if out.returncode != 0 or not out.stdout.strip():
            raise SystemExit("no forge credential: `gh auth token` returned nothing")
        return InstallationToken(
            token=out.stdout.strip(),
            installation=installation,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


class _Token:
    def jwt(self) -> str:  # pragma: no cover
        raise AssertionError("this leg presents a token, not an identity")


def _vault() -> VaultDatabaseCredentials:
    token = os.environ.get("VAULT_TOKEN", "").strip()
    if not token:
        raise SystemExit("VAULT_TOKEN is unset; the impact instrument measures against Vault")
    client = VaultDatabaseCredentials(
        identity=_Token(), vault_addr=os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    )
    client.login = lambda: token  # type: ignore[method-assign]
    return client


def main() -> int:
    target = os.environ.get("E2E_TARGET_REPOSITORY", "").strip()
    policy_path = os.environ.get("E2E_POLICY_PATH", "").strip()
    if not target or not policy_path:
        raise SystemExit("E2E_TARGET_REPOSITORY and E2E_POLICY_PATH are required")

    handlers._fabric = _vault

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 1. READ THE ESTATE — the subject, through 041's acquisition.
        acquired = acquire_subject(target_repository=f"https://github.com/{target}.git", into=root)
        current = (acquired.path / policy_path).read_text()
        print(f"--- current policy ({policy_path} @ {acquired.commit[:12]})")
        print(current)

        # 2. AUTHOR the change, through the tier's own file author.
        proposed = """path "secret/data/loadtest/*"
{
  capabilities = ["create", "read", "update", "list"]
}

path "secret/metadata/loadtest/*"
{
  capabilities = ["read", "list"]
}
"""
        trees = Trees(subject=acquired.path, workspace=acquired.path)
        artifact = AuthoredArtifact()
        author = FileAuthor(trees, artifact)
        author({"path": policy_path, "content": proposed})
        print(f"--- proposed policy\n{proposed}")

        # 3. MEASURE — the product answers.
        impact = handlers.vault_policy_impact(
            {"run_id": RUN, "current_document": current, "proposed_document": proposed}
        )
        print("--- measured impact")
        for entry in impact["results"]:
            print(
                f"  {entry['path']}: granted={entry['granted']} revoked={entry['revoked']}"
                + ("  UNANSWERED" if entry["unanswered"] else "")
            )

        # 4. COMPOSE, with the evidence attached, and PUBLISH.
        proposal = compose(
            artifact=artifact,
            target_repository=target,
            branch=branch_for(f"{RUN}-{acquired.commit[:8]}"),
            task="Scope the loadtest policy to the prefix it owns",
            authored_content=author.contents,
            subject_content={policy_path: current},
            rationale=RATIONALE,
            correlation_id=f"corr-{RUN}",
            consulted=(policy_path,),
            base_commit=acquired.commit,
        )
        compose_policy_evidence(proposal=proposal, impact=impact, resolves=_corpus_resolves())

        body = proposal.render()
        print("\n--- proposal body\n")
        print(body)

        # SC-001, checked before publishing rather than hoped for afterwards.
        for question, marker in (
            ("what changed", "### Files"),
            ("what it now permits", "### Measured impact"),
            ("on what basis", CITATION),
        ):
            if marker not in body:
                print(f"\nSC-001 FAILED: a reviewer cannot answer '{question}'", file=sys.stderr)
                return 1

        result = ProposalPublisher(
            proposal=proposal,
            workspace=acquired.path,
            token_source=_AmbientToken(),
            installation="ambient",
        )()
        print(f"\nPUBLISHED: {result}")

    surviving = [
        n
        for n in (_vault().list_path("sys/policies/acl") or [])
        if n.startswith(f"scratch-agent-{RUN}")
    ]
    if surviving:
        print(f"SCRATCH SURVIVED: {surviving}", file=sys.stderr)
        return 1
    print("zero scratch policies survived the end-to-end leg")
    return 0


def _corpus_resolves() -> object:
    """The real pin, so a citation that does not resolve is disclosed rather than believed."""
    from core.answering.corpus import load_corpus

    corpus = load_corpus()
    return corpus.resolves


if __name__ == "__main__":
    raise SystemExit(main())
