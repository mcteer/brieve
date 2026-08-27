# Data Model: A phase card delegates to the skill it is bound to

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

No runtime entity is added. Everything here is *authoring-time* structure: what the gate row
reads, and what a maintainer edits. Nothing reaches a checkpoint, a record, or a payload.

## Stated rule

An instruction a skill gives **in prose**. The unit of comparison.

| Field | Meaning |
| --- | --- |
| `id` | Stable slug, e.g. `two_space_indent`. Referenced by failures, so it must not churn |
| `skill` | The bound skill it comes from |
| `quote` | The skill's own words, so a reader can check the inventory against the source |
| `line` | Where it is stated, for the same reason |
| `match` | How the same rule is recognised in a card |

**The distinction that decides membership**: content appearing only inside a fenced code block
is **not** a stated rule (FR-003). Three of the four things the terraform Write card does not
carry — aliased providers, `default_tags`, `validation` blocks — are exactly this, and treating
them as taught practice is the selection error that produced 051's null SC-002 result.

## Override

A card rule that knowingly contradicts or narrows a stated rule. The one sanctioned overlap.

| Field | Meaning |
| --- | --- |
| `rule` | The stated rule it overrides |
| `reason` | Why, in the card itself — not in a test, not in a commit message |

**Known instance**: version pinning. The guide shows `required_version = ">= 1.14"` at lines 38
and 232; `write/AGENTS.md` §Pins says `>=` is not a pin. The card keeps its rule and must say
what it overrides, so the disagreement is visible on the page rather than resolved silently by
051's precedence rule at runtime.

An override is recognised **from the card's own text**. A rule the card merely restates and a
rule the card deliberately overrides must not be distinguishable only by a maintainer's
intention — the card has to say which it is, or the row cannot tell them apart and neither can
a reader.

## Rule inventory

The enumerated stated rules of one skill, with its digest.

| Field | Meaning |
| --- | --- |
| `skill` | Manifest name |
| `digest` | The bytes the inventory was built from |
| `rules` | The stated rules |

**Why the digest is a field and not a comment.** The inventory is only true of the bytes it was
read from. 051 already refuses to load a pack whose skill digest moved without a recorded
re-review; this makes the inventory part of what that review is *for*, because after this
feature the cards depend on content they no longer hold.

## Relationships

```
Rule inventory ──(built from)──> pinned SKILL.md bytes @ digest
      │
      ├──(each)──> Stated rule
      │                 │
      │                 └──(may be)──> Override, declared in the card, with a reason
      │
      └──(compared against)──> phase card, for every phase the skill is bound to
```

## What is deliberately not modelled

- **Example code.** Not a rule, not delegated, not a measurement candidate (FR-003).
- **Similarity.** There is no score. A rule is present in a card or it is not, and the row
  names which — the reviewability argument in [R7](research.md).
- **Per-run state.** A binding's *effect* is measured in the eval lane, never recorded per run.
  This feature changes what the card says, never what the record reports (FR-011).
