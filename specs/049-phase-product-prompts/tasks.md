# Tasks: Product-and-phase Build instructions

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/pack-agents.md](contracts/pack-agents.md),
[contracts/prompt-tune.md](contracts/prompt-tune.md),
[contracts/conformance-phase-product-prompts.md](contracts/conformance-phase-product-prompts.md),
[quickstart.md](quickstart.md)

**Tests**: Included — spec Independent Tests, contract rows A1–A13 / E1–E3, and constitution
gate types. Hermetic rows must be able to lose. Live GEPA/DSPy and SC-006 are named-runner
evals, never pytest-on-model-wording.

**Organization**: By user story. US1 (Terraform per-phase steer) is MVP. US2 (Vault isolation)
is the second P1. US3 (published practice + provenance) and US4 (GEPA then DSPy promotion)
are P2. Named helpers bind exactly: `AgentPin`, `load_phase_agents`, `bind_phase_agents`,
`promote_phase_agents`, `load_phase_agents_cases`, `load_build_agents_cases`. Do not
substitute SKILL.md, pack.toml prose, or repository-root `AGENTS.md`.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T016–T018, T026, T056, T044 (`agents_missing` / `agents_empty` / `digest_mismatch` / `pack_unbound` / `pack_ambiguous` / `refinement_unavailable`; no PR; candidates never loaded) |
| **Conformance** | T019–T021, T027, T035, T047 (A1–A13); T048 named-runner E1–E3 |
| **Correlation / evidence** | T014–T015, T021 (`{pack}/agents/{phase}@{version}` digest on the run, joinable on correlation ID; no instruction bodies in audit) |
| **Eval** | T036–T046, T057 (`phase_agents`, `build_agents` via `phase_agents_corpus`, GEPA then DSPy; suites include known-fail fixtures; not `SUITES`) |
| **No-secret-leak** | T015 — pin identity/version/digest only; never log `AGENTS.md` bodies or secret-shaped values in phase reasons |

## Path Conventions

Single project: `src/`, `tests/`, `packs/`, `evals/`, `docs/` at repository root.

---

## Phase 1: Setup

**Purpose**: Decision record and test package the later phases fill.

- [X] T001 Write Accepted ADR-0071 from research R5 in
      `docs/adr/0071-prompt-optimization-is-eval-lane-only.md` using `docs/adr/template.md`:
      `dspy`/`dspy.GEPA` are eval-lane and operator-machine only; served `src/core`,
      `src/adapters`, and `src/surfaces` never import them; model calls use the existing eval
      broker (ADR-0058); not a new served egress class; extra name is `prompt-tune`; pin is
      `dspy==3.3.0` (PyPI `dspy`, not the `dspy-ai` alias)
