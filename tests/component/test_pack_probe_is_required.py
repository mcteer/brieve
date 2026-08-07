# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a pack reaching a product must name a probe (analyze pass 12).

Without this, loading a real pack ends with **every one of its tools denied while the
product is up**:

    pack registers `vault_read` with product "vault"
      → `HealthChecker.products()` derives its subject set from the registry, so "vault"
        is monitored the moment the tool registers — that half needs nothing
      → but the probe is SUPPLIED, and the only one wired was `unconfigured_probe`
      → which returns `(False, "no probe configured for this product")`
      → recorded UNHEALTHY
      → `dependency_pre_hook` denies every vault tool: "vault is not reachable"

The message names the product, so whoever investigates goes and checks Vault, which is fine.
The missing probe is what is wrong and nothing points there. 009's docstring records the
assumption that made this safe — *"this platform fakes product APIs by constitutional
decision, so there is nothing here to reach yet"* — and FR-027b is the requirement that
stops it being true.

Refused at load, in the pack's vocabulary, rather than discovered at the first denied call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.packs.loader import FilesystemPackLoader, validate_manifest
from core.packs.manifest import ManifestError, PackManifest, ToolDeclaration
from surfaces.probes import (
    PLATFORM_PROBES,
    PLATFORM_PRODUCT_PROBES,
    dispatching_probe,
    fixture_probe,
    probes_for,
)
from surfaces.toolset import build_registry

PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"


def _manifest(*, probe: str | None, product: str | None = "vault") -> PackManifest:
    return PackManifest(
        name="vault",
        product="vault",
        version="0.1.0",
        provenance="authored",
        probe=probe,
        tools=(
            ToolDeclaration(
                name="vault_read",
                risk_class="secret_touching",
                transport="native",
                handler="vault_read",
                product=product,
                product_mode="federate" if product else "none",
                product_action="vault.read" if product else None,
            ),
        ),
    )


def test_a_pack_reaching_a_product_with_no_probe_refuses_at_load() -> None:
    with pytest.raises(ManifestError) as caught:
        validate_manifest(_manifest(probe=None))
    assert caught.value.reason_code == "probe_required"
    assert "denied while the product is up" in str(caught.value)


def test_a_pack_reaching_no_product_needs_none() -> None:
    """The bound is on reaching a product, not on being a pack."""
    validate_manifest(_manifest(probe=None, product=None))


def test_both_shipped_packs_name_a_probe_the_platform_provides() -> None:
    """The end-to-end case: a manifest names a probe and the platform has one.

    A manifest naming a probe absent from `PLATFORM_PROBES` refuses `unresolved_binding` —
    the same rule as a tool handler, because a name resolving to nothing must fail where the
    name was written.
    """
    loader = FilesystemPackLoader(PACKS_ROOT)
    for name in ("vault", "terraform"):
        manifest = loader.load(name)
        assert manifest.probe in PLATFORM_PROBES, (
            f"pack {name!r} names probe {manifest.probe!r}, which the platform does not "
            f"provide; a pack may only name what already exists"
        )


def test_loading_the_real_packs_resolves_a_probe_for_each_product() -> None:
    _, loaded = build_registry(packs=["vault", "terraform"], packs_root=PACKS_ROOT)
    table = probes_for(loaded)
    # Subset rather than equality since 041: `probes_for` also carries the products the
    # PLATFORM owns, which no manifest declares. The assertion this row exists to make is
    # about the packs, and it is unchanged — every loaded pack's product still has a probe.
    assert {"vault", "terraform"} <= set(table), (
        "a loaded pack's product has no probe; the health checker would record it UNHEALTHY "
        "and the dependency gate would deny every one of its tools"
    )
    # And the widening is bounded: the extra entries are exactly the platform's, never a
    # pack's product silently arriving from somewhere else.
    assert set(table) - {"vault", "terraform"} <= set(PLATFORM_PRODUCT_PROBES)


def test_a_fixture_backed_product_probes_reachable_and_says_why() -> None:
    """Terraform is not deployed here, so there is nothing to be unreachable.

    Reachable rather than unreachable, because the alternative denies every Terraform tool
    for a product that was never meant to be present. The *reason* string is what keeps this
    from reading as "Terraform is up".
    """
    reachable, detail = fixture_probe("terraform")
    assert reachable is True
    assert "fixture-backed" in detail


def test_a_product_with_no_probe_still_falls_through_to_unreachable() -> None:
    """The backstop, and it must stay.

    `probe_required` keeps this branch unreachable for packs. It is here for a product that
    arrived some other way — and `UNKNOWN`/unreachable is the right answer for one nobody
    knows how to check, because guessing reachable is how a dead dependency gets called.
    """
    _, loaded = build_registry(packs=["vault"], packs_root=PACKS_ROOT)
    reachable, detail = dispatching_probe(loaded)("something-nobody-declared")
    assert reachable is False
    assert "no probe configured" in detail
