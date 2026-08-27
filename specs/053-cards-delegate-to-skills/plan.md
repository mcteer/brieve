# Implementation Plan: A phase card delegates to the skill it is bound to

**Branch**: `spec/053-cards-delegate-to-skills` | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/053-cards-delegate-to-skills/spec.md`

## Summary

051 pinned two HashiCorp skills and delivered them to `plan`, `write` and `judge`. It proved
delivery byte-for-byte and could not prove effect: SC-002 returned NOT DEMONSTRATED. The
reason, measured hermetically on 2026-08-27, is that the Write card states **all sixteen** of
the guide's prose rules by hand — so removing the binding entirely would leave every rule in
force, and no measurement could show anything. The duplication is pack-wide
([R1](research.md)): Judge 7 of 12, Plan 6 of 12.

This feature makes the pin load-bearing. The three bound cards delegate the practice the skill
states, keep what is genuinely this platform's own, and keep §Pins as a **declared override**
that says what it contradicts and why. A hermetic row then holds the line, with `packs/vault`
as the passing control at 2 of 8 ([R4](research.md)).

**Everything is pack content and gate rows. No platform source changes** — the seam 051 built
is consumed, not widened.

Three findings from research are carried into the design rather than discovered during it.
Judge already states the two rules Write is silent on ([R2](research.md)), so de-duplication is
computed per phase and reported per pack, or distribution across cards would read as
cleanliness. Judge cannot delegate the skill's own Code Review Checklist ([R3](research.md)),
because two of its ten items are the `terraform fmt` / `terraform validate` steps this pack
already declares unsatisfiable. And SC-002's replacement rule must be **structural**
([R5](research.md)) — none of the nine existing detectors survives de-duplication as a
candidate.

## Technical Context

**Language/Version**: Python 3.14 (gate rows only); pack content is Markdown and TOML

**Primary Dependencies**: None added. Consumes `core.packs.loader`, `core.packs.agents` and the
`tests/evals_live` scorers as they stand

**Storage**: N/A — no schema, no payload, no record shape is touched

**Testing**: `pytest` hermetic rows in `tests/conformance/packs/`; the standing SC-002 harness
`evals/prompt-tune/sc002_skill_effect.py` for the live measurement

**Target Platform**: Unchanged — pack content is substrate-independent

**Project Type**: Content profile plus conformance rows (ADR-0003)

**Performance Goals**: N/A. Delegation reduces assembled instruction size; it cannot increase it

**Constraints**: `SKILL.md` is upstream and digest-pinned to commit `8c6573ab` and must not be
edited. Phase-agent promotion is all-five-or-none and gates on both suites ([R8](research.md))

**Scale/Scope**: Three terraform cards, one vault card, one skill rule inventory per skill, one
new structural detector, one enforcement row

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0 (Last Amended 2026-08-05) — checked against that version.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | The change is *removing* hand-written duplicates of adopted content. This is the principle applied to the content plane: what upstream supplies, this platform stops re-authoring |
| II — Total Interception; One Governed Tool Layer | Pass | No tool, transport or egress class touched. The registry bound stays stated in §Precedence, which is retained as platform-own ([R6](research.md)) |
| III — Fail-Closed, In-Process Enforcement | Pass **and depended upon** | Delegation is only safe because absent delivery refuses: `skill_missing`, `skill_empty`, `digest_mismatch` each `raise ManifestError`. Verified, not assumed — and asserted by a row, because the whole feature rests on it |
| IV — Zero Standing Credentials; Authority Per Task | N/A | No identity, credential, ceiling or scope surface is touched |
| V — Sealed Core, Versioned Seams | Pass | **Zero core source changes** (SC-006). Pack content and test rows only; no registry schema, no audit payload, no seam. No security-maintainer review is owed on that ground |
| VI — Lean by Default | Pass | Nothing operated, no dependency, no module. One new detector function and one new row; three cards get shorter |
| VII — Anti-Fragmentation | **The principle this feature serves** | One body of practice currently maintained in two places, one of them vendored and unmodifiable — and already contradicting itself on `required_version`. After this, one source with declared overrides |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | Pass **with obligation** | The edited cards are re-qualified before promotion ([R8](research.md)), all-five-or-none. FR-010. A card edit may not ship on a prior qualification |
| IX — Evidence Over Claims | Pass | FR-008 records the withdrawal of the minimality hypothesis rather than quietly dropping it; FR-009 keeps a level SC-002 result recordable. SC-004 forecloses leaving the question open to drive further edits |
| X — The Decision Record Governs | Pass | ADR-0004's pin is made load-bearing; ADR-0030's "executed content is pinned" is honoured by there being one copy; ADR-0047 is the failure being repaired. No Accepted ADR is contradicted and none is needed |

**Gate result**: **PASS — proceed to Phase 0.**

### One obligation the plan carries forward

Principle III is not merely satisfied here, it is **load-bearing**. If absent delivery did not
refuse, this feature would trade a duplicated rule for a silently missing one. That is why the
contract requires a row asserting the refusal from the delegating card's point of view, rather
than citing 051's rows and moving on.

## Project Structure

### Documentation (this feature)

```
specs/053-cards-delegate-to-skills/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R8
├── data-model.md        # stated rule, override, rule inventory
├── quickstart.md        # how to reproduce every measurement here
├── contracts/
│   └── conformance-cards-delegate.md
└── checklists/requirements.md
```

### Source Code (repository root)

```
packs/terraform/agents/write/AGENTS.md     # delegate 16 rules; keep §Precedence, §Pins (override), minimality
packs/terraform/agents/judge/AGENTS.md     # delegate style criteria; keep its own checklist (R3)
packs/terraform/agents/plan/AGENTS.md      # delegate 6 restated rules
packs/vault/agents/write/AGENTS.md         # remove the 2-of-8 residue