- [X] T002 [P] Create `tests/conformance/phase_agents/` (package `__init__.py`) for A1–A13
      and A4b hermetic rows named in
      `specs/049-phase-product-prompts/contracts/conformance-phase-product-prompts.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Product-blind pin, load, bind, and fail-closed seams every story uses.
Fixture packs in tests may use invented pack names; `src/core` must not contain managed
product identifiers (`terraform`, `packer`, `consul`).

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T003 Add frozen `AgentPin(phase, path, version, digest)` and
      `PackManifest.agents: tuple[AgentPin, ...]` in `src/core/packs/manifest.py` (parallel
      to `SkillPin`; export in `__all__`)
- [X] T004 Parse `[[agents]]` in `src/core/packs/loader.py` `parse_manifest` /
      `validate_manifest`: `phase` must be a `PhaseName` value; unknown → `unknown_phase`;
      duplicate → `duplicate_phase`; path must be `agents/<phase>/AGENTS.md` (no `..`
      escape); an authoring pack (workflow name contains `"author"`, same rule as
      `packs_declaring_authoring`) with fewer than five phases → `agents_incomplete`
- [X] T005 Extend `FilesystemPackLoader._verify_digests` in `src/core/packs/loader.py` to
      verify each `AgentPin` digest, refuse missing/empty `AGENTS.md`
      (`agents_missing` / `agents_empty`), and require sibling
      `agents/<phase>/PROVENANCE.md` non-empty (`agents_provenance_missing`)
- [X] T006 Implement `load_phase_agents(pack_name, phase, *, loader, packs_root) -> PhaseAgents`
      in `src/core/packs/agents.py` exactly as
      `specs/049-phase-product-prompts/contracts/pack-agents.md` and
      `specs/049-phase-product-prompts/data-model.md`; never read repository-root
      `AGENTS.md`, never read `SKILL.md` or `pack.toml` prose as the body
- [X] T007 Add `instruction: str = ""` to `ChoiceRequest` in `src/core/choice/chooser.py`;
      default empty for Ask
- [X] T008 Pass `instruction` into `ChoiceRequest` from `resolve_step_tool` in
      `src/core/choice/bounded.py` (new parameter default `""` so existing callers stay valid)
- [X] T009 Implement `bind_phase_agents(run, phase) -> PhaseAgents` in
      `src/surfaces/dispatch/entrypoint.py` (or a dedicated helper module it imports under
      `src/surfaces/dispatch/`): `RUN_PACKS` / run packs must be size 1 (`pack_unbound` /
      `pack_ambiguous`); call `load_phase_agents`; on failure mark the 047 phase
      `PhaseStatus.FAILED` and do not call `open_proposal`
- [X] T010 Extend `content_pins` in `src/surfaces/toolset.py` with keys
      `{pack}/agents/{phase}@{version}` → digest for each phase the run started (FR-012)
- [X] T011 Prepend non-empty `request.instruction` to the system prompt in
      `src/adapters/model_chooser.py`; keep `_AUTHORING_*_HINT` as tool-schema only; do not
      treat those hints as a fallback when Build `instruction` is missing
- [X] T012 Wire `bind_phase_agents` at each 047 phase start in
      `src/surfaces/dispatch/entrypoint.py` and pass `PhaseAgents.body` into
      `resolve_step_tool(..., instruction=...)`; Judge path (`judge_authored_work` in
      `src/adapters/model_chooser.py`) uses the Judge file on the **judge** cell; Write
      uses the Write file on the **write** cell (FR-015 / A9)
- [X] T013 [P] Component tests for `AgentPin` parse/load in
      `tests/component/test_pack_agents_loading.py` (new): completeness, digest mismatch,
      empty body, missing provenance, unknown/duplicate phase — using fixture pack names,
      not product identifiers in `src/core`
- [X] T014 [P] [GATE:correlation] Unit tests that `content_pins` emits
      `{pack}/agents/{phase}@{version}` in `tests/component/test_run_record_names_its_packs.py`
      (extend) or `tests/component/test_phase_agents_pins.py` (new)
- [X] T015 [GATE:no-secret-leak] Assert phase-fail reasons and audit payloads do not contain
      instruction bodies or secret-shaped values in
      `tests/conformance/phase_agents/test_pins_are_identity_only.py` (new)
- [X] T016 [GATE:fail-closed] Missing/empty instruction fails the phase and blocks PR in
      `tests/conformance/phase_agents/test_missing_agents_fail_closed.py` (new) (A4, A5)
- [X] T056 [GATE:fail-closed] A file under `evals/prompt-tune/candidates/` is never loaded
      as a phase instruction; missing `[[agents]]` pin is `agents_missing` in
      `tests/conformance/phase_agents/test_candidates_are_not_executed.py` (new) (A4b,
      FR-004 unpromoted)
- [X] T017 [GATE:fail-closed] Root `AGENTS.md` and pack `SKILL.md` are not stand-ins in
      `tests/conformance/phase_agents/test_no_standin_instruction.py` (new) (A6, FR-016)
- [X] T018 [GATE:fail-closed] Zero packs → `pack_unbound`; two packs → `pack_ambiguous`;
      neither defaults to a product in
      `tests/conformance/phase_agents/test_pack_bind_fail_closed.py` (new) (A7)
- [X] T019 [P] [GATE:conformance] Ask never sets `ChoiceRequest.instruction` from
      `packs/*/agents/` in `tests/conformance/phase_agents/test_ask_does_not_use_build_agents.py`
      (new) (A8, FR-014)
- [X] T020 [P] Unit gate: `src/core`, served `src/adapters`, and `src/surfaces` do not
      import `dspy` or `gepa` in `tests/unit/test_served_code_does_not_import_dspy.py` (new)
      (A10, ADR-0071)

**Checkpoint**: A fixture authoring pack with five pinned files can bind one phase; omissions
and ambiguity fail closed; Ask is untouched; core stays product-blind.

---

## Phase 3: User Story 1 — Terraform Build steered per phase (Priority: P1) 🎯 MVP

**Goal**: A Terraform-bound Build executes five distinct Terraform `AGENTS.md` files, one
per phase, recorded on the run. Propose intake stays `pack="terraform"` in
`src/surfaces/api/propose.py` (explicit 047 binding, not a default).

**Independent Test**: Start a terraform-bound authoring run (hermetic). Each executed phase
records `terraform/agents/<phase>@<version>` with a digest distinct from the other four.
Omit Write → Write fails, no PR.

### Tests for User Story 1

> Write these first; they must fail until T023–T025 land.

- [X] T021 [P] [US1] [GATE:conformance] A1/A3 rows for terraform in
      `tests/conformance/phase_agents/test_terraform_phase_pins.py` (new): five files load;
      run pins `terraform/agents/<phase>@<version>` only
- [X] T022 [P] [US1] [GATE:conformance] A9 judge-vs-write binding row in
      `tests/conformance/phase_agents/test_judge_file_not_write_file.py` (new)

### Implementation for User Story 1

- [X] T023 [P] [US1] Author five distinct Terraform phase files
      `packs/terraform/agents/{research,plan,write,judge,propose}/AGENTS.md` (FR-003: bodies
      differ by phase, not only the path; Write is not Research with tools changed). US3
      will deepen published practice; US1 must already be phase-distinct so SC-001 cannot
      pass on path names alone
- [X] T024 [P] [US1] Add five `[[agents]]` rows with matching SHA-256 digests to
      `packs/terraform/pack.toml`; add non-empty
      `packs/terraform/agents/<phase>/PROVENANCE.md` siblings (may be brief; US3 completes
      sources-and-date). These pins are the **seed set** so US1 can load files; they are
      not `promote_phase_agents` output. T036 must score these shipped paths. T041 may
      overwrite them from `evals/prompt-tune/candidates/` only after both qualifications
      pass.
- [X] T025 [US1] Confirm `src/surfaces/api/propose.py` still sets
      `AuthoringRequest.pack` to the terraform pack name explicitly; dispatch uses
      `bind_phase_agents` on that single pack for every 047 phase (T009/T012)

**Checkpoint**: Terraform Builds are steered per phase; missing Write does not open a PR.

---

## Phase 4: User Story 2 — Vault Build steered per phase (Priority: P1)

**Goal**: The same matrix for Vault. Cross-pack isolation is a property (SC-002). No portal
product picker. Vault-bound runs are constructed via `AuthoringRequest` / `RUN_PACKS` size 1
(research R3).

**Independent Test**: Vault-bound fake/hermetic five-phase walk records
`vault/agents/<phase>@<version>` and never `terraform/agents/*`. Vault Research text ≠
Terraform Research text. 042 policy authoring is not this walk.

### Tests for User Story 2

- [X] T026 [P] [US2] [GATE:fail-closed] Vault omit-Write fails closed in
      `tests/conformance/phase_agents/test_vault_missing_write_fail_closed.py` (new)
- [X] T027 [P] [US2] [GATE:conformance] Isolation A2/A3 in
      `tests/conformance/phase_agents/test_product_isolation.py` (new): terraform research
      digest/body never used on a vault-bound run and vice versa (SC-002)

### Implementation for User Story 2

- [X] T028 [P] [US2] Author five distinct Vault phase files
      `packs/vault/agents/{research,plan,write,judge,propose}/AGENTS.md` (not a renamed
      copy of Terraform; Write must not instruct Terraform resources)
- [X] T029 [P] [US2] Add five `[[agents]]` rows and digests to `packs/vault/pack.toml`
      plus `packs/vault/agents/<phase>/PROVENANCE.md` siblings (seed set, same rule as
      T024: T036 scores these paths; T041 overwrites only after both qualifications)
- [X] T030 [US2] Hermetic driver that constructs `AuthoringRequest` with the vault pack
      name and walks five phases, asserting pins in
      `tests/conformance/phase_agents/test_vault_phase_pins.py` (new)

**Checkpoint**: Two packs, two instruction sets, no cross-loading.

---

## Phase 5: User Story 3 — Published practice with provenance (Priority: P2)

**Goal**: Each shipped `AGENTS.md` encodes current published HashiCorp practice for that
product in that phase (design, implementation, safety, named anti-patterns). Provenance
names sources and authorship date. Runtime does not fetch the public web (FR-008, SC-005).

**Independent Test**: Reviewer can open each `PROVENANCE.md` and see sources + date.
Terraform Write constrains modules/state/variables/secrets/anti-patterns. Vault Write does
not emit Terraform resources as the change. A Build in progress has no public-internet
instruction fetch.

### Tests for User Story 3

- [X] T031 [P] [US3] [GATE:conformance] SC-001 body-distinctness (not path-only) in
      `tests/conformance/phase_agents/test_agents_bodies_differ_by_phase.py` (new)
- [X] T032 [P] [US3] Assert authoring-tier / bind path never calls out to the public web
      for instruction text in
      `tests/conformance/phase_agents/test_no_runtime_instruction_fetch.py` (new) (A/E1
      hermetic half)

### Implementation for User Story 3

- [X] T033 [P] [US3] Rewrite Terraform `packs/terraform/agents/*/AGENTS.md` from current
      public Terraform practice at authorship time; complete each
      `packs/terraform/agents/*/PROVENANCE.md` with named sources and ISO authorship date
      (FR-006, FR-007)
- [X] T034 [P] [US3] Rewrite Vault `packs/vault/agents/*/AGENTS.md` from current public
      Vault practice; complete `packs/vault/agents/*/PROVENANCE.md` the same way; recompute
      `[[agents]]` digests in both `pack.toml` files after the rewrites
- [X] T035 [US3] [GATE:conformance] Mechanical checks that Terraform Write mentions
      Terraform authoring constraints and Vault Write does not instruct Terraform resources
      in `tests/conformance/phase_agents/test_practice_is_product_specific.py` (new) —
      substring/structure only, never “the model wrote good HCL”

**Checkpoint**: Content is reviewable practice with provenance; pins still match bytes.

---

## Phase 6: User Story 4 — GEPA then DSPy, gates that can fail (Priority: P2)

**Goal**: Individual GEPA refinement per file, then a DSPy five-predictor joint compile,
both offline. Production executes only promoted pins. `promote_phase_agents` requires
provenance, injection lens, and both qualifications.

**Independent Test**: A phase-level fixture that must fail, and a full-Build fixture that
must fail. Losing either blocks promotion. Production path does not import `dspy`.

### Tests for User Story 4

- [X] T036 [P] [US4] [GATE:eval] `phase_agents` / `build_agents` floors and known-fail
      fixtures via `load_phase_agents_cases` / `load_build_agents_cases` in
      `tests/conformance/phase_agents/test_agents_eval_can_fail.py` (new) (A11, SC-004);
      assert `test_eval_gates` still iterates only `SUITES`; assert at least one `pass`
      case per phase (and one `build_agents` `pass`) names the shipped
      `packs/<pack>/agents/<phase>/AGENTS.md` path or digest
- [X] T037 [P] [US4] [GATE:fail-closed] `promote_phase_agents` refuses missing
      qualifications (`promotion_incomplete`) and missing extra (`refinement_unavailable`)
      in `tests/conformance/phase_agents/test_promote_phase_agents.py` (new) (A12)

### Implementation for User Story 4

- [X] T038 [US4] Add `PHASE_AGENTS_QUALIFICATION = "phase_agents"` and
      `BUILD_AGENTS_QUALIFICATION = "build_agents"` beside `AUTHORING_QUALIFICATION` in
      `src/core/evals/suites.py` — **not** members of `SUITES`; do not teach
      `parse_cases` / `load_pack_cases` these names
- [X] T057 [US4] Implement `load_phase_agents_cases` and `load_build_agents_cases` in
      `src/core/evals/phase_agents_corpus.py` (same refusal grain as
      `authoring_corpus.py`): floors from
      `specs/049-phase-product-prompts/data-model.md`; `CorpusRefused` /
      `UnrunnableSuite` below floor; **never** called from `test_eval_gates.py`
- [X] T039 [P] [US4] Ship `packs/terraform/evals/phase_agents.toml` and
      `packs/terraform/evals/build_agents.toml` loaded **only** by T057: `phase_agents`
      has ≥5 cases **per phase** and ≥1 `fail` **per phase**; `build_agents` has ≥5
      cases and ≥1 jointly poisonous `fail`; **at least one `pass` case per phase**
      (and one `build_agents` `pass`) sets `instruction_ref` / `set_ref` to the shipped
      `packs/terraform/agents/<phase>/AGENTS.md` path or digest
- [X] T040 [P] [US4] Ship the same two files, floors, and shipped-path `pass` refs under
      `packs/vault/evals/`, loaded only by T057
- [X] T041 [US4] Implement `promote_phase_agents` in `src/core/evals/promotion.py` per
      `specs/049-phase-product-prompts/contracts/prompt-tune.md` (digest, lens, both
      suites, provenance sibling; authored files do not invent `upstream_commit`)
- [X] T042 [US4] Add optional extra `prompt-tune` in `pyproject.toml`:
      `harness[evals]` + `dspy==3.3.0`; do not add `dspy` to `evals` or `adapters`; run
      `scripts/check-licenses.sh` — a GPL-family transitive stops the extra (do not
      weaken `licenses/allowlist.txt`)
- [X] T043 [P] [US4] Implement `evals/prompt-tune/gepa_phase.py` — `dspy.GEPA` on a
      one-predictor module per `AGENTS.md` against `phase_agents`; candidates write to
      `evals/prompt-tune/candidates/`; if **any** phase loses, copy **zero** files into
      `packs/` (whole-set rule)
- [X] T044 [P] [US4] Implement `evals/prompt-tune/dspy_build.py` — five-predictor
      `dspy.Module` compiled with `dspy.GEPA` against `build_agents`; no MIPROv2/COPRO
      substitute; a losing joint metric copies **zero** files (same whole-set rule as T043)
- [X] T045 [US4] In `evals/prompt-tune/gepa_phase.py` and
      `evals/prompt-tune/dspy_build.py` (and `promote_phase_agents` in
      `src/core/evals/promotion.py`): missing `dspy` import → `refinement_unavailable`;
      `promote_phase_agents` MUST NOT update `[[agents]]` without both suites. T024/T029
      seed pins are a different writer; they stay until this function overwrites them
      after both qualifications pass. Never treat a seed pin as evidence that GEPA/DSPy
      ran.
- [X] T046 [US4] [GATE:eval] Document named-runner SC-006 / E2 / E3 in
      `evals/prompt-tune/README.md`: n, generic-steer pass rate, promoted pass rate,
      **positive delta** on `evals/authoring` golden tasks (not pytest wording
      assertions); a non-positive delta is a failed eval

**Checkpoint**: Refinement is offline, named, and able to lose; served code still has no
`dspy`.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, portal containment, product-blindness, named-runner obligation.

- [X] T047 [P] [GATE:conformance] A13: portal templates/JS do not contain phase instruction
      bodies or a prompt composer in `tests/conformance/phase_agents/test_portal_does_not_compose_agents.py`
      (new); no edits to `portal/` that compose these files (FR-013)
- [X] T048 [GATE:conformance] Named-runner checklist for E1–E3 in
      `specs/049-phase-product-prompts/contracts/conformance-phase-product-prompts.md`
      (record who ran it on the implementation PR; **named runner: Dan McTeer**)
- [X] T049 [P] Update pack layout in `packs/README.md` to include `agents/<phase>/AGENTS.md`
      + `PROVENANCE.md`
- [X] T050 [P] Add glossary terms for pack phase `AGENTS.md` vs repository-root contributor
      `AGENTS.md` in `docs/glossary.md`
- [X] T051 [P] Changelog entry for user-visible Build steering in `CHANGELOG.md`
- [X] T052 [P] ROADMAP row/note for 049 in `ROADMAP.md` if that table is the feature index
- [X] T053 Re-run `tests/conformance/packs/test_core_is_product_blind.py` and T020; fix any
      product identifier or `dspy` leak in `src/core`
- [X] T054 Security-maintainer review request for `PackManifest` / `ChoiceRequest` /
      `content_pins` / adapter prompt concatenation (Principle V; named reviewer: Dan) on
      the **implementation** PR, not this spec PR
- [X] T055 Run `make check` and walk [quickstart.md](quickstart.md) hermetic steps 1–6
- [X] T058 Surgically amend the load sequence in
      `specs/013-capability-packs/contracts/pack-manifest.md` per research R11: skill
      **and** `AgentPin` digest verification; authoring-pack five-phase completeness;
      replace “this list is closed” with a pointer that 049
      `contracts/pack-agents.md` amends it

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: After Foundational — MVP
- **US2 (Phase 4)**: After Foundational; isolation tests need US1 terraform files in-tree
      (T023) so they can prove inequality — sequence US1 then US2, or land T023+T028
      together before T027
- **US3 (Phase 5)**: After US1 and US2 files exist (rewrites those bodies)
- **US4 (Phase 6)**: After Foundational; can overlap US3 once pin/load exists, but
      promotion copies into the same `packs/*/agents/` trees US3 authors — do not race
- **Polish (Phase 7)**: After US1–US4

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — independently testable as terraform-only
- **User Story 2 (P1)**: After Phase 2; isolation row needs both packs' files
- **User Story 3 (P2)**: After US1+US2 file paths exist
- **User Story 4 (P2)**: After Phase 2; uses US1/US2 paths as promotion targets

### Parallel Opportunities

- T001 ∥ T002
- T013 ∥ T014 ∥ T015 ∥ T019 ∥ T020 after T010
- T016 ∥ T017 ∥ T018 ∥ T056 after T009
- T021 ∥ T022 after Phase 2
- T023 ∥ T024
- T026 ∥ T027 after both packs' files
- T028 ∥ T029
- T031 ∥ T032
- T033 ∥ T034
- T036 ∥ T037 after T057
- T039 ∥ T040 after T057
- T043 ∥ T044 after T042 (both obey whole-set copy)
- T047 ∥ T049 ∥ T050 ∥ T051 ∥ T052

---

## Parallel Example: User Story 1

```bash
# Tests first (must fail):
Task: "A1/A3 terraform pins in tests/conformance/phase_agents/test_terraform_phase_pins.py"
Task: "A9 judge vs write in tests/conformance/phase_agents/test_judge_file_not_write_file.py"

