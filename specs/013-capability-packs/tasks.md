# Tasks: Capability Packs and Eval Gates

**Input**: Design documents from `/specs/013-capability-packs/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. This feature *is* a gate discipline — a version of it without tests
would be the passing stub ADR-0047 forbids, wearing the feature's own name.

**Organization**: Setup → Foundational (the seams every story needs) → US1–US5 in priority
order → Polish & gates. Gate tasks are tagged and live in the phase that delivers the
behaviour they guard.

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | Unqualified cell, withdrawn cell, no-fallback stop, tier violation, digest mismatch, incomplete promotion |
| **Conformance** | Four eval suites; the structural rows (product-blind core, no bypass, no widening, no auto-tracking); the live-model lane |
| **Correlation / evidence** | `MODEL_GATE`, `MATRIX_FALLBACK`, provenance-at-read into the run record |
| **Eval** | The whole of Phase 7 — this is the feature that brings them online |
| **No-secret-leak** | The provider key is a dev-lane secret: never in a jobspec, never read by a run, never in a pack |

## Path Conventions

Single project: `src/`, `tests/` at repository root. **`packs/` and `evals/seed/` at the
repository root** rather than under `src/` — they are content, and product knowledge inside
the Python package tree would ship in the distribution that Principle I says is
product-blind.

---

## Phase 1: Setup

- [ ] T001 Add an `evals` dev extra to `pyproject.toml` carrying the scoring harness and, for the live lane only, one model-provider SDK. Comment why it is an extra and not a base dependency: the platform's default posture is "calls no model", which `pyproject.toml` currently states in as many words, and this feature must not change that for anyone who is not running the live lane
- [ ] T002 [P] Add `@pytest.mark.live_model` to `pyproject.toml`'s marker list with the reason inline — needs a paid credential and is non-deterministic, so it is never in a blocking lane
- [ ] T003 [P] Create `packs/README.md` explaining why this directory is at the repository root: content, not code, and `src/core` stays product-blind
- [ ] T004 [P] Create `evals/seed/README.md` — the root of the judge chain (ADR-0052). It states that these labels are a human's judgement, that they are reviewed like code, and that a seed set which stops being representative silently weakens every gate above it

**Checkpoint**: `make check` green with the new extra resolving.

---

## Phase 2: Foundational (blocking all user stories)

**Purpose**: the manifest, the loader, the matrix reader, the registry field, and the two
audit events. No story is demonstrable until this phase completes.

### The two sealed-core additions

- [ ] T005 Add `risk_class` to `ToolRegistration` and `ToolRegistry.register` in `src/core/registry/memory.py` — additive and defaulted so every existing caller is unchanged. The docstring records finding F2: this has been in the glossary since the beginning and in no code, so Principle II's provision for demanding process isolation on `secret_touching` and `destructive` tools has never been actionable
- [ ] T006 Add `MODEL_GATE` and `MATRIX_FALLBACK` to `AuditEventType` in `src/core/audit/schema.py`. The `MODEL_GATE` docstring records F3 — there is no approval event to be confused with, so this **establishes** the distinction rather than repairing one, and when human approvals gain an event the two are already separate. `MATRIX_FALLBACK` is separate because "a model decided something" and "the model that ran was not the model that was pinned" are different questions

### Pack records and loading

- [ ] T007 Create `src/core/packs/__init__.py` with the package intent: packs are content, the core stays product-blind, and a manifest declares while the platform decides
- [ ] T008 [P] Create `src/core/packs/manifest.py`: `PackManifest`, `ToolDeclaration`, `RiskClass` (`read | write | destructive | secret_touching`), `SkillPin`, `WorkflowDeclaration`. Frozen dataclasses; `provenance` is `adopted | authored` and `adopted` requires an `upstream` table
- [ ] T009 [P] Create `src/core/packs/loader.py`: `PackLoader` protocol, `FilesystemPackLoader`, `InMemoryPackLoader`. Loading verifies **every content digest** and refuses `digest_mismatch` naming the file — verification at load rather than at review, because review is when someone looked and load is when it matters
- [ ] T010 Create `src/core/packs/registration.py`: manifest → `ToolRegistry` registrations with risk class preserved. **Loading executes nothing from the pack** — a declaration names a handler, and the handler is resolved from what the platform already provides
- [ ] T011 Create `src/core/packs/isolation.py`: which packs a definition reaches, the no-widening check against its ceiling, and ambiguous-tool-name refusal. A tool name is qualified by its pack; an unqualified name reachable from two packs refuses rather than resolving by load order, because load order changes without anyone deciding it did
- [ ] T012 [P] Component rows in `tests/component/test_pack_loading.py`: manifest parsing, digest verification and its refusal, two packs side by side, ambiguous name refused, and that a malformed manifest refuses the whole load rather than partially loading

### The matrix

- [ ] T013 Create `src/core/evals/__init__.py` with the package intent: gates are records, not claims
- [ ] T014 Create `src/core/evals/matrix.py`: `QualifiedCell`, the Vault-backed matrix reader (010's ceiling pattern — operator-authored, read-only to runs, refused loudly when absent), and `validate_binding_map`. Each cell carries `qualified_by` (`fixture | live`) and the judge that scored it
- [ ] T015 [P] Extend `OPERATION_REASONS` in `src/core/runs/refusals.py` with this feature's vocabulary: `unqualified_cell`, `cell_withdrawn`, `no_qualified_fallback`, `pack_exceeds_ceiling`, `above_tier`, `digest_mismatch`, `promotion_incomplete`, `injection_suspected`. Added to the frozen mapping rather than invented at call sites — the 010 rule
- [ ] T016 [P] Component rows in `tests/component/test_matrix_reader.py`: a green cell resolves; an absent matrix refuses loudly rather than resolving to empty; `qualified_by` round-trips

**Checkpoint**: `make check` green; a pack loads and registers tools; the matrix reads.

---

## Phase 3: User Story 1 — A pack makes the platform competent at one product (P1) 🎯 MVP

**Goal**: two packs load, their tools are callable through the ordinary pipeline, and no
core module names a product.

**Independent test**: load both packs, start a run whose definition names one pack's tools,
watch them reach the same hooks every other tool does — then grep `src/core` for a product
name and find nothing.

- [ ] T017 [US1] Create `packs/vault/pack.toml` and `packs/vault/skills/` — **authored**, in the same open Agent Skills format `hashicorp/agent-skills` uses (FR-027d), so contributing upstream is a pull request rather than a rewrite. Vault runs in the enclave, so this is the pack whose tools are exercised against a live product
- [ ] T018 [US1] Vendor the Terraform pack: `packs/terraform/pack.toml`, `skills/` copied unmodified from [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) at a pinned commit, and `packs/terraform/skills/PROVENANCE.md` recording repository, commit, licence (MPL-2.0), and retrieval date. **Adopted**, which is what gives ADR-0004's supply chain a genuine subject
- [ ] T019 [US1] Replace the hand-built registry in `src/surfaces/dispatch/entrypoint.py` with pack loading — **the line a previous feature signposted** ("when they land, this is the line they replace"). Keep the fixture tools available for definitions that name no pack, so 008–012's rows are unchanged
- [ ] T020 [P] [US1] [GATE:conformance] Structural row in `tests/conformance/packs/test_core_is_product_blind.py`: no module under `src/core` contains a product name, with `vault_fabric` and `credentials` excluded **by name and with a comment** — those are the trust fabric, not the product, and a pattern-only check would either miss the distinction or forbid the wrong thing
- [ ] T021 [US1] [GATE:conformance] Row in `tests/conformance/packs/test_no_bypass_path.py`: every pack tool is a `ToolRegistry` registration, and no pack-specific invocation path exists. Asserted structurally — there is no pack-tool code path, which is the whole design
- [ ] T022 [US1] [GATE:fail-closed] Rows in `tests/component/test_pack_cannot_widen.py`: a pack declaring a tool outside its definition's ceiling refuses `pack_exceeds_ceiling`; zero paths grant from a manifest. **The most plausible defect in this feature** — a pack that grants reads as the pack system working
- [ ] T023 [P] [US1] Enclave row in `tests/conformance/identity/test_pack_tools_dispatch.py` (`host_enclave`): a run whose definition names the Vault pack reaches a real Vault tool through the real pipeline, in an allocation

**Checkpoint**: US1 demonstrable; the core is provably product-blind.

---

## Phase 4: User Story 2 — A definition cannot pin what has not been qualified (P1)

**Goal**: the matrix binds. Unqualified cells are refused at definition time; withdrawn ones
at run start; fallback goes only to qualified cells or the run stops.

**Independent test**: pin a qualified cell and run; pin an unqualified one and watch the
definition refuse before anything executes; withdraw a pinned cell and watch the run refuse.

- [ ] T024 [US2] Wire binding-map validation into definition registration in `src/core/evals/matrix.py` — refuses `unqualified_cell` **naming the cell**, at definition time
- [ ] T025 [US2] Wire the second validation into run start, in `src/core/run.py` where the definition's authority is already resolved. **Not redundant**: a cell can be withdrawn after a definition pinned it, and validating only at registration would let a withdrawn cell keep running because nothing re-asked — the reasoning that makes 010 resolve a ceiling per run
- [ ] T026 [US2] Implement fallback in `src/core/evals/matrix.py`: search for another qualified cell for the same `(pack, role)`, take it and record `MATRIX_FALLBACK`; if none, stop the run with `no_qualified_fallback` recorded
- [ ] T027 [P] [US2] [GATE:fail-closed] Rows in `tests/component/test_matrix_refusals.py`: unqualified refused at definition time naming the cell; withdrawn refused at run start; fallback records; no-fallback stops. Each asserts **zero runs proceeded**
- [ ] T028 [US2] [GATE:conformance] Row in `tests/conformance/packs/test_no_auto_tracking.py`: no alias, no "latest", no configuration that resolves to a moving target. Asserted as an absence, with a positive control that constructs one and confirms the check fires
- [ ] T029 [P] [US2] [GATE:correlation] Row in `tests/component/test_model_gate_is_not_an_approval.py`: a `MODEL_GATE` event is distinguishable from any human approval in the trail, and a model verdict never satisfies an approval requirement (FR-015)

**Checkpoint**: US1+US2 is the MVP — packs load and the matrix binds.

---

## Phase 5: User Story 3 — An upstream skill bump is a reviewed change (P2)

**Goal**: promotion requires provenance, injection-lens review, and a passing eval. All
three.

**Independent test**: propose a bump; confirm each missing check blocks it independently;
confirm a skill carrying an injection attempt is refused.

- [ ] T030 [US3] Create `src/core/evals/promotion.py`: `promote_skill()` requiring all three checks. Provenance verifies the pinned commit exists upstream and the content hashes to what was recorded
- [ ] T031 [US3] Implement the injection lens in `src/core/evals/promotion.py` — pattern-based over skill content for instruction-shaped text targeting the agent: overriding system instructions, exfiltrating context, redirecting tool use. **Deliberately not model-scored**: that would make promotion depend on a model, which needs a qualified cell, which needs the gates — a second regress with no seed set to terminate it. Docstring records it as a floor rather than a guarantee
- [ ] T032 [P] [US3] [GATE:fail-closed] Rows in `tests/component/test_skill_promotion.py`: each of the three checks missing blocks independently; a pinned skill does not change when upstream does; an overlay's relationship to its baseline survives a bump (FR-019)
- [ ] T033 [P] [US3] Rows in `tests/component/test_injection_lens.py`: known injection shapes refused and recorded; benign skill content passes; **one row asserts a novel phrasing the lens does NOT catch**, so the floor is documented by a test rather than only by a docstring

**Checkpoint**: the supply chain has teeth.

---

## Phase 6: User Story 4 — What the agent consulted is part of the record (P2)

**Goal**: provenance-at-read. What the agent consulted is archived as published at that
moment.

**Independent test**: consult guidance, change it upstream, confirm the run record still
names what was actually read.

- [ ] T034 [US4] Create `src/core/packs/consulted.py`: record URL, timestamp, and content hash into the run record at read time
- [ ] T035 [P] [US4] [GATE:correlation] Rows in `tests/component/test_provenance_at_read.py`: the triple is archived; changing the source afterwards does not change the record; an executed artifact is always pinned, so the executed/consulted distinction holds in both directions

**Checkpoint**: attestation can name its inputs.

---

## Phase 7: User Story 5 — A definition's tier bounds what it may compose (P2)

**Goal**: the tier restricts workflows, and it is a property of the definition.

**Independent test**: two definitions, different tiers, same pack — the lower one confined
to paved workflows regardless of what the request asks for.

- [ ] T036 [US5] Add tier resolution to `src/core/packs/isolation.py`: a workflow above the definition's tier refuses `above_tier`. **Tiers bound workflows, never tools** — the ceiling answers about tools, and two mechanisms answering one question is the duplication ADR-0044 forbids
- [ ] T037 [P] [US5] [GATE:fail-closed] Rows in `tests/component/test_competency_tiers.py`: lower tier confined to paved workflows; higher tier composes; a request asking for behaviour above the tier is refused — **the tier wins, because it belongs to the definition and not the request**
- [ ] T038 [P] [US5] Row in `tests/component/test_tiers_do_not_duplicate_the_ceiling.py`: a tier change never alters which tools are reachable — the disjointness ADR-0044 requires, asserted rather than assumed

**Checkpoint**: all five stories demonstrable.

---

## Phase 8: The eval gates

**Purpose**: Principle VIII online. This is the phase the roadmap has been waiting for.

- [ ] T039 [GATE:eval] Create `src/core/evals/suites.py`: the four suites as sets of cases with expected outcomes — `must_deny`, `must_decline`, `citation_accuracy`, `estate_state`. **Report fidelity is deliberately absent**, with an explicit skip citing ADR-0018 in the output rather than silence (FR-013a)
- [ ] T040 [GATE:eval] Create `src/core/evals/scoring.py`: `Scorer` protocol, `FixtureScorer` (replays a recorded response), `LiveModelScorer` (calls a provider). The suites, thresholds, and refusals are **identical across both** — only the scorer differs, which is what makes "the machinery is real even when the substrate is a recording" true rather than aspirational
- [ ] T041 [GATE:eval] Create `evals/seed/` with human-labelled verdict cases, and `src/core/evals/judge.py` implementing the chain: the first judge is qualified against the seed, every later judge by a judge already qualified. A judge pointed at itself refuses rather than closing the loop
- [ ] T042 [P] Write `packs/vault/evals/` and `packs/terraform/evals/` cases for each suite
- [ ] T043 [GATE:eval] Add `make evals` (fixtures, blocking) and `make evals-live` (`live_model` marker, named runner) to the `Makefile`, and wire `tests/conformance/packs` into the conformance recipe — **in the same commit that creates the directory**, because 010 lost a feature's rows to a directory no lane enumerated
- [ ] T044 [P] [GATE:eval] Rows in `tests/component/test_judge_chain.py`: the first judge qualified against the seed; a later judge qualified by a qualified judge; a judge pointed at itself refused; **and a cell recorded without a judge is refused unless it is the seed-qualified first**
- [ ] T045 [P] [GATE:no-secret-leak] Row in `tests/conformance/packs/test_provider_key_is_dev_lane_only.py`: the provider credential appears in no jobspec, is read by no run path, and is absent from every pack manifest

---

## Phase 9: Polish, records, and the gate run

- [ ] T046 [P] Draft `docs/adr/0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md`: the regress, the three bounded options, why external attestation imports trust the platform cannot inspect and a declared floor makes the chain's root unarguable, and the **maintenance obligation** — a seed set that stops being representative silently weakens every gate above it
- [ ] T047 [P] Update `docs/glossary.md`: `risk class` now exists in code; add `capability pack` cross-references, `qualified cell`, `competency tier`, and `seed set`
- [ ] T048 [P] [GATE:conformance] Apply every break fixture from `contracts/conformance-packs.md` to the tree, watch the row fail, revert: a pack that grants; a cell qualified by the cell it qualifies; a withdrawn cell that keeps running; a skill bumped without review; an alias resolving to latest; a model verdict filed as an approval. **A row nobody has seen fail is a row nobody knows works**
- [ ] T049 [P] Update `ROADMAP.md`: 013 shipped; four of five eval-gate rows move Deferred → In force; report fidelity recorded as still-owed against ADR-0018; portal answering unblocked
- [ ] T050 [P] Record rows **In force** in `specs/013-capability-packs/contracts/conformance-packs.md`, and note in `specs/012-conversational-portal/`'s record that answering's dependency is now met
- [ ] T051 [GATE:conformance] Run `make check`, `make conformance`, and `make evals` against a live enclave on a clean tree, and walk `specs/013-capability-packs/quickstart.md` sections 2–7. Then run `make evals-live` as the named runner and **record each cell's `qualified_by` in the per-cell table** — a cell absent from that table is not qualified (SC-013)

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─→ Phase 2 Foundational ─→ Phase 3 US1 (MVP start)
                                          ─→ Phase 4 US2 (MVP complete)
                                          ─→ Phase 5 US3 (needs US1's packs)
                                          ─→ Phase 6 US4 (needs US1's packs)
                                          ─→ Phase 7 US5 (needs US1's workflows)
                                                     ─→ Phase 8 Eval gates (needs US2's matrix)
                                                                ─→ Phase 9 Polish
```

- **US3, US4, US5 are mutually independent** and each depends only on Foundational + US1.
- **Phase 8 depends on US2**, because a gate that qualifies cells needs a matrix to write to.
- T018 (vendoring Terraform) can start any time after T008 — it is content, not code.

## Parallel opportunities

- T002 ∥ T003 ∥ T004 (setup); T008 ∥ T009 (records/loader); T015 ∥ T016 after T014.
- After US1+US2: Phases 5, 6, and 7 in parallel.
- T042 (eval cases) ∥ T041 (the chain) — cases are content.
- Polish: T046 ∥ T047 ∥ T049 ∥ T050.

## Implementation strategy

**MVP = Phase 3 (US1) + Phase 4 (US2)**: packs load and the matrix binds. That is the
smallest thing that is recognisably this feature — product knowledge the platform can use,
and models it may only use once demonstrated.

Phase 8 is what the roadmap has been waiting for and is deliberately last among the
building phases: the gates need something to gate. Phase 9's break fixtures are not optional
polish — 011 found one fixture in four survivable, and it was the one guarding the defect
that feature was most likely to reintroduce.
