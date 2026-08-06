# Tasks: Code mode becomes reachable

**Input**: Design documents from `/specs/039-code-mode-reachability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: The feature's claim *is* reachability, so its rows are the deliverable. Every contract
row — nineteen of them, K1 through K14 — has a task, and **every task that asserts has a task that builds**. That pairing
is the discipline 036/037/038's analyze passes each paid for: the recurring defect was a row
asserting over something no task built.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T012 (an absent runtime refuses with a stated reason), T020b (a looping program writes one intent per effect), T023 (an exhausted bound ends the RUN) |
| **Conformance** | Phases 3–6 — `tests/conformance/adapter/`, beside 036's parity rows |
| **Correlation / evidence** | T009 (the program is the recorded cause, written before it runs) |
| **Eval** | **None, and that is deliberate.** No model is promoted and no cell changes; the runtime is pinned exact and its identity is already asserted by `test_sandbox_dependency_identity.py` |
| **No-secret-leak** | T010 (`PROGRAM_SUBMITTED` is verbatim by argument — the one member where that is correct, and the row says why) |

**Three tasks exist to prove the others can lose.** **T013** re-runs the absent-runtime row *with*
the runtime installed and requires it to **fail** — a row that passes either way asserts nothing
about absence. **T024** rewrites the budget program to catch its own failure and continue, and
requires the run to end anyway; if a program can catch the bound and carry on, the exhausted-bound
path has been converted into a program-visible failure, which the seam names as the most plausible
way code mode ships a hole. **T031** checks the inverted guard **exists**, not that it passes —
a deleted guard also produces a green suite.

## The three layers, and why no phase closes the feature alone

Measurement found the gap is three deep (research R1–R3). Each layer alone yields something that
looks like progress and is not:

| Layer | Alone it gives you | Lands in |
| --- | --- | --- |
| **Registration** | an honest refusal and no code mode | Phase 2 |
| **Runtime installed where work runs** | a runtime nothing can invoke | Phase 2 |
| **An answer wide enough to carry a program** | a program the model cannot express | Phase 5 |

**FR-003 names two environments in its own text** so "we registered the tool" cannot be argued as
done. The third layer is the one the spec could not name — it deliberately named no module, which
is why measurement was free to find that the model's only channel is a bare tool name.

## Path Conventions

Single project: `src/`, `tests/` at repository root. Rows land in
`tests/conformance/adapter/test_code_mode_reachable.py` **beside 036's parity rows** — splitting
them would let one be read without the other, which is the mistake that produced this feature.

---

## Phase 1: Setup

- [ ] T001 Create `tests/conformance/adapter/test_code_mode_reachable.py` with a module docstring stating what it owns — *the seam is reachable* — and what 036's `test_code_mode_parity.py` owns beside it — *the seam is governed*. Neither claim implies the other, and for a month the second passed while the first was false.
- [ ] T002 [P] Add a `sandbox`-marked fixture in `tests/conformance/adapter/conftest.py` that skips-with-failure rather than skipping silently when the runtime is absent, so Scenario B's rows can distinguish "runtime not installed" from "row not run".

---

## Phase 2: Foundational — layers one and two (blocking all stories)

**The tool becomes resolvable and the allocation carries the runtime. Nothing in Phases 3–6 can
be reached until both exist, and either alone produces something that looks finished.**

- [ ] T003 Implement the program-tool handler in `src/surfaces/handlers.py`, importing the concrete runtime from `src/adapters/pydantic_ai/sandbox_runtime.py`: it constructs the runtime, calls `run_submitted_program`, and returns the program's value. **The import belongs here and nowhere lower** — `core` must not import an adapter (Principle I) and `SandboxRuntime` is a Protocol, so the binding is injected from a surface. The obvious wrong move is reaching for it from `core/sandbox/`. **Constructed per run rather than as a module-level callable** — it needs the run and a runtime, exactly as 038's authoring handlers do, and a singleton would share a sandbox ledger between runs.
- [ ] T004 Register the program tool in `src/surfaces/toolset.py` under `PROGRAM_TOOL_NAME`, binding the T003 handler through `PLATFORM_HANDLERS`. **The registry is the opt-in switch and the ceiling is the decision** — registration makes the name resolvable, and `authority.py` decides whether this run may reach it (036's own design; this supplies the caller it never had).
- [ ] T005 Add `--extra sandbox` to the run command in `infra/jobs/agent-run.nomad.hcl`. **Without this the allocation refuses honestly and the feature is half-closed** — which is FR-003's own wording, present so this cannot be argued as out of scope.
- [ ] T006 Amend the `sandbox` extra's comment in `pyproject.toml`: "optional" now means **absent from the base install**, not absent from the thing that runs. The current comment says the extra exists *"so the base install never grows a Rust interpreter for a capability most runs do not use"* — after T005 every dispatched allocation carries one, and the comment must describe the posture the platform has rather than the one it had.

---

## Phase 3: US1 — A definition can enter code mode at all (P1)

**Goal**: a definition whose ceiling names the tool submits a program, and it runs.

**Independent test**: give a definition the capability, submit a program **through the registry**,
and confirm it executed.

- [ ] T007 [US1] Row **K1** in `tests/conformance/adapter/test_code_mode_reachable.py`: resolve the tool **from the registry** and invoke it through `invoke_tool`; assert the program ran and returned its value. **Not by calling the handler** — a row that called the implementation directly would assert what 036 already asserts, and would have passed every day of the month this capability was unreachable.
- [ ] T008 [US1] Row **K2** in `tests/conformance/adapter/test_code_mode_reachable.py`: a definition whose ceiling omits the tool is refused `authority_insufficient`. **The registry knows the name and the ceiling still decides** — that is the opt-in property, and this is what makes it true rather than claimed.
- [ ] T009 [US1] Row **K3** in `tests/conformance/adapter/test_code_mode_reachable.py`: `PROGRAM_SUBMITTED` carries the program and its digest, each inner call appears as its own governed step, and **the program is recorded before it runs** — a program that fails partway still caused whatever it caused.
- [ ] T010 [US1] [GATE:no-secret-leak] Extend **K3** in `tests/conformance/adapter/test_code_mode_reachable.py` to assert the program is recorded **verbatim**, with the row stating why this member is the exception: `TURN_RECORDED`'s precedent, *a model's own words recorded as said*. **Contrast 038's `ARTIFACT_AUTHORED`, which carries digests only** because its subject is a derivative of somebody else's private repository. Opposite rules, and the reason is the subject rather than the format.
- [ ] T011 [US1] Row **K11** in `tests/conformance/authoring/test_producing.py`: rewrite the row that asserts the program tool is registered **nowhere** so it asserts the tool is **reachable**. Its own failure message asks for exactly this: *"run_program is now registered; W3's caveat is stale and this row should be promoted to drive the production path rather than the seam."* **Inverted, never deleted** (FR-013).

**Checkpoint**: a program can be submitted and run through the registry. The model still cannot send one.

---

## Phase 4: US2 — Where the capability is absent, the refusal is honest (P1)

**Goal**: an environment that cannot run programs says so.

**Independent test**: remove the runtime, submit a program, confirm the refusal names what is missing.

- [ ] T012 [US2] [GATE:fail-closed] Row **K4** in `tests/conformance/adapter/test_code_mode_reachable.py`: with the runtime absent, a submission is refused with a reason naming the absent capability — **not an import failure surfacing three frames down, and not a partial success**. `SandboxUnavailableError` exists for precisely this and its docstring says so.
- [ ] T013 [US2] **Prove K4 can fail**: a companion assertion in `tests/conformance/adapter/test_code_mode_reachable.py` that the same row **fails** when the runtime IS installed. A row that passes either way asserts nothing about absence, and absence is the entire subject of this story.
- [ ] T014 [US2] Row **K5** in `tests/conformance/adapter/test_code_mode_reachable.py`: an unavailable-runtime refusal, a policy denial, and a program that failed on its own terms are **distinguishable in the record**. Three situations calling for three different responses — an operator told the wrong one fixes the wrong thing.

**Checkpoint**: the optional-by-default posture is honest rather than merely documented.

---

## Phase 5: US3 — Code mode does not become a second way to act (P1)

**Goal**: making the capability reachable adds no path around the pipeline — and the model gains
a channel wide enough to send a program.

**Independent test**: drive a program through the reachable path; every call it makes carries the
records a direct call would, including calls the program invents.

- [ ] T015 [US3] Define the structured choice type in `src/core/choice/bounded.py`: a tool **name** and its **arguments**. **The platform still invokes** — this widens what the model may *answer*, not what it may *do*, which is what keeps 031's four properties intact (research R7).
- [ ] T016 [US3] Pass it as `output_type` in `src/adapters/model_chooser.py` and update `_SYSTEM` so the model returns a name **and arguments** rather than a bare word. Keep `NONE` working — a run with nothing to do must still be able to say so.
- [ ] T016a [US3] Correct the stale `_PROBE_ARGUMENTS` docstring in `src/surfaces/dispatch/entrypoint.py`. It says *"a handler exception does not make `outcome.allowed` false"*; measured, `src/core/hooks/engine.py:374` returns `decision="deny", reason_code="tool_error"` when `execution_error_code is not None`, so it does. **The comment is in the code T017 modifies**, which is the worst place for a stale one — it is read by whoever is changing that path, at the moment they are deciding what is safe. It nearly produced a finding about model-supplied arguments causing silent success, a failure mode that no longer exists.
- [ ] T017 [US3] Carry the model's arguments through to the governed invoke in `src/core/choice/bounded.py`, in place of `_PROBE_ARGUMENTS` — whose own docstring in `src/surfaces/dispatch/entrypoint.py` calls it *"a fixture affordance, and it always was"*. **This is the actual gap**: the platform, not the model, has supplied every tool's arguments.
- [ ] T018 [US3] Extend `resolve_step_tool`'s bounded retry in `src/core/choice/bounded.py` to cover a **malformed object**, not only an unpermitted **name**. A model that could produce a valid word can produce an invalid object, and that is a failure mode the existing retry was not written for.
- [ ] T019 [US3] Row **K6** in `tests/conformance/adapter/test_code_mode_reachable.py`: drive a program through the registered path calling a permitted tool, a denied tool, and a name that does not exist. Assert the **pipeline** is identical to a direct call — same entry, same hooks, same bracket — and **state that argument provenance differs**: a direct call carries arguments the platform chose, an inner call carries arguments the program wrote. Without that clause the row reads as a stronger claim than it makes.
- [ ] T020 [US3] Row **K6a** in `tests/conformance/adapter/test_code_mode_reachable.py`: widening the answer leaves all four of 031's properties intact — bounded retry validates before invoking, `already_chosen` governs a resumed step, `TOOL_CHOSEN` is recorded per step, and the **platform** performs the invoke. Assert also that `GovernedToolset` **still has no production caller**, recorded as an open gap rather than closed here.
- [ ] T020a [US3] Row **K6b** in `tests/conformance/adapter/test_code_mode_reachable.py`: a malformed structured answer is **retried, not executed**, and a run whose ceiling omits the program tool behaves identically before and after the widening. **Both sides of the bound** — one row checking the mechanism is not the same as one checking the consequence.

- [ ] T020b [US4] [GATE:fail-closed] Add a `call_ordinal` to `GovernedRun` in `src/core/run.py` (default `0`), have `src/core/sandbox/seam.py` **set it on entry and clear it on exit** so outside a program it is always `0`, and fold it into the key in `src/core/hooks/engine.py` **only when non-zero**. **Scoped to the submission, not the run** — nothing resets a run-level counter between steps (`run.step_index` is reset by the entrypoint's loop; an ordinal would not be), so a run whose step 0 ran a three-call program would carry `3` into step 1 and the next **direct** call would key `run:1:tool:3`. The byte-identical guarantee would hold until a program ran and then quietly stop — failing only in the case this feature creates. **Measured (research R8): the seam never advances `step_index`, so a program calling one non-repeatable tool twice keys both calls identically — and intents insert `ON CONFLICT DO NOTHING`, so the second is a silent no-op while the effect happens anyway.**
- [ ] T020c [US4] Row **K13** in `tests/conformance/adapter/test_code_mode_reachable.py`: a program calling one non-repeatable tool twice writes **two** intents, and a resume re-observes **twice**. A loop is the whole point of code mode, so this fires on the first realistic program.
- [ ] T020d [US4] Row **K13a** in `tests/conformance/adapter/test_code_mode_reachable.py`: a call made **outside** a program produces exactly the key it produces today — asserted **at a step that follows a program which made several calls**, because a property that fails only after the feature is used is not caught by testing the feature's absence. **Byte-identical is not a nicety** — changing every key would invalidate 014's durability rows and break resume for any run in flight.
- [ ] T020e [US4] Row **K13b** in `tests/conformance/adapter/test_code_mode_reachable.py`: interrupt a program partway, resume, and assert the re-issued ordinals match the intents from the first attempt. **This is what submission-scoping buys beyond the key** — a run-scoped counter would offset every ordinal on resume, leaving the intents unmatchable and re-observation resolving nothing.
- [ ] T021 [US4] Row **K8** in `tests/conformance/adapter/test_code_mode_reachable.py`: run a program making N calls and **count** the steps consumed, asserting N+1. **Measured rather than asserted** (SC-005's own wording) — an assertion that the arithmetic holds passes against an implementation where the bound never fires.
- [ ] T022 [US4] Build a bounded fixture run in `tests/conformance/adapter/test_code_mode_reachable.py` whose `ExecutionBounds` are small enough that a short program exhausts them. Nothing today runs a program against a real budget, so the fixture is the thing that has never existed.
- [ ] T023 [US4] [GATE:fail-closed] Row **K9** in `tests/conformance/adapter/test_code_mode_reachable.py`: a program that exhausts the budget **ends the run** — it does not merely receive a refusal. **A bound a program can route around is not a bound.**
- [ ] T024 [US4] **Prove K9 is a bound**: in `tests/conformance/adapter/test_code_mode_reachable.py`, rewrite the program so it catches the failure its call raises and continues; assert the run **still ends**. If a program can catch it and carry on, the exhausted-bound path has been converted into a program-visible failure — which the seam's docstring names as the most plausible way code mode ships a hole.
- [ ] T025 [US4] Row **K10** in `tests/conformance/adapter/test_code_mode_reachable.py`: three distinct records — a program that finished, a program whose calls were all denied and which completed having done nothing, and a program stopped by the bound. **The middle one is not a platform failure** and must not be recorded as one.

**Checkpoint**: the cost of code mode is measurable before anyone is granted it.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T026 Author **one** demonstration definition in `infra/environments/dev/variables.tf` whose ceiling names the program tool, with `tier` and `packs` sufficient for a program to call something. **A fixture, not a policy**: registration forces that a ceiling *can* name the tool and never *which ceilings do*, and 036 deferred that as configuration design (FR-012).
- [ ] T027 Row **K12** in `tests/conformance/adapter/test_code_mode_reachable.py`: the demonstration definition is the **only** one whose ceiling names the program tool, and it lives in the dev estate. The line between "one definition exists so the capability can be proven" and "code mode is part of the offering" is a sentence in a variables file, which is why it gets a row.
- [ ] T027a Widen the recording format in `src/adapters/model_chooser.py` so `parse_recording` accepts a tool **and its arguments**, and `RecordedChooser` returns a structured choice. **Measured, this is on the dispatched path and not in a harness**: `build_chooser` returns `RecordedChooser(parse_recording(recording))` for the fixture provider, and every dispatched conformance row goes through it — so widening the model's answer changes what a recording must contain whether or not anyone planned it.
- [ ] T027b Row **K14** in `tests/conformance/adapter/test_code_mode_reachable.py`: a fixture recording carries a structured choice and `RecordedChooser` returns it. **This decides what K7 proves** — if a recording carries only a bare name, the enclave row shows the allocation carries the runtime and not that a model can reach it.
- [ ] T028 Row **K7** in `tests/conformance/adapter/test_code_mode_reachable.py`, **enclave-marked**: dispatch a run whose definition carries the tool, submit a program, and assert it ran **in the allocation**. **This is the row the whole feature exists for** — every other row could pass while the capability stayed unreachable in production, which is precisely the state 036 left, with green parity rows, for a month.
- [ ] T029 Run quickstart **Scenario E** from `specs/039-code-mode-reachability/quickstart.md` against the enclave: `make dev-up`, dispatch, and read the trail. Confirm the allocation's command carries `--extra sandbox` — without it the run refuses honestly, which is correct behaviour and is **not** this feature being finished.
- [ ] T030 [P] Update `ROADMAP.md`: 036's row gains a note that its parity gate was satisfied while the capability was unreachable, and that 039 closed it. The shipped table records what a feature *did*; leaving it silent here would preserve the impression that 036 delivered a usable capability.
- [ ] T031 Verify the inverted guard **exists** rather than that the suite is green: grep `tests/conformance/authoring/test_producing.py` for the reachability assertion T011 wrote. **A deleted guard also produces a green suite**, and the property being watched is that code mode's reachability is a deliberate state rather than an accident.
- [ ] T032 Run `make check` **and** the hermetic conformance lane with `--extra sandbox`. The local gate does not collect `tests/conformance/`, so a green `make check` says nothing about any row in this feature.

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: registration + the runtime where work runs)
          ├─> Phase 3 (US1 — reachable through the registry)
          │      └─> Phase 4 (US2 — the honest refusal)
          ├─> Phase 5 (US3 — the model channel, and still governed)
          └─> Phase 6 (US4 — the budget)
                 └─> Phase 7 (Polish, incl. the enclave proof)
```

