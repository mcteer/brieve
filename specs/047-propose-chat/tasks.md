# Tasks: Propose chat (047)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/conformance-propose-chat.md](contracts/conformance-propose-chat.md)

**Tests**: every story includes hermetic rows that can lose; enclave E1–E3 are named-runner.

## Phase 1 — Setup

- [x] T001 Create `tests/conformance/propose/` package and wire into Makefile conformance if needed
- [x] T002 Add ROADMAP row numbering note pointing at 047 (docs only)

## Phase 2 — Foundational

- [x] T003 [P] Define phase enum + progress helpers (`research`…`propose`) with fail-closed transitions
- [x] T004 [P] Normalize repository URL → ownership/clone identifier; unit rows for good/bad URLs
- [x] T005 Dev owned-repositories allowlist (demo repo) readable by propose intake
- [x] T006 Extend `NomadDispatcher` for `authoring-tier` + `subject_path` meta (R3)
- [x] T007 Production caller: propose path → `prepare_authoring_run` → dispatch (R2)

## Phase 3 — User Story 1 (Propose → PR) — P1

- [x] T008 [US1] API propose intake (repository + task) building `AuthoringRequest`
- [x] T009 [US1] MCP parity operation for propose intake
- [x] T010 [US1] Portal `/propose` surface: composer without agent picker; posts to propose API
- [x] T011 [US1] Success outcome carries `pr_url` into conversation/run result
- [x] T012 [US1] Hermetic P1/P2/P7 + wiring tests; Ask still separate in nav

## Phase 4 — User Story 2 (Live phases) — P1

- [x] T013 [US2] Persist/expose `ProposeProgress` on run view for SSE consumers
- [x] T014 [US2] Entrypoint advances phases with user-visible updates (ordered
  `advance`/`fail` checkpoints: Research → Plan → Write → Judge → Propose)
- [x] T015 [US2] Portal phase strip + SSE updates (`portal-propose.js` / templates)
- [x] T016 [US2] Hermetic P3/P4; walkthrough note for E3 (named-runner live SSE)

## Phase 5 — User Story 3 (Fail closed) — P1

- [x] T017 [US3] Ownership refusal before acquisition success path
- [x] T018 [US3] Judge deny helper (P5) — wired into analyzer before compose
- [x] T019 [US3] Publish failure → Propose phase failed; no success PR URL
- [x] T020 [US3] Hermetic P5/P6 helpers; secret non-leakage on reasons

## Phase 6 — User Story 4 (Real plan) — P2

- [x] T021 [US4] Real `terraform_plan` handler (refuses when binary missing; no always-green fixture)
- [x] T022 [US4] `compose_plan_evidence` helper (+ reject fixture evidence)
- [x] T023 [US4] Authoring-tier / alloc has Terraform CLI (pinned in
  `authoring-runtime` image; analyzer verifies at start)
- [x] T024 [US4] Hermetic plan-fail blocks PR end-to-end (`HARNESS_TERRAFORM_PLAN_FAIL` /
  missing binary / stub exit 1); enclave E2 remains named-runner
- [x] T025 [US4] Successful PR includes bounded plan evidence (handoff serialises
  `evidence`; publish puts it on the PR body and result payload)

## Phase 7 — Gates & polish

- [x] T026 [GATE] Hermetic propose rows + operation snapshot / parity green under `make check`
- [ ] T027 [GATE] E1–E3 recorded by named runner before merge when lane cannot cover
- [x] T028 [P] Ask remains separate nav (P8 surface isolation)
- [ ] T029 Security review request (dispatch/meta seams) — request on implementation PR
- [x] T030 Changelog / glossary “Propose” term

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
