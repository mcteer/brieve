# Tasks: A model chooses, and the choice is governed

**Input**: Design documents from `/specs/020-model-in-the-loop/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required. FR-010 says rows must drive a **dispatched run**, not a constructed agent — the adapter's governance is already asserted; that a real run consults a model is not.

**Organization**: By user story. All three are P1 and none is optional.

## Format: `[ID] [P?] [Story] Description`

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — a provider that can be down, a bound that can be exhausted, a model that names nothing | T012, **T016b**, T019, T024 |
| **Conformance** | **Yes** — sealed-core seam and the run loop | Phases 3–5 |
| **Correlation / evidence** | **Yes** — a new audit event joins the run's trail | **T014** |
| **No-secret-leak** | **Yes** — provider credential, and model output that may carry tool results | T013, T034 |
| **Eval** | **No** | Consumes the qualified matrix; promotes no pack, model, or policy. Principle VIII is N/A. |

---

## Phase 1: Setup

- [ ] T001 Create `tests/conformance/choice/__init__.py` — the directory only, no rows yet. **Not** the `host_enclave` pytest line in `Makefile`: these rows need a dispatched run, and 019 shipped rows a lane collected with nothing serving. The lane wiring is T017 and must land before T018 writes the first `test_*.py`, which is when `tests/unit/test_every_conformance_directory_is_run.py` starts checking this directory at all.
- [ ] T002 Record the per-directory `pytest --collect-only -q` counts from `main` in `specs/020-model-in-the-loop/contracts/conformance.md`, as SC-008's baseline.
- [ ] T003 [P] Confirm in `specs/020-model-in-the-loop/research.md` which `pydantic-ai` model interface a provider and a double must both satisfy — the seam T007 defines depends on it, and nothing in this repository has passed `build_governed_agent` a model before.

---

## Phase 2: Foundational — blocking prerequisites

### The sealed-core change, done deliberately

- [ ] T004 Add one `TOOL_CHOSEN` member to `AuditEventType` in `src/core/audit/schema.py` (FR-009, FR-009a). **This is a Principle V change** — the audit schema is named sealed core and requires security-maintainer review. Research F1 established the change is additive, the enum unversioned, and no test asserts its membership; **that is not the same as exempt**, and the plan records the review as owed rather than discharged.
- [ ] T005 Assert in `tests/unit/test_audit_chain.py` that adding a member changes no existing entry's `entry_hash` — the hash covers an entry's own `event_type` value, not the set of possible values. Cheap to check and the assumption everything else here rests on.

### The seam

- [ ] T006 Create `src/core/choice/__init__.py` and `src/core/choice/chooser.py` — the interface a provider or a double satisfies: given the task, the permitted tools, and what has happened at this step, return a named tool or nothing.
- [ ] T007 Implement the provider-backed chooser in `src/core/choice/chooser.py`, calling the model through `build_governed_agent` in `src/adapters/pydantic_ai/agent.py` — **which is unchanged**. It has taken a model since it was written and installs governance outermost; this feature is its first production caller.
- [ ] T008 Implement the re-choice budget in `src/core/choice/bounded.py` (FR-004b). **Per step, not per run** — a run that legitimately needs several tools must not inherit a smaller budget because an earlier step took two attempts.
- [ ] T009 Create `tests/harness/scripted_chooser.py` — the lane's double, satisfying the same interface. **Injected where the binding resolves a model, never at the loop** (research F5): a double at the loop would let the loop be tested without the code path that consults a model, which is the shape this feature exists to end.

---

## Phase 3: US1 — a model chooses and governance sees the choice (P1)

**Goal**: the tool invoked is one a model named, and an unpermitted choice is refused by the enforcement that already exists.

**Independent test**: run a task whose correct tool is not the one round-robin would have picked; observe the model's choice executed and recorded.

- [ ] T010 [US1] Replace the selection site in `src/surfaces/dispatch/entrypoint.py`: the loop asks a chooser instead of computing an index.
- [ ] T011 [US1] **Delete `_tool_for_step`** from `src/surfaces/dispatch/entrypoint.py` (FR-002). Not kept as a fallback: a surviving fallback is taken exactly when the provider is down, silently reverting the platform to a scripted sequence **while every governance row keeps passing** — this feature's own defect, preserved as a feature.
- [ ] T012 [GATE:fail-closed] [US1] Make a provider failure terminal and recorded in `src/core/choice/chooser.py` (FR-007), with no path back to any non-model selection.
- [ ] T013 [GATE:no-secret-leak] [US1] Ensure the model's reasoning is **not** recorded, in `src/core/choice/chooser.py`. It is not a governance fact and it would carry whatever the model read from tool results into the trail — the no-secret-leak posture applies to what is recorded about a choice, not only to tool results.
- [ ] T014 [GATE:correlation] [US1] Emit `TOOL_CHOSEN` from `src/core/choice/chooser.py` carrying the run's correlation id, so the choice joins the same trail its tool bracket joins.
- [ ] T015 [US1] Record **every** refusal, not only the last before success (FR-004c), in `src/core/choice/bounded.py`. A run denied four times and permitted on the fifth is a different event from one permitted immediately, and a trail showing only the success would describe the wrong run.
- [ ] T016 [US1] Return a refused choice to the model as context (FR-004a) in `src/core/choice/bounded.py`, so the denial teaches rather than only blocks.
- [ ] T016a [US1] Handle a **malformed choice** in `src/core/choice/chooser.py` — a name that is not a tool at all. Refused *as malformed*, distinguishable from a tool that was named and denied (spec Edge Cases). **The two mean different things to whoever reads the trail**: one is a model that misunderstood the task, the other is a model that understood it and reached past its ceiling.

  Analysis pass 1 found no task for this. It is a behaviour, not only a row — 019's equivalent shipped as a bare `KeyError('run_id')` reaching the client, indistinguishable from a platform fault, because the handling was discovered while writing the assertion rather than before.

- [ ] T016b [US1] Handle an **empty choice** in `src/core/choice/chooser.py` — the model names nothing. The run ends in a recorded terminal state and **does not default to a tool** (US1 acceptance scenario 3). Defaulting here would be `_tool_for_step` returning through the back door.

- [ ] T017 [US1] Add `infra/bin/choice-conformance` and call it from `Makefile`'s `conformance` recipe — bring up what a dispatched run needs, run the rows, tear down what it started. **Must land before T018.**
- [ ] T018 [P] [US1] Add `test_a_model_choice_is_executed` in `tests/conformance/choice/test_a_model_chooses.py` (FR-001, SC-001) — against a dispatched run, evidenced from the trail.
- [ ] T019 [GATE:fail-closed] [P] [US1] Add `test_no_arithmetic_selection_remains` in `tests/conformance/choice/test_a_model_chooses.py` (FR-002, SC-002) — by source inspection, because a deleted function leaves no runtime trace to assert on.
- [ ] T020 [US1] Add `test_an_unpermitted_choice_is_refused_by_existing_enforcement` in `tests/conformance/choice/test_a_choice_is_governed.py` (FR-003, FR-004, SC-003). **Assert the refusal came from the core, not from the choosing code** — 019 learned that a layer refusing on its own is outcome-identical to the core refusing, so this discriminates on provenance.
- [ ] T021 [P] [US1] Add `test_a_refusal_returns_to_the_model` in `tests/conformance/choice/test_a_choice_is_governed.py` (FR-004a).
- [ ] T022 [US1] Add `test_the_rechoice_bound_is_terminal` in `tests/conformance/choice/test_a_choice_is_governed.py` (FR-004b, SC-003a) — **the property whose absence would look like the feature working**, because a run grinding against its ceiling forever and a run thinking hard are the same picture from outside.
- [ ] T022a [P] [US1] Add `test_a_malformed_choice_is_distinguishable` and `test_an_empty_choice_ends_the_run` in `tests/conformance/choice/test_a_choice_is_governed.py` — the rows for T016a and T016b. Collapsing malformed into refused would tell a reader a model reached past its ceiling when it merely misunderstood.
- [ ] T022b [P] [US1] Add `test_repetition_is_bounded_by_the_step_budget` in `tests/conformance/choice/test_a_choice_is_governed.py` — a model naming the same permitted tool forever is stopped by the existing step budget, not by anything new. **Asserted because it is the case where nothing is wrong**: no refusal, no malformed answer, and a run that never ends unless the budget holds.
- [ ] T023 [P] [US1] Add `test_every_refusal_is_recorded` in `tests/conformance/choice/test_a_choice_is_governed.py` (FR-004c, SC-003b).

---

## Phase 4: US2 — the model is the one the matrix bound (P1)

**Goal**: the run uses the model its definition names, validated before any provider call.

**Independent test**: two definitions bound to different models produce runs evidenced as using different models.

- [ ] T024 [GATE:fail-closed] [US2] Resolve the model from the definition's binding map and validate it against the qualified matrix in `src/core/choice/chooser.py` **before any provider call** (FR-005, FR-006). A model the matrix does not qualify must not be *reached*, not merely not used.
- [ ] T025 [US2] Refuse a run with no binding for the role, in `src/core/choice/chooser.py` (FR-006). **Never default** — a default model is an ungoverned model choice, the same defect as an ungoverned tool choice one level up.
- [ ] T026 [P] [US2] Add `test_the_bound_model_is_the_one_used` in `tests/conformance/choice/test_the_model_is_bound.py` (FR-005, SC-004).
- [ ] T027 [P] [US2] Add `test_an_unqualified_model_refuses_before_any_call` in `tests/conformance/choice/test_the_model_is_bound.py` (FR-006).
- [ ] T028 [P] [US2] Add `test_no_binding_refuses_rather_than_defaults` in `tests/conformance/choice/test_the_model_is_bound.py` (FR-006).

---

## Phase 5: US3 — a model-driven run is still durable (P1)

**Goal**: kill it mid-flight; it resumes and completes with exactly one execution per step and no repeated provider call.

**Independent test**: a killed model-driven run resumes and completes.

- [ ] T029 [US3] Persist each step's chosen tool so resume honours the choice already made, in `src/core/choice/chooser.py`. **A replay that re-asked the model would be re-execution wearing observation's clothes** — the model may answer differently, which is exactly what makes this stronger than the deterministic case.
- [ ] T030 [US3] Verify in `src/core/hooks/engine.py` that the re-choice bound does not disturb the step bracket, per research F3: `invoke_tool` keys brackets `{run_id}:{step_index}:{tool}`, so a second choice yields a different key and does not collide. A bound implemented as a retry **around** the bracket would make that key ambiguous on resume — two attempts, one key — and re-observe-never-re-execute would have to guess.
- [ ] T031 [US3] Add `test_a_model_driven_run_resumes` in `tests/conformance/durability/test_model_driven_resume.py` (FR-008, SC-005) — beside the existing resume rows, because it is the same guarantee under a harder condition.
- [ ] T032 [P] [US3] Add `test_resume_reissues_no_provider_call` in `tests/conformance/durability/test_model_driven_resume.py` (FR-008). **The observable property.** It cannot assert what a second call *would* have returned, and does not try.

---

## Phase 6: Polish & cross-cutting

- [ ] T033 Add `test_the_double_is_faithful` in `tests/conformance/choice/test_the_double_is_faithful.py` (FR-011a) — the double and a real provider must agree in **shape** on one fixture: a well-formed choice from the permitted set. **Not on which tool.** Two models may reasonably differ, and demanding they match would assert a model's judgement rather than the platform's contract. Behind a named runner, since it costs a provider call.
- [ ] T034 [GATE:no-secret-leak] [P] Assert in `tests/conformance/choice/test_a_choice_is_governed.py` that no provider credential appears in any allocation's output, and that the credential never reaches an allocation's environment where scheduler access would expose it (research F6).
- [ ] T035 [P] Add `test_the_merge_lane_needs_no_provider` in `tests/conformance/choice/test_the_double_is_faithful.py` (FR-011, SC-006).
- [ ] T036 Add `test_the_contract_states_what_this_gate_does_not_assert` in `tests/conformance/choice/test_a_model_chooses.py` (FR-009) — checked rather than trusted. **The limit most likely to be misread**: a demonstration of a model picking the right tool is far more persuasive than what it proves.
- [ ] T037 Update `specs/020-model-in-the-loop/contracts/conformance.md` — replace the sketch row table with the rows as shipped, and record SC-008 against T002's baseline. 019's contract carried a stale table through six analysis passes.
- [ ] T038 [P] Close ROADMAP gap 0e in `ROADMAP.md`, and state what remains true: the choice is governed, not that it is good.
- [ ] T039 Perform the FR-012 demonstration (SC-007) by hand against a real provider and record it in `specs/020-model-in-the-loop/contracts/conformance.md`: the model used, the choice made, whether it was permitted, and the trail entry. **Never in a lane** — and it is the step that proves the wiring carries a real inference call, which the double cannot.
- [ ] T040 (FR-009a) Obtain the **security-maintainer review Principle V requires** for the audit-schema change (T004), and record it in `specs/020-model-in-the-loop/contracts/conformance.md`. Not a formality: it is the obligation the plan recorded as owed rather than discharged, and a feature that shipped without it would have passed a Constitution Check that said so in writing.
- [ ] T041 Run the gates defined in `Makefile` — `make check`, `make conformance-hermetic`, and the full `make conformance`; compare per-directory counts against T002 (SC-008).

---

## Dependencies

```
Phase 1 (Setup)
   ↓
