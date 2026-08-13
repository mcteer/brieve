# SPDX-License-Identifier: Apache-2.0
"""046 U1 — answer_sufficiency cases with empty must_contain are refused at load."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.evals.suites import (
    SUFFICIENCY_SUITES,
    UnrunnableSuite,
    load_pack_cases,
    parse_cases,
)

PACKS = Path(__file__).resolve().parents[2] / "packs"


def test_empty_must_contain_is_refused_at_load() -> None:
    with pytest.raises(UnrunnableSuite, match="must_contain"):
        parse_cases(
            {
                "cases": [
                    {
                        "id": "bad",
                        "suite": "answer_sufficiency",
                        "prompt": "How long are logs kept?",
                        "must_contain": [],
                        "recorded": '{"answer":"x","citations":[]}',
                    }
                ]
            },
            source="test",
        )


def test_both_packs_ship_answer_sufficiency() -> None:
    assert "answer_sufficiency" in SUFFICIENCY_SUITES
    for pack in ("vault", "terraform"):
        cases = load_pack_cases(PACKS / pack, "answer_sufficiency")
        assert cases
        assert all(case.must_contain for case in cases)
