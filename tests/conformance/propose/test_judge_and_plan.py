# SPDX-License-Identifier: Apache-2.0
"""P5/P6 helpers — judge deny and non-fixture plan evidence (047)."""

from __future__ import annotations

import os

import pytest

from surfaces.dispatch.terraform_authoring import compose_plan_evidence, judge_may_publish


def test_p5_judge_deny_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_JUDGE_DENY", "1")
    ok, reason = judge_may_publish(authored_paths=["main.tf"], task="deploy")
    assert ok is False
    assert "denied" in reason


def test_judge_denies_empty_authored() -> None:
    os.environ.pop("HARNESS_JUDGE_DENY", None)
    ok, _reason = judge_may_publish(authored_paths=[], task="deploy")
    assert ok is False


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
