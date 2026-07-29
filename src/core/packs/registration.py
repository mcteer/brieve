# SPDX-License-Identifier: Apache-2.0
"""Manifest → registry. The one place a declaration becomes something callable.

**Loading executes nothing from the pack.** A declaration names a handler; this module
looks that name up in what the platform provides and refuses if it is not there. The pack
never supplies a callable, so there is no arrangement of manifest content that runs code —
the boundary is structural rather than a rule about what pack authors should not do.

That is also why `PlatformBindings` is passed in rather than discovered. Discovery by import
path or entry point would make "resolved from what the platform provides" depend on what
happens to be importable, which is a different and much weaker claim.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from core.hooks.types import HookHandler, HookRegistration
from core.observation.types import Observer
from core.packs.loader import PackLoader
from core.packs.manifest import ManifestError, PackManifest
from core.registry.memory import ToolHandler, ToolRegistry

#: How a product is probed for reachability: given a product name, is it reachable and why.
#: Structurally identical to `surfaces.mcp.health.Probe`, restated here so `core` does not
#: import a surface — the checker owns probing, and this is only the resolution table.
Probe = Callable[[str], tuple[bool, str]]


@dataclass(frozen=True)
class PlatformBindings:
    """Everything a manifest is allowed to name.

    A pack declares `handler = "vault_read"`; this is where that string is permitted to
    become a function, and only if the platform already had one by that name.
    """

    handlers: dict[str, ToolHandler] = field(default_factory=dict)
    observers: dict[str, Observer] = field(default_factory=dict)
    hooks: dict[str, HookHandler] = field(default_factory=dict)
    probes: dict[str, Probe] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedPack:
    """A pack that registered, and what it contributed."""

    manifest: PackManifest
    tool_names: tuple[str, ...]
    hook_registrations: tuple[HookRegistration, ...]
    #: The resolved probe, for the health checker. `None` when the pack reaches no product.
    probe: Probe | None = None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def product(self) -> str:
        return self.manifest.product


def _resolve[T](table: dict[str, T], key: str, *, kind: str, pack: str) -> T:
    """A name becomes a callable here, or it refuses. There is no third outcome."""
    if key not in table:
        raise ManifestError(
            f"pack {pack!r} names {kind} {key!r}, which the platform does not provide. A "
            f"manifest may only name what already exists — nothing is loaded from the pack",
            reason_code="unresolved_binding",
        )
    return table[key]


def register_pack(
    manifest: PackManifest,
    *,
    registry: ToolRegistry,
    bindings: PlatformBindings,
) -> LoadedPack:
    """Register a manifest's tools and hooks, preserving risk class.

    Registrations are ordinary `ToolRegistry` registrations, which is the whole design:
    pack tools inherit the hook pipeline **by construction rather than by discipline**.
    There is no pack-tool code path to bypass, which is what lets the no-bypass row be
    asserted structurally rather than reviewed.
    """
    registered: list[str] = []
    for tool in manifest.tools:
        handler = _resolve(bindings.handlers, tool.handler, kind="handler", pack=manifest.name)
        observer: Observer | None = None
        if tool.observer is not None:
            observer = _resolve(
                bindings.observers, tool.observer, kind="observer", pack=manifest.name
            )
        registry.register(
            tool.name,
            handler,
            risk_class=tool.risk_class,
            product_mode=tool.product_mode,
            product=tool.product,
            product_action=tool.product_action,
            repeatable=tool.repeatable,
            observer=observer,
        )
        registered.append(tool.name)

    hook_registrations = tuple(
        HookRegistration(
            name=hook.name,
            phase=hook.phase,
            capability_kind=hook.capability_kind,
            handler=_resolve(bindings.hooks, hook.handler, kind="hook handler", pack=manifest.name),
        )
        for hook in manifest.hooks
    )

    probe: Probe | None = None
    if manifest.probe is not None:
        probe = _resolve(bindings.probes, manifest.probe, kind="probe", pack=manifest.name)

    return LoadedPack(
        manifest=manifest,
        tool_names=tuple(registered),
        hook_registrations=hook_registrations,
        probe=probe,
    )


def load_packs(
    names: list[str],
    *,
    loader: PackLoader,
    registry: ToolRegistry,
    bindings: PlatformBindings,
) -> dict[str, LoadedPack]:
    """Load and register several packs.

    A failure in any one refuses the whole set rather than loading the rest. Partial
    loading would leave the platform holding some packs and silently missing others, and
    "which packs are loaded" is what FR-005's isolation is decided against.
    """
    loaded: dict[str, LoadedPack] = {}
    for name in names:
        loaded[name] = register_pack(loader.load(name), registry=registry, bindings=bindings)
    return loaded


__all__ = ["LoadedPack", "PlatformBindings", "load_packs", "register_pack"]
