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

from tests.conformance.packs import card_fixtures as fixtures
from tests.conformance.packs.rule_inventory import (
    INVENTORIES,
    TERRAFORM_STYLE,
    Inventory,
    bound_phases,
    compare_card,
    declared_overrides,
    prose_lines,
    verify_inventory,
)

ROOT = Path(__file__).resolve().parents[3]

#: The content the terraform Write card does NOT carry, every piece of which appears in the
#: guide only inside a fenced code block. These are the two rules 051 measured SC-002 on.
EXAMPLE_ONLY = ("default_tags", "validation", "alias")


def _card(pack: str, phase: str) -> str:
    return (ROOT / "packs" / pack / "agents" / phase / "AGENTS.md").read_text(encoding="utf-8")


def _skill(inventory: Inventory) -> str:
    return (ROOT / inventory.path).read_text(encoding="utf-8")


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


# ---------------------------------------------------------------- A7: what gets compared

#: Every shipped pack, and the skills its manifest declares.
PACKS = ("terraform", "vault")


def _manifest(pack: str) -> str:
    return (ROOT / "packs" / pack / "pack.toml").read_text(encoding="utf-8")


def _bindings() -> list[tuple[str, str, str]]:
    """`(pack, skill, phase)` for every binding any manifest declares.

    Derived rather than hard-coded, so a fourth binding added later is compared without
    anybody remembering to add it here (FR-005).
    """
    found: list[tuple[str, str, str]] = []
    for pack in PACKS:
        manifest = _manifest(pack)
        for skill in INVENTORIES:
            for phase in bound_phases(manifest, skill):
                found.append((pack, skill, phase))
    return found


def test_the_comparison_covers_every_binding_the_manifests_declare() -> None:
    """ROW A7. A hard-coded list of three phases would stop covering a fourth."""
    bindings = _bindings()
    assert bindings, "no bindings found; the comparison below would assert nothing"
    assert {(p, ph) for p, _, ph in bindings} == {
        ("terraform", "plan"),
        ("terraform", "write"),
        ("terraform", "judge"),
    }, (
        "the set of skill-bound phases has changed. Add the new binding's pack to PACKS and "
        f"its skill to INVENTORIES, then re-derive: {sorted(bindings)}"
    )


# ---------------------------------------------------------------- A1 / A0 / A2: the rule


@pytest.mark.parametrize("pack,skill,phase", _bindings(), ids=lambda v: str(v))
def test_no_card_restates_what_its_bound_skill_states(pack: str, skill: str, phase: str) -> None:
    """ROW A1 — the rule this feature exists to hold.

    While a card restated the guide, removing the binding changed nothing, so ADR-0004's pin
    governed none of the rules it was supposed to govern and 051's SC-002 could not be
    measured at all.
    """
    restated = compare_card(_card(pack, phase), INVENTORIES[skill])
    assert restated == [], (
        f"`packs/{pack}/agents/{phase}/AGENTS.md` states rules that `{skill}` already states, "
        f"so removing the binding would leave them in force: {restated}. Delete them from the "
        "card, or — if the card knowingly contradicts or narrows one — declare it with "
        "`> **Overrides `<rule_id>`**: <reason>` so the disagreement is visible on the page."
    )


def test_the_baselines_are_derived_not_probed() -> None:
    """ROW A0. A probe count is not a baseline, and analysis caught this before it shipped.

    An earlier draft recorded write 16 / judge 7 / plan 6 as the numbers the real mechanism
    must reproduce. The first was measured against the guide's full stated surface, the other
    two against a twelve-rule hand-built probe — three figures, two denominators, and a target
    the derived inventory could only have hit by being bent to fit it.
    """
    for phase, expected in fixtures.DERIVED_BASELINES.items():
        actual = compare_card(fixtures.PRE_053_CARDS[phase], TERRAFORM_STYLE)
        assert len(actual) == expected, (
            f"the derived baseline for {phase} moved from {expected} to {len(actual)}. If the "
            "inventory or its patterns changed, re-record `DERIVED_BASELINES` — but never edit "
            "the inventory to reach a number."
        )
        assert set(actual) == set(fixtures.PRE_053_RESTATED[phase])

    assert fixtures.DERIVED_BASELINES != fixtures.PROBE_COUNTS, (
        "the derived baselines have become the probe counts. That is the defect analysis "
        "caught: the probe was a subset chosen to establish THAT the cards duplicate, not "
        "how much."
    )


def test_an_override_states_what_it_overrides_and_why() -> None:
    """ROW A2 / FR-002. An override without a reason is a restatement nobody has to justify.

    The known instance is version pinning: the guide shows `required_version = ">= 1.14"` and
    lists `>=` among its constraint operators, while every card here refuses `>=` as a pin.
    051's precedence rule resolves that at runtime; this keeps it visible on the page.
    """
    seen: set[str] = set()
    for pack, skill, phase in _bindings():
        known = {rule.id for rule in INVENTORIES[skill].rules}
        for rule_id, reason in declared_overrides(_card(pack, phase)).items():
            seen.add(rule_id)
            assert rule_id in known, (
                f"{pack}/{phase} declares an override of `{rule_id}`, which `{skill}` does not "
                "state. An override of nothing exempts the card from a rule that never applied."
            )
            assert len(reason) > 30, (
                f"{pack}/{phase}'s override of `{rule_id}` gives no real reason: {reason!r}"
            )
    assert "version_constraint_operators" in seen, (
        "no card declares the pinning override any more. Either the guide stopped showing "
        "`>= 1.14`, or a card silently stopped refusing a floating constraint."
    )


