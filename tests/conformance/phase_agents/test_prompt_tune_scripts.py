# SPDX-License-Identifier: Apache-2.0
"""Hermetic checks on GEPA/DSPy scripts (049, T043–T045). No live model."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> dict[str, object]:
    return runpy.run_path(str(ROOT / "evals" / "prompt-tune" / name))


def test_missing_dspy_is_refinement_unavailable() -> None:
    gepa = _load("gepa_phase.py")
    joint = _load("dspy_build.py")
    if not gepa["refinement_available"]():  # type: ignore[operator]
        try:
            gepa["compile_phase"]("text", metric_lost=False)  # type: ignore[operator]
        except Exception as exc:
            assert getattr(exc, "reason_code", "") == "refinement_unavailable"
    if not joint["refinement_available"]():  # type: ignore[operator]
        try:
            joint["compile_build"]({}, metric_lost=False)  # type: ignore[operator]
        except Exception as exc:
            assert getattr(exc, "reason_code", "") == "refinement_unavailable"


def test_a_losing_metric_copies_zero_files(tmp_path: Path) -> None:
    gepa = _load("gepa_phase.py")
    copied = gepa["copy_into_packs"](  # type: ignore[operator]
        lost=True,
        files={"write": b"candidate"},
        packs_root=tmp_path,
        pack="alpha",
    )
    assert copied == 0
    assert not (tmp_path / "alpha").exists()
    joint = _load("dspy_build.py")
    copied = joint["copy_into_packs"](  # type: ignore[operator]
        lost=True,
        files={"research": b"a", "plan": b"b", "write": b"c", "judge": b"d", "propose": b"e"},
        packs_root=tmp_path,
        pack="alpha",
    )
    assert copied == 0


def test_terraform_write_uses_authoring_gates() -> None:
    common = _load("_common.py")
    uses = common["uses_authoring_gates"]
    assert uses("terraform", "write")  # type: ignore[operator]
    assert not uses("terraform", "plan")  # type: ignore[operator]
    assert not uses("vault", "write")  # type: ignore[operator]
