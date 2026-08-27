# Tasks: Adopted skills reach the phase that needs them

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/pack-skill-binding.md](contracts/pack-skill-binding.md),
[contracts/conformance-phase-skill-binding.md](contracts/conformance-phase-skill-binding.md),
[quickstart.md](quickstart.md)

**Tests**: Included and mandatory — spec Independent Tests, contract rows A1–A21 / E1–E4, and
the constitution's gate types. Hermetic rows must be able to lose. SC-002 and the
`required_version` non-regression are named-runner evals, never pytest-on-model-wording.

**Organization**: By user story. **US2 is sequenced before US1** — see Ordering note below.
Named contracts bind exactly: `SkillPin`, `UnsatisfiableRecommendation`, `DeliveredSkill`,
`PhaseAgents`, `load_phase_agents`, `bind_phase_agents`, `load_packs`, `content_pins`,
`promote_phase_agents`, `score_phase_agents_case`, `score_build_agents_case`,
`INSTRUCTION_BUDGET_BYTES`, `assemble_instruction`. Do not substitute a near-equivalent name.

## Ordering note — why US2 (P2) precedes US1 (P1)

The spec requires it: *"it must not ship after P1, or the first correct runs are recorded by
a scheme that could not distinguish them from the incorrect ones."* Both halves of US2 are
buildable before delivery exists — the `content_pins` suffix is computable the moment
`phases` parses, and the per-phase pin map is written whether or not it yet contains skill
keys. US1 remains the MVP: it is the story that makes ADR-0004 true, and Phase 4 is where the
feature becomes observable.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T009, T010, T011, T024, T025, T036, T037, T038 — `unknown_phase`, `skill_binding_unbacked`, `duplicate_skill`, `unsatisfiable_declaration_unreviewed`, `unsatisfiable_declaration_stale`, `skill_missing`, `skill_empty`, `digest_mismatch`, `instruction_too_large`; **nine** distinct codes, no fallback to delivery and none to proceeding without |
| **Conformance** | T012, T016, T033–T035, T039–T041, T046–T049 (rows A1–A21); T057 named-runner E1–E4 |
| **Correlation / evidence** | T014, T017, T018 — per-phase pins written into the checkpoint payload and joinable on the correlation ID; T018 asserts the negative (a run stopped before Write records no Write skill) |
| **Eval** | T030–T032 (`phase_agents` / `build_agents` over **assembled** content, then re-promotion), T042, T051–T052 (SC-002 property and the corpus case the detector must fail) |
| **No-secret-leak** | T019 — pins carry names and digests only; no instruction or skill body reaches the recorded map, a payload, or a phase failure reason |

## Path Conventions

Single project: `src/`, `tests/`, `packs/`, `evals/`, `docs/` at repository root.

---

## Phase 1: Setup

**Purpose**: Fixtures the later phases assert against. No production code.

- [X] T001 [P] Add bound / unbound / mismatched-skill fixture packs to
      `tests/conformance/phase_agents/fixtures.py`: a pack whose skill binds to `write`, a
      pack whose skill binds to nothing, a pack whose skill file has drifted from its digest,
      and a pack whose skill file is empty. Fixture packs use invented pack and skill names —
      `src/core` must stay product-blind
- [X] T002 [P] Add manifest fixtures for each load-stage refusal to
      `tests/conformance/packs/`: `phases = ["deploy"]`, `phases` naming a phase with no
      `[[agents]]` pin, two `[[skills]]` sharing a `name`, and an `unsatisfiable.capability`
      naming a tool the registry offers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: A binding can be declared, and a bad one refuses, before anything can bind.
Sealed core — `src/core/packs/manifest.py` is a registry schema.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T003 Add frozen `UnsatisfiableRecommendation(capability, recommendation)` to
      `src/core/packs/manifest.py`, exported in `__all__`, with a docstring stating the
      scope: unsatisfiable means **no registry tool**, not "the repository never runs it"
      (research R6 — `tests/evals_live/write_gates.py` does run `terraform validate`)
