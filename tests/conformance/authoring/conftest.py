# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the 038 rows: two trees, a seeded subject, and a governed run."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import FileAuthor, SubjectReader
from core.authoring.workspace import Trees
from tests.harness.secrets import AUTHORING_SUBJECT_SECRET_MARKER

#: The seeded credential C1 asserts never arrives. From the harness factory, and **absurd rather
#: than plausible** — the first version of this fixture was a cloud-access-key-shaped literal,
#: and the gitleaks lane caught it on the first CI run. A credential-shaped string in the repository
#: is a finding whether or not it is real.
#:
#: What the must-deny case needs is a secret a generator could **reach**, not one that looks
#: real: it sits in a subject file the agent reads, and the assertion is that it does not come
#: out the other side. A subject that never contains one is the passing stub ADR-0047 forbids.
SEEDED_SECRET = AUTHORING_SUBJECT_SECRET_MARKER

#: Distinctive content in a file the task does not touch. C2 asserts it never appears; C7
#: asserts it is refused when the agent copies it into a file it DID create.
SEEDED_UNRELATED = (
    "The quarterly reconciliation ledger uses a bespoke gravitational settlement curve\n"
    "whose damping coefficient is derived from the prior period's unmatched residuals,\n"
    "and the whole scheme is proprietary to the finance team who wrote it in 2019.\n"
)

#: Detectors supplied to the scan rather than owned by it, so files, commits and prose are
#: governed by one set. A second copy would eventually disagree about what a secret looks like.
#:
#: The marker pattern stands in for the credential shapes a production detector set would carry.
#: Asserting the MECHANISM — a pattern fires, the finding carries a digest and not the match —
#: is what these rows are for; which regexes ship is a tuning question that belongs with the
#: detectors rather than in a conformance row.
SECRET_DETECTORS = (re.compile(re.escape(AUTHORING_SUBJECT_SECRET_MARKER)),)


@pytest.fixture
def trees(tmp_path: Path) -> Trees:
    """A read-only subject and a writable workspace — the two trees, separate by construction."""
    subject = tmp_path / "subject"
    workspace = tmp_path / "workspace"
    (subject / "app").mkdir(parents=True)
    workspace.mkdir()
    (subject / "app" / "config.py").write_text(
        f'DATABASE_PASSWORD = "{SEEDED_SECRET}"\nDEBUG = False\n'
    )
    (subject / "app" / "ledger.py").write_text(SEEDED_UNRELATED)
    (subject / "app" / "main.py").write_text("def main() -> None:\n    print('hello')\n")
    return Trees(subject=subject, workspace=workspace)


@pytest.fixture
def subject_files(trees: Trees) -> dict[str, str]:
    """Path → content for everything in the subject, as the scan consumes it."""
    return {
        str(p.relative_to(trees.subject)): p.read_text()
        for p in sorted(trees.subject.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def artifact() -> AuthoredArtifact:
    return AuthoredArtifact()


@pytest.fixture
def author(trees: Trees, artifact: AuthoredArtifact) -> FileAuthor:
    return FileAuthor(trees, artifact)


@pytest.fixture
def reader(trees: Trees) -> SubjectReader:
    return SubjectReader(trees)
