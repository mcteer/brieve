# SPDX-License-Identifier: Apache-2.0
"""ADR-0067's second binding point: a bound judge may not be the answering model (043).

**Written because 043 implemented half its own ADR.** ADR-0067 names two places the rule binds
— qualification and runtime — and the first pass built only the first: `promote_model_version`
refuses a matrix cell whose `judge` names its own model, while nothing stopped an operator
*binding* `relevance_cell` to a judge cell for the same model the answering cell names. Same
defect, arriving through configuration instead of through promotion, and the runtime one is the
one that reaches a person: this verdict decides whether an answer is shown at all.

The dev estate would have hit it immediately. Both sources bind Sonnet 5, and Sonnet 5 is the
model 043's qualification lane scored — so the obvious binding was the forbidden one.
"""

from __future__ import annotations

import pytest

from core.authority.ask_binding import (
    ASK_ROLE,
    RELEVANCE_ROLE,
    SUPPORTED_SCHEMA_VERSION,
    parse_ask_binding_record,
    resolve_relevance_cell,
)
from core.authority.errors import ResolutionRefused
from core.authority.matrix import QualifiedCell, parse_matrix_record

ANSWERING = "anthropic/claude-sonnet@5"
OTHER = "anthropic/claude-opus@5"


def _binding(**cells: str) -> object:
    return parse_ask_binding_record({"schema_version": SUPPORTED_SCHEMA_VERSION, **cells})


def _cells(*judges: str) -> dict[str, QualifiedCell]:
    entries: list[dict[str, object]] = [
        {
            "pack": "vault",
            "model": ANSWERING,
            "role": ASK_ROLE,
            "qualified_by": "live",
            "judge": OTHER,
        }
    ]
    entries += [
        {
            "pack": "vault",
            "model": judge,
            "role": RELEVANCE_ROLE,
            "qualified_by": "live",
            "judge": "seed",
        }
        for judge in judges
    ]
    return parse_matrix_record({"schema_version": 1, "cells": entries})


def test_a_judge_naming_the_answering_model_is_refused() -> None:
    """The row this file exists for. Qualified, bound, and still refused."""
    binding = _binding(
        guidance_cell=f"vault:{ANSWERING}:{ASK_ROLE}",
        relevance_cell=f"vault:{ANSWERING}:{RELEVANCE_ROLE}",
    )

    with pytest.raises(ResolutionRefused) as raised:
        resolve_relevance_cell(
            binding,  # type: ignore[arg-type]
            _cells(ANSWERING),
            available=frozenset({ANSWERING, OTHER}),
        )

    assert raised.value.reason_code == "self_judged_relevance"
    assert "ADR-0067" in str(raised.value)


def test_the_refusal_is_not_relevance_unqualified() -> None:
    """The distinction is the whole value of the code.

    The cell IS qualified — it passed the seed set at the floor. What is wrong is the pairing,
    and the fix is to bind a different judge, not to qualify anything. A reader sent to the
    eval lane by `relevance_unqualified` would run it, watch it pass, and be no closer.
    """
    binding = _binding(
        guidance_cell=f"vault:{ANSWERING}:{ASK_ROLE}",
        relevance_cell=f"vault:{ANSWERING}:{RELEVANCE_ROLE}",
    )

    with pytest.raises(ResolutionRefused) as raised:
        resolve_relevance_cell(
            binding,  # type: ignore[arg-type]
            _cells(ANSWERING),
            available=frozenset({ANSWERING, OTHER}),
        )

    assert raised.value.reason_code != "relevance_unqualified"
    assert "does not judge its own output" in str(raised.value)


def test_a_different_model_judging_is_permitted() -> None:
    """ADR-0067's scope is model identity, not vendor or family — Sonnet judged by Opus passes.

    Without this row the rule could be satisfied by refusing everything, which is a gate that
    cannot pass and therefore says nothing about the one that can.
    """
    binding = _binding(
        guidance_cell=f"vault:{ANSWERING}:{ASK_ROLE}",
        relevance_cell=f"vault:{OTHER}:{RELEVANCE_ROLE}",
    )

    resolved, fallback = resolve_relevance_cell(
        binding,  # type: ignore[arg-type]
        _cells(OTHER),
        available=frozenset({ANSWERING, OTHER}),
    )

    assert resolved.model == OTHER
    assert fallback is None


def test_the_estate_source_is_checked_too_not_only_guidance() -> None:
    """One relevance cell serves both sources, and the record does not say which will generate.

    A check on `guidance_cell` alone would permit self-judgement for every estate question —
    failing exactly when the unchecked source was asked, which is the shape that stays green
    in every test that happens to ask the other one.
    """
    binding = _binding(
        guidance_cell=f"vault:{OTHER}:{ASK_ROLE}",
        estate_cell=f"vault:{ANSWERING}:{ASK_ROLE}",
        relevance_cell=f"vault:{ANSWERING}:{RELEVANCE_ROLE}",
    )

    with pytest.raises(ResolutionRefused) as raised:
        resolve_relevance_cell(
            binding,  # type: ignore[arg-type]
            _cells(ANSWERING),
            available=frozenset({ANSWERING, OTHER}),
        )

    assert raised.value.reason_code == "self_judged_relevance"
    assert "estate" in str(raised.value)


def test_a_fallback_onto_the_answering_model_is_refused() -> None:
    """Checked against the RESOLVED cell, not the pinned one.

    An operator binds a conforming judge; that model goes unavailable; the fallback lands on
    another qualified judge cell — which may be the answering model. Checking the pinned
    reference would pass a binding that was fine and run a judgement that was not.
    """
    binding = _binding(
        guidance_cell=f"vault:{ANSWERING}:{ASK_ROLE}",
        relevance_cell=f"vault:{OTHER}:{RELEVANCE_ROLE}",
    )

    with pytest.raises(ResolutionRefused) as raised:
        resolve_relevance_cell(
            binding,  # type: ignore[arg-type]
            _cells(OTHER, ANSWERING),
            available=frozenset({ANSWERING}),  # OTHER is unreachable, so it falls back
        )

    assert raised.value.reason_code == "self_judged_relevance"


def test_an_unbound_relevance_cell_still_refuses_unbound_first() -> None:
    """Governance ordering: nobody decided beats a rule about what they decided."""
    binding = _binding(guidance_cell=f"vault:{ANSWERING}:{ASK_ROLE}")

    with pytest.raises(ResolutionRefused) as raised:
        resolve_relevance_cell(
            binding,  # type: ignore[arg-type]
            _cells(ANSWERING),
            available=frozenset({ANSWERING}),
        )

    assert raised.value.reason_code == "relevance_unbound"