- [X] T004 Add `phases: tuple[str, ...] = ()`,
      `unsatisfiable: tuple[UnsatisfiableRecommendation, ...] = ()` and
      `unsatisfiable_reviewed_at: str = ""` to `SkillPin` in
      `src/core/packs/manifest.py`. `phases` and `unsatisfiable` default empty so an unbound
      skill stays valid unchanged (FR-011); `unsatisfiable_reviewed_at` is **required on
      every skill** and its empty default is what the T006 refusal catches (FR-019)
- [X] T005 Parse both fields in `_parse_skill` in `src/core/packs/loader.py`, preserving
      `[[skills]]` declaration order and `[[skills.unsatisfiable]]` order within a skill.
      Missing `capability` or `recommendation`, or an empty string in either, refuses
      `malformed_manifest`
- [X] T006 Add the binding refusals to `validate_manifest` in `src/core/packs/loader.py`: a
      `phases` entry that is not a `PhaseName` value → `unknown_phase`; a `phases` entry
      naming a phase with no `[[agents]]` pin → `skill_binding_unbacked`; two `[[skills]]`
      sharing a `name` → `duplicate_skill`; `unsatisfiable_reviewed_at` absent or not equal to
      that entry's `digest` → `unsatisfiable_declaration_unreviewed` (FR-019). Collapse
      duplicates within one `phases` array
- [X] T007 Add `INSTRUCTION_BUDGET_BYTES = 256 * 1024` to `src/core/packs/agents.py` with the
      reasoning inline (research R4): largest current assembly is Write at 16,603 bytes;
      fixed with its reasoning because an unfixed threshold is one that gets raised until the
      corpus passes, per `READ_BUDGET_BYTES`
- [X] T008 Add the FR-017 stale-declaration check to `load_packs` in
      `src/core/packs/registration.py`, **after every pack in the set has registered**: a
      declared `capability` present in `registry.tool_names()` or in `bindings.handlers`
      refuses `unsatisfiable_declaration_stale` for the whole set. Not in `register_pack` —
      that is order-dependent, and load order changes without anybody deciding it did
- [X] T009 [GATE:fail-closed] Assert each load-stage refusal is distinct and none stands in
      for another, in `tests/conformance/packs/test_skill_binding_refusals.py` (rows A7, SC-005):
      `unknown_phase`, `skill_binding_unbacked`, `duplicate_skill`. Each fixture must load
      cleanly once the single defect is removed, so the row can lose
- [X] T010 [GATE:fail-closed] Assert a skill whose `digest` changed without
      `unsatisfiable_reviewed_at` changing refuses `unsatisfiable_declaration_unreviewed`, and
      that the rule applies to a skill declaring **nothing** as well as one declaring
      something, in `tests/conformance/packs/test_declaration_keeps_pace.py` (row A20, FR-019,
      SC-010). A bump that loads with an unexamined declaration makes the pull request
      understate what a person still has to do
- [X] T011 [GATE:fail-closed] Assert `unsatisfiable_declaration_stale` refuses the whole load
      set and is **order-independent** — same verdict whichever pack registers first — in
      `tests/conformance/packs/test_unsatisfiable_declaration_stale.py` (row A15, SC-009)
- [X] T012 [GATE:conformance] Assert `terraform_fmt` and `terraform_validate` are not in
      `known_tools(registry)`, in `tests/conformance/packs/test_unsatisfiable_capabilities.py`
      (row A19). This is the premise both Terraform declarations rest on; if it ever becomes
      false, this row fails alongside A15

**Checkpoint**: a binding can be declared and every bad declaration refuses. Nothing binds yet.

---

## Phase 3: User Story 2 — The record says which skills shaped the run (Priority: P2)

