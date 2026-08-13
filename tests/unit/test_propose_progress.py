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
)


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
