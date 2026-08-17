# SPDX-License-Identifier: Apache-2.0
"""After Plan, remaining analyzer steps must author (047)."""

from __future__ import annotations

from adapters.model_chooser import _authoring_hint
from core.choice import ChoiceOutcome
from surfaces.dispatch.entrypoint import (
    _MAX_AUTHOR_FILES,
    _POST_PLAN_READ_BUDGET,
    _authoring_step_tools,
    _empty_after_plan,
)

TOOLS = ["read_subject", "author_file", "open_proposal"]


def test_research_permits_only_read_subject() -> None:
    assert _authoring_step_tools(TOOLS, planned=False, post_plan_reads=0) == ["read_subject"]


def test_just_after_plan_still_allows_a_short_read() -> None:
    assert _authoring_step_tools(TOOLS, planned=True, post_plan_reads=0) == TOOLS
    assert _authoring_step_tools(TOOLS, planned=True, post_plan_reads=1) == TOOLS


def test_after_read_budget_only_author_file_remains() -> None:
    assert _authoring_step_tools(TOOLS, planned=True, post_plan_reads=_POST_PLAN_READ_BUDGET) == [
        "author_file"
    ]


def test_write_only_hint_does_not_invite_more_research() -> None:
    hint = _authoring_hint(("author_file",))
    assert "author_file now" in hint
    assert "keep reading" not in hint
    assert "NONE" in hint


def test_empty_before_any_file_retries_instead_of_stopping() -> None:
    assert _empty_after_plan(planned=True, authored=0, outcome=ChoiceOutcome.EMPTY) == "retry"
    assert _empty_after_plan(planned=True, authored=0, outcome=ChoiceOutcome.EXHAUSTED) == "retry"


def test_empty_after_files_is_write_complete() -> None:
    assert _empty_after_plan(planned=True, authored=2, outcome=ChoiceOutcome.EMPTY) == "done"


def test_empty_before_plan_still_stops() -> None:
    assert _empty_after_plan(planned=False, authored=0, outcome=ChoiceOutcome.EMPTY) == "stop"


def test_research_hint_still_asks_for_read_first() -> None:
    hint = _authoring_hint(("read_subject",))
    assert "begin with read_subject" in hint


def test_author_file_budget_is_below_the_step_budget() -> None:
    assert 1 <= _MAX_AUTHOR_FILES < 20