tests/conformance/packs/
├── rule_inventory.py                      # rules derived per skill, digest-bound (R7)
├── card_fixtures.py                       # frozen pre-feature card text; the baselines
└── test_cards_delegate_to_skills.py       # the enforcement row + the vault control

tests/evals_live/authoring_properties.py   # one new structural detector (R5)
evals/authoring/corpus.toml                # a task that exercises it
```

**Structure Decision**: Pack content plus conformance rows, matching ADR-0003 and the
`tests/conformance/packs/` family this row joins ([R7](research.md)). Nothing under `src/`.

## Complexity Tracking

| Question | Answer |
| --- | --- |
| Why a curated rule inventory rather than automatic overlap detection? | Reviewability. A maintainer must see *which rule* is duplicated and where. A similarity score is a number to argue with; an inventory entry is a fact to act on ([R7](research.md)) |
| Why does Judge keep a checklist when Write delegates its rules? | Two of the skill checklist's ten items are the capabilities this pack declares unsatisfiable. Delegating them would make an unperformable step operative instruction ([R3](research.md)) |
| Why a new detector rather than reusing one of nine? | All nine either were measured flat or belong to rules the card keeps. `variable_has_validation` fails the spec's own bar — Sonnet 5 emits it unprompted at 5/5 in both arms ([R5](research.md)) |
| Why is vault in scope at all? | As the control. A gate whose only subject is the thing it condemns proves nothing about whether it can be satisfied ([R4](research.md)) |

## Post-design Constitution re-check

*Run after Phase 1. Design artifacts: [research.md](research.md), [data-model.md](data-model.md),
[contracts/conformance-cards-delegate.md](contracts/conformance-cards-delegate.md),
[quickstart.md](quickstart.md).*

**Verdict unchanged: PASS.** Three verdicts were re-examined because the design moved after
they were recorded:

| Principle | Re-checked because | Outcome |
| --- | --- | --- |
| V — Sealed Core | Phase 1 added a new **detector** to `tests/evals_live/authoring_properties.py` and a corpus task | Still Pass. Both are test-lane assets, not `src/`. SC-006 is now asserted by a row rather than by intention (contract §4) |
| VI — Lean by Default | The file list grew from "three cards" to four cards, an inventory module, a row, a detector and a corpus task | Still Pass, and worth stating plainly: the feature **removes** more content than it adds. The additions are all gate machinery, which Principle VI has never counted against a feature that would otherwise rest on review |
| VIII — Eval-Gated Promotion | [R3](research.md) found Judge cannot delegate the skill's checklist | Still Pass, and the constraint is now explicit rather than discovered at implementation. Delegating those two items would have made an unperformable step operative instruction |

**One thing the design made stronger.** Principle III was recorded as "Pass and depended upon".
Phase 1 turned that dependency into row A8, which asserts the refusal from the delegating
card's point of view. Before that row, the plan's safety argument was a citation of 051; now it
is a test that fails if 051's guarantee ever weakens.

**Nothing in Phase 1 required a new ADR**, and no Accepted record is contradicted. ADR-0004's
pin becomes load-bearing, which is the record being honoured rather than amended.
