# SPDX-License-Identifier: Apache-2.0
"""047 Plan — ``author_file`` is refused until the write outline exists.

Lives here rather than in 041's frozen producing rows: 042's SC-008 forbids editing those
files to make a successor pass.
"""

from __future__ import annotations

import pytest

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import (
    EnvTemplateRefused,
    FileAuthor,
    WritePlanIncomplete,
    is_dotenv_template,
)
from core.authoring.workspace import Trees

MODULE = "modules/secrets/main.tf"
BODY = 'data "vault_generic_secret" "db" {\n  path = "database/creds/app"\n}\n'


def test_author_file_is_refused_until_the_write_plan_is_recorded(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """Writing before the outline exists is a governed refusal, not a skip."""
    author = FileAuthor(trees, artifact)
    author.plan_ready = False
    with pytest.raises(WritePlanIncomplete):
        author({"path": MODULE, "content": BODY})
    author.plan_ready = True
    written = author({"path": MODULE, "content": BODY})
    assert written["path"] == MODULE


def test_author_file_refuses_dotenv_templates(trees: Trees, artifact: AuthoredArtifact) -> None:
    """A first-PR slice does not include .env.example placeholders."""
    assert is_dotenv_template(".env.example")
    assert is_dotenv_template("config/.env")
    assert not is_dotenv_template("src/config/vaultConfig.js")
    author = FileAuthor(trees, artifact)
    with pytest.raises(EnvTemplateRefused) as refused:
        author({"path": ".env.example", "content": "VAULT_ADDR=\n"})
    assert refused.value.reason_code == "env_template_refused"
    assert not list(trees.workspace.rglob(".env.example"))
    assert artifact.paths == ()
