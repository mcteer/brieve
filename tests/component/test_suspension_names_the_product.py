# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a suspended pack-tool step names the PRODUCT, not the tool.

`resume_run` suspends with `awaiting=(depends_on or {}).get(intent.tool_name,
intent.tool_name)` — falling back to the tool name when no mapping is supplied.
`SuspendedRunIndex.awaiting()` matches on the **product**. So a suspension carrying
`vault_read` is never matched by `vault` recovering, and the run waits forever with nobody
told. `resume_run`'s own docstring says exactly this.

That was harmless while every tool was `echo` and reached no product. A Vault pack tool
reaches one that can genuinely be down, which is what makes the mapping load-bearing now.

**What this does not prove**: that anything calls `resume_run`. It does not — the function
is invoked from tests and from nowhere in `src/`. The sweeper dispatches a new allocation
and the entrypoint calls `start_governed_run`. The mapping below is correct and connected to
no caller, which is recorded in `contracts/conformance-packs.md` rather than papered over.
"""

from __future__ import annotations

from core.packs.loader import InMemoryPackLoader
from core.packs.manifest import PackManifest, ToolDeclaration
from core.packs.registration import PlatformBindings, load_packs
from core.registry.memory import ToolRegistry
from surfaces.toolset import dependency_products


def _pack() -> PackManifest:
    return PackManifest(
        name="vault",
        product="vault",
        version="0.1.0",
        provenance="authored",
        probe="vault_probe",
        tools=(
            ToolDeclaration(
                name="vault_read",
                risk_class="secret_touching",
                transport="native",
                handler="h",
                product="vault",
                product_mode="federate",
                product_action="vault.read",
            ),
            ToolDeclaration(name="think", risk_class="read", transport="native", handler="h"),
        ),
    )


def _loaded() -> dict[str, object]:
    loader = InMemoryPackLoader()
    loader.add(_pack())
    return dict(
        load_packs(
            ["vault"],
            loader=loader,
            registry=ToolRegistry(),
            bindings=PlatformBindings(
                handlers={"h": lambda args: "ok"},
                probes={"vault_probe": lambda product: (True, "up")},
            ),
        )
    )


def test_a_pack_tool_maps_to_the_product_it_reaches() -> None:
    assert dependency_products(_loaded()) == {"vault_read": "vault"}  # type: ignore[arg-type]


def test_a_tool_reaching_no_product_contributes_no_mapping() -> None:
    """Absent, not mapped to itself.

    `resume_run` already falls back to the tool name, and a mapping that restated the
    fallback would hide the difference between "this tool reaches nothing" and "nobody said
    what this tool reaches" — which are the two cases the fallback exists to distinguish.
    """
    assert "think" not in dependency_products(_loaded())  # type: ignore[arg-type]


def test_the_mapping_is_what_the_sweeper_matches_on() -> None:
    """The point of the whole row: `awaiting` must equal what `awaiting(product)` is called
    with, or the run is never resumed."""
    mapping = dependency_products(_loaded())  # type: ignore[arg-type]
    awaiting = mapping.get("vault_read", "vault_read")
    assert awaiting == "vault", "a suspension naming the tool is never matched by the product"
