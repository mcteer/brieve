# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a declaration may not lag the bytes (051, T010, row A20, FR-019, SC-010).

The hazard this closes is not a mid-run change. Skill bytes that move while a run is in
flight are caught at delivery by the digest check. This is the **adoption** path: a
maintainer bumps a pinned skill to new upstream bytes, the new content recommends something
this platform has no registry tool for, and nobody adds the declaration.

The model behaves correctly — the phase instruction's precedence rule says do not perform
what the registry lacks. The pull request is what goes wrong: it derives from the
declaration and never from the skill's content, so it names two outstanding items when
three are, and the reviewer has no way to know. That is the overstatement Principle IX
forbids, pointed the other way.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from tests.conformance.packs import skill_fixtures as fixtures


def _load(root: Path) -> None:
    FilesystemPackLoader(root).load("alpha")


def test_a_reviewed_declaration_loads(tmp_path: Path) -> None:
    """The control. `healthy` records the skill's own digest, so it loads."""
    fixtures.healthy(tmp_path)
    _load(tmp_path)


def test_a_declaration_examined_against_other_bytes_refuses(tmp_path: Path) -> None:
    fixtures.declaration_unreviewed(tmp_path)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "unsatisfiable_declaration_unreviewed"


def test_the_rule_applies_to_a_skill_declaring_nothing(tmp_path: Path) -> None:
    """The case that would be easiest to wave through, and must not be.

    "Nothing here is unsatisfiable" is a claim about content. A bump can falsify it exactly
    as it falsifies a non-empty declaration, and a skill exempted from the check would be
    the one nobody ever looks at again.
    """
    fixtures.declaration_unreviewed(tmp_path, declaring=False)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "unsatisfiable_declaration_unreviewed"


def test_omitting_the_field_entirely_refuses(tmp_path: Path) -> None:
    """An absent field is not a pass. Skipping the record must not skip the check."""
    pack = fixtures.healthy(tmp_path)
    manifest = pack / "pack.toml"
    text = manifest.read_text(encoding="utf-8")
    stripped = "\n".join(
        line for line in text.splitlines() if not line.startswith("unsatisfiable_reviewed_at")
    )
    assert stripped != text, "fixture no longer writes the field; this row asserts nothing"
    manifest.write_text(stripped, encoding="utf-8")
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path)
    assert caught.value.reason_code == "unsatisfiable_declaration_unreviewed"


def test_a_bump_that_re_examines_the_declaration_loads(tmp_path: Path) -> None:
    """The whole point is that a bump *can* land — after somebody looks.

    Without this row the check would be satisfied by a rule that refuses every bump, which
    would make the gate an obstacle rather than a control.
    """
    from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack

    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(SkillSpec("house-style", body="# bumped upstream content\n", phases=("write",)),),
    )
    _load(tmp_path)
