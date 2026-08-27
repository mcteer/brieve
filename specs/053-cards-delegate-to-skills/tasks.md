# Tasks: A phase card delegates to the skill it is bound to

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md),
[contracts/conformance-cards-delegate.md](contracts/conformance-cards-delegate.md),
[quickstart.md](quickstart.md)

**Tests**: Included and mandatory — contract rows A1–A9 hermetic, E1–E3 named-runner. A row
that cannot fail is worse than a missing one (ADR-0047), so A4 and A5 are not optional: the
row must be shown to catch the real defect and to be satisfiable.

**Organization**: By user story. **US3's comparison mechanism is Foundational**, ahead of US1's
edits — see Ordering note. Named contracts bind exactly: `rule_inventory`, `stated_rules`,
`declared_overrides`, `compare_card`, `TERRAFORM_STYLE_RULES`, `VAULT_ACCESS_RULES`,
`standard_file_organisation`. Do not substitute a near-equivalent name.

## Ordering note — why the mechanism precedes the edits

Row A4 requires the comparison to **fail against the pre-feature card text**. The naive way to
get that is to write the row first and watch it go red, which proves nothing after the edit
lands and leaves A4 unable to run for the rest of the pack's life.

So the pre-feature text is **frozen as a fixture in Setup, before anything is edited** (T002),
and A4 asserts against the fixture permanently. This inverts the usual order — the mechanism
and its fixtures come before the content change they measure — and it is what makes A4 a
standing row rather than a one-time observation.

US1 remains the MVP: it is the story that makes ADR-0004's pin load-bearing.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Conformance** | T003a, T032–T038 (rows A1, A2, A4, A5, A7, A9 and the SC-006 source check); T010–T011 (rows A3, A6 on the mechanism itself) |
| **Fail-closed** | T001, T039 — the refusal delegation depends on. T001 verifies it before any card is shortened; T039 (row A8) asserts it permanently |
| **Eval** | T024–T028 (the structural detector, its must-fail corpus case, and the SC-002 arms), T020–T023 (re-qualification, all-five-or-none) |
| **Evidence** | T029–T031, T040 — the SC-002 outcome and the two amendments owed to 051, recorded with the measurement rather than as a restated conclusion |

## Path Conventions

Single project: `src/`, `tests/`, `packs/`, `evals/`, `docs/` at repository root.

---

## Phase 1: Setup

- [ ] T001 Verify delegation's premise before shortening any card: confirm `skill_missing`, `skill_empty` and `digest_mismatch` are each reached by `raise ManifestError` in `src/core/packs/loader.py`. If any is a warning, STOP — the feature's safety argument is gone
- [ ] T002 Freeze the pre-feature card text as fixtures in `tests/conformance/packs/card_fixtures.py`: the current `packs/terraform/agents/{write,judge,plan}/AGENTS.md` **and `packs/vault/agents/write/AGENTS.md`** bodies, verbatim, with the date and commit they were taken from. Row A4 asserts against these forever, and without the vault copy the residue this feature removes could never be shown to have been caught
- [ ] T003 Record the **provisional** probe counts (write 16/16 against the full stated surface; judge 7 and plan 6 against a twelve-rule probe; vault 2 against an eight-rule probe) in `tests/conformance/packs/card_fixtures.py` as *direction*, explicitly not as targets. **The denominators differ and only Write's is derived** — see [R1](research.md). T008/T009 set the real inventories and T009b re-records the baselines against them
- [ ] T003a Confirm before proceeding that no later task treats a probe count as a target. T032 reproduces the baselines recorded by T009b, never the numbers in T003

---

## Phase 2: Foundational (Blocking Prerequisites)

**Blocks every user story.** The comparison mechanism and its rule inventories.

- [ ] T004 Create `tests/conformance/packs/rule_inventory.py` with the `StatedRule` shape from [data-model.md](data-model.md): `id`, `skill`, `quote`, `line`, `match`
- [ ] T005 Implement `stated_rules(text)` in `tests/conformance/packs/rule_inventory.py` — returns prose-stated rules only, excluding every line inside a fenced code block (FR-003)
- [ ] T006 Implement `declared_overrides(card_text)` in `tests/conformance/packs/rule_inventory.py` — recognises an override **from the card's own text**, requiring both the overridden rule and a stated reason (FR-002)
- [ ] T007 Implement `compare_card(card_text, rules)` in `tests/conformance/packs/rule_inventory.py` — returns each restated rule with its id, so a failure names the rule and both documents rather than scoring a similarity (FR-006, [R7](research.md))
- [ ] T008 **Derive** `TERRAFORM_STYLE_RULES` in `tests/conformance/packs/rule_inventory.py` from `terraform-style-guide/SKILL.md` — every prose-stated rule, each with the guide's own words and line number, bound to digest `fea8a0ea…`. The count is whatever the guide yields; sixteen is what a probe found, not a quota to fill
- [ ] T009 **Derive** `VAULT_ACCESS_RULES` in `tests/conformance/packs/rule_inventory.py` from `vault-secret-access/SKILL.md`, same shape, bound to its pinned digest. The guide carries fifteen bullet-form statements and the probe used eight — the inventory records what is there, not the probe's subset
- [ ] T009a Reconcile the checklist against the rules it restates: `vault-secret-access/SKILL.md` ends with a six-item checklist that repeats rules stated above it. Count each rule once, or the vault denominator is inflated and its ratio is meaningless
- [ ] T009b Re-record the real per-card baselines in `tests/conformance/packs/card_fixtures.py`, all three terraform cards and vault measured against the **derived** inventories, so every figure shares a denominator. These are what T032 reproduces
- [ ] T010 [P] Row A3 in `tests/conformance/packs/test_cards_delegate_to_skills.py` — content inside a fenced block is never a stated rule. Asserted against the real guide: `default_tags`, `validation` and the aliased-provider example must all be absent from `TERRAFORM_STYLE_RULES`
- [ ] T011 [P] Row A6 in `tests/conformance/packs/test_cards_delegate_to_skills.py` — each inventory's digest matches the manifest's pinned digest, so a re-pin cannot leave the inventory describing bytes that are gone

