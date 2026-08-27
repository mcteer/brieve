# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — `RUN_START` says which skills are bound (051, T016, row A12, FR-005).

Before this, every pinned skill was recorded the same way, and the record read as "this
governed the run" for content no model ever received. The key now carries the binding, so an
adopted-and-inert skill is distinguishable from one that reaches a phase — which is US2
acceptance 1, and it is answerable without opening the pack.

**What this record cannot do** is say a skill was *delivered*. It is written before any phase
executes. `test_phase_delivery_record.py` covers that half.
"""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PHASE_ORDER
from core.packs.registration import PlatformBindings
from surfaces.toolset import PACKS_ROOT, build_registry, content_pins
from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack


def _skill_keys() -> dict[str, str]:
    _, loaded = build_registry(packs=["terraform", "vault"], packs_root=PACKS_ROOT)
    return {k: v for k, v in content_pins(loaded).items() if "/skills/" in k}


def _fixture_skill_keys(root: Path, *names: str) -> set[str]:
    """Skill keys for fixture packs — invented names, so `src/core` stays product-blind."""
    bindings = PlatformBindings(
        handlers={"h": lambda **_: None},
        probes={f"{name}_probe": (lambda _p: (True, "ok")) for name in names},
    )
    _, loaded = build_registry(packs=list(names), packs_root=root, bindings=bindings)
    return {k for k in content_pins(loaded) if "/skills/" in k}


def test_an_unbound_skill_is_recorded_as_unbound() -> None:
    """Vault adopts a skill and binds it nowhere. Legitimate, and it must say so."""
    keys = _skill_keys()
    assert "vault/skills/vault-secret-access@unbound" in keys


def test_a_bound_skill_names_the_phases_it_reaches(tmp_path: Path) -> None:
    """The mechanism, on a fixture pack.

    Which skills the *shipped* Terraform pack binds is pack content, asserted where that
    binding lands — `tests/conformance/phase_agents/test_shipped_terraform_binding.py`.
    Here the question is only whether a declared binding reaches the key.
    """
    write_authoring_pack(
        tmp_path, "alpha", skills=(SkillSpec("house-style", phases=("write", "plan")),)
    )
    keys = _fixture_skill_keys(tmp_path, "alpha")
    assert keys == {"alpha/skills/house-style@plan+write"}


def test_bound_and_unbound_are_distinguishable_from_the_key_alone(tmp_path: Path) -> None:
    """US2 acceptance 1, stated as the property rather than as two examples.

    An auditor reading the trail must not have to open `pack.toml` to learn which of two
    pinned skills actually steers a phase.
    """
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(
            SkillSpec("house-style", phases=("write",)),
            SkillSpec("reference"),
        ),
    )
    bindings = {key.rsplit("@", 1)[1] for key in _fixture_skill_keys(tmp_path, "alpha")}
    assert bindings == {"write", "unbound"}


def test_the_binding_suffix_is_in_phase_order_not_manifest_order(tmp_path: Path) -> None:
    """A rewritten `phases` array must not change the key.

    Declared judge-then-plan-then-write; recorded in `PHASE_ORDER`. Two identical bindings
    that produced two different keys would put a difference in the trail that an auditor has
    to chase and then discard.
    """
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(SkillSpec("house-style", phases=("judge", "plan", "write")),),
    )
    assert _fixture_skill_keys(tmp_path, "alpha") == {"alpha/skills/house-style@plan+write+judge"}
    order = [phase.value for phase in PHASE_ORDER]
    assert order.index("plan") < order.index("write") < order.index("judge")


def test_no_pre_051_skill_key_survives() -> None:
    """Old and new shapes must differ, with no shim.

    A trail written before this change and one written after it are different records of
    different things, and they should not be able to look alike.
    """
    _, loaded = build_registry(packs=["terraform", "vault"], packs_root=PACKS_ROOT)
    pins = content_pins(loaded)
    for pack, manifest in ((name, p.manifest) for name, p in loaded.items()):
        for skill in manifest.skills:
            assert f"{pack}/{skill.name}" not in pins
