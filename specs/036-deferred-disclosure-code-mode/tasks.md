# Tasks: Deferred disclosure and code mode

**Input**: Design documents from `/specs/036-deferred-disclosure-code-mode/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature is a governance-parity claim, so its rows *are* the deliverable —
test tasks are not optional here. Every contract row (D1–D8, C1–C10, U1–U3) has a task, and
several are the acceptance criteria of their story rather than a follow-on.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T014 (denied call fails inside the program), T016 (invented name refuses), T031 (guard survives) |
| **Conformance** | Phases 3–5 — both contracts, `tests/conformance/adapter/` |
| **Correlation / evidence** | T023 (discovery in trail), T027 (program recoverable), T012 (N+1 decisions on one correlation ID) |
| **No-secret-leak** | T020 (seeded credential in sandbox state → `CredentialInCheckpointError`) |

The **break fixture** (T017, C5) is the load-bearing gate: it proves the parity rows can
fail. It is tagged `[GATE:conformance]` and placed in US2, not Polish.

## Path Conventions

Single project: `src/`, `tests/` at repository root. New: `src/core/sandbox/`,
`src/adapters/pydantic_ai/{disclosure,sandbox_runtime}.py`, `docs/adr/0061-*.md`.

---

## Phase 1: Setup

- [X] T001 Add `pydantic-monty==0.0.19` under a new optional extra `sandbox` in `pyproject.toml`; add nothing to the base install. Add a `[dependency-groups]`/extra comment naming the PyPI trap (plain `monty` is the pymatgen package). Run `uv sync --extra sandbox` and confirm `import pydantic_monty` resolves.
- [X] T002 [P] Unit gate U3 in `tests/unit/test_sandbox_dependency_identity.py`: assert the dependency line reads `pydantic-monty==` (exact pin) and that the bare token `monty` appears in no dependency group. Positive control: the assertion must fail if fed a `monty>=` line. This is FR-014b (adopt the *identified* project) as an executable gate. (FR-014b, R7)
- [X] T003 [P] Extend `tests/harness/adapter_fixtures.py` with a `scripted_search_model(...)` (emits a `search_tools` call then a discovered-tool call) and a `scripted_program_model(program_text)` helper, mirroring `scripted_tool_model`. No sandbox dependency in the disclosure helper.

---

## Phase 2: Foundational (blocking all stories)

**These are the fixed points and the seam every story composes around. Nothing in Phases
3–5 is reachable until the audit vocabulary and the sandbox seam exist.**

- [X] T004 [GATE:conformance] Add `DISCOVERY_OBSERVED` and `PROGRAM_SUBMITTED` to `AuditEventType` in `src/core/audit/schema.py`, additive, each with a docstring recording the Principle V review (follow `TOOL_CHOSEN`'s exact precedent) and the verbatim-content argument for `PROGRAM_SUBMITTED` (follow `TURN_RECORDED`). This is a sealed-core change and pairs with T033 (the review) and T005 (the ADR) — none merges without the others.
- [X] T005 Write `docs/adr/0061-discovery-is-recorded-never-refused.md`: discovery is an observation, never a decision; amends ADR-0040 (whose Decision says "no registry, hook, or audit change"). Status-line pointer on `docs/adr/0033`-style precedent from ADR-0060; ADR-0040's Decision section untouched. Update `docs/adr/README.md` and ADR-0040's status line. (FR-006b, Principle X)
- [X] T006 Define the platform-owned seam in `src/core/sandbox/seam.py`: a `SandboxRuntime` Protocol (start/step/resume/dump/load over an opaque snapshot) and `run_program(governed_run, program, runtime) -> ProgramResult`, the loop that routes **every** call request to `invoke_tool` and resumes with the governed result or a refusal-as-exception. **Safe under re-entrant `invoke_tool`** (R11): the seam runs inside the outer `run_program` `invoke_tool` call, so a policy deny becomes an in-sandbox failure the program sees, while `ExecutionBoundExceeded` and `LeaseSupersededError` are let to **propagate** and terminate the run — converting either to a program-visible failure would let a program outlive its budget or its lease. Resolve the nested-bracket question R11 names before wiring T020. No framework import, no `pydantic_monty` import. (FR-014c, FR-010a)
- [X] T007 [P] Define suspended-state handling in `src/core/sandbox/state.py`: the seam's own scannable ledger of what entered the sandbox (inputs, resume values), separate from the runtime's opaque snapshot bytes, so the credential discipline never parses a `0.0.x` format. (R9, FR-011)
- [X] T008 [GATE:fail-closed] Unit gate U2 in `tests/unit/test_sandbox_seam_is_core.py`: assert `src/core/sandbox/` imports no `pydantic_ai` and no `pydantic_monty`, and that `run_program`'s only route to execution is `invoke_tool` (no direct handler call). Positive control included.
- [X] T009 Implement the runtime binding in `src/adapters/pydantic_ai/sandbox_runtime.py` — the **only** `pydantic_monty` import in the tree: `Monty()` pool, `checkout()` session, `feed_start`/resume with `{"return_value": ...}` / exception envelopes, `dump`/`load_snapshot`. Implements the `SandboxRuntime` Protocol. (R5)
- [X] T010 [P] Unit gate U1 in `tests/unit/test_sandbox_runtime_is_the_only_import.py`: exactly one module under `src/` imports `pydantic_monty`, and it is `adapters/pydantic_ai/sandbox_runtime.py`. Grep-shaped, with a positive control. (FR-014a, Principle I)

**Checkpoint**: audit vocabulary, ADR, seam, and runtime binding exist and are gated. US1
and US2 can now proceed independently.

---

## Phase 3: User Story 1 — Deferred disclosure with governance unchanged (P1) 🎯 MVP

**Goal**: a run pays for tools it uses; every governed outcome is identical to eager.
**Independent test**: quickstart Scenario A + B — parity rows green, discovery in the trail.

- [X] T011 [US1] Implement `src/adapters/pydantic_ai/disclosure.py`: an adapter-owned composition that marks a definition's tools deferred and lets the framework's search machinery wrap them, **outside** the terminal `GovernedToolset`, without manually constructing `ToolSearchToolset` (R2 — the double-wrap). Wrap the search function to emit `DISCOVERY_OBSERVED` (queries, matches, `undisclosed_remaining`). Detect and record the run's `disclosure_posture`.
- [X] T012 [US1] Add a `disclosure` option to `build_governed_agent` in `src/adapters/pydantic_ai/agent.py` that installs the T011 composition. Leave `_reject_unreachable_wrappers` and the caller-supplied-capability path **unchanged**. Record `disclosure_posture` on the run's `RUN_START` payload.
- [X] T013 [P] [US1] [GATE:conformance] Rows D1–D2 in `tests/conformance/adapter/test_disclosure_parity.py`: one operation, eager vs deferred-then-discovered, identical decision/reason/executed/result and field-identical records between `PRE_DECISION` and `POST_DECISION` (allow path and deny path). The field-identity of the records is also what discharges **FR-005** (deferral changes nothing recorded about a call). (FR-002, FR-005, SC-001 — the owed gate row)
- [X] T014 [P] [US1] [GATE:conformance] Row D3 in `tests/conformance/adapter/test_disclosure_schema.py`: per-tool, a deferred tool contributes name + one-line description and no parameter schema; registry/ceiling/policy inputs byte-identical between postures. (FR-001, SC-002)
- [ ] T015 [US1] Row D4 in `tests/conformance/adapter/test_disclosure_benefit.py`: pre-task schema material deferred ≤ 25% of eager for the shipped definitions, both measured by the same harness, values printed on failure. Calibrate the threshold against the real pack corpus; if unmet, fail and revise the number *in `contracts/conformance-disclosure.md` with the measurement*. (SC-002a, R10)
- [X] T016 [P] [US1] [GATE:correlation] Rows D5 in `tests/conformance/adapter/test_discovery_recorded.py`: a search writes `DISCOVERY_OBSERVED` (including an empty match); no `PRE_DECISION` for the search; event type distinct from every tool-call type so "looked for" ≠ "attempted". (FR-006/006a/006c)
- [X] T017 [P] [US1] Row D6 in `tests/conformance/adapter/test_search_is_structural.py`: (a) a search resolves without `invoke_tool` observing a call; (b) a genuine tool named `search_tools` in a non-disclosure agent routes to `invoke_tool` normally — the exemption is positional, not a name match. (R3)
- [X] T018 [P] [US1] [GATE:fail-closed] Row D7 in `tests/conformance/adapter/test_guard_survives.py`: `build_governed_agent(model, capabilities=[ToolSearch()])` still raises `unreachable_capability_wrapper`; the adapter's composition is reachable only through its named option. (FR-003 — R1's regression)
- [X] T019 [P] [US1] Row D8 in `tests/conformance/adapter/test_fallback_posture.py`: deferral requested where composition can't support it → `disclosure_posture: eager_fallback` on `RUN_START`, distinguishable from both other postures through the governed read path. (FR-004, SC-006)

**Checkpoint**: US1 is a shippable increment — disclosure works, governance is provably
unchanged, discovery is in the trail. This alone closes the owed gate row.

---

## Phase 4: User Story 2 — Code mode with per-call parity (P1)

**Goal**: the model writes a program; every call it makes is governed identically to a
structured call. **Independent test**: quickstart Scenario C + D + E.

- [X] T020 [US2] Register the `run_program` native tool in the adapter: its handler drives the T006 seam with the T009 runtime, submission passing the full pipeline (a definition lacking `run_program` in its ceiling has no code mode — FR-016 by construction). Emit `PROGRAM_SUBMITTED` (verbatim, `program_sha256`) when the submission is allowed — verbatim on `TURN_RECORDED`'s argued precedent (the record is the only durable copy of the cause), even as `run_program`'s own arguments are redacted in `PRE_DECISION` by the normal pipeline. Note that no-secret-leak (T021/T028) governs credentials the *platform* injects, not model-authored program text: a model writing a literal secret into its own program is `TURN_RECORDED`'s case, not a platform leak. (R8, FR-012)
- [ ] T021 [US2] [GATE:no-secret-leak] Wire suspended state through the adapter's `save_state`: the T007 ledger flows under the existing `_reject_credentials`; `MontySession.dump()` bytes go through the `DurabilityProvider`. (FR-011)
- [X] T022 [US2] [GATE:conformance] Rows C1 in `tests/conformance/adapter/test_code_mode_parity.py`: a program issuing N tool calls yields N+1 `PRE_DECISION`s on one correlation ID, at N∈{0,1,3}. (FR-007, SC-003)
- [X] T023 [US2] [GATE:conformance] Row C2 in the same file: a tool called once structurally and once from a program has field-identical records between `PRE_DECISION` and `POST_DECISION`; the code-mode trail additionally carries `PROGRAM_SUBMITTED`. (FR-007, US3)
- [X] T024 [US2] [GATE:fail-closed] Row C3 in `tests/conformance/adapter/test_code_mode_deny.py`: a policy-denied inner call is recorded, delivered to the sandbox as a failure (never a fabricated return), and the program cannot ride past it to the denied effect — but **keeps running** and may make further permitted calls, which is what distinguishes a deny from a bound (T027c). (FR-007)
- [X] T025 [US2] [GATE:fail-closed] Row C4 in `tests/conformance/adapter/test_code_mode_invented_name.py`: `open`, `eval`, `__import__`, and a nowhere-declared name each route to `invoke_tool`, refuse as unregistered, and are recorded as that refusal — the refusal comes from the registry lookup, not a blocklist. (FR-008, R5)
- [X] T026 [US2] [GATE:conformance] **The break fixture** — Row C5 in `tests/conformance/adapter/test_code_mode_break_fixture.py`: a test-local seam handler that returns without calling `invoke_tool` makes C1's assertion body **fail**. Asserts the parity rows can lose (the vacuous-mutation lesson, 030). (FR-009, SC-004)
- [ ] T027 [US2] Row C7 in `tests/conformance/adapter/test_code_mode_bounds.py`: (a) each inner call is checked and counted once by `invoke_tool`; (b) a program of N inner calls spends **N+1** of `max_steps` (the submission is the +1) and is stopped one inner call before an equivalent structured run — asserted with exact counts, **not** a "same total" claim; (c) a mid-program bound raises `ExecutionBoundExceeded` and terminates the run rather than becoming an in-sandbox failure (the C3-vs-C7 distinction). The seam owns no bound and none is settable from inside a program. (FR-010, FR-010a, R11)
- [ ] T028 [US2] [GATE:no-secret-leak] Row C6 in `tests/conformance/adapter/test_code_mode_checkpoint.py`: a credential-shaped value seeded as input and as a resume value makes the checkpoint write raise `CredentialInCheckpointError`, asserted against the ledger, not the runtime's serialization. (FR-011)
- [ ] T029 [P] [US2] Row C8 in `tests/conformance/adapter/test_code_mode_absent.py`: without the `sandbox` extra, `run_program` refuses with a stated reason code naming the missing runtime — never ImportError, never silence. Run in a path-filtered subprocess. (FR-013, SC-007)
- [ ] T029a [US2] [GATE:conformance] Row C10 in `tests/conformance/adapter/test_code_mode_resume.py`: interrupt a program mid-execution, resume on a new allocation/identity (014's dispatched-resume path), and assert (a) post-resume inner calls round-trip `invoke_tool` under the surviving grant with the same record shape as pre-kill calls (ADR-0026); (b) pre-kill inner calls are not re-executed — the snapshot resumes past them (re-observe, never re-execute); (c) the N+1 count and bracket resolution survive the boundary — the concrete exercise of R11's nested-bracket question. Depends on the bracket resolution T006 owns; if it cannot be green, code mode does not ship for interruptible runs (FR-013 applied to durability). (FR-011a, US2#4)

**Checkpoint**: code mode ships **only if every row above is honestly green**. If any
cannot be, the outcome is FR-013 — `run_program` refuses with a reason, and US2 lands as a
demonstrated, recorded absence rather than a partial capability.

---

## Phase 5: User Story 3 — The cause is recoverable (P1)

**Goal**: an auditor reconstructs a code-mode run's cause from its evidence.
**Independent test**: quickstart Scenario F.

- [ ] T030 [US3] Row C9 in `tests/conformance/adapter/test_code_mode_evidence.py`: after a code-mode run, the governed read operation returns the program text and the ordered inner calls, joined by `program_sha256` and the correlation ID — nothing outside the platform's records used. (FR-012, SC-005)
- [ ] T031 [P] [US3] Component test in `tests/component/test_code_mode_cause_vs_effect.py`: a code-mode run and a structured run doing the same work produce identically-described decisions; only the code-mode trail carries its cause. Confirms US3's "reduction in evidence" concern is answered, not introduced.

**Checkpoint**: the trail explains code-mode runs rather than merely recording their
effects.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T032 [P] Update `ROADMAP.md`: move "Deferred disclosure and code mode" from `Next` to `Shipped` with the ADR list and what it found; note ADR-0054 stays Proposed (delegation half out of scope, FR-015). Remove the `Next` entry — landing means removing it, not only adding a Shipped row (the 2026-08-05 maintenance rule).
- [ ] T033 [P] Update `docs/glossary.md`: add "disclosure posture", "discovery", "code mode", "the sandbox seam", each pointing at ADR-0040/0041/0061.
- [ ] T034 Run the full local gate: `make check`, `make conformance-hermetic`, and the two new conformance files with the `sandbox` extra. Confirm `OWED` is untouched (the parity row bound at merge, never entering the owed table).

---

## Phase 7: Sealed-core review (blocks merge, not a code task)

- [ ] T035 [GATE:conformance] **Principle V security-maintainer review** (Dan). Two sealed-core touches: the adapter composition, and the additive `AuditEventType` pair. Reviewed against `TOOL_CHOSEN`'s precedent. Recorded on the implementation PR. The feature does not merge without it, and this task is checked only when that review is on the PR.

---

## Dependencies

```text
Setup (T001–T003)
   └─> Foundational (T004–T010)   [audit vocab + ADR + seam + runtime binding]
          ├─> US1 (T011–T019)     ── disclosure; independently shippable, closes owed row
          └─> US2 (T020–T029a)    ── code mode; depends on the seam (T006) + runtime (T009)
                 │                    T029a (resume parity) depends on T006's bracket resolution (R11)
                 └─> US3 (T030–T031)  ── evidence; depends on PROGRAM_SUBMITTED (T020)
