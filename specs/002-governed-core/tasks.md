# Tasks: Governed Core MVP

**Input**: Design documents from `specs/002-governed-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec FR-013 and per-story Independent Tests require deterministic unit/component
tests — include test tasks for every user story. No live models or product APIs.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Hook pipeline, registry, audit-append | Denial on internal error; no allow-on-exception; un-auditable pre-path denies |
| **Conformance** | Governance-first ordering (ADR-0019) | Deterministic order test fails if governance is not first |
| **Correlation / evidence** | Run, hooks, audit, spans | One correlation ID joins trail; hash chain verifiable |
| **Eval** | N/A | No packs/models/policies |
| **No-secret-leak** | Audit, spans, denial messages, fixtures | Secret markers never appear; harness fixtures use obvious markers only |

## Path Conventions

- Core: `src/core/` (errors, correlation, run, registry, hooks, audit, telemetry, tools)
- Harness: `tests/harness/` (`from tests.harness import …`)
- Tests: `tests/unit/`, `tests/component/`
- Config: `pyproject.toml` (deps + pytest paths)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and test discovery for the governed-core suite

- [ ] T001 Add runtime dependencies `pydantic` and `opentelemetry-api` to `pyproject.toml` with PR-justification notes ready (Principle VI / research.md)
- [ ] T002 [P] Add dev dependency `opentelemetry-sdk` to `pyproject.toml` for in-memory span export in tests
- [ ] T003 Expand `[tool.pytest.ini_options].testpaths` in `pyproject.toml` to include `tests/component` alongside `tests/unit`
- [ ] T004 Run `uv sync` and update committed `uv.lock`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, audit chain, registry, hook engine skeleton, and `invoke_tool`
entry — all stories build on this

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 [P] Create `src/core/errors.py` with typed domain exceptions that can carry a correlation ID when known
- [ ] T006 [P] Create `src/core/correlation.py` with non-empty `CorrelationId` validation (blank/missing refused)
- [ ] T007 [P] Create `src/core/audit/schema.py` with Pydantic `AuditEntry` fields per `contracts/audit-sink.md` and `data-model.md` (`seq` starts at 0)
- [ ] T008 [P] Create `src/core/audit/chain.py` implementing SHA-256 over pinned canonical UTF-8 JSON (sorted keys, no insignificant whitespace, RFC 3339 UTC timestamps, `prev_hash` included); genesis `prev_hash` exactly 64 ASCII `0` characters
- [ ] T009 Create `src/core/audit/sink.py` with `AuditSink` protocol and `InMemoryAuditSink.append` / `list_by_correlation_id` (append-only; reject chain-breaking appends)
- [ ] T010 [P] Create `src/core/registry/memory.py` minimal in-process `ToolRegistry` (name → handler; resolve failure distinct)
- [ ] T011 [P] Create `src/core/hooks/types.py` with `HookDecision`, pre/post protocols, and `capability_kind` (`governance` \| `other`)
- [ ] T012 [P] Create `src/core/telemetry/spans.py` emitting one OTel span per hook decision with correlation ID and safe attributes only (no vendor SDK)
- [ ] T013 Create `src/core/run.py` `GovernedRun` start: require correlation ID, scope frozenset, audit sink, registry; refuse uncorrelated start (fail closed)
- [ ] T014 Create `src/core/hooks/governance.py` built-in governance/enforcement hook registration
- [ ] T015 Create `src/core/hooks/engine.py` pipeline skeleton per `contracts/hook-pipeline.md` (resolve → scope → pre governance-first → exec → post governance-first)
- [ ] T016 Create `src/core/tools/invoke.py` public `invoke_tool(run, tool_name, arguments) -> InvokeResult` as the only tool-body entry
- [ ] T017 [GATE:correlation] Unit test in `tests/unit/test_correlation_refuse.py` that blank/missing correlation ID refuses run start
- [ ] T018 [GATE:correlation] Unit test in `tests/unit/test_audit_chain.py` that genesis + chained entries verify; broken link / gap fails
- [ ] T019 [GATE:no-secret-leak] Create `tests/harness/secrets.py` with obvious fixture markers only (no plausible real secrets)

**Checkpoint**: Packages importable; audit chain verifies; run start refuses missing correlation ID

---

## Phase 3: User Story 1 - In-scope tool call allowed and fully joined (Priority: P1) 🎯 MVP

**Goal**: Allow path executes once; correlation joins audit + spans; post-hooks run after tool-body error

**Independent Test**: Scripted agent issues one in-scope registered tool call; assert allow, one
execution, correlation on decisions + audit, no secret values (quickstart Scenarios A, D)

### Tests for User Story 1

- [ ] T020 [P] [US1] Add `tests/component/test_governed_allow.py` for in-scope allow, single execution, audit trail by correlation ID, span correlation
- [ ] T021 [P] [US1] Add `tests/component/test_tool_body_error.py` proving post-hooks still run and failed execution is audited (FR-015)
- [ ] T022 [P] [US1] Add `tests/component/test_multi_invoke_same_run.py` proving two tool calls on one run share one correlation ID with distinct per-call audit and span records (spec edge case)
- [ ] T023 [P] [US1] Add `tests/component/test_post_hook_error.py` proving a post-hook exception after a successful tool body: audit shows the tool executed and the post-path failed-closed; `InvokeResult` is not clean success (spec edge case)
- [ ] T024 [P] [US1] [GATE:correlation] Assert `assert_correlated` / `assert_audit_chain` pass on allow-path and multi-invoke fixtures
- [ ] T025 [P] [US1] [GATE:no-secret-leak] Assert `assert_no_secret_values` on allow-path, tool-body-error, and post-hook-error fixtures

### Implementation for User Story 1

- [ ] T026 [US1] Wire pre/post allow path in `src/core/hooks/engine.py` and `src/core/tools/invoke.py` so allowed calls execute the handler exactly once
- [ ] T027 [US1] Append audit events `run_start`, `pre_decision`, `tool_outcome`, `post_decision` via `InMemoryAuditSink` with hash links
- [ ] T028 [US1] Emit OTel hook-decision spans from `src/core/telemetry/spans.py` on allow path
- [ ] T029 [US1] On tool-body exception after pre-allow: still run post-hooks; audit failed execution under same correlation ID; redact error content
- [ ] T030 [US1] On post-hook exception after the tool body already ran: record failed-closed post-path in audit under the same correlation ID; `InvokeResult` must not report clean success (`contracts/hook-pipeline.md` step 7 / spec edge case)
- [ ] T031 [US1] [GATE:fail-closed] On pre-path audit-append failure, deny with reason `internal_error` and do not execute the tool body (`contracts/hook-pipeline.md` invariant 5)
- [ ] T032 [US1] Implement `tests/harness/scripted_agent.py` and `tests/harness/capture_audit.py` used by US1 tests

**Checkpoint**: Scenarios A and D green; SC-001/SC-003/SC-004 satisfied for allow path; multi-invoke and post-hook-error edge cases covered

---

## Phase 4: User Story 2 - Out-of-scope or unregistered deny with no side effects (Priority: P1)

**Goal**: Unregistered and out-of-scope calls deny before execution; zero side effects; audited

**Independent Test**: Scripted agent requests unregistered or out-of-scope tool; deny, zero
executions, audited denial (quickstart Scenario B)

### Tests for User Story 2

- [ ] T033 [P] [US2] Add `tests/component/test_governed_deny.py` covering unregistered and out-of-scope denials
- [ ] T034 [P] [US2] [GATE:fail-closed] Assert `assert_denied_closed` for both denial classes
- [ ] T035 [P] [US2] Assert `assert_no_side_effect` against a counter-bearing registered handler / fake in deny tests

### Implementation for User Story 2

- [ ] T036 [US2] Enforce unregistered → deny before body in `src/core/hooks/engine.py` / `src/core/tools/invoke.py` with reason `unregistered`
- [ ] T037 [US2] Enforce out-of-scope → deny before body with reason `out_of_scope` (do not build caller logic that depends on external visibility of this distinction — see hook-pipeline known future tightening)
- [ ] T038 [US2] Audit denials under the run correlation ID; emit denial spans
- [ ] T039 [US2] Implement `assert_no_side_effect(target)` in `tests/harness/assertions.py` as counter-based helper

**Checkpoint**: Scenario B green; SC-001 deny half + SC-002 for these paths

---

## Phase 5: User Story 3 - Enforcement errors deny (fail closed) (Priority: P1)

**Goal**: Hook/registry/enforcement faults deny; never allow; no secret leakage

**Independent Test**: Inject fault into pre-hook or registry resolution; deny, no execution,
audited, no secrets (quickstart Scenario C)

### Tests for User Story 3

- [ ] T040 [P] [US3] Add `tests/component/test_fail_closed.py` for pre-hook raise, registry resolution failure, and missing required enforcement dependency
- [ ] T041 [P] [US3] [GATE:fail-closed] Assert deny + zero executions on every injected enforcement fault (including missing required enforcement dependency)
- [ ] T042 [P] [US3] [GATE:no-secret-leak] Assert no secret markers in audit, spans, or denial messages on fault paths
- [ ] T043 [P] [US3] Cover post-path audit-append failure: outcome failed-closed; never clean success with incomplete trail (`contracts/hook-pipeline.md` invariant 5)

### Implementation for User Story 3

- [ ] T044 [US3] Map pre-hook exceptions and corrupt decisions to deny (`internal_error` / `hook_deny` as designed) in `src/core/hooks/engine.py` — never allow
- [ ] T045 [US3] Map registry resolution failures to deny with audited record under correlation ID
- [ ] T046 [US3] [GATE:fail-closed] Map missing required enforcement dependency to deny with reason `internal_error` (FR-006): engine requires the built-in governance/enforcement hook to be present on the pipeline; tests omit or null that dependency and assert deny with zero tool-body executions and an audited failure under the correlation ID
- [ ] T047 [US3] Ensure user-facing denial messages use safe reason codes/text only (FR-014) in `InvokeResult`

**Checkpoint**: Scenario C green; SC-002/SC-005 for enforcement-error paths including missing dependency

---

## Phase 6: User Story 4 - Governance order fixed and observable (Priority: P2)

**Goal**: Governance/enforcement runs before non-governance co-resident hooks; order deterministic

**Independent Test**: Ordered probe hooks; assert governance-first (quickstart Scenario E / SC-006)

### Tests for User Story 4

- [ ] T048 [P] [US4] Add `tests/component/test_governance_order.py` with probe hooks recording invocation order
- [ ] T049 [P] [US4] [GATE:conformance] Assert `assert_hook_order` fails if governance is not first

### Implementation for User Story 4

- [ ] T050 [US4] Sort hooks by `capability_kind` in `src/core/hooks/engine.py` so all `governance` run before `other` in pre and post phases (stable within kind)
- [ ] T051 [US4] Implement `assert_hook_order` in `tests/harness/assertions.py` using spans or probe log (not private engine internals)

**Checkpoint**: Scenario E green; SC-006 met

---

## Phase 7: User Story 5 - Harness assertion helpers (Priority: P2)

**Goal**: Public helpers under exact names; import path `tests.harness`; README matches contract

**Independent Test**: Import four FR-012 helpers + side-effect helper; docs match
(quickstart Scenario F)

### Tests for User Story 5

- [ ] T052 [P] [US5] Add `tests/unit/test_harness_exports.py` importing `assert_denied_closed`, `assert_correlated`, `assert_audit_chain`, `assert_no_secret_values`, `assert_no_side_effect` from `tests.harness`

### Implementation for User Story 5

- [ ] T053 [US5] Implement remaining helpers in `tests/harness/assertions.py`: `assert_denied_closed`, `assert_correlated`, `assert_audit_chain`, `assert_no_secret_values`
- [ ] T054 [US5] Export public surface from `tests/harness/__init__.py` for the contracted names
- [ ] T055 [US5] Update `tests/harness/README.md` to document import path `from tests.harness import …`, helper names, packaging deferral note per `contracts/harness-helpers.md`

**Checkpoint**: Scenario F green; FR-012 contract satisfied

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Inner-loop green, redaction consistency, review readiness

- [ ] T056 [P] Add unit coverage in `tests/unit/test_redaction.py` that argument values and raw exception text do not enter audit payloads or span attributes
- [ ] T057 [GATE:no-secret-leak] Scan new fixtures under `tests/` for plausible secret-like values; keep only harness markers from `tests/harness/secrets.py`
- [ ] T058 Confirm `src/core` imports no agent frameworks (extend `tests/unit/test_core_import.py` if needed)
- [ ] T059 Run `make check` to green (unit + component); fix any typing/lint issues in touched files
- [ ] T060 Walk quickstart Scenarios A–G and record results in the `feat/002` PR description
- [ ] T061 Open `feat/002-governed-core` implementation PR only after this spec/plan/tasks PR merges; request security-maintainer review (sealed core + attestation-relevant)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Setup — **blocks all user stories**
- **Phase 3 (US1)**: Depends on Foundational — MVP
- **Phase 4 (US2)**: Depends on Foundational; shares engine with US1 (prefer US1 first)
- **Phase 5 (US3)**: Depends on Foundational; builds on deny/allow plumbing
- **Phase 6 (US4)**: Depends on Foundational + working invoke path
- **Phase 7 (US5)**: Can finalize exports after helpers land in US1–US4; import test can draft earlier
- **Phase 8 (Polish)**: Depends on US1–US5 complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — MVP increment
- **US2 (P1)**: Foundational; independently testable deny paths once `invoke_tool` exists
- **US3 (P1)**: Foundational; fault injection on same pipeline
- **US4 (P2)**: Needs multi-hook registration on the engine
- **US5 (P2)**: Aggregates helpers used by US1–US4; export/README can complete last

### Parallel Opportunities

- T005–T008, T010–T012 in Foundational (different files)
- Within a story: test modules marked [P] can be written in parallel before/while implementation
- US2/US3 test drafting can proceed in parallel once Foundational checkpoint passes

### Parallel Example: After Foundational

```bash
# Developer A: US1 allow path + harness fakes
# Developer B: US2 deny path + assert_no_side_effect
# Developer C: US3 fail-closed fault tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup
2. Complete Phase 2 Foundational
3. Complete Phase 3 US1
4. **STOP and VALIDATE**: Scenarios A and D, `make check`
5. Deploy/demo ready as library behavior before deny/order polish

### Incremental Delivery

1. Setup + Foundational → chain + refuse-start proven
2. US1 → allow + join (MVP)
3. US2 → deny + no side effects
4. US3 → fail-closed faults + audit-append failure
5. US4 → governance-first conformance
6. US5 → harness public API freeze
7. Polish → security-maintainer review on feat PR

### Notes

- Eval gate type omitted (N/A).
- Full `make conformance` suite remains stubbed from 001; SC-006 lives under `tests/component` until that suite exists.
- Reason codes `unregistered` vs `out_of_scope` remain distinct in 002; callers must not rely on that external distinction lasting past multi-tenancy.
- Analyze remediation (C1–C3): T022 multi-invoke same run; T023/T030 post-hook error after successful body; T040/T041/T046 missing required enforcement dependency (governance hook absent → `internal_error`).