**Goal**: An auditor can tell a skill *delivered to a phase that ran* from one merely present
in the bound pack. Today `content_pins` records a digest for every pinned skill, which reads
as "this governed the run" and is true of none of them.

**Independent Test**: Inspect a completed Build's record. A skill bound to a phase that
executed is distinguishable from a skill present in the pack but bound to no phase that ran —
without consulting the pack.

**⚠️ Sequenced before US1** per the Ordering note. Both halves are buildable now: the
`content_pins` suffix comes from `phases`, and the per-phase map is written whether or not it
yet contains skill keys.

### Implementation

- [X] T013 [US2] Change the skill key grammar in `content_pins` in `src/surfaces/toolset.py`
      from `<pack>/<skill-name>` to `<pack>/skills/<skill-name>@<binding>`, where `<binding>`
      is the bound phase names joined by `+` **in `PHASE_ORDER` order** (not manifest order,
      so rewriting a `phases` array does not change the key), or the literal `unbound`. Pack
      and `[[agents]]` keys unchanged
- [X] T014 [US2] **Close the 049 gap** (FR-005, SC-003): write `run.agent_content_pins` into
      the checkpoint payload under the `agent_content_pins` key, in `_payload_with_progress` in
      `src/surfaces/dispatch/entrypoint.py`. The map is set by `bind_phase_agents` and is
      currently carried by no checkpoint, audit event, or result body — US2 is unobservable
      until it is written at all
- [X] T015 [US2] Update the two existing consumers of the old key shape:
      `tests/component/test_run_record_names_its_packs.py` and
      `tests/component/test_phase_agents_pins.py`. **No compatibility shim** — a run started
      before this change and resumed after it must not silently match (contract §5)

### Tests

- [X] T016 [P] [US2] [GATE:conformance] Assert the `RUN_START` key shape in
      `tests/component/test_content_pins_name_bindings.py` (row A12): Terraform's two skills
      record `@plan+write+judge`, Vault's records `@unbound`, and a bound skill is
      distinguishable from an unbound one by the key alone (US2 acceptance 1)
- [X] T017 [P] [US2] [GATE:correlation] Assert per-phase pins reach the checkpoint payload
      and join on the correlation ID, in
      `tests/component/test_phase_delivery_record.py` (row A13, SC-003)
- [X] T018 [US2] [GATE:correlation] Assert the **negative**: a Build stopped before Write
      carries no `…/agents/write@…+<skill>` key (US2 acceptance 2, row A13). This is the half
      that makes the record honest; without it a run that never reached Write reads as one
      whose Write model saw the skill
- [X] T019 [P] [US2] [GATE:no-secret-leak] Extend
      `tests/conformance/phase_agents/test_pins_are_identity_only.py` to the skill keys (row
      A14): names and digests only, never an instruction or skill body, in the map, the
      payload, or a phase failure reason

**Checkpoint**: the record can distinguish bound from unbound and delivered from not-yet-run,
before any skill is delivered. US2 is independently testable here.

---

## Phase 4: User Story 1 — Authored Terraform follows the vendored style guide (Priority: P1) 🎯 MVP

**Goal**: The `terraform-style-guide` skill is in the write model's context while it writes,
so the output follows vendor practice because the platform supplied that practice — not
because the model absorbed it in training.

**Independent Test**: Run a Terraform Build whose task requires a style-sensitive choice the
skill rules on and the base model does not reliably make. Assert the authored files follow the
rule. Remove the binding and assert the same case is no longer reliably correct.

### Assembly and delivery

- [X] T020 [US1] Add frozen `DeliveredSkill(name, digest)` and
      `skills: tuple[DeliveredSkill, ...] = ()` to `PhaseAgents` in
      `src/core/packs/agents.py`. `PhaseAgents.digest` stays the `AGENTS.md` digest — a pin
      identity, not a hash of the assembly (spec Assumptions: `[[agents]]` pins keep their
      shape)
