# SPDX-License-Identifier: Apache-2.0
"""Manifests broken exactly one way each, for the 051 load-stage refusal rows (T002).

**One defect per fixture.** A manifest broken two ways can refuse for the wrong reason and
still look green, so each builder here changes a single thing away from a manifest that
loads cleanly — and `healthy` is that clean manifest, which is what lets every row lose.

Pack and skill names are invented. `src/core` stays product-blind, so no fixture may name a
managed product.
"""

from __future__ import annotations

from pathlib import Path

from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack

#: A skill bound to `write`, reviewed against its own bytes, declaring nothing unsatisfiable.
#: Every builder below is this, minus one property.
BOUND = SkillSpec("house-style", phases=("write",))

#: 64 hex characters that are not any real content's digest.
STALE_DIGEST = "0" * 64


def healthy(root: Path, name: str = "alpha") -> Path:
    """A pack that loads. The control every refusal fixture is measured against."""
    return write_authoring_pack(root, name, skills=(BOUND,))


def unknown_phase(root: Path, name: str = "alpha") -> Path:
    """`phases` names something that is not a `PhaseName` → `unknown_phase`."""
    return write_authoring_pack(root, name, skills=(SkillSpec("house-style", phases=("deploy",)),))


def binding_unbacked(root: Path, name: str = "alpha") -> Path:
    """Bound to a real phase the pack ships no instruction for → `skill_binding_unbacked`.

    The pack omits its `judge` instruction *and* binds a skill to `judge`. Without the
    binding this manifest already refuses `agents_incomplete`, so the row must assert the
    binding code specifically rather than whichever check happens to run first.
    """
    return write_authoring_pack(
        root,
        name,
        omit_phase="judge",
        skills=(SkillSpec("house-style", phases=("judge",)),),
    )


def duplicate_name(root: Path, name: str = "alpha") -> Path:
    """Two `[[skills]]` entries share a `name` → `duplicate_skill`."""
    return write_authoring_pack(
        root,
        name,
        skills=(
            SkillSpec("house-style", phases=("write",)),
            SkillSpec("house-style", body="# a second file, same name\n", path="skills/other.md"),
        ),
    )


def declaration_unreviewed(root: Path, name: str = "alpha", *, declaring: bool = True) -> Path:
    """`unsatisfiable_reviewed_at` does not match the skill's digest.

    This is the shape a bump leaves behind: new bytes, new digest, a declaration nobody
    re-read. `declaring=False` is the case that would be easiest to wave through — a skill
    that declares nothing still makes a claim, and the claim goes stale the same way.
    """
    note = "No registry tool formats the authored files."
    declared = (("widget_fmt", note),) if declaring else ()
    return write_authoring_pack(
        root,
        name,
        skills=(
            SkillSpec(
                "house-style",
                phases=("write",),
                unsatisfiable=declared,
                reviewed_at=STALE_DIGEST,
            ),
        ),
    )


def declaration_stale(root: Path, name: str = "alpha", *, capability: str = "read") -> Path:
    """Declares unsatisfiable a capability the registry **does** offer → stale.

    ``read`` is the tool `write_authoring_pack` always registers, so the declaration is
    false the moment the pack loads. A reviewer reading its pull request would be told to
    go and do work the platform already did.
    """
    return write_authoring_pack(
        root,
        name,
        skills=(
            SkillSpec(
                "house-style",
                phases=("write",),
                unsatisfiable=((capability, "No registry tool does this."),),
            ),
        ),
    )


def unbound(root: Path, name: str = "beta") -> Path:
    """Adopted, pinned, bound to nothing — legitimate, and must stay distinguishable."""
    return write_authoring_pack(root, name, skills=(SkillSpec("reference"),))


__all__ = [
    "BOUND",
    "STALE_DIGEST",
    "binding_unbacked",
    "declaration_stale",
    "declaration_unreviewed",
    "duplicate_name",
    "healthy",
    "unbound",
    "unknown_phase",
]
