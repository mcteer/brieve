# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — every skill-binding refusal is distinct (051, T009, row A7, SC-005).

**Each row must be able to lose.** `test_the_control_loads` is what makes the rest mean
something: the same builder, minus the single defect, loads clean. Without it a bug that
refused every manifest for any reason would pass every assertion below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from tests.conformance.packs import skill_fixtures as fixtures


def _load(root: Path) -> None:
    FilesystemPackLoader(root).load("alpha")


def test_the_control_loads(tmp_path: Path) -> None:
    """A pack binding a skill to a phase it ships loads. This row is why the others count."""
    fixtures.healthy(tmp_path)
    _load(tmp_path)


def test_binding_to_a_phase_that_does_not_exist_refuses(tmp_path: Path) -> None:
    fixtures.unknown_phase(tmp_path)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "unknown_phase"
    assert "deploy" in str(caught.value)


def test_binding_to_a_phase_the_pack_does_not_ship_refuses(tmp_path: Path) -> None:
    """Distinct from `unknown_phase`: `judge` is a real phase this pack has no file for.

    Delivery would refuse `agents_missing` far from the manifest that caused it, so the
    binding is refused where somebody is looking at the binding.
    """
    fixtures.binding_unbacked(tmp_path)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "skill_binding_unbacked"


def test_two_skills_sharing_a_name_refuse(tmp_path: Path) -> None:
    fixtures.duplicate_name(tmp_path)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "duplicate_skill"


def test_no_refusal_stands_in_for_another(tmp_path: Path) -> None:
    """SC-005 directly: three defects, three codes, no collisions.

    Asserted as a set rather than one-by-one because the failure this guards against is two
    conditions collapsing onto one code — which every individual row above would still pass.
    """
    codes = []
    for index, build in enumerate(
        (fixtures.unknown_phase, fixtures.binding_unbacked, fixtures.duplicate_name)
    ):
        root = tmp_path / str(index)
        root.mkdir()
        build(root)
        with pytest.raises(ManifestError) as caught:
            _load(root)
        codes.append(caught.value.reason_code)
    assert len(set(codes)) == len(codes), codes