- [X] T021 [US1] Add the pure function `assemble_instruction(agents_body, skills, bodies)` to
      `src/core/packs/agents.py` and have `load_phase_agents` call it (FR-001, SC-001).
      It takes the instruction bytes as a **parameter** and never re-derives them from a pin,
      so the eval scorers can assemble a candidate that has no `[[agents]]` pin (contract
      §2.5). Format: `AGENTS.md` bytes, then each bound skill between the fixed delimiters
      `--- BEGIN PINNED SKILL: <name> (<digest>) ---` /
      `--- END PINNED SKILL: <name> ---`, in `[[skills]]` declaration order filtered by
      `phases`. Skill bytes verbatim — never edited, filtered, reordered internally, or
      truncated (ADR-0004, FR-015). Assembly exists **only here**; production and the eval
      lane both reach it through this function (contract §2.5)
- [X] T022 [US1] Verify each bound skill at delivery in `src/core/packs/agents.py`, on the
      same terms as the existing `AGENTS.md` check: resolve the path inside the pack
      directory, re-read the bytes, re-hash, compare to `SkillPin.digest`. `DeliveredSkill.digest`
      is the value re-verified here, never copied from the manifest (FR-003)
- [X] T023 [US1] Record delivered skills per phase in `bind_phase_agents` in
      `src/surfaces/dispatch/phase_agents.py`: add
      `<pack>/agents/<phase>@<version>+<skill-name>` → digest for each `DeliveredSkill`.
      **No assembly here** — the surface resolves the pack name and records, nothing more

### Fail-closed

- [ ] T024 [US1] [GATE:fail-closed] Raise `ManifestError` with `skill_missing` (absent,
      unreadable, or path escaping the pack), `skill_empty` (bytes empty after strip), and
      `digest_mismatch` (bytes ≠ pin) in `src/core/packs/agents.py`. No fallback exists:
      neither delivering unverified content nor proceeding without the skill (FR-004)
- [ ] T025 [US1] [GATE:fail-closed] Check the budget after assembly and **before return** in
      `src/core/packs/agents.py`: `len(body.encode("utf-8")) > INSTRUCTION_BUDGET_BYTES`
      raises `instruction_too_large`. Never truncate — a truncated instruction delivers
      partial practice while the record claims the whole skill (FR-009)

### Pack content

- [X] T026 [US1] Add `phases = ["plan", "write", "judge"]` to both `[[skills]]` entries in
      `packs/terraform/pack.toml`. Plan is bound because its output is Write's instruction: a
      plan formed without the skills can direct Write toward something the skills would not
      sanction, and Write receiving them does not undo a direction it was told to take
      (FR-012)
- [X] T027 [P] [US1] Remove the *"Practice is this file and the pinned skills
      `terraform-style-guide` / `terraform-style-guide-security`"* sentence from
      `packs/terraform/agents/research/AGENTS.md` and
      `packs/terraform/agents/propose/AGENTS.md` (FR-012a). It is false today for all five
      phases and stays false for these two after T026
- [X] T028 [US1] Add both precedence sentences to
      `packs/terraform/agents/{plan,write,judge}/AGENTS.md` (contract §7.2): **capability** —
      the registry bounds what can be done and adopted practice does not widen it, so a step
      naming a capability the registry does not offer is neither performed nor reported as
      performed (FR-014); **content** — where this file and a delivered skill differ on a
      concrete rule, this file governs, and the difference is not a licence to do neither
- [X] T029 [US1] Update `PROVENANCE.md` for all five Terraform phases in
      `packs/terraform/agents/*/PROVENANCE.md` — what changed, why, and that the set
      re-promotes as a unit

### Re-qualification (FR-013, SC-007)

