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

## R4 — Vault has no bound skill, and is the *unbound* case rather than a control

**Decision**: `packs/vault` is **not edited**, and its role is to prove that a pack with no
bound skill is reported as **unbound**, never as clean.

**Measured**: `packs/vault/pack.toml` has **no `phases` key**. `vault-secret-access` is pinned
and bound to nothing. `grep -n "^phases" packs/*/pack.toml` returns only the two terraform
entries.

**This was deliberate, and it is load-bearing.** 051's [R12](../051-phase-skill-binding/research.md)
decided it explicitly: the skill *"stays adopted and inert, and is recorded `@unbound`"*, it is
*"the live fixture"* for distinguishing a pack with a bound skill from one without, and it
**"must not acquire a binding by tidiness."**

**What this feature got wrong before analysis, and why it matters.** An earlier draft measured
`vault/agents/write/AGENTS.md` against `vault-secret-access/SKILL.md`, found 2 of 8 rules
restated, and proposed removing them as a "control". Three things are wrong with that:

1. **There is no delegation relationship to enforce.** FR-001 governs a rule a skill *bound to
   that phase* states. Vault has no bound phase, so FR-001 is vacuously satisfied and the
   overlap is not a defect at all.
2. **Removing those rules would delete guidance nothing delivers.** The card would lose
   check-and-set and dynamic-secret-first, and no skill would supply them — the precise failure
   the spec's own edge case warns about, committed deliberately.
3. **It would break 051's fixture**, which R12 forbids in as many words.

**The hazard this leaves behind is real and is now a row.** Run the comparison over vault today
and it returns zero restated rules, which *reads as compliance*. It is not compliance; it is
absence of a binding. A gate that cannot tell those apart would report the vault pack as clean
for the same reason it would report a pack whose cards delegate perfectly.

**The positive control is terraform itself**: A4 fails against the frozen pre-feature cards,
A1 passes after the edits. That pairing does the work "vault passes" was wrongly asked to do.

**Recorded, not fixed here** (T040a): `vault-secret-access` is pinned, digest-verified,
re-reviewed on every bump — and delivered to no model. Under ADR-0004 that is a supply chain
with no consumer, which is the defect 051 was written to fix, surviving one pack over. It is
not fixed here for two reasons: 051's R12 chose it deliberately and calls it a live fixture
that "must not acquire a binding by tidiness", and binding it would cost a re-qualification of
all five vault phases. **Row A5 fails informatively if it ever acquires a binding**, so the
decision cannot be taken silently. Worth a look on its own terms; not this feature's to take
while passing through.

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
