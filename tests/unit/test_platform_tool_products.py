# SPDX-License-Identifier: Apache-2.0
"""A suspendable tool that names no product is a run that waits forever (041, FR-030).

**The rule is general; the authoring trio are only the first instance.** `toolset.py` states
the consequence plainly — the sweeper matches suspensions by *product*, so a suspension
carrying a tool name no product map answers is never matched by anything recovering. Until 041
that could not happen, because every registered tool arrived through a pack manifest and the
loader refuses a pack whose product has no probe. `open_proposal` is the first registered tool
with no manifest behind it, and this row exists so it is not the last one nobody checked.

The row deliberately does **not** enumerate the trio. Naming them would pass forever once they
were mapped, while the next platform tool reintroduced the gap in silence.
"""

from __future__ import annotations

import pytest

from surfaces.probes import PLATFORM_PRODUCT_PROBES, probes_for
from surfaces.toolset import PLATFORM_TOOL_PRODUCTS, build_registry


def _suspendable(registry: object) -> set[str]:
    """Registered tools whose failure could suspend a run rather than end it.

    A read that cannot be repeated is not suspendable in the sense that matters here: the
    property is whether a run parks waiting for a product, and that is decided by the tool
    reaching a product at all.
    """
    names: set[str] = set()
    for name in registry.tool_names():  # type: ignore[attr-defined]
        registration = registry.resolve(name)  # type: ignore[attr-defined]
        mode = getattr(registration, "product_mode", "none") or "none"
        if mode != "none" or getattr(registration, "product", None):
            names.add(name)
    return names


def test_every_product_reaching_tool_is_answered_by_the_product_map() -> None:
    """No registered tool reaches a product the dependency map cannot name."""
    registry, loaded = build_registry(packs=["vault", "terraform"])
    from surfaces.toolset import dependency_products

    products = dependency_products(loaded)
    unmapped = {
        name
        for name in _suspendable(registry)
        if name not in products and name not in PLATFORM_TOOL_PRODUCTS
    }
    assert not unmapped, (
        f"these tools reach a product and the dependency map cannot name it: {sorted(unmapped)}. "
        f"A run suspended on one waits for a recovery signal the sweeper can never match."
    )


def test_every_platform_product_has_a_probe_the_checker_will_consult() -> None:
    """A product named for a platform tool is probed by the table the checker actually reads.

    **This is the half that was missing, and the half that is easy to get wrong.** A probe in
    `PLATFORM_PROBES` is resolvable *by a manifest*; a probe in the checker's table is one that
    fires. The first without the second denies the tool while the product is up.
    """
    _registry, loaded = build_registry(packs=["vault", "terraform"])
    table = probes_for(loaded)
    for tool, product in PLATFORM_TOOL_PRODUCTS.items():
        assert product in table, (
            f"{tool} reaches product {product!r}, which the health checker's probe table does "
            f"not carry — the dependency gate would deny the tool while the product is up"
        )


def test_the_platform_probe_table_is_merged_not_replaced() -> None:
    """Packs still supply their own probes; the platform's entries only add."""
    _registry, loaded = build_registry(packs=["vault"])
    table = probes_for(loaded)
    assert "vault" in table, "a loaded pack's own probe must survive the platform merge"
    assert set(PLATFORM_PRODUCT_PROBES) <= set(table)


def test_a_pack_probe_wins_over_a_platform_default() -> None:
    """Ordering is asserted, not assumed — the manifest sits closer to the tool.

    Rigged rather than observed, because no pack declares `github` today. A row that could
    only pass by there being no conflict would prove nothing about what happens when there is.
    """
    from surfaces import probes as probes_module

    original = dict(probes_module.PLATFORM_PRODUCT_PROBES)
    sentinel_platform = lambda product: (False, "platform")  # noqa: E731
    try:
        probes_module.PLATFORM_PRODUCT_PROBES["vault"] = sentinel_platform
        _registry, loaded = build_registry(packs=["vault"])
        table = probes_for(loaded)
        assert table["vault"] is not sentinel_platform, (
            "the pack's own probe must win; a platform default overriding a manifest would "
            "make a pack's declared probe unreachable without saying so"
        )
    finally:
        probes_module.PLATFORM_PRODUCT_PROBES.clear()
        probes_module.PLATFORM_PRODUCT_PROBES.update(original)


@pytest.mark.parametrize("tool", sorted(PLATFORM_TOOL_PRODUCTS))
def test_each_platform_tool_product_is_a_real_product_name(tool: str) -> None:
    """A typo'd product is a suspension nothing matches, which is the defect one letter over."""
    product = PLATFORM_TOOL_PRODUCTS[tool]
    assert product and product.strip() == product and product.islower()
