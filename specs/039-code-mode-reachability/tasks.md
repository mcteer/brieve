# Tasks: Code mode becomes reachable

**Input**: Design documents from `/specs/039-code-mode-reachability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: The feature's claim *is* reachability, so its rows are the deliverable. Every contract
row — fourteen of them, K1 through K12 with K6a and K6b — has a task, and **every task that asserts has a task that builds**. That pairing
is the discipline 036/037/038's analyze passes each paid for: the recurring defect was a row
asserting over something no task built.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T012 (an absent runtime refuses with a stated reason), T023 (an exhausted bound ends the RUN) |
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
| **A channel the model can send a program through** | a program the model cannot express | Phase 5 |

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

- [ ] T003 Implement the program-tool handler in `src/surfaces/handlers.py`: it constructs the runtime, calls `run_submitted_program`, and returns the program's value. **Constructed per run rather than as a module-level callable** — it needs the run and a runtime, exactly as 038's authoring handlers do, and a singleton would share a sandbox ledger between runs.
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

- [ ] T015 [US3] **Layer three**: give the chooser's agent a toolset in `src/adapters/model_chooser.py`, so the model issues a real tool call with **arguments** rather than answering with a bare tool name. **A program is an argument, not a name** — `output_type=str` under a prompt demanding *"EXACTLY ONE tool name … no punctuation"* is a channel too narrow to carry one (research R3).
- [ ] T016 [US3] Build the toolset from the run's **effective scope** in `src/adapters/model_chooser.py` — `effective.tool_names`, the same set the authority hook decides against. **This is the blast-radius bound**: giving the agent a toolset changes how *every* model-driven run behaves, and building it from effective scope means a run whose ceiling omits the program tool sees nothing new.
- [ ] T017 [US3] Update the chooser's system prompt in `src/adapters/model_chooser.py` so it describes issuing a tool call rather than naming one, and keep the `NONE` terminal answer working — a run with nothing to do must still be able to say so.
- [ ] T018 [US3] Row **K6** in `tests/conformance/adapter/test_code_mode_reachable.py`: drive a program **through the registered path** that calls a permitted tool, a denied tool, and a name that does not exist. Assert all three produce the records the same calls issued directly would, and that the invented name refuses as *not registered* — **through the registry, not through any blocklist**, because a second decision-maker would eventually disagree with the first.
- [ ] T019 [US3] Row **K6a** in `tests/conformance/adapter/test_code_mode_reachable.py`: the model-facing toolset routes through `GovernedToolset` and the framework's own execution path is never taken. **This feature is that mapping's first production caller** — it has existed since 004 with its central claim unexercised outside a test. Assert also that the toolset equals the run's effective scope, which is T016's bound made checkable.
- [ ] T020 [US3] Row **K6b** in `tests/conformance/adapter/test_code_mode_reachable.py`: a run whose ceiling omits the program tool sees **no change** in what it can do after T015. The blast radius is asserted from the other side — T019 checks the toolset is bounded, this checks an unrelated run is unaffected.

**Checkpoint**: the model can express a program, and expressing one changes nothing about how
anything is governed.

---

## Phase 6: US4 — What a program costs is knowable before it is permitted (P1)

**Goal**: the budget arithmetic meets a real budget for the first time.

**Independent test**: run a program whose calls exceed the run's bounds; the outcome is recorded
and distinguishable.

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

**Phase 5 has the widest blast radius and the smallest word count.** Three tasks change how every
model-driven run behaves. T016's bound — the toolset is built from the run's effective scope — is
what keeps that change from being a widening, and T019/T020 assert it from both sides.

**Phase 7's T028 is the one that would have caught this feature's own subject.** Everything else
can be green while production is unreachable.

## Notes

- **Gate types omitted**: **Eval**, deliberately. No model is promoted, no matrix cell changes,
  and the runtime is pinned exact with its distribution identity already asserted by
  `tests/unit/test_sandbox_dependency_identity.py`.
- **No sealed-core change and no new ADR.** `PROGRAM_SUBMITTED` exists; ADR-0041's gate is
  satisfied and stays satisfied; **ADR-0054 stays Proposed** because its delegation half still has
  no substrate and this feature does not give it one.
- **The obligation that travels**: `pyproject.toml`'s comment (T006). After T005 it describes a
  posture the platform no longer has, and a comment that outlives its truth is how the next reader
  makes a wrong assumption about what "optional" bought.
- **What the previous three features kept finding**, so this list starts from it: a row that
  asserts over something no task builds. Every K row above names its builder, and T022 exists
  because K9 needs a bounded run that has never existed.
