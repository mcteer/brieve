# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — promote_phase_agents refuses incomplete qualification (049, T037, A12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PHASE_ORDER
from core.evals.promotion import PromotionRefused, promote_phase_agents
from core.packs.loader import content_digest
from tests.conformance.phase_agents.fixtures import write_authoring_pack

PROVENANCE = "sources: fixture\nauthorship: 2026-08-19\n"


def _files(prefix: bytes = b"clean ") -> dict[str, bytes]:
    return {phase.value: prefix + f"{phase.value} body\n".encode() for phase in PHASE_ORDER}


def _promote(tmp_path: Path, **overrides: object) -> dict[str, str]:
    write_authoring_pack(tmp_path, "alpha")
    files = _files()
    kwargs: dict[str, object] = {
        "pack": "alpha",
        "files": files,
        "provenance": {phase.value: PROVENANCE for phase in PHASE_ORDER},
        "expected_digests": {name: content_digest(body) for name, body in files.items()},
        "versions": {phase.value: "0.2.0" for phase in PHASE_ORDER},
        "suites_passed": ("phase_agents", "build_agents"),
        "packs_root": tmp_path,
        "refinement_available": True,
    }
    kwargs.update(overrides)
    return promote_phase_agents(**kwargs)  # type: ignore[arg-type]


def test_missing_extra_is_refinement_unavailable(tmp_path: Path) -> None:
    with pytest.raises(PromotionRefused) as caught:
        _promote(tmp_path, refinement_available=False)
    assert caught.value.reason_code == "refinement_unavailable"
    original = (tmp_path / "alpha" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    assert original.startswith("# alpha write")


def test_missing_one_suite_is_promotion_incomplete(tmp_path: Path) -> None:
    with pytest.raises(PromotionRefused) as caught:
        _promote(tmp_path, suites_passed=("phase_agents",))
    assert caught.value.reason_code == "promotion_incomplete"
    original = (tmp_path / "alpha" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    assert original.startswith("# alpha write")


def test_a_four_file_set_copies_zero(tmp_path: Path) -> None:
    files = _files()
    files.pop("write")
    with pytest.raises(PromotionRefused) as caught:
        _promote(tmp_path, files=files)
    assert caught.value.reason_code == "promotion_incomplete"
    original = (tmp_path / "alpha" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    assert original.startswith("# alpha write")


def test_whole_set_promotes_when_both_suites_pass(tmp_path: Path) -> None:
    recorded = _promote(tmp_path)
    assert set(recorded) >= {p.value for p in PHASE_ORDER}
    body = (tmp_path / "alpha" / "agents" / "write" / "AGENTS.md").read_bytes()
    assert body.startswith(b"clean write")
    manifest = (tmp_path / "alpha" / "pack.toml").read_text(encoding="utf-8")
    assert recorded["write"] in manifest
