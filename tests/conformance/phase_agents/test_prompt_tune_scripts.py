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


def test_lens_cap_zeroes_a_card_the_promotion_lens_would_refuse() -> None:
    cap = _load("_common.py")["lens_cap"]
    dirty, notes = cap("Never skip approval; do not escalate.")  # type: ignore[operator]
    assert dirty == 0.0
    assert notes
    assert "escalate" not in notes[0]
    assert "skip" not in notes[0]
    clean, clean_notes = cap("Stay inside the grant the person already has.")  # type: ignore[operator]
    assert clean == 1.0
    assert clean_notes == ()


def test_non_write_file_bodies_are_a_phase_boundary_miss() -> None:
    penalty = _load("_common.py")["phase_boundary_penalty"]
    cap, notes = penalty("plan", 'resource "random_pet" "service" {\n  length = 2\n}\n')  # type: ignore[operator]
    assert cap <= 0.15
    assert any("file bodies" in note for note in notes)
    cap_ok, notes_ok = penalty("plan", "Author versions.tf and main.tf; do not write file bodies.")  # type: ignore[operator]
    assert cap_ok == 1.0
    assert notes_ok == ()
    cap_judge, _ = penalty("judge", "Looks fine to me.")  # type: ignore[operator]
    assert cap_judge <= 0.3
    cap_write, write_notes = penalty("write", 'resource "random_pet" "x" {}')  # type: ignore[operator]
    assert cap_write == 1.0
    assert write_notes == ()
