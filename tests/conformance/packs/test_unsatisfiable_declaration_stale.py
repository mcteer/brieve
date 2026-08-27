# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a stale declaration refuses, in any load order (051, T011, A15, SC-009).

A declaration naming a capability the registry **does** offer would put a line in a pull
request telling a reviewer to go and do work the platform already did. Refusing it at load
is the only moment at which the manifest and the registry are both in front of the same
piece of code.

**Order-independence is the property, not a nicety.** The obvious place for this check is
`register_pack`, which sees one manifest at a time — and there, pack B's declaration would
refuse only if pack A's tool registered first. Load order changes without anybody deciding
it did.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from core.packs.registration import PlatformBindings, load_packs
from core.registry.memory import ToolRegistry
from tests.conformance.packs import skill_fixtures as fixtures
from tests.conformance.phase_agents.fixtures import SkillSpec, write_authoring_pack


def _bindings(*packs: str) -> PlatformBindings:
    return PlatformBindings(
        handlers={"h": lambda **_: None},
        probes={f"{name}_probe": (lambda _p: (True, "ok")) for name in packs},
    )


def _load(root: Path, *names: str) -> Any:
    return load_packs(
        list(names),
        loader=FilesystemPackLoader(root),
        registry=ToolRegistry(),
        bindings=_bindings(*names),
    )


def test_a_declaration_naming_nothing_the_registry_offers_loads(tmp_path: Path) -> None:
    """The control: `widget_fmt` is no tool anyone registered, so the claim stands."""
    write_authoring_pack(
        tmp_path,
        "alpha",
        skills=(
            SkillSpec(
                "house-style",
                phases=("write",),
                unsatisfiable=(("widget_fmt", "No registry tool formats these files."),),
            ),
        ),
    )
    assert _load(tmp_path, "alpha")


def test_declaring_an_offered_capability_refuses(tmp_path: Path) -> None:
    fixtures.declaration_stale(tmp_path)
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path, "alpha")
    assert caught.value.reason_code == "unsatisfiable_declaration_stale"
    assert "read" in str(caught.value)


@pytest.mark.parametrize("order", [("alpha", "beta"), ("beta", "alpha")])
def test_the_verdict_does_not_depend_on_which_pack_registers_first(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    """Both orders refuse. A check in `register_pack` would pass one of these and fail the other."""
    write_authoring_pack(tmp_path, "alpha", skills=(fixtures.BOUND,))
    write_authoring_pack(
        tmp_path,
        "beta",
        skills=(
            SkillSpec(
                "reference",
                phases=("write",),
                unsatisfiable=(("read", "No registry tool does this."),),
            ),
        ),
    )
    with pytest.raises(ManifestError) as caught:
        _load(tmp_path, *order)
    assert caught.value.reason_code == "unsatisfiable_declaration_stale"


def test_a_stale_declaration_refuses_the_whole_set(tmp_path: Path) -> None:
    """All-or-nothing, matching `load_packs`. No pack loads while another's claim is false."""
    write_authoring_pack(tmp_path, "alpha", skills=(fixtures.BOUND,))
    write_authoring_pack(
        tmp_path,
        "beta",
        skills=(
            SkillSpec(
                "reference",
                phases=("write",),
                unsatisfiable=(("read", "No registry tool does this."),),
            ),
        ),
    )
    with pytest.raises(ManifestError):
        _load(tmp_path, "alpha", "beta")
