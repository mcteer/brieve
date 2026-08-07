# SPDX-License-Identifier: Apache-2.0
"""The one place that answers "what can this platform do".

Before 013 the answer lived in four places: `entrypoint.py` derived it from a registry it
built by hand, `api/service.py` and the identity conformance conftest each held a literal
`frozenset`, and a unit row held a fourth copy. Three of those had to agree with a
fourth-hand copy of reality, and **three copies of a constant is how the fourth gets
missed**.

That was survivable while the answer was `{"echo", "plan", "apply"}` forever. It stops being
survivable the moment a pack declares `vault_read`, because `parse_ceiling_record` refuses
any ceiling naming a tool outside the known set:

    a correct ceiling record → `unknown_ceiling_entry` → the error names the CEILING

and whoever reads that error goes and looks at the ceiling, which is fine, and at the trust
fabric, which is fine, and not at the stale constant in a surface module, which is not.

So the vocabulary is derived from what actually registered. A pack that loads is a pack
whose tools a ceiling may name; a pack that does not load contributes nothing, and the
failure surfaces at load with a pack-shaped reason rather than three layers away wearing a
ceiling's name.

**The fixture tools stay.** Definitions that name no pack are what 008–012's rows are built
on, and removing them would break a dozen lanes to prove a point about packs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.packs.loader import FilesystemPackLoader
from core.packs.registration import LoadedPack, PlatformBindings, load_packs
from core.registry.memory import ToolRegistry
from surfaces.handlers import PLATFORM_HANDLERS, PLATFORM_OBSERVERS
from surfaces.probes import PLATFORM_PROBES

#: Where packs live: the repository root, deliberately outside the Python package tree.
PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"


def _echo(_arguments: Mapping[str, Any]) -> dict[str, str]:
    return {"ok": "ran"}


def _planned(_arguments: Mapping[str, Any]) -> dict[str, str]:
    return {"ok": "planned"}


def _applied(_arguments: Mapping[str, Any]) -> dict[str, str]:
    return {"ok": "applied"}


def register_fixture_tools(registry: ToolRegistry) -> None:
    """The reference toolset, product-tagged.

    An empty registry knows no tools, so a ceiling naming any of them refuses
    `unknown_ceiling_entry` — correct behaviour and useless as an entrypoint. A toolset
    declaring no product actions makes every product-shaped ceiling refuse for the same
    reason, which is why these carry product bindings.
    """
    registry.register("echo", _echo)
    registry.register(
        "plan",
        _planned,
        product_mode="federate",
        product="workspace",
        product_action="product.workspace.read",
    )
    registry.register(
        "apply",
        _applied,
        risk_class="write",
        product_mode="federate",
        product="workspace",
        product_action="product.workspace.write",
    )


def build_registry(
    *,
    packs: list[str] | None = None,
    bindings: PlatformBindings | None = None,
    packs_root: Path | None = None,
) -> tuple[ToolRegistry, dict[str, LoadedPack]]:
    """The fixture toolset plus whichever packs were asked for.

    Returns the loaded packs alongside the registry because the caller needs both: the
    registry answers "what can be called", and the loaded packs answer "which product does
    each tool reach" and "what probes it" — questions the dependency gate and the health
    checker ask, and which a registry alone cannot answer for a pack that failed to load.
    """
    registry = ToolRegistry()
    register_fixture_tools(registry)
    if not packs:
        return registry, {}
    loader = FilesystemPackLoader(packs_root or PACKS_ROOT)
    # The platform's probes are supplied by default. Without them a pack loads, its
    # product starts being monitored, `unconfigured_probe` reports it unreachable, and
    # every one of that pack's tools is denied while the product is up.
    resolved = bindings or PlatformBindings(
        handlers=dict(PLATFORM_HANDLERS),
        observers=dict(PLATFORM_OBSERVERS),
        probes=dict(PLATFORM_PROBES),
    )
    loaded = load_packs(packs, loader=loader, registry=registry, bindings=resolved)
    return registry, loaded


def known_tools(registry: ToolRegistry) -> frozenset[str]:
    """What a ceiling may name, derived rather than declared."""
    return frozenset(registry.tool_names())


def known_actions(registry: ToolRegistry) -> frozenset[str]:
    """What a ceiling may name as a product action, derived rather than declared."""
    return frozenset(registry.product_actions())


def content_pins(loaded: Mapping[str, LoadedPack]) -> dict[str, str]:
    """name → digest of every executed content artifact, for `RUN_START`.

    Keyed `pack@version` and `pack/skill` so the record reads without a schema. The core
    records these without interpreting them — it never learns what a pack is — and the
    payload is what lets a resumed run's content be compared to what the original run
    actually loaded, rather than to the manifest sitting beside whatever is on disk now.
    """
    pins: dict[str, str] = {}
    for pack in loaded.values():
        pins[f"{pack.name}@{pack.manifest.version}"] = pack.manifest.version
        for skill in pack.manifest.skills:
            pins[f"{pack.name}/{skill.name}"] = skill.digest
    return pins


#: Tool name → product, for tools the **platform** owns rather than a pack (041, FR-029).
#:
#: A pack tool's product comes from its manifest. A platform tool has no manifest, so without
#: this table `dependency_products` cannot answer for one — and the consequence is the one
#: that function already states: the sweeper watches products, so a suspension carrying only a
#: tool name is never matched by anything recovering. `open_proposal` reaches a forge that can
#: certainly be down, so it is the first platform tool that needed an answer here.
#:
#: The Vault and Terraform platform handlers are deliberately absent: they are bound *into*
#: packs through `PlatformBindings`, so their products already arrive by the manifest path.
#: `plan` and `apply` are here because FR-030's guard found them, not because 041 needed them.
#: They are fixture tools registered by `register_fixture_tools`, they declare
#: `product="workspace"`, and no manifest has ever named that product — so they carried the
#: same wait-forever shape as `open_proposal` and nothing had looked. They are fixture-backed,
#: so `workspace` is probed by `fixture_probe`: there is no live product to be down, which is
#: an answer, where previously there was none.
PLATFORM_TOOL_PRODUCTS: dict[str, str] = {
    "open_proposal": "github",
    "plan": "workspace",
    "apply": "workspace",
}


def dependency_products(loaded: Mapping[str, LoadedPack]) -> dict[str, str]:
    """Tool name → the product it reaches, for `resume_run`'s `depends_on`.

    Built from the manifests, **plus the platform's own table** for tools no manifest
    declares. A suspension carrying a tool name rather than a product is never matched by that
    product recovering — the sweeper watches products. A run suspended on a Vault tool would
    wait forever, and until 041 a run suspended on `open_proposal` would have too.

    Manifests are merged last, so a pack naming a product for a tool this table also lists
    wins: the manifest sits closer to the tool than a platform default does.
    """
    table: dict[str, str] = dict(PLATFORM_TOOL_PRODUCTS)
    table.update(
        {
            tool.name: tool.product
            for pack in loaded.values()
            for tool in pack.manifest.tools
            if tool.product
        }
    )
    return table


__all__ = [
    "PACKS_ROOT",
    "PLATFORM_TOOL_PRODUCTS",
    "build_registry",
    "content_pins",
    "dependency_products",
    "known_actions",
    "known_tools",
    "register_fixture_tools",
]
