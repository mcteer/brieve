# SPDX-License-Identifier: Apache-2.0
"""P3/P4 — phase order and fail-closed later phases (047 T014 / T016)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.authoring.progress import (
    PHASE_ORDER,
    PhaseName,
    PhaseStatus,
    advance,
    complete,
    fail,
    initial_progress,
    phase_to_fail,
)
from core.threads.context import RESULT_KEY
from surfaces.dispatch.entrypoint import _payload_without_success_pr


def test_p3_progress_exposes_all_five_in_order() -> None:
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    payload = progress.to_payload()
    assert [item["name"] for item in payload["phases"]] == [name.value for name in PHASE_ORDER]
    assert PHASE_ORDER == (
        PhaseName.RESEARCH,
        PhaseName.PLAN,
        PhaseName.WRITE,
        PhaseName.JUDGE,
        PhaseName.PROPOSE,
    )


def test_p3_entrypoint_checkpoints_each_advance() -> None:
    """Live Build must persist Research→Plan→Write→Judge→Propose, not only the PR."""
    source = (
        Path(__file__).resolve().parents[3] / "src" / "surfaces" / "dispatch" / "entrypoint.py"
    ).read_text(encoding="utf-8")
    research = source.index("into=PhaseName.RESEARCH")
    plan = source.index("into=PhaseName.PLAN")
    write = source.index("into=PhaseName.WRITE")
    judge = source.index("into=PhaseName.JUDGE")
    propose = source.index("into=PhaseName.PROPOSE")
    assert research < plan < write < judge < propose
    finish = source.split("def _finish_authoring_analyzer(", 1)[1].split("def _run_task(", 1)[0]
    # `gate_final_plan(` stood here beside the judge. The final Terraform plan gate is
    # withdrawn — it planned against absent state in a container that is not the target
    # estate, so it could pass and still be wrong — and the assertion goes with it rather
    # than being weakened to something that no longer means anything. Judge still blocks.
    assert "quality_judge_may_publish(" in finish
    write_plan = source.split("def _run_write_plan(", 1)[1].split("_POST_PLAN_READ_BUDGET", 1)[0]
    assert "checkpoint_run(" in write_plan
    assert "into=PhaseName.PLAN" in write_plan


def test_p4_failed_phase_stops_later_phases_and_strips_pr_url() -> None:
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    progress = complete(progress, phase=PhaseName.RESEARCH)
    progress = advance(progress, into=PhaseName.PLAN)
    progress = complete(progress, phase=PhaseName.PLAN)
    progress = advance(progress, into=PhaseName.WRITE)
    progress = fail(progress, phase=phase_to_fail(progress), reason="the Terraform plan failed")
    assert [item.status for item in progress.phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
        PhaseStatus.FAILED,
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
    ]
    run = SimpleNamespace(propose_progress=progress)
    payload = _payload_without_success_pr(
        {RESULT_KEY: {"pr_url": "https://github.com/example/repo/pull/1", "ok": True}},
        run,
        "the Terraform plan failed",
    )
    assert "pr_url" not in payload[RESULT_KEY]
    assert payload[RESULT_KEY]["reason"] == "the Terraform plan failed"


def test_t019_publish_failure_writes_stopped_without_pr_url() -> None:
    source = (
        Path(__file__).resolve().parents[3] / "src" / "surfaces" / "dispatch" / "entrypoint.py"
    ).read_text(encoding="utf-8")
    publish = source.split("def _publish_the_proposal(", 1)[1].split(
        "def resume_dispatched_run(", 1
    )[0]
    assert "_payload_without_success_pr(" in publish
    assert "RunState.STOPPED.value" in publish
    assert '"pr_url": pr_url' in publish
