# Research: A phase card delegates to the skill it is bound to

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

All measurements here are hermetic and cheap to reproduce. Nothing below rests on a model run.

---

## R1 — The duplication is pack-wide, not one card

**Decision**: All three bound terraform phases are in scope, not the Write card alone.

**Measured**: `terraform-style-guide/SKILL.md` is 314 lines, 64 of them prose.

| Card | Restates | Against | Notes |
| --- | --- | --- | --- |
| `write/AGENTS.md` | **16 of 16** | the full stated-rule surface | every prose rule the guide gives |
| `judge/AGENTS.md` | 7 | a twelve-rule **probe** subset | plus two rules Write does not carry — see R2 |
| `plan/AGENTS.md` | 6 | the same probe subset | naming, `for_each`, meta-arguments, alphabetical, `tfstate` |

**The denominators are not comparable, and the Judge and Plan figures are provisional.** Write
was compared against the guide's whole stated surface; Judge and Plan against a twelve-rule
hand-built probe used to establish *that* they duplicate, not *how much*. Only the derived
inventory (T008) can give all three a common denominator, and the baselines are re-recorded
there. Any use of "7 of 12" or "6 of 12" as a target for the real mechanism is a mistake —
they were never measured against it.

**Rationale**: The spec's FR-005 already binds the rule to every phase bound to a skill. This
measurement is what makes the scope concrete: three cards, one pack.

**Alternatives considered**: Write-only. Rejected — it would leave Judge and Plan free to
re-import the practice, and SC-001 would be satisfiable while the pack still fragmented.

---

## R2 — Judge already states the two rules Write is silent on

**Decision**: De-duplication is computed per phase against that phase's bindings, and the
pack-level picture is reported so distribution across cards cannot hide it.

**Measured**: `judge/AGENTS.md` §Check states *"constrained variables have `validation`"* and
*"`default_tags` when the provider supports them."* Those are precisely the two properties
SC-002 was measured on, and precisely the two the Write card does not carry.

**Why this matters, carefully.** It does **not** invalidate 051's SC-002 result. Write's arms
were Write's instruction, which never held either rule, so the measurement was sound as run.
What it shows is that the practice is *distributed* — absent from one card, present in
another — so a per-card view alone would report the terraform pack as partly clean when the
pack as a whole restates nearly everything.

---

## R3 — Judge cannot simply delegate to the skill's own checklist

**Decision**: Judge delegates its style criteria but keeps a checklist of its own; the skill's
`## Code Review Checklist` is not adoptable wholesale.

