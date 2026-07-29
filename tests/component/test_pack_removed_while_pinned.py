# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a definition naming an unloaded pack refuses at RUN START.

Not at tool-call time. The distinction is the whole row: refusing at run start tells the
person before anything executes; refusing at the first call tells them after a step has
already run, and possibly after a step with an external effect.

**The same shape as `cell_withdrawn`, one level up.** A definition names a pack; the pack is
later removed, renamed, or fails to load. The definition sits unchanged in the registry and
was correct when it was written — only re-asking at run start sees that what it names is
gone. This went unnoticed for six analyze passes because the refusal vocabulary looked
complete without it.

**Refusing, not resolving to nothing.** A definition whose pack failed to load has a
configuration problem. Resolving it to an empty tool set would present that as a definition
deliberately scoped to nothing, and the run would proceed doing less than it was meant to
with nobody told.
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


def _pack(name: str = "vault") -> PackManifest:
    return PackManifest(
        name=name,
        product=name,
        version="0.1.0",
        provenance="authored",
        probe=f"{name}_probe",
        tools=(
            ToolDeclaration(
                name=f"{name}_read", risk_class="read", transport="native", handler="h"
            ),
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
            probes={f"{m.name}_probe": (lambda p: (True, "up")) for m in manifests},
        ),
    )


def _bindings(*packs: str) -> DefinitionBindings:
    return DefinitionBindings(
        agent_definition_id="applier", packs=frozenset(packs), binding_map={}, tier=1
    )


def _ceiling(*tools: str) -> AuthorityScope:
    return AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset())


def test_a_definition_naming_an_unloaded_pack_refuses() -> None:
    with pytest.raises(IsolationRefused) as caught:
        assert_pack_does_not_widen(_bindings("vault"), {}, _ceiling("vault_read"))
    assert caught.value.reason_code == "pack_not_loaded"
    assert "vault" in str(caught.value)


def test_the_refusal_happens_before_any_tool_is_resolved() -> None:
    """Run start, not tool-call time.

    `assert_pack_does_not_widen` runs while establishing what the definition may do — the
    same point the ceiling and the binding map are checked. Nothing has executed yet.
    """
    loaded = _load(_pack("vault"))
    with pytest.raises(IsolationRefused) as caught:
        assert_pack_does_not_widen(_bindings("vault", "terraform"), loaded, _ceiling("vault_read"))
    assert caught.value.reason_code == "pack_not_loaded"
    assert "terraform" in str(caught.value), "the refusal does not name the missing pack"


def test_a_partially_available_definition_refuses_rather_than_degrading() -> None:
    """One pack present, one gone. The run does not proceed with half its capability.

    Degrading silently is the failure mode that looks like success: the agent does less,
    reports what it did, and nobody learns that a whole pack was missing.
    """
    loaded = _load(_pack("vault"))
    with pytest.raises(IsolationRefused):
        assert_pack_does_not_widen(
            _bindings("vault", "terraform"), loaded, _ceiling("vault_read", "terraform_read")
        )


def test_resolving_a_tool_from_a_missing_pack_also_refuses() -> None:
    """The second door, closed for the same reason.

    Even if run start were bypassed, resolving a name from a pack that is not loaded refuses
    rather than falling through to "no such tool" — which would send whoever reads it
    looking for a typo.
    """
    with pytest.raises(IsolationRefused) as caught:
        resolve_tool_name("vault_read", _bindings("vault"), {})
    assert caught.value.reason_code == "pack_not_loaded"


def test_a_loaded_pack_is_unaffected() -> None:
    """The positive control."""
    loaded = _load(_pack("vault"))
    assert_pack_does_not_widen(_bindings("vault"), loaded, _ceiling("vault_read"))
    assert reachable_tools(_bindings("vault"), loaded, _ceiling("vault_read")) == frozenset(
        {"vault_read"}
    )
