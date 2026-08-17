# SPDX-License-Identifier: Apache-2.0
"""P5/P6 helpers — judge deny and non-fixture plan evidence (047)."""

from __future__ import annotations

import os

import pytest

from surfaces.dispatch.terraform_authoring import (
    compose_plan_evidence,
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
    assert "Terraform plan" in text
    assert "plan ok" in text