- [X] T030 [US1] Score the **assembled** instruction in `score_phase_agents_case` and
      `score_build_agents_case` in `src/core/evals/phase_agents_corpus.py`: read the case's
      referenced bytes as today, resolve the pack's skills bound to that phase from the
      manifest, and call `assemble_instruction`. **Do not route through `load_phase_agents`** —
      that would deadlock re-qualification (editing a phase file makes its pin stale,
      `load_phase_agents` refuses `digest_mismatch`, so the suites cannot pass, so promotion
      cannot run). Scoring the file alone would green the gate without looking at the bytes
      the model receives (ADR-0047)
- [ ] T031 [US1] [GATE:eval] Add a `phase_agents` case whose bound skill is missing and which
      must score `fail`, to `packs/terraform/evals/phase_agents.toml`. Without it T030's
      change is unfalsifiable
- [X] T032 [US1] [GATE:eval] Re-run `phase_agents` and `build_agents` over the assembled
      content and re-promote all five Terraform phase files through `promote_phase_agents`,
      updating `[[agents]]` digests and bumping `version` in `packs/terraform/pack.toml`.
      All five or none; both suites or neither (FR-013, FR-013a — no runtime state exists for
      a binding not in force)

### Tests

- [ ] T033 [P] [US1] [GATE:conformance] Assert the write model receives both skills in full,
      between the fixed delimiters, in
      `tests/conformance/phase_agents/test_skill_assembly.py` (row A1, FR-001, SC-001,
      US1 acceptance 1)
- [ ] T034 [P] [US1] [GATE:conformance] Assert delivery order is `[[skills]]` declaration
      order and that two loads of identical manifest content produce byte-identical `body`,
      in `tests/conformance/phase_agents/test_skill_order_deterministic.py` (row A2, FR-006)
- [ ] T035 [P] [US1] [GATE:conformance] Assert a phase bound to no skills produces `body`
      byte-identical to its `AGENTS.md` — no delimiter, no trailing-byte change — for
      Terraform `research`/`propose` and all five Vault phases, in
      `tests/conformance/phase_agents/test_unbound_phase_unchanged.py` (row A3, FR-011,
      US1 acceptance 3)
- [ ] T036 [P] [US1] [GATE:fail-closed] Assert a drifted skill fails the phase
      `digest_mismatch` and that `run.phase_instruction` never holds the mismatched content,
      in `tests/conformance/phase_agents/test_skill_digest_mismatch.py` (row A4,
      US1 acceptance 2)
- [ ] T037 [P] [US1] [GATE:fail-closed] Assert `skill_missing` and `skill_empty` are distinct
      and neither collapses into the other or into `digest_mismatch`, in
      `tests/conformance/phase_agents/test_skill_fail_closed.py` (row A5, SC-005)
- [ ] T038 [P] [US1] [GATE:fail-closed] Assert an over-budget assembly raises
      `instruction_too_large` and that no truncated body is ever returned, in
      `tests/conformance/phase_agents/test_instruction_budget.py` (row A6)
- [ ] T039 [P] [US1] [GATE:conformance] Assert `packs/terraform/skills/LICENSE` and
      `PROVENANCE.md` — on disk, absent from `[[skills]]` — never appear in any phase's
      `body`, in `tests/conformance/phase_agents/test_undeclared_skill_files.py` (row A8,
      FR-008)
- [ ] T040 [US1] [GATE:conformance] Assert **no shipped `AGENTS.md` in any pack names a skill
      it is not bound to**, deriving both sides from the manifests rather than a hard-coded
      list, in `tests/conformance/phase_agents/test_prose_matches_binding.py` (row A9,
      FR-010, SC-006). This is the check that makes the divergence visible rather than
      audited by hand
- [ ] T041 [P] [US1] [GATE:conformance] Assert every phase bound to a skill states both
      precedence sentences, in
      `tests/conformance/phase_agents/test_precedence_stated.py` (row A10)
