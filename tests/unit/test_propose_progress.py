# SPDX-License-Identifier: Apache-2.0
"""Propose phase progress — fail-closed transitions (047)."""

from __future__ import annotations

import pytest

from core.authoring.progress import (
    PhaseName,
    PhaseStatus,
    ProgressRefused,
    advance,
    complete,
    fail,
    initial_progress,
    phase_to_fail,
)


def test_fail_after_plan_marks_write_not_research() -> None:
    """Write never started; failing must not rewind Research/Plan (portal strip)."""
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    progress = complete(progress, phase=PhaseName.RESEARCH)
    progress = advance(progress, into=PhaseName.PLAN)
    progress = complete(progress, phase=PhaseName.PLAN)
    assert progress.current is None
    assert phase_to_fail(progress) == PhaseName.WRITE
    progress = fail(progress, phase=phase_to_fail(progress), reason="the model chose not to act")
    assert [p.status for p in progress.phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
        PhaseStatus.FAILED,
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
    ]
    assert progress.phases[2].reason == "the model chose not to act"


def test_advance_activates_research_and_completes_nothing_prior() -> None:
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    assert progress.current == PhaseName.RESEARCH
    assert progress.phases[0].status == PhaseStatus.ACTIVE


def test_fail_blocks_later_advance() -> None:
    progress = advance(initial_progress(), into=PhaseName.PLAN)
    progress = fail(progress, phase=PhaseName.PLAN, reason="plan failed")
    with pytest.raises(ProgressRefused):
        advance(progress, into=PhaseName.WRITE)


def test_complete_then_advance() -> None:
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    progress = complete(progress, phase=PhaseName.RESEARCH)
    progress = advance(progress, into=PhaseName.PLAN)
    assert progress.phases[0].status == PhaseStatus.COMPLETED
    assert progress.phases[1].status == PhaseStatus.ACTIVE


def test_advance_does_not_complete_phases_that_never_ran() -> None:
    """Jumping Research → Write must not paint Plan completed."""
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    progress = advance(progress, into=PhaseName.WRITE)
    assert progress.phases[0].status == PhaseStatus.COMPLETED
    assert progress.phases[1].status == PhaseStatus.PENDING
    assert progress.phases[2].status == PhaseStatus.ACTIVE
    assert progress.phases[3].status == PhaseStatus.PENDING


def test_research_then_plan_then_write_then_judge() -> None:
    """The live Build order: collect, outline, author, then gate publish."""
    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    progress = complete(progress, phase=PhaseName.RESEARCH)
    progress = advance(progress, into=PhaseName.PLAN)
    progress = complete(progress, phase=PhaseName.PLAN)
    progress = advance(progress, into=PhaseName.WRITE)
    progress = complete(progress, phase=PhaseName.WRITE)
    progress = advance(progress, into=PhaseName.JUDGE)
    assert [p.status for p in progress.phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
        PhaseStatus.ACTIVE,
        PhaseStatus.PENDING,
    ]