Phase 2 (Foundational) ── the seam, the budget, the audit member; blocks everything
   ↓
Phase 3 (US1) ── the feature. US2 and US3 are properties OF a model-driven run
   ↓
Phase 4 (US2)   Phase 5 (US3)   ── independent of each other once US1 lands
   ↓
Phase 6 (Polish)
```

**Story independence, honestly.** All three are P1 and none ships alone. US2 and US3 are
independently *testable* but not independently *deliverable* — both are properties of a run that
consults a model, which is US1. **US1 alone is the dangerous state**: a model choosing, with
nothing yet asserting the model is the bound one or that a killed run resumes correctly.

---

## Parallel opportunities

- **T003** alongside T001–T002.
- **Within Phase 2**: T004/T005 (audit) and T006–T009 (the seam) are independent.
- **Within US1**: T018, T019, T021, T022a, T022b and T023 once T017 lands. T016a and T016b are independent of each other.
- **Within US2**: T026, T027, T028 are three assertions in one module.
- **Phase 6**: T034, T035 and T038 are independent of the rest.

---

## Implementation strategy

**MVP is Phase 1 + 2 + US1** — a model choosing, governed. That is the thing that has never
happened.

**Do not stop there.** Without US2 nothing asserts the model is the one the matrix bound, and an
ungoverned model choice is an ungoverned tool choice one level up. Without US3 the platform's
durability guarantees remain asserted only against a deterministic sequence.

**T004 is the first task with a cost outside this feature.** It touches sealed core. T040 closes
that obligation, and the two should be planned as a pair rather than discovered as a surprise at
merge.

## Notes

- **Eval gates are N/A**: this consumes the qualified matrix rather than promoting anything.
- **No new ADR.** ADR-0022, ADR-0039, ADR-0017, ADR-0019 and ADR-0032 already decided this.
- **`build_governed_agent` is untouched.** The adapter's governance was always correct; it has
  simply never been given a real decision to intercept.