- [ ] T042 [P] [US1] [GATE:eval] Assert the scorers read assembled content and that a case
      with a missing bound skill scores `fail`, in
      `tests/conformance/phase_agents/test_scorers_score_assembled.py` (rows A18, A21, SC-007).
      A21 is the one that would have caught the deadlock: assert a candidate with **no
      `[[agents]]` pin** scores successfully, which is only possible because
      `assemble_instruction` takes bytes rather than re-deriving them

**Checkpoint**: US1 is complete and observable — the write model receives the skill, every
failure mode stops the run with its own code, and the record from Phase 3 now names what was
delivered.

---

## Phase 5: User Story 4 — The pull request says what the platform could not do (Priority: P2)

**Goal**: A reviewer opening a Build's pull request sees which recommendations from the
vendored skills this platform could not carry out, so the work left to a human is stated
rather than discovered.

**Independent Test**: Open a pull request from a Build bound to a skill with declared
unsatisfiable recommendations. Each appears in the body, and the text is identical across two
runs of different content.

### Implementation

- [ ] T043 [US4] Declare the two unsatisfiable recommendations on
      **`terraform-style-guide` only** in `packs/terraform/pack.toml` — `terraform_fmt` and
      `terraform_validate`, with the exact recommendation strings from
      [data-model.md](data-model.md) §2. **`terraform-style-guide-security` declares nothing**:
      `SECURITY.md` contains neither string, no shell block, and no tool invocation of any
      kind. Declaring them on it would print each bullet twice and attribute a recommendation
      to a skill that does not make it. Set `unsatisfiable_reviewed_at` to each skill's own
      digest (FR-019). **Wording is deliberately narrow**: no registry tool runs them, so the branch was not formatted or validated by
      the platform — not "the platform cannot run `terraform validate`", which the eval lane
      disproves (research R6)
- [ ] T044 [US4] Add `unsatisfiable_recommendations: tuple[str, ...] = ()` to `Proposal` in
      `src/core/authoring/proposal.py` and render `## Adopted practice not carried out`
      between `## Provenance` and `## Limits`, one `- ` bullet per recommendation, verbatim.
      **Not folded into `limits`** — `limits` is `DERIVATIVE_LIMIT + disclosures` and
      disclosures are run-derived, while this text must be run-independent (FR-018)
- [ ] T045 [US4] Populate it in `compose` in `src/core/authoring/proposal.py` and pass it from
      the `compose(...)` call in `src/surfaces/dispatch/entrypoint.py`: the recommendations of
      every skill bound to **any** phase of the bound pack, in `[[skills]]` order then
      declaration order within a skill (FR-016). Read the manifest, never the progress record — a run
      that opens a pull request has necessarily executed all five phases, so the two sets
      coincide and FR-018 holds structurally (research R10)

### Tests

- [ ] T046 [P] [US4] [GATE:conformance] Assert the section appears with both recommendations
      verbatim in the right position, and that two runs over different content produce
      byte-identical section bytes, in
      `tests/component/test_proposal_unsatisfiable_recommendations.py` (row A16, FR-016, SC-008,
      US4 acceptances 1–2)
- [ ] T047 [P] [US4] [GATE:conformance] Assert a pack with no bound skills — or none
      declaring unsatisfiable recommendations — renders today's body exactly, with no empty
      heading, in the same file (row A17)
- [ ] T048 [US4] Assert the stale-declaration guard end to end: declaring
      `terraform_fmt` as a `[[tools]]` entry with a resolvable handler refuses the load rather
      than telling a reviewer to do work the platform now does (row A15 tie-in, US4
      acceptance 3)

**Checkpoint**: the reviewer is told what adopted practice remains for a person to carry out,
in text no model wrote.

---

## Phase 6: User Story 3 — Binding is a declaration, not a code change (Priority: P3)

**Goal**: Whoever adopts the next skill binds it by editing the pack manifest — the same
place its pin, version and digest already live. No platform source names a skill.

**Independent Test**: Add a skill binding to a pack manifest with no source change and observe
the bound phase receive it.

