# SPDX-License-Identifier: Apache-2.0
"""What a bound skill states, and whether a phase card says it too (053, T004-T009b).

051 pinned two HashiCorp skills and delivered them to `plan`, `write` and `judge`. It could not
show that receiving one *changed* anything, and the reason measured on 2026-08-27 is that the
Write card states the guide's rules by hand — so removing the binding would leave them all in
force. A pin that governs nothing is ADR-0047's failure in the content plane.

**Rules are derived from the guide, then verified against it.** `INVENTORIES` below is
hand-authored, because recognising "the same rule, said differently" in a card is a judgement a
regex cannot make. What is *not* hand-asserted is that each rule is really in the skill:
`verify_inventory` requires every rule's `quote` to appear in the guide's own prose, so an
entry describing a rule the guide does not give fails rather than quietly widening the gate.

**Prose only.** Content inside a fenced code block is not a stated rule (FR-003). Three of the
four things the Write card does not carry — aliased providers, `default_tags`, `validation`
blocks — appear only in examples, and treating them as taught practice is the selection error
that produced 051's null SC-002 result.

**The count is what the guide yields.** A probe found sixteen rules and that number reached the
spec as a baseline; the derivation here finds more, because the probe was a subset chosen to
establish *that* the card duplicates rather than *how much*. Fitting the inventory back to
sixteen would be answering to the probe instead of the guide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: How a card declares that it knowingly contradicts a stated rule (FR-002).
#:
#: Machine-readable so the gate can tell an override from a restatement, and readable so the
#: disagreement is visible on the page rather than resolved silently by 051's precedence rule
#: at runtime. Leading whitespace is allowed: a blockquote nested inside a list item is
#: legitimate markdown, and the Plan card needs one there.
OVERRIDE_MARKER = re.compile(
    r"^[ \t]*>\s*\*\*Overrides `(?P<rule>[a-z0-9_]+)`\*\*:\s*(?P<reason>\S.*)$", re.MULTILINE
)


@dataclass(frozen=True)
class StatedRule:
    """One instruction a skill gives in prose."""

    id: str
    #: The guide's own words. Verified to appear in its prose by `verify_inventory`.
    quote: str
    #: Patterns recognising the same rule in a card, however differently it is worded.
    match: tuple[str, ...]
    #: Where the guide states it, so a reader can check this entry against the source.
    line: int = 0
    #: Set when the rule names a capability this platform has no registry tool for.
    unsatisfiable: bool = False


@dataclass(frozen=True)
class Inventory:
    """The stated rules of one skill, bound to the bytes they were read from (FR-012)."""

    skill: str
    path: str
    digest: str
    rules: tuple[StatedRule, ...] = field(default_factory=tuple)


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Every line outside a fenced code block, numbered from 1.

    The whole distinction this feature rests on. `terraform-style-guide/SKILL.md` is 314 lines
    of which 64 are prose; everything else is example HCL that states nothing.
    """
    out: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("```"):
            fenced = not fenced
            continue
        stripped = line.strip()
        # Headings name a section; they state nothing. Excluding them is what makes the count
        # comparable to the 64-of-314 figure the spec rests on.
        if not fenced and stripped and not stripped.startswith("#"):
            out.append((number, stripped))
    return out


def unfenced(text: str) -> list[str]:
    """Every line outside a fenced code block, headings included.

    The invariant a stated rule must satisfy: said, not merely shown. `prose_lines` is
    narrower and exists for the 64-of-314 measurement; this is what membership is judged on,
    because the guide states "Prefer for_each over count" as a heading and that is an
    instruction whatever its markdown level.
    """
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if not fenced and line.strip():
            out.append(line.strip())
    return out


def verify_inventory(inventory: Inventory, skill_text: str) -> list[str]:
    """Rule ids whose `quote` is NOT in the skill's prose. Empty means the inventory is honest.

    This is what makes the inventory derived rather than asserted. An entry quoting something
    the guide only shows in an example, or does not say at all, would widen what counts as
    delegated practice — and a card could then delete a rule nothing supplies.
    """
    stated = "\n".join(unfenced(skill_text))
    return [rule.id for rule in inventory.rules if rule.quote not in stated]


def declared_overrides(card_text: str) -> dict[str, str]:
    """Rule ids the card declares it overrides, mapped to the reason it gives (FR-002).

    A reason is required. An override without one is indistinguishable from a card that simply
    kept the rule, which is the thing being forbidden.
    """
    found: dict[str, str] = {}
    lines = card_text.splitlines()
    for index, line in enumerate(lines):
        opener = OVERRIDE_MARKER.match(line)
        if opener is None:
            continue
        # A reason runs to the end of its blockquote, not to the end of its first line. Taking
        # only the first line would reject a properly-explained override for being terse.
        reason = [opener.group("reason").strip()]
        for follow in lines[index + 1 :]:
            stripped = follow.strip()
            if not stripped.startswith(">"):
                break
            reason.append(stripped.lstrip("> ").strip())
        found[opener.group("rule")] = " ".join(part for part in reason if part).strip()
    return found


