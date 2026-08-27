# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a phase may not claim a skill it is not bound to (051, T040/T041).

Rows A9 and A10, FR-010, SC-006. This is the defect the feature removes, made
un-reintroducible.

All five Terraform phase files read *"Practice is this file and the pinned skills
`terraform-style-guide` / `terraform-style-guide-security`"*, and not one of them received
either. The pack's authors had already declared where the skills applied; the platform
honoured that declaration nowhere. A phase whose prose names practice it will not be given
teaches the model something false about its own context.

**Derived from the manifests, not from a list.** A hard-coded expectation would go stale the
first time somebody adopted a third skill, and would go stale silently.
"""

from __future__ import annotations

import re

import pytest

from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import PackManifest
from surfaces.toolset import PACKS_ROOT

PACKS = ("terraform", "vault")


def _manifest(pack: str) -> PackManifest:
    return FilesystemPackLoader(PACKS_ROOT).load(pack)


def _cases() -> list[tuple[str, str]]:
    return [(pack, pin.phase) for pack in PACKS for pin in _manifest(pack).agents]


@pytest.mark.parametrize(("pack", "phase"), _cases())
def test_no_phase_names_a_skill_it_is_not_bound_to(pack: str, phase: str) -> None:
    manifest = _manifest(pack)
    body = (PACKS_ROOT / pack / "agents" / phase / "AGENTS.md").read_text(encoding="utf-8")
    for skill in manifest.skills:
        if phase in skill.phases:
            continue
        # Backticked, because a phase may legitimately discuss "style" or "security" in prose.
        # Naming the skill is the claim; using an English word is not.
        assert f"`{skill.name}`" not in body, (
            f"{pack}/{phase} names `{skill.name}` as practice but is not bound to it. "
            f"Either bind it in pack.toml or stop claiming it."
        )


@pytest.mark.parametrize(("pack", "phase"), _cases())
def test_a_bound_phase_states_both_precedences(pack: str, phase: str) -> None:
    """Row A10, FR-014 and FR-014a.

    A phase receiving adopted content needs two rules stated, and the second is the one that
    is easy to forget: the skill's `required_version = ">= 1.14"` example contradicts the
    Write card's "`>=` is not a pin", and the eval detector agrees with the card. Delivering
    both documents with no precedence makes a regression the likeliest outcome.
    """
    manifest = _manifest(pack)
    if not any(phase in skill.phases for skill in manifest.skills):
        pytest.skip(f"{pack}/{phase} is bound to no skill")
    body = (PACKS_ROOT / pack / "agents" / phase / "AGENTS.md").read_text(encoding="utf-8")
    where = f"{pack}/{phase}"
    assert re.search(r"registry bounds what can be done", body), f"{where}: no capability rule"
    assert re.search(r"this file governs", body), f"{where}: no content-precedence rule"


def test_at_least_one_phase_is_bound_so_the_rows_can_fail() -> None:
    """Both parametrised rows would pass vacuously against a repository binding nothing."""
    bound = [
        (pack, phase)
        for pack in PACKS
        for skill in _manifest(pack).skills
        for phase in skill.phases
    ]
    assert bound, "no pack binds any skill; the rows above assert nothing"


def test_the_bound_phases_still_name_their_skills() -> None:
    """The other direction. Removing every mention would satisfy A9 and lose the point.

    A phase that receives adopted practice should say so, so a reader of the instruction can
    tell that the content below it is governed rather than incidental.
    """
    manifest = _manifest("terraform")
    for skill in manifest.skills:
        for phase in skill.phases:
            body = (PACKS_ROOT / "terraform" / "agents" / phase / "AGENTS.md").read_text(
                encoding="utf-8"
            )
            assert f"`{skill.name}`" in body, (phase, skill.name)