**Measured**: The skill's checklist has ten items. Two are *"Code formatted with `terraform
fmt`"* and *"Configuration validated with `terraform validate`"* — the exact two capabilities
`packs/terraform/pack.toml` declares under `[[skills.unsatisfiable]]`, because this platform
has no registry tool for either.

**Rationale**: Delegating that checklist would reinstate, as Judge's operative instruction,
two steps the pack already declares unperformable. That is the overstatement 051's
unsatisfiable-declaration machinery exists to prevent, arriving by a new route.

**Alternatives considered**: Delegate the checklist and rely on the precedence rule to
suppress the two items at runtime. Rejected — precedence is how the platform survives a
contradiction it did not choose, not a licence to author one, which is the spec's own
reasoning about version pinning applied a second time.

---

## R4 — Vault is the control, and its residue is small

**Decision**: `packs/vault` is corrected where it overlaps, and serves as the passing control.

**Measured, provisionally**: 2 of an eight-rule **probe** subset restated by
`vault/agents/write/AGENTS.md` — check-and-set
on writes, and preferring a dynamic secret. Six are not: never asking for or reusing a token,
reporting an auth failure rather than routing around it, passing a path rather than the value,
use-and-discard, redacting before a durable write, and writing only to a scoped path. The
skill is also 50 prose lines of 109 — a far healthier ratio than terraform's 64 of 314.

**The eight is a probe, not a count.** The vault guide carries fifteen bullet-form prose
statements; eight were selected to establish direction quickly. The derived inventory (T009)
sets the real denominator, and "2 of 8" must not be treated as a target it should reproduce.

**Rationale**: This is what makes the rule credible rather than aspirational. A gate whose
only subject is the thing it was written to condemn proves nothing about whether it can be
satisfied; vault passes at 2 of 8 today and at 0 after a small correction.

---

## R5 — The candidate rule for SC-002 must be structural

**Decision**: A new property detector is required, and it should be **structural** — derived
from which files exist and how declarations are ordered — not a regex over HCL prose.

**Measured**: `tests/evals_live/authoring_properties.py` `detect()` reports nine properties.
None survives de-duplication as a candidate: `variable_has_validation` and
`tags_are_shared_not_ad_hoc` are the two already measured flat, and the rest are credential
and pinning properties the card keeps as its own or as overrides.

**Candidates, in order**:

1. **Standard file organisation.** The skill states it twice (the file table, and *"Files
   organized according to standard structure"*); the Write card restates it and would
   delegate it; and a model asked for a small change commonly emits a single `main.tf`.
   Detectable from the artefact's own filenames — no HCL parsing, no false positives.
2. **Variables alphabetical in `variables.tf`.** Same structural character, also stated by
   both documents today.

**Rationale**: The original SC-002 arms failed partly because the rules were drawn from
example code. A structural rule is stated in prose, is unambiguous to detect, and cannot be
scored differently by two readers — which is what a rule has to be to carry a success
criterion that a feature's honesty depends on.

**Alternatives considered**: Reuse `variable_has_validation`. Rejected — 051 measured Sonnet 5
emitting validation blocks unprompted at 5/5 in both arms, so it fails the spec's own bar that
a rule the model already follows cannot serve as evidence.

---

## R6 — What is genuinely the platform's own

**Decision**: Four categories stay in the card, and the boundary is stated rather than felt.

**Measured**, from `write/AGENTS.md`:

| Stays | Why |
| --- | --- |
| §Precedence | About how this file and a delivered skill meet. Cannot be delegated to the thing it governs |
| §Decide whether any change is needed, §Order of authorship | Minimality, and what to do when a task names nothing. Not Terraform style practice |
| §Pins | **Override.** The guide shows `required_version = ">= 1.14"`; this card says `>=` is not a pin. Must keep its rule *and* say what it overrides |
| §Least privilege, §Do not invent provider syntax, §Anti-patterns | This platform's own constraints on authoring, not the upstream style guide's |

**Rationale**: The line is *subject*, not tone: rules about Terraform style delegate; rules
about how this platform authors, and rules that knowingly disagree with the guide, stay.

---

## R7 — Where the check lives, and what it compares

**Decision**: A hermetic row in `tests/conformance/packs/`, comparing each card against a
curated rule inventory per skill.

**Measured**: That directory already holds this family — `test_declaration_keeps_pace.py`
(a declaration may not lag the bytes) and `test_unsatisfiable_declaration_stale.py` are the
nearest siblings, and both are hermetic with fixture packs in `skill_fixtures.py`.

**Rationale**: A semantic-similarity detector over prose would be a large build with false
positives in both directions, and would make the gate's verdict unreviewable. A curated
inventory is honest about being hand-built, is precise, and is revisited exactly when 051
already forces a human to read the content — on a digest change.

**Alternatives considered**: Compare token overlap or embeddings. Rejected on reviewability:
a maintainer must be able to see *which rule* is duplicated and where, which is what makes the
failure actionable rather than a score to argue with.

---

## R8 — Re-qualification is unavoidable, and that is the design

**Decision**: The card edits and the re-qualification ship in one change.

**Measured**: 051 established phase-agent promotion as all-five-or-none, gated on both suites
over assembled content (row E3, passed 2026-08-27: terraform 25+6, vault 25+6).

**Rationale**: The instruction that was qualified is the instruction being edited. Shipping the
edit on the strength of the previous qualification would assert an eval result for bytes no
eval ever saw — the same overstatement, in the promotion path.