# Then content + manifest:
Task: "Five Terraform AGENTS.md under packs/terraform/agents/<phase>/"
Task: "[[agents]] pins in packs/terraform/pack.toml"
```

---

## Implementation Strategy

US1–US3 files under `packs/*/agents/` are the **seed set**. They are not an eval-gated
production ship until US4 (`promote_phase_agents` + both qualifications). **Do not merge
`feat/049-phase-product-prompts` to `main` until US4 (T036–T046, T057) is in that same
implementation PR.** Principle VIII / FR-011.

### Validate after User Story 1 (in-branch only)

1. Phase 1 Setup (ADR-0071 + test package)
2. Phase 2 Foundational (pin/load/bind/fail-closed)
3. Phase 3 US1 Terraform
4. **STOP and VALIDATE in the feature branch**: terraform-bound hermetic run records five
   distinct `{pack}/agents/{phase}@{version}` pins; omit Write → no PR. Do not open a
   production merge.
5. Do not open `feat/049-…` until this spec PR is merged

### Incremental Delivery (one implementation PR)

1. Setup + Foundational → bind seam
2. US1 Terraform → terraform steer
3. US2 Vault → isolation claim is real
4. US3 practice + provenance → content is the point
5. US4 GEPA then DSPy + T057 loaders → promotion can lose
6. Polish T058 (013 contract) + docs + named-runner
7. Merge `feat/049` only after US4 gates exist

### Parallel Team Strategy

After Phase 2: one person US1 terraform files, another US2 vault files; US3 rewrites both;
US4 extra/scripts last so they do not fight US3 bytes. T057 before T039/T040.

---

## Notes

- [P] = different files, no incomplete dependency
- Named contracts bind exactly — `load_phase_agents`, `bind_phase_agents`,
  `promote_phase_agents`, `load_phase_agents_cases`, `load_build_agents_cases`,
  `dspy.GEPA`, extra `prompt-tune`, `dspy==3.3.0`
- Do not cite Proposed ADR-0067 as governing (use ADR-0039 for Judge ≠ Write)
- Tests never call a live model; evals do, on the named-runner path only
- Spec PR (`spec/049-phase-product-prompts`) merges before implementation PR
  (`feat/049-phase-product-prompts`)
