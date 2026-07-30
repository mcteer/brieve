# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a pack cannot widen a ceiling (FR-005).

**The most plausible defect in this feature.** A pack that grants reads exactly like the
pack system working: tools appear in the registry, calls succeed, the agent becomes capable
of more, and nothing looks wrong. It would ship as a feature.

The direction is the whole property. A pack contributes *candidates*; the ceiling *decides*.
Reversing that — letting a manifest extend what a definition may do — puts authority in a
file anybody who ships a pack can write, which is the shortcut Principle IV exists to close.

Two behaviours, and they are not the same:

**Intersection** is what `reachable_tools` does — a definition calls what its packs offer
and its ceiling permits, and nothing else.

**Refusal** is what `assert_pack_does_not_widen` does when a pack over-declares. Silently
intersecting would treat that as a configuration which happens to be narrower than it looks;
refusing says the pack and the ceiling disagree about this definition, and somebody should
decide which is right.
"""

from __future__ import annotations

import pytest

from core.authority.bindings import DefinitionBindings
from core.authority.types import AuthorityScope
from core.packs.isolation import (
    IsolationRefused,
    assert_pack_does_not_widen,
    reachable_tools,
    resolve_tool_name,
)
from core.packs.loader import InMemoryPackLoader
from core.packs.manifest import PackManifest, ToolDeclaration
from core.packs.registration import LoadedPack, PlatformBindings, load_packs
from core.registry.memory import ToolRegistry


def _pack(name: str, *tools: str) -> PackManifest:
    return PackManifest(
        name=name,
        product=name,
        version="0.1.0",
        provenance="authored",
        probe=f"{name}_probe",
        tools=tuple(
            ToolDeclaration(name=t, risk_class="read", transport="native", handler="h")
            for t in tools
        ),
    )


def _load(*manifests: PackManifest) -> dict[str, LoadedPack]:
    loader = InMemoryPackLoader()
    for manifest in manifests:
        loader.add(manifest)
    return load_packs(
        [m.name for m in manifests],
        loader=loader,
        registry=ToolRegistry(),
        bindings=PlatformBindings(
            handlers={"h": lambda args: "ok"},
            probes={f"{m.name}_probe": (lambda product: (True, "up")) for m in manifests},
        ),
    )


def _bindings(*packs: str) -> DefinitionBindings:
    return DefinitionBindings(
        agent_definition_id="applier", packs=frozenset(packs), binding_map={}, tier=1
    )


def _ceiling(*tools: str) -> AuthorityScope:
    return AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset())


def test_a_pack_declaring_beyond_the_ceiling_refuses() -> None:
    """`pack_exceeds_ceiling`, naming the tools, so the disagreement is visible."""
    loaded = _load(_pack("vault", "vault_read", "vault_delete"))
    with pytest.raises(IsolationRefused) as caught:
        assert_pack_does_not_widen(_bindings("vault"), loaded, _ceiling("vault_read"))
    assert caught.value.reason_code == "pack_exceeds_ceiling"
    assert "vault_delete" in str(caught.value)


def test_a_pack_within_the_ceiling_is_accepted() -> None:
    """The positive control. A check that refused everything would pass the row above."""
    loaded = _load(_pack("vault", "vault_read"))
    assert_pack_does_not_widen(_bindings("vault"), loaded, _ceiling("vault_read", "vault_write"))


def test_zero_paths_grant_from_a_manifest() -> None:
    """The property stated as an absence.

    A manifest declaring a tool the ceiling omits contributes **nothing** — not the tool,
    not a widened scope, not a candidate for later. The reachable set is bounded by the
    ceiling in every case, including the one where the pack asks for more.
    """
    loaded = _load(_pack("vault", "vault_read", "vault_delete", "vault_root"))
    reachable = reachable_tools(_bindings("vault"), loaded, _ceiling("vault_read"))
    assert reachable == frozenset({"vault_read"})


def test_a_definition_reaches_only_the_packs_it_names() -> None:
    """Isolation: two packs loaded, one named, and the other is not reachable."""
    loaded = _load(_pack("vault", "vault_read"), _pack("terraform", "terraform_plan"))
    reachable = reachable_tools(
        _bindings("vault"), loaded, _ceiling("vault_read", "terraform_plan")
    )
    assert reachable == frozenset({"vault_read"}), (
        "a tool from an unnamed pack was reachable; the ceiling permitting it is not the "
        "same as the definition naming the pack that provides it"
    )


def test_naming_an_unloaded_pack_refuses_rather_than_resolving_to_nothing() -> None:
    """Not "reaches nothing" — those are different claims.

    A definition naming a pack that failed to load has a configuration problem. Resolving it
    to an empty tool set would present that as a definition deliberately scoped to nothing,
    and the run would proceed doing less than it was meant to with nobody told.
    """
    with pytest.raises(IsolationRefused) as caught:
        assert_pack_does_not_widen(_bindings("vault"), {}, _ceiling("vault_read"))
    assert caught.value.reason_code == "pack_not_loaded"


def test_an_ambiguous_tool_name_refuses_rather_than_resolving_by_load_order() -> None:
    """Load order changes without anybody deciding it did.

    Two packs declaring `read` is legitimate. Picking one by directory listing means the
    answer changes when a filesystem does, which is a governance decision made by `ls`.
    """
    loaded = _load(_pack("vault", "read"), _pack("terraform", "read"))
    bindings = _bindings("vault", "terraform")

    with pytest.raises(IsolationRefused) as caught:
        resolve_tool_name("read", bindings, loaded)
    assert caught.value.reason_code == "ambiguous_tool_name"

    assert resolve_tool_name("vault/read", bindings, loaded) == "vault/read"


def test_a_qualified_name_from_an_unnamed_pack_refuses() -> None:
    loaded = _load(_pack("vault", "read"), _pack("terraform", "read"))
    with pytest.raises(IsolationRefused) as caught:
        resolve_tool_name("terraform/read", _bindings("vault"), loaded)
    assert caught.value.reason_code == "pack_not_reachable"
