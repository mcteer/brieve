# SPDX-License-Identifier: Apache-2.0
"""047 — the forge title is a summary of what was authored, not the Build prompt.

Lives outside 041's frozen proposing rows (042 SC-008).
"""

from __future__ import annotations

from core.authoring.artifact import AuthoredArtifact
from core.authoring.proposal import (
    TITLE_LIMIT,
    ProposedFile,
    branch_for,
    compose,
    title_for,
)
from core.authoring.tool import FileAuthor
from core.authoring.workspace import Trees

MODULE = "modules/secrets/main.tf"
BODY = 'data "vault_generic_secret" "db" {\n  path = "database/creds/app"\n}\n'


def test_row_p1b_the_pr_title_is_not_the_intake_string(
    trees: Trees, artifact: AuthoredArtifact, author: FileAuthor
) -> None:
    """A pasted URL plus a paragraph is the Request section, not ``--title``."""
    author({"path": MODULE, "content": BODY})
    long_task = (
        "I need you to create a terraform template that will provision the appropriate "
        "infrastructure in AWS for this application: https://github.com/mcteer/brieve-demo"
    )
    proposal = compose(
        artifact=artifact,
        target_repository="acme/app",
        branch=branch_for("run-title:0:open_proposal"),
        task=long_task,
        authored_content=author.contents,
        subject_content={},
    )
    assert proposal.title != long_task
    assert proposal.title != f"Add {MODULE}"
    assert "https://" not in proposal.title
    assert "terraform" in proposal.title.lower()
    assert len(proposal.title) <= TITLE_LIMIT
    body = proposal.render()
    assert body.startswith("## Summary")
    assert "## Request" in body
    assert long_task in body
    gist = title_for(files=[], task=long_task)
    assert gist == proposal.title
    assert gist != long_task
    assert "https://" not in gist
    assert "## How to use" in body
    short = title_for(
        files=[ProposedFile(path="main.tf", body="x", is_diff=False)],
        task="Wire dynamic database secrets",
    )
    assert short == "Wire dynamic database secrets"
    fallback = title_for(
        files=[ProposedFile(path="main.tf", body="x", is_diff=False)],
        task="https://github.com/acme/app",
    )
    assert fallback == "Add main.tf"
    planned = title_for(
        files=[ProposedFile(path="main.tf", body="x", is_diff=False)],
        task=long_task,
        summary="Terraform template for AWS resources. Files: main.tf, variables.tf",
    )
    assert planned == "Terraform template for AWS resources"
