# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a bound skill that cannot be trusted stops the phase (051, T036-T039).

Rows A4-A6 and A8. Delivery verifies at the moment of delivery, not only at load: load-time
verification says the bytes were right when the pack loaded, and a phase is entitled to know
they are right when a model is about to be steered by them.

**There is no fallback in either direction** (FR-004). Not delivering unverified content, and
not quietly proceeding without the skill — a phase that was supposed to author under vendor
practice and did not is a different phase, and it must say so rather than produce plausible
output nobody can attribute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName, PhaseStatus
from core.packs.agents import INSTRUCTION_BUDGET_BYTES, PhaseAgents, load_phase_agents
from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from surfaces.dispatch.entrypoint import _bind_phase_or_fail
from surfaces.toolset import PACKS_ROOT
from tests.conformance.phase_agents.fixtures import (
    SkillSpec,
    fake_run,
    run_at,
    write_authoring_pack,
)


def _load(root: Path, phase: PhaseName = PhaseName.WRITE) -> PhaseAgents:
    return load_phase_agents("alpha", phase, loader=FilesystemPackLoader(root), packs_root=root)


def _refuses(root: Path) -> str:
    with pytest.raises(ManifestError) as caught:
        _load(root)
    return caught.value.reason_code


def test_the_control_delivers(tmp_path: Path) -> None:
    """An intact bound skill is delivered. Without this the rows below prove nothing."""
    write_authoring_pack(tmp_path, "alpha", skills=(SkillSpec("guide", phases=("write",)),))
    assert len(_load(tmp_path).skills) == 1


def test_drifted_bytes_refuse_digest_mismatch(tmp_path: Path) -> None:
    """Row A4, US1 acceptance 2."""
    write_authoring_pack(
        tmp_path, "alpha", skills=(SkillSpec("guide", phases=("write",), drift=True),)
    )
    assert _refuses(tmp_path) == "digest_mismatch"


def test_a_drifted_skill_never_reaches_the_run(tmp_path: Path) -> None:
    """Row A4's second half: no model is asked to author under unverified practice."""
    write_authoring_pack(
        tmp_path, "alpha", skills=(SkillSpec("guide", phases=("write",), drift=True),)
    )
    run = run_at(fake_run(("alpha",), tmp_path), PhaseName.WRITE)
    assert _bind_phase_or_fail(run, PhaseName.WRITE) == "digest_mismatch"
    assert "drifted after the pin" not in (getattr(run, "phase_instruction", "") or "")
    state = next(p for p in run.propose_progress.phases if p.name is PhaseName.WRITE)
    assert state.status is PhaseStatus.FAILED


def test_an_absent_skill_refuses_skill_missing(tmp_path: Path) -> None:
    write_authoring_pack(
        tmp_path, "alpha", skills=(SkillSpec("guide", phases=("write",), absent=True),)
    )
    assert _refuses(tmp_path) == "skill_missing"


def test_an_empty_skill_refuses_skill_empty(tmp_path: Path) -> None:
    write_authoring_pack(
        tmp_path, "alpha", skills=(SkillSpec("guide", phases=("write",), empty=True),)
    )
    assert _refuses(tmp_path) == "skill_empty"


def test_the_three_delivery_failures_are_distinct(tmp_path: Path) -> None:
    """Row A5, SC-005. Collapsing two onto one code is what this guards against."""
    codes = []
    for index, spec in enumerate(
        (
            SkillSpec("guide", phases=("write",), drift=True),
            SkillSpec("guide", phases=("write",), absent=True),
            SkillSpec("guide", phases=("write",), empty=True),
        )
    ):
        root = tmp_path / str(index)
        root.mkdir()
        write_authoring_pack(root, "alpha", skills=(spec,))
        codes.append(_refuses(root))
    assert len(set(codes)) == 3, codes


def test_an_over_budget_assembly_refuses_and_delivers_nothing(tmp_path: Path) -> None:
    """Row A6, FR-009. Truncating would deliver part of a skill the record names in full."""
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(
            SkillSpec(
                "huge",
                body="# huge\n" + ("x" * INSTRUCTION_BUDGET_BYTES),
                phases=("write",),
            ),
        ),
    )
    assert _refuses(tmp_path) == "instruction_too_large"


def test_a_skill_just_under_the_budget_is_delivered_whole(tmp_path: Path) -> None:
    """The budget is a ceiling, not a habit of refusing. It must be able to pass."""
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(SkillSpec("large", body="# large\n" + ("x" * 1000), phases=("write",)),),
    )
    loaded = _load(tmp_path)
    assert len(loaded.skills) == 1
    assert len(loaded.body.encode("utf-8")) < INSTRUCTION_BUDGET_BYTES


def test_a_skill_file_no_manifest_declares_is_never_delivered() -> None:
    """Row A8, FR-008. Unpinned content sitting beside pinned content.

    Structural rather than a rule somebody follows: delivery iterates `manifest.skills`, so a
    file nothing declares is never opened. `LICENSE` and `PROVENANCE.md` are the live cases.
    """
    for phase in PhaseName:
        body = load_phase_agents(
            "terraform", phase, loader=FilesystemPackLoader(PACKS_ROOT), packs_root=PACKS_ROOT
        ).body
        for undeclared in ("LICENSE", "PROVENANCE.md"):
            content = (PACKS_ROOT / "terraform" / "skills" / undeclared).read_text(encoding="utf-8")
            marker = content.strip().splitlines()[0]
            assert marker not in body, (phase, undeclared)
