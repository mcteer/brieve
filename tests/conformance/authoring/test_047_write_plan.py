# SPDX-License-Identifier: Apache-2.0
"""047 Plan — ``author_file`` is refused until the write outline exists.

Lives here rather than in 041's frozen producing rows: 042's SC-008 forbids editing those
files to make a successor pass.
"""

from __future__ import annotations

import pytest

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import FileAuthor, WritePlanIncomplete
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
