# SPDX-License-Identifier: Apache-2.0
"""P5/P6 helpers — judge deny and non-fixture plan evidence (047)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from surfaces.dispatch.terraform_authoring import (
    PlanGateRefused,
    attach_plan_evidence,
    compose_plan_evidence,
    gate_final_plan,
    judge_may_publish,
    quality_judge_may_publish,
)


def test_p5_judge_deny_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_JUDGE_DENY", "1")
    ok, reason = judge_may_publish(authored_paths=["main.tf"], task="deploy")
    assert ok is False
    assert "denied" in reason


def test_judge_denies_empty_authored() -> None:
    os.environ.pop("HARNESS_JUDGE_DENY", None)
    ok, _reason = judge_may_publish(authored_paths=[], task="deploy")
    assert ok is False


def test_quality_judge_skips_model_when_write_is_fixture() -> None:
    class Boom:
        def judge_authored_work(self, **_kwargs: object) -> tuple[bool, str]:
            raise AssertionError("fixture write must not call a language-model judge")

    ok, reason = quality_judge_may_publish(
        authored_paths=["main.tf"],
        task="add a bucket",
        write_plan="Write main.tf",
        files={"main.tf": 'resource "null_resource" "x" {}'},
        write_model="fixture/scripted@1",
        judge_chooser=Boom(),
    )
    assert ok is True
    assert reason == "ok"


def test_quality_judge_calls_model_when_write_is_live() -> None:
    class Deny:
        def judge_authored_work(self, **_kwargs: object) -> tuple[bool, str]:
            return False, "the change does not match the task"

    ok, reason = quality_judge_may_publish(
        authored_paths=["main.tf"],
        task="add a bucket",
        write_plan="Write main.tf",
        files={"main.tf": 'resource "null_resource" "x" {}'},
        write_model="anthropic/claude-sonnet@5",
        judge_chooser=Deny(),
    )
    assert ok is False
    assert "does not match" in reason


def test_quality_judge_fail_closed_without_chooser() -> None:
    ok, reason = quality_judge_may_publish(
        authored_paths=["main.tf"],
        task="add a bucket",
        write_plan="Write main.tf",
        files={"main.tf": 'resource "null_resource" "x" {}'},
        write_model="anthropic/claude-sonnet@5",
        judge_chooser=None,
    )
    assert ok is False
    assert "could not judge" in reason


def test_quality_judge_fail_closed_on_provider_error() -> None:
    class Broken:
        def judge_authored_work(self, **_kwargs: object) -> tuple[bool, str]:
            raise RuntimeError("provider down")

    ok, reason = quality_judge_may_publish(
        authored_paths=["main.tf"],
        task="add a bucket",
        write_plan="Write main.tf",
        files={"main.tf": 'resource "null_resource" "x" {}'},
        write_model="anthropic/claude-sonnet@5",
        judge_chooser=Broken(),
    )
    assert ok is False
    assert "could not judge" in reason


def test_quality_judge_still_honours_structural_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_JUDGE_DENY", "1")

    class MustNotRun:
        def judge_authored_work(self, **_kwargs: object) -> tuple[bool, str]:
            raise AssertionError("structural deny must not reach the model")

    ok, reason = quality_judge_may_publish(
        authored_paths=["main.tf"],
        task="add a bucket",
        write_plan="Write main.tf",
        files={"main.tf": 'resource "null_resource" "x" {}'},
        write_model="anthropic/claude-sonnet@5",
        judge_chooser=MustNotRun(),
    )
    assert ok is False
    assert "denied" in reason


def test_compose_plan_evidence_rejects_fixture() -> None:
    with pytest.raises(RuntimeError):
        compose_plan_evidence(plan_result={"fixture": True, "output": "nope"})


def test_compose_plan_evidence_bounds_output() -> None:
    text = compose_plan_evidence(
        plan_result={
            "fixture": False,
            "exit_code": 2,
            "has_changes": True,
            "output": "plan ok",
        }
    )
    assert "terraform plan" in text
    assert "plan ok" in text


def test_p6_harness_plan_fail_refuses_before_a_real_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_TERRAFORM_PLAN_FAIL", "1")
    (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
    with pytest.raises(PlanGateRefused, match="plan failed"):
        gate_final_plan(workspace=tmp_path, authored_paths=["main.tf"])


def test_p6_missing_binary_is_a_red_gate_not_a_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HARNESS_TERRAFORM_PLAN_FAIL", raising=False)
    monkeypatch.setenv("HARNESS_TERRAFORM_BIN", str(tmp_path / "no-such-terraform"))
    (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
    with pytest.raises(PlanGateRefused, match="plan failed"):
        gate_final_plan(workspace=tmp_path, authored_paths=["main.tf"])


def test_p6_stub_plan_error_blocks_and_success_attaches_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HARNESS_TERRAFORM_PLAN_FAIL", raising=False)
    failing = tmp_path / "tf-fail"
    failing.write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.exit(1 if sys.argv[1] == 'init' else 1)\n",
        encoding="utf-8",
    )
    failing.chmod(0o755)
    monkeypatch.setenv("HARNESS_TERRAFORM_BIN", str(failing))
    (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
    with pytest.raises(PlanGateRefused):
        gate_final_plan(workspace=tmp_path, authored_paths=["main.tf"])

    passing = tmp_path / "tf-ok"
    passing.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1] == 'init':\n"
        "    sys.exit(0)\n"
        "if sys.argv[1] == 'plan':\n"
        "    print('Plan: 1 to add, 0 to change, 0 to destroy.')\n"
        "    sys.exit(2)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    passing.chmod(0o755)
    monkeypatch.setenv("HARNESS_TERRAFORM_BIN", str(passing))
    result = gate_final_plan(workspace=tmp_path, authored_paths=["main.tf"])
    assert result["fixture"] is False
    assert result["exit_code"] == 2
    assert result["has_changes"] is True

    class _Proposal:
        evidence: list[str] = []

    proposal = _Proposal()
    proposal.evidence = []
    attach_plan_evidence(proposal=proposal, plan_result=result)
    assert any("terraform plan" in line for line in proposal.evidence)
    assert any("1 to add" in line for line in proposal.evidence)


def test_attach_plan_evidence_refuses_a_missing_oracle() -> None:
    class _Proposal:
        evidence: list[str] = []

    proposal = _Proposal()
    proposal.evidence = []
    with pytest.raises(PlanGateRefused):
        attach_plan_evidence(proposal=proposal, plan_result=None)
