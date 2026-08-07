# SPDX-License-Identifier: Apache-2.0
"""Asking a model what to do next, bounding how often it may re-ask, and recording both.

A separate package from `surfaces.dispatch` on purpose. The step loop's job is to bracket
work; deciding *what* to do next has its own failure modes — a bound that can be exhausted, a
refusal that must travel back, a provider that can be down — and none of them belong beside a
step budget, where the two bounds would be confused for each other.

Nothing here imports an agent framework, and nothing here decides permission.
"""

from __future__ import annotations

from core.choice.bounded import (
    DEFAULT_RECHOICE_BOUND,
    StepResolution,
    record_unconsulted_step,
    resolve_step_tool,
)
from core.choice.chooser import (
    CHOICE_ROLE,
    Answer,
    Choice,
    ChoiceOutcome,
    ChoiceRequest,
    Chooser,
    ChooserUnavailable,
    MalformedAnswer,
    is_tool_name,
    record_choice,
    resolve_bound_model,
)
from core.choice.recorded import NOTHING, RecordedChooser, parse_recording

__all__ = [
    "CHOICE_ROLE",
    "Answer",
    "DEFAULT_RECHOICE_BOUND",
    "NOTHING",
    "Choice",
    "ChoiceOutcome",
    "ChoiceRequest",
    "Chooser",
    "ChooserUnavailable",
    "MalformedAnswer",
    "RecordedChooser",
    "StepResolution",
    "is_tool_name",
    "parse_recording",
    "record_choice",
    "record_unconsulted_step",
    "resolve_bound_model",
    "resolve_step_tool",
]