Polish (T032–T034) after the stories it documents
Review (T035) gates merge
```

- **US1 does not depend on US2.** Disclosure ships without the sandbox extra and closes the
  owed gate row on its own — the MVP.
- **US2 depends on Foundational only**, not US1. The seam and runtime binding are its
  prerequisites; disclosure is orthogonal.
- **T004/T005/T035 are one obligation in three files** — the enum member, the ADR that
  legitimizes it, and the review that approves it. None merges alone.

## Parallel Opportunities

- Setup: T002, T003 in parallel after T001.
- Foundational: T007 ∥ (T006 then T009 then T010); T008 after T006; T004/T005 independent.
- US1: T013–T019 are all `[P]` once T011–T012 land — seven rows, seven files.
- US2: T029 `[P]`; the rest share the seam wiring and serialize on T020.

## Implementation Strategy

**MVP is US1 alone.** It closes the owed parity gate row, ships without a sandbox
dependency, and is provably governance-neutral. If the code-mode rows (US2) cannot all be
made honestly green, US1 still ships and US2 lands as FR-013's stated absence — which
ADR-0041 explicitly calls an acceptable outcome. Do **not** ship US2 partially green:
per-call parity is unconditional, and a half-verified code mode is the exact stub ADR-0047
forbids.

**Order**: Setup → Foundational → US1 (ship-ready checkpoint) → US2 → US3 → Polish, with
T035 (review) gating the merge throughout. The break fixture (T026) is written *before*
the code-mode rows are trusted, because a suite that cannot lose has proven nothing.