# ---------------------------------------------------------------- A4 / A5a: the control


@pytest.mark.parametrize("phase", sorted(fixtures.PRE_053_CARDS))
def test_the_comparison_fails_against_the_pre_feature_cards(phase: str) -> None:
    """ROW A4 — what makes A1 evidence rather than a detector that finds nothing.

    Asserted against text frozen before the edit, so this keeps working forever. Watching a row
    go red once and then green proves the same thing exactly once.
    """
    restated = compare_card(fixtures.PRE_053_CARDS[phase], TERRAFORM_STYLE)
    assert restated, (
        f"the comparison finds nothing wrong with the {phase} card as it stood at "
        f"{fixtures.CAPTURED_AT}, which is the text this feature was written to fix. The "
        "detector has been weakened."
    )


def test_the_comparison_passes_after_the_edits() -> None:
    """ROW A5a — the other half of the control. A4 alone shows only that something was wrong."""
    for pack, skill, phase in _bindings():
        assert compare_card(_card(pack, phase), INVENTORIES[skill]) == []


# ---------------------------------------------------------------- A5: the unbound case


def test_a_pack_with_no_bound_skill_is_reported_unbound_not_clean() -> None:
    """ROW A5, and the row that exists because this feature got it wrong first.

    An earlier draft made "the comparison passes against `packs/vault`" the control. It would
    have passed by asserting nothing: `packs/vault/pack.toml` has no `phases` key, so its cards
    have no bound skill, and zero restated rules there means *no binding* rather than good
    delegation. The draft also proposed deleting two rules from the vault Write card — guidance
    no skill would then supply — and would have broken the fixture 051's R12 says must not
    acquire a binding by tidiness.
    """
    manifest = _manifest("vault")
    assert "vault-secret-access" in manifest, "the vault skill is gone; this row asserts nothing"
    assert bound_phases(manifest, "vault-secret-access") == (), (
        "`vault-secret-access` has acquired a binding. That is a real decision with a "
        "re-qualification cost — and its cards must now be compared, so add an inventory for "
        "it and drop this row's assumption."
    )
    assert "vault" not in {pack for pack, _, _ in _bindings()}, (
        "a vault phase now appears in the compared set while this row still calls it unbound"
    )


def test_the_pack_level_picture_is_reported_not_only_per_card() -> None:
    """ROW A9. Practice distributed across cards must not read as cleanliness.

    Judge states `validation` and `default_tags` — the two rules Write is silent on, and the
    two 051 measured SC-002 against. A per-card view alone would have called the terraform
    pack partly clean while the pack as a whole restated nearly everything.
    """
    by_pack: dict[str, list[str]] = {}
    for pack, skill, phase in _bindings():
        by_pack.setdefault(pack, []).extend(compare_card(_card(pack, phase), INVENTORIES[skill]))
    assert by_pack, "no pack was measured"
    for pack, restated in by_pack.items():
        assert restated == [], f"pack `{pack}` restates {sorted(set(restated))} across its cards"


# ---------------------------------------------------------------- A8: the load-bearing one


def test_absent_delivery_still_refuses() -> None:
    """ROW A8 — the row the whole feature rests on.

    Delegation removes rules from a card on the strength of them arriving from elsewhere. If
    absent delivery ever stopped refusing, 053 would have converted a duplicated rule into a
    missing one, silently, and nothing else here would notice.

    Read from the loader's source rather than by staging a broken pack: the property is that
    each code is reached by a raise, and a fixture pack would prove it for one path at a time.
    """
    loader = (ROOT / "src" / "core" / "packs" / "loader.py").read_text(encoding="utf-8")
    for code in ("skill_missing", "skill_empty", "digest_mismatch"):
        marker = f'reason_code="{code}"'
        assert marker in loader, f"{code} is gone from the loader"
        raised = False
        start = 0
        while (found := loader.find(marker, start)) != -1:
            head = loader.rfind("raise ManifestError", 0, found)
            if head != -1 and len(loader[head:found]) < 400:
                raised = True
            start = found + 1
        assert raised, (
            f"`{code}` no longer stops the load. Every delegating card now relies on delivery "
            "that can silently not happen — 053's premise is gone, and the cards must take "
            "their rules back before this can be allowed to pass."
        )


# ---------------------------------------------------------------- SC-006


def test_the_feature_changed_no_platform_source() -> None:
    """SC-006. 053 is pack content and gate rows; a `src/` change would mean it grew a seam.

    Named modules rather than a diff, following `test_relevance_prompt_untouched_by_046.py`:
    a git-diff check reports whatever the working tree happens to hold, which is not a property
    of the feature.
    """
    src = ROOT / "src"
    for module in ("core/packs/loader.py", "core/packs/agents.py", "core/packs/manifest.py"):
        text = (src / module).read_text(encoding="utf-8")
        assert "053" not in text and "rule_inventory" not in text, (
            f"{module} references 053. The feature was specified as pack content and gate rows "
            "with zero core changes; if a seam really is needed, SC-006 is invalidated and the "
            "security-maintainer review obligation returns with it."
        )