def compare_card(card_text: str, inventory: Inventory) -> list[str]:
    """Rule ids the card states without declaring them as overrides.

    Returns ids rather than a score, because a maintainer has to see *which* rule is duplicated
    to act on it. A similarity number is something to argue with.

    Rules marked `unsatisfiable` are skipped — see the comment below, and research R3.
    """
    overrides = declared_overrides(card_text)
    body = OVERRIDE_MARKER.sub("", card_text)
    # Collapsed to one line: a rule wrapped across a line break is the same rule, and a card
    # must not be able to evade the gate by reflowing a paragraph.
    body = re.sub(r"\s+", " ", body)
    restated: list[str] = []
    for rule in inventory.rules:
        if rule.id in overrides:
            continue
        # A rule naming a capability the registry does not offer is one the card must DECLINE,
        # not delegate. All three terraform cards name `terraform fmt` and `terraform validate`
        # in their Precedence section to say they are not performed and never reported as
        # performed — which is 051's requirement, not duplication. Counting that as a
        # restatement would push a maintainer to delete the refusal.
        if rule.unsatisfiable:
            continue
        if any(re.search(pattern, body, re.IGNORECASE | re.MULTILINE) for pattern in rule.match):
            restated.append(rule.id)
    return restated


def bound_phases(pack_manifest: str, skill_name: str) -> tuple[str, ...]:
    """The phases a skill is bound to, read from the pack manifest (FR-005, row A7).

    Derived rather than hard-coded, so a binding added later is not silently unchecked. Returns
    empty for a skill bound to nothing — which is `vault-secret-access`, and is why row A5
    exists: no binding is not the same as good delegation.
    """
    block = re.search(
        rf'\[\[skills\]\]\s*\nname\s*=\s*"{re.escape(skill_name)}".*?(?=\n\[\[|\Z)',
        pack_manifest,
        re.DOTALL,
    )
    if block is None:
        return ()
    phases = re.search(r"^phases\s*=\s*\[(.*?)\]", block.group(0), re.MULTILINE)
    if phases is None:
        return ()
    return tuple(re.findall(r'"([a-z]+)"', phases.group(1)))


