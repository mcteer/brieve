# Tasks: Propose chat (047)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/conformance-propose-chat.md](contracts/conformance-propose-chat.md)

**Tests**: every story includes hermetic rows that can lose; enclave E1–E3 are named-runner.

## Phase 1 — Setup

- [ ] T001 Create `tests/conformance/propose/` package and wire into Makefile conformance if needed
- [ ] T002 Add ROADMAP row numbering note pointing at 047 (docs only)

## Phase 2 — Foundational

- [ ] T003 [P] Define phase enum + progress helpers (`research`…`propose`) with fail-closed transitions
- [ ] T004 [P] Normalize repository URL → ownership/clone identifier; unit rows for good/bad URLs
- [ ] T005 Dev owned-repositories allowlist (demo repo) readable by propose intake
- [ ] T006 Extend `NomadDispatcher` for `authoring-tier` + `subject_path` meta (R3)
- [ ] T007 Production caller: propose path → `prepare_authoring_run` → dispatch (R2)

## Phase 3 — User Story 1 (Propose → PR) — P1

- [ ] T008 [US1] API propose intake (repository + task) building `AuthoringRequest`
- [ ] T009 [US1] MCP parity operation for propose intake
- [ ] T010 [US1] Portal `/propose` surface: composer without agent picker; posts to propose API
- [ ] T011 [US1] Success outcome carries `pr_url` into conversation/run result
- [ ] T012 [US1] Hermetic P1/P2/P7 + wiring tests; Ask still separate in nav

## Phase 4 — User Story 2 (Live phases) — P1

- [ ] T013 [US2] Persist/expose `ProposeProgress` on run view for SSE consumers
- [ ] T014 [US2] Entrypoint advances phases with user-visible updates
- [ ] T015 [US2] Portal phase strip + SSE updates (`portal.js` / templates)
- [ ] T016 [US2] Hermetic P3/P4; walkthrough note for E3

## Phase 5 — User Story 3 (Fail closed) — P1

- [ ] T017 [US3] Ownership refusal before acquisition success path
- [ ] T018 [US3] Judge deny blocks publish (P5)
- [ ] T019 [US3] Publish failure → Propose phase failed; no success PR URL
- [ ] T020 [US3] Hermetic P5/P6/P9; secret non-leakage on reasons

## Phase 6 — User Story 4 (Real plan) — P2

- [ ] T021 [US4] Real `terraform_plan` handler for authoring/propose path (no always-green fixture gate)
- [ ] T022 [US4] `compose_plan_evidence` + checkpoint evidence round-trip to proposer
- [ ] T023 [US4] Authoring-tier / alloc has Terraform CLI (or documented Plan execution host)
- [ ] T024 [US4] Hermetic plan-fail blocks PR (P6); enclave E2 named-runner
- [ ] T025 [US4] Successful PR includes bounded plan evidence (FR-011)

## Phase 7 — Gates & polish

- [ ] T026 [GATE] Conformance contract P1–P10 green in CI where hermetic
- [ ] T027 [GATE] E1–E3 recorded by named runner before merge when lane cannot cover
- [ ] T028 [P] Ask regression P8
- [ ] T029 Security review request if sealed schemas/dispatch seams warrant (plan Constitution Check)
- [ ] T030 Changelog / glossary “Propose” term if user-visible

## Dependency graph

```text
T001–T002 → T003–T007 → US1 (T008–T012) → US2 (T013–T016) → US3 (T017–T020)
                ↘ US4 (T021–T025) can start after T007 + T014 checkpoint seam
→ T026–T030
```

## Parallel examples

- T003 ∥ T004 ∥ T005 after T001
- T008 ∥ T009 after T007
- T021 can parallel US3 once plan tool registration exists
