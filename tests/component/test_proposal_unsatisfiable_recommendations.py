# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the PR says what the platform could not do (051, T046-T048, A16/A17).

The vendored style guide tells the agent to run `terraform fmt -recursive` and
`terraform validate` before committing, and neither is a registry tool. Delivered with no
precedence rule, a model either names tools that will be rejected or reports a checklist item
it did not perform. The phase instruction stops it doing either; this section is the other
half — what the platform cannot carry out is handed to the reviewer rather than silently
skipped, which is the same move that withdrew the plan gate.

**The text derives from the manifest and from nothing else** (FR-018), which is what makes it
identical across two runs of entirely different content. A model's account of its own work is
not evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.authoring.artifact import AuthoredArtifact, AuthoredFile
from core.authoring.proposal import compose
from core.packs.agents import unsatisfiable_recommendations
from core.packs.loader import FilesystemPackLoader
from surfaces.toolset import PACKS_ROOT

SECTION = "## Adopted practice not carried out"


def _terraform() -> tuple[str, ...]:
    return unsatisfiable_recommendations(FilesystemPackLoader(PACKS_ROOT).load("terraform"))


def _render(content: str, recommendations: tuple[str, ...] = ()) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    artifact = AuthoredArtifact(files=[AuthoredFile(path="main.tf", digest=digest, edited=False)])
    return compose(
        artifact=artifact,
        target_repository="acme/infra",
        branch="brieve/authoring/deadbeef",
        task="wire the app to dynamic credentials",
        authored_content={"main.tf": content},
        subject_content={},
        unsatisfiable_recommendations=recommendations,
    ).render()


def test_both_recommendations_appear_verbatim() -> None:
    """Row A16, US4 acceptance 1."""
    recommendations = _terraform()
    assert len(recommendations) == 2
    body = _render('resource "aws_vpc" "main" {}\n', recommendations)
    assert SECTION in body
    for entry in recommendations:
        assert f"- {entry}" in body


def test_the_section_sits_between_provenance_and_limits() -> None:
    """What was proposed, where it came from, what was not done, then what is not covered."""
    body = _render('resource "aws_vpc" "main" {}\n', _terraform())
    assert body.index(SECTION) < body.index("## Limits")


def test_two_runs_over_different_content_produce_identical_text() -> None:
    """US4 acceptance 2, FR-018. The section comes from the manifest, not from either model."""
    recommendations = _terraform()
    first = _render('resource "aws_vpc" "one" {}\n', recommendations)
    second = _render('variable "environment" { type = string }\n', recommendations)

    def section(body: str) -> str:
        start = body.index(SECTION)
        return body[start : body.index("## Limits", start)]

    assert section(first) == section(second)


def test_exactly_two_bullets_because_only_one_skill_declares() -> None:
    """`terraform-style-guide-security` declares nothing, and must not.

    `SECURITY.md` contains neither `terraform fmt` nor `terraform validate`, no shell block,
    and no tool invocation of any kind — it is guidance on what to author, not on what to
    run. Declaring the pair on both skills would print each bullet twice and attribute a
    recommendation to a skill that does not make it.
    """
    manifest = FilesystemPackLoader(PACKS_ROOT).load("terraform")
    by_name = {skill.name: skill for skill in manifest.skills}
    assert len(by_name["terraform-style-guide"].unsatisfiable) == 2
    assert by_name["terraform-style-guide-security"].unsatisfiable == ()

    security = (
        PACKS_ROOT / "terraform" / "skills" / "terraform-style-guide" / "SECURITY.md"
    ).read_text(encoding="utf-8")
    assert "terraform fmt" not in security
    assert "terraform validate" not in security

    body = _render('resource "aws_vpc" "main" {}\n', _terraform())
    start = body.index(SECTION)
    bullets = [
        line
        for line in body[start : body.index("## Limits", start)].splitlines()
        if line.startswith("- ")
    ]
    assert len(bullets) == 2, bullets


def test_a_pack_declaring_nothing_renders_no_section() -> None:
    """Row A17. An empty heading tells a reviewer less than no heading at all."""
    assert unsatisfiable_recommendations(FilesystemPackLoader(PACKS_ROOT).load("vault")) == ()
    body = _render('path "secret/data/app" { capabilities = ["read"] }\n')
    assert SECTION not in body


def test_the_wording_is_scoped_to_the_registry_not_the_repository() -> None:
    """The claim nearly shipped unqualified, and would have been false.

    `tests/evals_live/write_gates.py` shells out to `terraform validate` as gate one of Write
    scoring. A pull request saying "this platform cannot run terraform validate" would be
    contradicted by this repository's own eval lane — the same overstated-evidence failure
    the feature exists to remove, pointed the other way.
    """
    for entry in _terraform():
        assert "No registry tool runs" in entry
        assert "platform cannot run" not in entry

    gates = (Path(__file__).resolve().parents[1] / "evals_live" / "write_gates.py").read_text(
        encoding="utf-8"
    )
    assert "validate" in gates, "the distinction this row documents may have changed"
