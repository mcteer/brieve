# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — Judge file on the judge cell, Write on write (049, T022, A9)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.authoring.progress import PhaseName
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run

ROOT = Path(__file__).resolve().parents[3]
PACKS = ROOT / "packs"
ENTRY = ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py"


def test_write_and_judge_bodies_are_not_the_same_file() -> None:
    run = fake_run(("terraform",), PACKS)
    write = bind_phase_agents(run, PhaseName.WRITE)
    judge = bind_phase_agents(run, PhaseName.JUDGE)
    assert write.body != judge.body
    assert "author_file" in write.body
    assert "allow=true" in judge.body
    assert "You do not write files" in judge.body
    assert write.digest != judge.digest


def test_entrypoint_binds_judge_before_the_judge_cell_and_write_before_write() -> None:
    source = ENTRY.read_text(encoding="utf-8")
    plan_fn = source.index("def _run_write_plan")
    write_bind = source.index("_bind_phase_or_fail(run, PhaseName.WRITE)", plan_fn)
    plan_bind = source.index("_bind_phase_or_fail(run, PhaseName.PLAN)", plan_fn)
    drafter_call = source.index("draft_write_plan", plan_fn)
    judge_bind = source.index("_bind_phase_or_fail(run, PhaseName.JUDGE)")
    judge_call = source.index("quality_judge_may_publish(")
    assert plan_bind < drafter_call < write_bind
    assert judge_bind < judge_call
    tree = ast.parse(source, filename=str(ENTRY))
    assert tree is not None
