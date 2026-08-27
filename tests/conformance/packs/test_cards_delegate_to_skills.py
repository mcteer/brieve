# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a phase card does not restate what its bound skill teaches (053).

051 delivered adopted skills to `plan`, `write` and `judge` and proved delivery byte-for-byte.
It could not prove effect: SC-002 came back NOT DEMONSTRATED. The reason, measured on
2026-08-27, is that the cards state the guide's rules by hand — so removing the binding would
leave every rule in force, and no measurement could show anything. ADR-0004's pin governed
nothing it was supposed to govern.

**Why the rows below are shaped the way they are.** A1 on its own would pass against a
detector that finds nothing, which is the passing stub ADR-0047 forbids. A4 pins that the
comparison caught the real defect, against card text frozen before the edit. A5a pins that the
rule is satisfiable. Terraform is both halves of the control.

**A5 is a different guard, and it exists because this feature got it wrong first.** An earlier
draft made "the row passes against `packs/vault`" the control. It would have passed by
asserting nothing — `packs/vault/pack.toml` has no `phases` key, so its cards have no bound
skill and zero restated rules there means *no binding*, not good delegation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conformance.packs.rule_inventory import (
    INVENTORIES,
    TERRAFORM_STYLE,
    prose_lines,
    verify_inventory,
)

ROOT = Path(__file__).resolve().parents[3]

#: The content the terraform Write card does NOT carry, every piece of which appears in the
#: guide only inside a fenced code block. These are the two rules 051 measured SC-002 on.
EXAMPLE_ONLY = ("default_tags", "validation", "alias")


def _card(pack: str, phase: str) -> str:
    return (ROOT / "packs" / pack / "agents" / phase / "AGENTS.md").read_text(encoding="utf-8")


def _skill(inventory: object) -> str:
    return (ROOT / inventory.path).read_text(encoding="utf-8")  # type: ignore[attr-defined]


# ---------------------------------------------------------------- A3: what counts as a rule


def test_the_inventory_holds_only_what_the_guide_actually_states() -> None:
    """Row A3's foundation. An inventory entry quoting something the guide does not say in
    prose would widen what counts as delegated practice — and a card could then delete a rule
    nothing supplies.

    This is what makes the inventory *derived* rather than asserted. It has already caught one
    entry, whose quote had drifted from the guide's wording by a clause.
    """
    for inventory in INVENTORIES.values():
        missing = verify_inventory(inventory, _skill(inventory))
        assert missing == [], (
            f"{inventory.skill}: these rules quote text that is not in the guide's prose — "
            f"either the guide changed or the entry was written from memory: {missing}"
        )


@pytest.mark.parametrize("term", EXAMPLE_ONLY)
def test_example_only_content_is_never_a_stated_rule(term: str) -> None:
    """ROW A3, and the selection error this whole feature is a correction of.

    `default_tags`, `validation` and aliased providers appear in the guide **only inside fenced
    code blocks**. 051 measured SC-002 on two of them, which is why both arms came back level:
    the guide never instructs any of it, so delivering the guide could not teach it.

    Asserted against the real file rather than a fixture, because the claim is about this
    specific vendored document.
    """
    text = _skill(TERRAFORM_STYLE)
    assert term in text, f"{term} is gone from the guide; this row now asserts nothing"

    prose = "\n".join(line for _, line in prose_lines(text))
    assert term not in prose, (
        f"`{term}` is now stated in the guide's prose rather than shown in an example. It has "
        "become taught practice, so it belongs in the inventory — and it becomes a legitimate "
        "SC-002 candidate for the first time."
    )

    assert not any(term in rule.quote for rule in TERRAFORM_STYLE.rules), (
        f"the inventory admits `{term}` as a stated rule, but the guide only shows it in an "
        "example. This is exactly the selection error that produced 051's null result."
    )


# ---------------------------------------------------------------- A6: the inventory's bytes


def test_each_inventory_is_bound_to_the_pinned_digest() -> None:
    """ROW A6 / FR-012. An inventory is only true of the bytes it was read from.

    051 already refuses to load a pack whose skill digest moved without a recorded re-review.
    This is what that review is now *for*: after 053 the cards depend on content they no longer
    hold, so an inventory left describing bytes that are gone would let a card delegate a rule
    the guide has stopped giving.
    """
    manifests = {
        "terraform": (ROOT / "packs" / "terraform" / "pack.toml").read_text(encoding="utf-8"),
        "vault": (ROOT / "packs" / "vault" / "pack.toml").read_text(encoding="utf-8"),
    }
    for inventory in INVENTORIES.values():
        found = any(inventory.digest in text for text in manifests.values())
        assert found, (
            f"{inventory.skill}'s inventory is pinned to digest {inventory.digest[:16]}…, which "
            "no pack manifest declares. The skill was re-pinned and the inventory was left "
            "describing bytes that are gone — re-derive it against the new content."
        )
