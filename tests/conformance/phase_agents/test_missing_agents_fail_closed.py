# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — missing/empty phase instruction blocks the PR (049, T016, A4, A5)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PHASE_ORDER, PhaseName, PhaseStatus
from surfaces.dispatch.entrypoint import _bind_phase_or_fail
from tests.conformance.phase_agents.fixtures import fake_run, run_at, write_authoring_pack


def _later_are_pending(run: object, failed: PhaseName) -> None:
    progress = run.propose_progress  # type: ignore[attr-defined]
    failed_index = PHASE_ORDER.index(failed)
    for item in progress.phases:
        if PHASE_ORDER.index(item.name) > failed_index:
            assert item.status is PhaseStatus.PENDING, item


def test_missing_write_fails_the_phase_and_does_not_advance(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", omit_phase="write")
    run = run_at(fake_run(("alpha",), tmp_path), PhaseName.WRITE)
    reason = _bind_phase_or_fail(run, PhaseName.WRITE)
    assert reason in {"agents_missing", "agents_incomplete"}
    write_state = next(p for p in run.propose_progress.phases if p.name is PhaseName.WRITE)
    assert write_state.status is PhaseStatus.FAILED
    _later_are_pending(run, PhaseName.WRITE)


def test_empty_write_is_agents_empty(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", empty_phase="write")
    run = run_at(fake_run(("alpha",), tmp_path), PhaseName.WRITE)
    reason = _bind_phase_or_fail(run, PhaseName.WRITE)
    assert reason == "agents_empty"
    write_state = next(p for p in run.propose_progress.phases if p.name is PhaseName.WRITE)
    assert write_state.status is PhaseStatus.FAILED
    _later_are_pending(run, PhaseName.WRITE)