#: The stated rules of `terraform-style-guide/SKILL.md` (T008).
#:
#: Derived from the guide's prose, in the order it states them, and verified by
#: `verify_inventory` — every quote below appears in the file. The `match` patterns are the
#: judgement: they recognise the same rule in a card however differently it is worded, which is
#: what "restates by hand" means and what no regex over the guide alone could establish.
TERRAFORM_STYLE = Inventory(
    skill="terraform-style-guide",
    path="packs/terraform/skills/terraform-style-guide/SKILL.md",
    digest="fea8a0eadf68f1ac45cae3b1d6dc4c66b489fb6e40a3d41762120059c49540c2",
    rules=(
        StatedRule(
            "generation_starts_with_versions",
            "Start with provider configuration and version constraints",
            (r"start with .*(provider|version)", r"terraform\.tf.*first"),
            16,
        ),
        StatedRule(
            "data_sources_before_dependents",
            "Create data sources before dependent resources",
            (r"data sources? before", r"before dependent resources"),
            17,
        ),
        StatedRule(
            "resources_in_dependency_order",
            "Build resources in dependency order",
            (r"dependency order",),
            18,
        ),
        # `r"output if a later phase"` was here and had to go: it matched a parenthetical
        # inside the card's Vault-wiring guidance, which applies the idea rather than stating
        # the rule. The general form lived in §Order of authorship and is now delegated.
        StatedRule(
            "outputs_for_key_attributes",
            "Add outputs for key resource attributes",
            (r"outputs? for key", r"^\s*\d\.\s*outputs? for"),
            19,
        ),
        StatedRule(
            "variables_for_configurable_values",
            "Use variables for all configurable values",
            (r"variables for all configurable", r"variable for (every|each) configurable"),
            20,
        ),
        StatedRule(
            "standard_file_set",
            "| `locals.tf` | Local value declarations |",
            (
                # The canonical FILE SET, not any mention of two of its members. Naming
                # `variables.tf` and `outputs.tf` while deciding which files a slice needs
                # is a planning decision; enumerating the set is the restatement.
                r"(?:`(?:terraform|versions|providers|main|variables|outputs|locals)\.tf`"
                r"(?: |,|/|or)*){3,}",
            ),
            31,
        ),
        StatedRule(
            "variables_alphabetical",
            "| `variables.tf` | Input variable declarations (alphabetical) |",
            (r"alphabetical in `variables\.tf`", r"variables.{0,20}alphabetical"),
            29,
        ),
        StatedRule(
            "outputs_alphabetical",
            "| `outputs.tf` | Output value declarations (alphabetical) |",
            (r"outputs.{0,20}alphabetical",),
            30,
        ),
        StatedRule(
            "two_space_indent",
            "- Use **two spaces** per nesting level (no tabs)",
            (r"two spaces per (indent|nesting)", r"two-space indent"),
            88,
        ),
        StatedRule(
            "align_equals",
            "- Align equals signs for consecutive arguments",
            (r"align.{0,12}equals",),
            89,
        ),
        StatedRule(
            "for_each_over_count",
            "### Prefer for_each over count",
            (r"`for_each`.{0,40}over `count`", r"`for_each` for a named set", r"prefer `for_each`"),
            191,
        ),
        StatedRule(
            "arguments_before_blocks",
            "Arguments precede blocks, with meta-arguments first:",
            (r"meta-arguments?\b.{0,30}first", r"arguments? (precede|before) .{0,16}blocks"),
            106,
        ),
        StatedRule(
            "lowercase_with_underscores",
            "- Use **lowercase with underscores** for all names",
            (r"lowercase with underscores",),
            131,
        ),
        StatedRule(
            "descriptive_nouns",
            "- Use **descriptive nouns** excluding the resource type",
            (r"descriptive nouns",),
            132,
        ),
        StatedRule(
            "names_specific_and_meaningful",
            "- Be specific and meaningful",
            (r"specific and meaningful",),
            133,
        ),
        StatedRule(
            "resource_names_singular",
            "- Resource names must be singular, not plural",
            (r"singular",),
            134,
        ),
        StatedRule(
            "main_when_redundant",
            "Default to `main` for resources where a specific descriptive name is redundant "
            "or unavailable, provided only one instance exists",
            (r"one of a kind may be `main`", r"default to `main`"),
            135,
        ),
        StatedRule(
            "variable_type_and_description",
            "Every variable must include `type` and `description`:",
            (r"variable has `type` and `description`", r"variables? (must )?(have|include) `type`"),
            151,
        ),
        StatedRule(
            "output_description",
            "Every output must include `description`:",
            (r"output has `description`", r"outputs? (must )?(have|include) `description`"),
            174,
        ),
        StatedRule(
            "security_in_security_md",
            "Refer to SECURITY.md. It includes guidance on encrypting resources,",
            (r"refer to security\.md",),
            225,
        ),
        StatedRule(
            "latest_versions_unless_constrained",
            "Use the latest major version of each provider and the latest minor version of",
            (r"latest major version",),
            243,
        ),
        StatedRule(
            "version_constraint_operators",
            "- `~> 1.0` - Allow rightmost component to increment",
            (r"`~>`.{0,40}(is a pin|pessimistic)", r"rightmost component"),
            250,
        ),
        StatedRule(
            "never_commit_state",
            "- `terraform.tfstate`, `terraform.tfstate.backup`",
            (r"no `terraform\.tfstate`", r"never.{0,24}commit.{0,40}tfstate"),
            277,
        ),
        StatedRule(
            "never_commit_terraform_dir", "- `.terraform/` directory", (r"`\.terraform/`",), 278
        ),
        StatedRule("never_commit_tfplan", "- `*.tfplan`", (r"\.tfplan",), 279),
        StatedRule(
            "never_commit_secret_tfvars",
            "- `.tfvars` files with sensitive data",
            (r"secret `\.tfvars`", r"`\.tfvars`.{0,30}sensitive"),
            280,
        ),
        StatedRule(
            "always_commit_lock_file",
            "- `.terraform.lock.hcl` (dependency lock file)",
            (r"`\.terraform\.lock\.hcl`",),
            284,
        ),
        StatedRule(
            "sensitive_true_on_secrets",
            "- [ ] Sensitive values marked with `sensitive = true`",
            (r"`sensitive = true`",),
            308,
        ),
        StatedRule(
            "no_hardcoded_credentials",
            "- [ ] No hardcoded credentials or secrets",
            (r"no literal credential", r"no hardcoded credential"),
            309,
        ),
        StatedRule(
            "run_fmt_before_commit",
            "- [ ] Code formatted with `terraform fmt`",
            (r"`terraform fmt`",),
            301,
            unsatisfiable=True,
        ),
        StatedRule(
            "run_validate_before_commit",
            "- [ ] Configuration validated with `terraform validate`",
            (r"`terraform validate`",),
            302,
            unsatisfiable=True,
        ),
        StatedRule(
            "additional_linting_tools", "- `tflint` - Linting and best practices", (r"tflint",), 296
        ),
    ),
)

#: Every inventory, by skill name.
INVENTORIES = {TERRAFORM_STYLE.skill: TERRAFORM_STYLE}