**Checkpoint**: the mechanism can be run by hand against any card and names what it finds.

---

## Phase 3: User Story 1 — The pin becomes load-bearing (Priority: P1) 🎯 MVP

**Goal**: The three bound terraform cards and the vault card stop restating what the skill
states, so removing a binding would change what the phase is told.

**Independent test**: Run `compare_card` over each edited card — zero restated rules, except
declared overrides.

### Pack content

- [ ] T012 [US1] Delegate the sixteen restated rules from `packs/terraform/agents/write/AGENTS.md` §"Required HashiCorp practice" (**FR-004**). Keep §Precedence, §Decide whether any change is needed, §Order of authorship, §Least privilege, §Do not invent provider syntax and §Anti-patterns — platform-own per [R6](research.md)
- [ ] T013 [US1] Rewrite `packs/terraform/agents/write/AGENTS.md` §Pins as a **declared override**: keep the rule that `>=` is not a pin, and state that it overrides the guide's `required_version = ">= 1.14"` (lines 38, 232) and why (FR-002)
- [ ] T014 [US1] Delegate the seven restated rules from `packs/terraform/agents/judge/AGENTS.md` §Check, keeping the checklist's own structure — the skill's Code Review Checklist is **not** adoptable, because two of its ten items are the `terraform fmt` / `terraform validate` steps this pack declares unsatisfiable ([R3](research.md))
- [ ] T015 [US1] Keep `validation` and `default_tags` in the Judge card, and say in the card why: they appear in the guide **only inside code examples**, so they are not delegated practice but Judge's own criteria. Without the note a later reader assumes they were missed by T014
- [ ] T016 [US1] Delegate the six restated rules from `packs/terraform/agents/plan/AGENTS.md`
- [ ] T017 [US1] Remove the two-of-eight residue from `packs/vault/agents/write/AGENTS.md` — check-and-set on writes, and preferring a dynamic secret ([R4](research.md))
- [ ] T018 [US1] Confirm no card was left nearly empty by delegation. If a phase's instruction was never more than a copy, say so in the card rather than padding it
- [ ] T019 [US1] Re-read each edited card end to end for coherence — delegation removes sentences from the middle of prose, and a card that no longer reads as instruction is a defect this feature introduced

### Re-qualification (FR-010, SC-005)

- [ ] T020 [US1] Run the `phase_agents` suite over **assembled** content for every edited terraform phase
- [ ] T021 [US1] Run the `build_agents` suite over assembled content for the same phases
- [ ] T022 [US1] Run both suites for the edited vault phase
- [ ] T023 [US1] Promote all five phase agents together, all-five-or-none, only after T020–T022 pass ([R8](research.md)). A card edit may not ship on the eval that qualified the previous text

**Checkpoint**: US1 is independently verifiable — the cards no longer restate, and the phases
are qualified on the bytes they now carry.

---

## Phase 4: User Story 2 — SC-002 can return a real answer (Priority: P2)

**Goal**: Measure whether a delivered skill changes authored output, on a rule that can carry
the question. Throughout this phase **SC-002 means 051's** — 053's own SC-002 is a different
claim, about the instruction rather than the output.

**Independent test**: Bound and unbound arms now differ in instruction; a delta is possible
where it was previously excluded by construction.