**Phases 4, 5 and 6 are independent of each other** once Phase 3 lands. Phase 5 is the largest and
the only one that changes behaviour outside code mode, so it is the one to start early if work is
parallelised.

## Parallel opportunities

- **Phase 1**: T001, T002 together.
- **Phase 2**: T003/T004 (registration) alongside T005/T006 (the install) — different trees, and
  the two layers are independent by construction.
- **Phase 3**: T007, T008, T009 together once T003/T004 land.
- **Phases 4, 5, 6** entire, in parallel.
- **Phase 5**: T015–T017 are one file and sequential; T018–T020 parallel after them.
- **Phase 7**: T026/T030 alongside the rest.

## Implementation strategy

**MVP is Phases 1–3**: a definition can submit a program and it runs, through the registry, with
the trail carrying the program as the cause. That closes two of the three layers and is
independently valuable — but **it is not the feature**, because the model still cannot send a
program. Phase 5 is what makes FR-001 true rather than nearly-true.

**Phase 5 changes what every model-driven run's model is asked to produce**, which is a real blast
radius and a far smaller one than the first design's. The platform still invokes, so nothing about
a step's governance moves; what can newly go wrong is a malformed object, and T018's retry is what
absorbs it. T020/T020a assert the bound from both sides.

**Phase 6 carries a defect 036 shipped.** T020b is not part of making code mode reachable — it is
the thing reachability *reaches*. A program that loops over one non-repeatable tool writes one
intent for two effects, silently, and that defeats a durability gate the constitution names as in
force.

**Phase 7's T028 is the one that would have caught this feature's own subject.** Everything else
can be green while production is unreachable.

## Notes

- **Gate types omitted**: **Eval**, deliberately. No model is promoted, no matrix cell changes,
  and the runtime is pinned exact with its distribution identity already asserted by
  `tests/unit/test_sandbox_dependency_identity.py`.
- **One sealed-core-adjacent change, and no new ADR.** `PROGRAM_SUBMITTED` exists; ADR-0041's
  gate is satisfied and stays satisfied; **ADR-0054 stays Proposed** because its delegation half
  still has no substrate and this feature does not give it one. **But T020b touches the hook
  engine's idempotency key**, so the earlier "no sealed-core change" claim was wrong — it is a
  narrowing that leaves every existing key byte-identical, and it carries the Principle V review.
- **The obligations that travel**: the Principle V review for T020b's key change, and
  `pyproject.toml`'s comment (T006). After T005 it describes a
  posture the platform no longer has, and a comment that outlives its truth is how the next reader
  makes a wrong assumption about what "optional" bought.
- **What the previous three features kept finding**, so this list starts from it: a row that
  asserts over something no task builds. Every K row above names its builder, and T022 exists
  because K9 needs a bounded run that has never existed.