**Note**: US3 acceptance 2 (binding to an unknown phase refuses and names it) is delivered by
T006 and asserted by T009. This phase adds the property that keeps the boundary from eroding.

- [ ] T049 [US3] [GATE:conformance] Assert **no file under `src/` names a skill, a
      skill-to-phase binding, or a recommendation string** — scanning for the shipped skill
      names, `phases`-adjacent literals, and the recommendation text — in
      `tests/conformance/packs/test_no_source_names_a_skill.py` (row A11, SC-004). Extends the
      existing `test_core_is_product_blind.py` property to skills
- [ ] T050 [US3] Assert the positive case: adding a `phases` entry to an in-memory fixture
      manifest, with zero source change, causes the bound phase to receive the skill —
      in `tests/conformance/phase_agents/test_binding_is_declaration.py` (US3 acceptance 1)

**Checkpoint**: adding the next skill's binding is a `pack.toml` edit and nothing else.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T051 [P] [GATE:eval] Add a `variable_has_validation` property to
      `tests/evals_live/authoring_properties.py`: a `variable` block containing a
      `validation { condition, error_message }` block. **Chosen deliberately** — research R7
      found the phase files already hand-restate most of `SKILL.md` (indentation, naming,
      `type`/`description`, `sensitive`, `for_each` over `count`, `~>` as a pin), so measuring
      SC-002 on any of those would measure nothing when the binding is removed. `validation`
      appears in the skill twice and in no phase file
- [ ] T052 [P] [GATE:eval] Add the corpus task that asks for a constrained input, plus the
      case the detector **must fail** — a `variable` with `type` and `description` but no
      `validation` — to `evals/authoring/corpus.toml`, following the precedent
      `static_credential_lookalike` sets. A detector that cannot fail has measured nothing
- [ ] T053 [P] Add `skill binding` and `unsatisfiable recommendation` to
      `docs/glossary.md`, with the registry-scoped reading of "unsatisfiable" stated
      explicitly
- [ ] T054 [P] Add a `CHANGELOG.md` entry: adopted skills now reach the phases bound to them;
      `content_pins` skill key shape changed with no compatibility shim
- [ ] T055 Run every scenario in [quickstart.md](quickstart.md), restoring
      `packs/terraform/skills/terraform-style-guide/SKILL.md` and `packs/terraform/pack.toml`
      after the tamper and unbind scenarios — a left-behind edit fails everything downstream
- [ ] T056 Run `make check`, then `make conformance`, then `make test-full`. Rows A1–A19 are
      hermetic and must pass in CI
- [ ] T057 [GATE:conformance] Named-runner rows on the implementation PR — **Dan McTeer**:
      **E1** identical assembled instruction in connected, restricted and air-gapped profiles;
      **E2** SC-002 — `variable_has_validation` present in ≥ 4 of 5 runs bound and
      demonstrably less often unbound, same n, recording n, both rates and the delta;
      **E3** both suites pass over assembled content before promotion, a losing set copies
      zero files; **E4** no `required_version` regression against the pre-binding baseline.
      Rows fail loudly when the enclave or eval broker is absent — do not skip green
- [ ] T058 Request **security-maintainer review** on the implementation PR. This feature edits
      `src/core/packs/manifest.py` (registry schema) and the `RUN_START` `content_pins`
      payload (audit schema), both named sealed core — constitution Principle V and
      `AGENTS.md` rule 4

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — no dependencies
- **Phase 2 (Foundational)** — depends on Phase 1; **blocks every story**
- **Phase 3 (US2)** — depends on Phase 2; must precede Phase 4 shipping (Ordering note)
- **Phase 4 (US1, MVP)** — depends on Phase 2 and Phase 3
- **Phase 5 (US4)** — depends on Phase 2 (declarations) and Phase 4 (bindings)
- **Phase 6 (US3)** — depends on Phase 2; independent of Phases 3–5
- **Phase 7 (Polish)** — depends on all preceding