- [ ] T024 [US2] Add the `standard_file_organisation` detector to `tests/evals_live/authoring_properties.py` — structural, derived from the artefact's filenames, no HCL parsing ([R5](research.md))
- [ ] T025 [US2] Add a corpus case to `evals/authoring/corpus.toml` that asks for the situation the rule applies to, **without naming the rule** — the design defect that invalidated 051's first attempt
- [ ] T026 [US2] Add a must-fail case: an artefact in a single `main.tf` that the detector scores `fail`, following the `static_credential_lookalike` precedent. A detector that cannot fail is not evidence
- [ ] T027 [US2] Point `evals/prompt-tune/sc002_skill_effect.py` at the new property and task, leaving its null-result instruction text intact
- [ ] T028 [US2] Run E2: `uv run python evals/prompt-tune/sc002_skill_effect.py -n 5`, both arms, on the qualified model
- [ ] T029 [US2] Record the E2 result in `contracts/conformance-cards-delegate.md` §5 — the numbers, the model, the date, whichever way it went (**FR-009**: a level result stays recordable as a finding)
- [ ] T030 [US2] If E2 is level, record it as the finding (SC-004) and amend 051's SC-002 to say this skill has no teachable surface for the qualified model. **Do not** move the threshold or search for a fourth rule
- [ ] T031 [US2] If E2 demonstrates an effect, record 051's SC-002 as met, naming the rule and the measurement that met it

**Checkpoint**: SC-002 has an answer that means something, in either direction.

---

## Phase 5: User Story 3 — No card silently re-absorbs the practice (Priority: P3)

**Goal**: The ratchet. The terraform card did not arrive duplicated; it drifted there one
helpful edit at a time.

**Independent test**: Add a rule to a card that its bound skill states — the check fails naming
both locations. Remove it and it passes.

- [ ] T032 [US3] Rows A0 and A1 in `tests/conformance/packs/test_cards_delegate_to_skills.py` — no card states a rule its bound skill states, except a declared override (A1); and the baselines compared against are the **derived** ones sharing a denominator across all four cards, never T003's probe counts (A0)
- [ ] T033 [US3] Row A2 — an override passes, and a §Pins that keeps its rule but stops saying what it overrides fails
- [ ] T034 [US3] Row A4 — the comparison **fails** against the frozen pre-feature fixtures from T002. This is what makes A1 evidence rather than a detector that finds nothing
- [ ] T035 [US3] Row A5 — the comparison **passes** against `packs/vault` after T017, the control that the rule is satisfiable ([R4](research.md))
- [ ] T036 [US3] Row A7 — every phase bound to a skill is compared, derived from the manifest rather than a hard-coded three, so a fourth binding is not silently unchecked
- [ ] T037 [US3] Row A9 — the pack-level total is reported, not only per-card, so practice distributed across cards cannot read as cleanliness ([R2](research.md))
- [ ] T038 [US3] Row asserting SC-006: this feature's file list touches no path under `src/`
- [ ] T039 [US3] Row A8 — the load-bearing one. `skill_missing`, `skill_empty` and `digest_mismatch` each still refuse, asserted from the delegating card's point of view, because delegation converts a duplicated rule into a missing one the moment that stops being true

**Checkpoint**: the line holds without anyone remembering to look.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T040 Amend `specs/051-phase-skill-binding/contracts/conformance-phase-skill-binding.md`: record the **withdrawal** of the minimality hypothesis and the **selection error** (both measured rules drawn from fenced example code), with the 2026-08-27 measurement (FR-008)
- [ ] T041 Confirm FR-011 by inspection — this feature changes what the card says, never what the record reports. No `content_pins` or payload shape is touched
- [ ] T042 Add the 053 row to `ROADMAP.md`'s shipped table, naming ADR-0004 as the record made load-bearing
- [ ] T043 Run `make check` — the hermetic suite including every A row
- [ ] T044 Run `make conformance` — the enclave rows, exit 0
- [ ] T045 Fill `contracts/conformance-cards-delegate.md` §5 with the E1–E3 named-runner record

---

## Dependencies

```
Setup (T001–T003a)
  │  T001 gates everything: if refusals are not fail-closed, STOP
  │  T002 must precede T012–T017 — the fixtures cannot be captured after the edit
  ▼
Foundational (T004–T011)   the mechanism and the DERIVED inventories, blocking all stories
  │  T009b sets the only baselines T032 may reproduce; T003's probe counts are not targets
  ▼
US1 (T012–T023)  ──────────► US3 (T032–T039)  rows need the edited cards to be green
  │                                A4 needs only T002's fixtures
  ▼
US2 (T024–T031)  needs US1: unbound arms are only different once the card delegates
  ▼
Polish (T040–T045)
```

**Parallel opportunities**: T010/T011 (different rows, same file — sequential within the file
but independent in reasoning). T012, T014, T016, T017 touch four different cards and are
genuinely parallel. T032–T039 are one file and are sequential.

## Implementation strategy

**MVP is US1 plus Foundational.** That is the story that makes ADR-0004's pin load-bearing, and
it is verifiable on its own by running `compare_card` over the edited cards.

US3 is what stops it decaying and should not be deferred past the same change — the duplication
this feature removes arrived by drift, and shipping the cleanup without the ratchet buys one
release.

US2 is last because it depends on US1 and costs live model calls, and because its answer is
allowed to be "no". Nothing downstream is blocked by which way it goes.
