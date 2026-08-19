# SPDX-License-Identifier: Apache-2.0
"""PR title and body are a reviewer summary, not the intake prompt (047)."""

from __future__ import annotations

from core.authoring.artifact import AuthoredArtifact, AuthoredFile
from core.authoring.proposal import (
    DEFAULT_USAGE,
    ProposedFile,
    compose,
    files_from_write_plan,
    format_rationale,
    title_for,
)
from surfaces.dispatch.terraform_authoring import reviewer_copy, usage_notes_for


def test_files_from_write_plan_reads_the_trailing_list() -> None:
    assert files_from_write_plan(
        "Add a focused AWS slice. Files: main.tf, variables.tf, outputs.tf"
    ) == ["main.tf", "variables.tf", "outputs.tf"]
    assert files_from_write_plan("no file list here") == []


def test_files_from_write_plan_drops_dotenv_templates() -> None:
    assert files_from_write_plan(
        "Vault slice. Files: src/vault/client.js, .env.example, src/vault/README.md"
    ) == ["src/vault/client.js", "src/vault/README.md"]


def test_format_rationale_turns_a_write_plan_blob_into_a_list() -> None:
    body = format_rationale("Add a focused AWS slice. Files: main.tf, variables.tf, outputs.tf")
    assert "Add a focused AWS slice." in body
    assert "- `main.tf`" in body
    assert "- `variables.tf`" in body
    assert "Files: main.tf" not in body


def test_format_rationale_leaves_markdown_alone() -> None:
    markdown = "Adds a VPC.\n\n- `main.tf` — network\n- `variables.tf` — inputs"
    assert format_rationale(markdown) == markdown


def test_title_uses_the_plan_summary_not_the_prompt() -> None:
    title = title_for(
        files=[ProposedFile(path="main.tf", body="x", is_diff=False)],
        task=(
            "I need you to create a terraform template that will provision the "
            "appropriate infrastructure in AWS for this application"
        ),
        summary="Terraform template for AWS resources. Files: main.tf",
    )
    assert title == "Terraform template for AWS resources"


def test_render_explains_how_to_use_and_formats_rationale() -> None:
    artifact = AuthoredArtifact()
    artifact.files.append(AuthoredFile(path="main.tf", digest="abc", edited=False))
    proposal = compose(
        artifact=artifact,
        target_repository="acme/app",
        branch="brieve/authoring/deadbeef",
        task="please write terraform for AWS",
        authored_content={"main.tf": 'resource "aws_vpc" "main" {}\n'},
        subject_content={},
        title="Terraform template for AWS resources",
        rationale="A first-PR slice. Files: main.tf",
        usage="1. terraform init\n2. terraform plan",
    )
    body = proposal.render()
    assert proposal.title == "Terraform template for AWS resources"
    assert "## How to use" in body
    assert "terraform init" in body
    assert "- `main.tf`" in body
    assert "A first-PR slice." in body
    assert "Files: main.tf" not in body
    assert body.index("## Rationale") < body.index("## How to use")
    assert body.index("## How to use") < body.index("## Request")


def test_render_always_has_how_to_use() -> None:
    proposal = compose(
        artifact=AuthoredArtifact(),
        target_repository="acme/app",
        branch="brieve/authoring/none",
        task="nudge",
        authored_content={},
        subject_content={},
    )
    assert DEFAULT_USAGE in proposal.render()


def test_usage_notes_for_terraform_name_init_plan_apply() -> None:
    notes = usage_notes_for(["modules/app/main.tf", "modules/app/variables.tf"])
    assert "terraform init" in notes
    assert "terraform plan" in notes
    assert "terraform apply" in notes
    assert "modules/app" in notes
    assert "merges" in notes


def test_reviewer_copy_uses_the_chooser_when_it_describes() -> None:
    class _Describer:
        def describe_proposal(self, **_kwargs: object) -> tuple[str, str, str]:
            return (
                "Terraform template for AWS resources",
                "Adds a VPC module.\n\n- `main.tf` — network",
                "Run terraform init then plan.",
            )

    title, rationale, usage = reviewer_copy(
        chooser=_Describer(),
        task="I need a terraform template for AWS",
        write_plan="Files: main.tf",
        files={"main.tf": 'resource "aws_vpc" "x" {}\n'},
    )
    assert title == "Terraform template for AWS resources"
    assert "VPC" in rationale
    assert "terraform init" in usage


def test_reviewer_copy_falls_back_when_the_chooser_cannot_describe() -> None:
    title, rationale, usage = reviewer_copy(
        chooser=object(),
        task="I need you to create a terraform template for AWS",
        write_plan="Terraform template for AWS resources. Files: main.tf",
        files={"main.tf": 'resource "aws_vpc" "x" {}\n'},
    )
    assert title == "Terraform template for AWS resources"
    assert rationale.startswith("Terraform template")
    assert "terraform init" in usage