### Within Phase 4

T020 → T021 → T022 → T023 (assembly before verification before recording).
T024–T025 depend on T021. T026 depends on T006. T030 depends on T020 — the scorer calls
`assemble_instruction`, **not** `load_phase_agents`, which is what keeps re-qualification from
deadlocking on the stale pin its own content edit creates. **T032 depends on T026–T031** —
re-promotion is last, because every content edit changes a digest.

### Parallel Opportunities

- T001 ‖ T002 (Setup)
- T016 ‖ T017 ‖ T019 (US2 tests; T018 follows T014)
- T027 ‖ (T028 after T026) — different files
- T033 ‖ T034 ‖ T035 ‖ T036 ‖ T037 ‖ T038 ‖ T039 ‖ T041 ‖ T042 (US1 tests, all distinct files)
- T046 ‖ T047 (US4 tests)
- T051 ‖ T052 ‖ T053 ‖ T054 (Polish)
- **Phase 6 can run in parallel with Phases 3–5** — it touches no production file

### Parallel Example: Phase 4 tests

```bash
uv run pytest tests/conformance/phase_agents/ -k "assembly or order or unbound or mismatch or fail_closed or budget or undeclared or precedence or scorers" -n auto
```

---

## Implementation Strategy

### MVP (US1)

1. Phase 1 → Phase 2 → Phase 3 → Phase 4.
2. **Stop and validate**: quickstart scenarios 1–4 and 6. The write model receives both
   skills, every failure mode stops the run with its own code, and the record names what was
   delivered.
3. US4 and US3 add value without changing US1's behaviour.

### Incremental Delivery

Phase 2 → declarations refuse correctly. Phase 3 → the record is honest before it has
anything to be honest about. Phase 4 → **the feature**. Phase 5 → the reviewer is told what
is left. Phase 6 → the boundary holds for the next adopter. Phase 7 → the measurement.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Commit after each task or logical group; sign off every commit (`git commit -s`).
- Run `make check` before declaring any task complete.
- **Never edit skill bytes.** ADR-0004 requires the adopted content stay identical to
  upstream. Every problem this feature meets is solved by a manifest declaration or a
  precedence sentence in the phase file, never by touching `SKILL.md` or `SECURITY.md`.

### `/speckit-analyze` remediation — do not lose on regeneration

Three spec defects were resolved in `spec.md` (Clarifications → Session 2026-08-26 —
`/speckit-analyze` remediation), and three artifact defects were corrected in place.

**Spec changes**, now implemented by tasks:

1. **FR-007** rewritten — its second clause named a refusal unreachable under FR-002's shape.
   T006 ships the three refusals that are reachable.
2. **FR-014a** added — content precedence, not only capability. T028 ships the sentence;
   T057/E4 guards the `required_version` regression it prevents.
3. **FR-019 / SC-010** added — `unsatisfiable_reviewed_at` on every `[[skills]]` entry, so a
   skill bump cannot land with a declaration nobody re-examined. T004, T006, T010, T043.

**Artifact corrections**, and why each mattered:

- **Only `terraform-style-guide` declares the two recommendations** (T043).
  `SECURITY.md` contains neither string, no shell block, no tool invocation. Declaring them
  on it would print each bullet twice and attribute a recommendation to a skill that does not
  make it.
- **`assemble_instruction` is a pure function** (T020, T030). Routing the scorers through
  `load_phase_agents` deadlocked re-qualification: a content edit makes the pin stale, the
  loader refuses `digest_mismatch`, the suites cannot pass, and promotion requires them to
  have passed.
- **Contract §5 no longer claims a resume comparison.** `resume_run` never reads
  `content_pins` — zero occurrences. Changing the key shape is inert at resume because
  nothing at resume looks; the record's audience is a person reading it afterwards.
