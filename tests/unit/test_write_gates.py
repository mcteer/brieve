# SPDX-License-Identifier: Apache-2.0
"""Write GEPA's two-gate scorer must be able to fail (049). No live model, no terraform."""

from __future__ import annotations

from tests.evals_live.write_gates import (
    iter_write_train_items,
    parse_authored,
    score_write_prediction,
)

from core.evals.authoring_scoring import ToolingResult


def test_write_trainset_is_all_five_golden_tasks() -> None:
    items = iter_write_train_items()
    names = [item.task_name for item in items]
    assert names == [
        "dynamic_database_secret",
        "static_credential_lookalike",
        "pin_the_provider",
        "existing_integration_is_not_duplicated",
        "least_privilege_role",
    ]
    dup = next(i for i in items if i.task_name == "existing_integration_is_not_duplicated")
    assert dup.expects_no_artifact
    assert "CURRENT REPOSITORY CONTENTS" in dup.task_text
    assert "database/creds/orders" in dup.task_text


def test_empty_artefact_when_work_remains_is_zero() -> None:
    """The over-fire GEPA must see: 'already done' on a repo that is not."""
    passed = ToolingResult(ran=True, passed=True, detail="no artefact")
    result = score_write_prediction(
        task_name="dynamic_database_secret",
        artefact_text="--- NO CHANGE",
        tooling=passed,
    )
    assert result.score == 0.0
    assert not result.reference_passed
    assert "authored nothing" in result.feedback


def test_empty_artefact_when_already_integrated_is_one() -> None:
    passed = ToolingResult(ran=True, passed=True, detail="no artefact")
    result = score_write_prediction(
        task_name="existing_integration_is_not_duplicated",
        artefact_text="--- NO CHANGE",
        tooling=passed,
    )
    assert result.score == 1.0
    assert result.reference_passed
    assert result.tooling_passed


def test_duplicating_an_existing_integration_is_not_a_pass() -> None:
    passed = ToolingResult(ran=True, passed=True)
    result = score_write_prediction(
        task_name="existing_integration_is_not_duplicated",
        artefact_text='--- FILE: secrets.tf\ndata "vault_generic_secret" "db" {}\n--- END',
        tooling=passed,
    )
    assert result.score < 1.0
    assert not result.reference_passed
    assert "second copy" in result.feedback


def test_hashicorp_pessimistic_pin_passes_the_reference_gate() -> None:
    """Pin oracle: `~>` is a pin, so Write GEPA is not paid to unlearn the style guide."""
    passed = ToolingResult(ran=True, passed=True)
    body = """--- FILE: main.tf
terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
--- END
"""
    result = score_write_prediction(
        task_name="pin_the_provider",
        artefact_text=body,
        tooling=passed,
    )
    assert result.reference_passed
    assert result.score == 1.0


def test_unbounded_provider_constraint_fails_the_reference_gate() -> None:
    passed = ToolingResult(ran=True, passed=True)
    body = """--- FILE: main.tf
terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}
--- END
"""
    result = score_write_prediction(
        task_name="pin_the_provider",
        artefact_text=body,
        tooling=passed,
    )
    assert not result.reference_passed
    assert result.score == 0.5
    assert "provider_version_is_pinned" in result.feedback or "still missing" in result.feedback


def test_parse_authored_reads_file_blocks() -> None:
    files = parse_authored("--- FILE: a.tf\nfoo\n--- END\n")
    assert files == {"a.tf": "foo\n"}
    assert parse_authored("I'll skip this.\n--- NO CHANGE\n") == {}
