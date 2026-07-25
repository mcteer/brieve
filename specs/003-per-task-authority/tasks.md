# Tasks: Per-Task Authority

**Input**: Design documents from `specs/003-per-task-authority/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec FR-012/FR-013 and per-story Independent Tests require deterministic
unit/component tests with fakes only — include test tasks for every user story. No live
IdP, Vault, models, or product APIs.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Identity, exchange, expiry, mirroring, authority audit-append | Denial/refuse on error; never allow; evidential-gap on un-auditable authority paths |
| **Conformance** | Governance-first order with new authority/mirroring hooks | Authority + mirroring run as `capability_kind=governance` before `other` |
| **Correlation / evidence** | Authority issue/refuse/deny, mirroring, expiry | Same correlation ID joins trail; new event types hash-chained |
| **Eval** | N/A | No packs/models/policies |
| **No-secret-leak** | Credential manufacture, brokered fakes, audit/spans | Secret markers never appear; only refs + per-run salted hashes |

## Path Conventions

- Core: `src/core/authority/`, `src/core/hooks/`, `src/core/run.py`, `src/core/audit/`, `src/core/registry/`
- Harness: `tests/harness/` (`from tests.harness import …`)
- Tests: `tests/unit/`, `tests/component/`
- Config: `pyproject.toml` (no new runtime deps)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package layout for authority module; confirm no new runtime dependencies

- [x] T001 Create package skeleton `src/core/authority/__init__.py` exporting public types once implemented
- [x] T002 Confirm `pyproject.toml` gains **no** new runtime dependencies (research.md); document that justification in the eventual `feat/003` PR body only
- [x] T003 [P] Extend secret markers in `tests/harness/secrets.py` with authority/credential fixture markers used by 003 tests (obvious fake markers only)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Types, intersection, clock, errors, audit event types, registry product metadata,
manufacture skeleton, run extensions, governance hook registration slots — all stories build
on this

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 [P] Create `src/core/authority/types.py` with Pydantic/`frozenset` `AuthorityScope` (`tool_names`, `product_actions`) and `TaskCredentialRef` per `data-model.md`
- [x] T005 [P] Create `src/core/authority/errors.py` with typed refuse/deny errors carrying correlation ID when known (`AuthorityRefuseError`, `AuthorityExpiredError`, and related)
- [x] T006 [P] Create `src/core/authority/clock.py` with `Clock` protocol (`now() -> datetime`) and a system-clock default implementation
- [x] T007 [P] Create `src/core/authority/intersection.py` pure function computing effective scope = user ∩ ceiling ∩ requested ∩ policy for both components
- [x] T008 [P] Unit test `tests/unit/test_authority_intersection.py` covering intersection and equality-at-bound (not strictly-less)
- [x] T009 Extend `AuditEventType` in `src/core/audit/schema.py` with `authority_issued`, `authority_refused`, `authority_denied`, `authority_expired`, `mirroring_decision` exactly as in research.md
- [x] T010 Extend `ToolRegistration` in `src/core/registry/memory.py` with optional `product_mode` (`none`\|`federate`\|`broker`), `product`, `product_action` per `contracts/entitlement-mirroring.md`; update `register` API accordingly
- [x] T011 Create `src/core/authority/manufacture.py` with manufacture/refuse logic (amplification check, TTL `expires_at = now + 15 minutes`, opaque `credential_id`, 32-byte `run_salt`) per `contracts/authority-binding.md`
- [x] T012 Extend `GovernedRun` in `src/core/run.py` with `authority: TaskCredentialRef`, `run_salt: bytes`, and identity/clock/fabric references needed by hooks (memory-only; never persist secret values)
- [x] T013 Create identity-fabric protocol in `src/core/authority/fabric.py` (user/ceiling/policy/entitlements/issue methods) — harness fakes implement it
- [x] T014 Create stub governance hook modules `src/core/hooks/authority.py` and `src/core/hooks/mirroring.py` registered from `src/core/hooks/governance.py` as `capability_kind=governance` (behavior filled in story phases)
- [x] T015 [GATE:no-secret-leak] Unit test `tests/unit/test_run_salt_hashing.py` that secret-class content hashes use HMAC-SHA256(run_salt, material) and raw salt/secrets never appear in audit payloads
- [x] T016 [GATE:fail-closed] Unit test `tests/unit/test_authority_manufacture_refuse.py` that requested ⊈ user or requested ⊈ ceiling refuses with no credential
- [x] T017 [P] Implement `src/core/authority/hashing.py` with `content_hash(run_salt: bytes, material: bytes | str) -> str` (HMAC-SHA256 hex); use it from authority-related audit payload builders

**Checkpoint**: Types/intersection importable; amplification refuse unit-tested; audit enum extended; registry metadata present; hooks registered as governance

---

## Phase 3: User Story 1 - In-scope task receives narrowed authority and may proceed (Priority: P1) 🎯 MVP

**Goal**: Manufacture narrowed authority at start; in-scope tool allow through existing pipeline; audit `authority_issued`; no secret leakage

**Independent Test**: Fakes for identity/ceiling; task scope ⊂ user ∩ ceiling; invoke one in-scope tool; allow + `assert_scope_narrowed` + correlated authority audit (quickstart Scenario A; invoke half of C)

### Tests for User Story 1

- [x] T018 [P] [US1] Add `tests/component/test_authority_issue.py` for successful manufacture, effective = intersection, `authority_issued` under correlation ID
- [x] T019 [P] [US1] Extend or add allow-path coverage in `tests/component/test_authority_invoke.py` for in-scope tool under `live_effective.tool_names`
- [x] T020 [P] [US1] [GATE:correlation] Assert `assert_correlated` / `assert_audit_chain` on authority-issued + tool decisions for the same run
- [x] T021 [P] [US1] [GATE:no-secret-leak] Assert `assert_no_secret_values` on issue + allow fixtures (including brokered marker material if present in fabric)
- [x] T022 [P] [US1] [GATE:no-secret-leak] Assert `GovernedRun` and any dumped run-state shape expose only `TaskCredentialRef` fields — never brokered secret material (FR-011) in `tests/unit/test_authority_run_state.py`

### Implementation for User Story 1

- [x] T023 [US1] Implement `fake_identity_fabric` in `tests/harness/fake_identity_fabric.py` with user/ceiling/policy fixtures sufficient for happy-path manufacture (including mid-run policy shrink hooks for later tests)
- [x] T024 [US1] Implement `frozen_clock` in `tests/harness/frozen_clock.py` with `now()` and `advance(delta)`
- [x] T025 [US1] Extend `start_governed_run` in `src/core/run.py` to require `subject_user_id`, `requested_scope`, `identity_fabric`, `clock`; bind `TaskCredentialRef`; set `scope` to `effective.tool_names`; append `authority_issued` (remove bare `scope=`-only start — authority bind is mandatory)
- [x] T026 [US1] Migrate `tests/component/conftest.py` `make_run` and every 002 caller of `start_governed_run` under `tests/` to supply `subject_user_id`, `requested_scope`, `identity_fabric`, and `clock` so `make check` stays green with the new signature
- [x] T027 [US1] [GATE:fail-closed] If `authority_issued` audit append fails after manufacture: raise typed refuse, leave run non-ACTIVE / unusable (no `InvokeResult` path); do not set invoke-style `evidential_gap` on a successful start
- [x] T028 [US1] Wire authority pre-hook in `src/core/hooks/authority.py`: re-resolve policy each invoke; compute `live_effective = authority.effective ∩ current_policy`; allow only when tool ∈ `live_effective.tool_names` and not expired (expiry deny fleshed in US5; product_action bound in T037)
- [x] T029 [US1] Implement `assert_scope_narrowed` in `tests/harness/assertions.py` comparing both scope components ⊆ `at_most`
- [x] T030 [US1] Export `fake_identity_fabric`, `frozen_clock`, `assert_scope_narrowed` from `tests/harness/__init__.py` (product fake may land in US3)

**Checkpoint**: Scenario A green; SC-002 for allow/issue path; SC-007 for `authority_issued`

---

## Phase 4: User Story 2 - Amplification and out-of-ceiling scope are denied (Priority: P1)

**Goal**: Refuse amplify at start; deny tool beyond effective authority; zero side effects

**Independent Test**: Request scope above user/ceiling → refuse, no credential; invoke beyond effective → deny before body (quickstart Scenario B; deny half of C)

### Tests for User Story 2

- [x] T031 [P] [US2] Add `tests/component/test_authority_refuse.py` for task scope exceeding user and exceeding ceiling
- [x] T032 [P] [US2] Add deny cases in `tests/component/test_authority_invoke.py` for tool ∉ `live_effective.tool_names` with reason `authority_insufficient`
- [x] T033 [P] [US2] [GATE:fail-closed] Assert refuse/deny + `assert_no_side_effect` + no usable amplified credential (SC-001)
- [x] T034 [P] [US2] [GATE:correlation] Assert `authority_refused` / `authority_denied` audited under correlation ID when sink available
- [x] T035 [P] [US2] Add mid-run **policy** shrink case in `tests/component/test_authority_invoke.py`: after issue, fabric returns stricter policy; next invoke denies a tool that was in issued effective but not in `live_effective`

### Implementation for User Story 2

- [x] T036 [US2] Wire amplification refuse at start in `src/core/run.py` to call manufacture refuse + append `authority_refused` (do not re-implement intersection algebra from T011)
- [x] T037 [US2] Enforce `live_effective` membership in `src/core/hooks/authority.py` before tool body: tool_names always; when `product_mode` ≠ `none`, also `product_action` ∈ `live_effective.product_actions` → else `authority_insufficient`; audit `authority_denied`
- [x] T038 [US2] Ensure equality-at-bound still issues (edge case) — covered by unit/component assertion in `tests/unit/test_authority_intersection.py` or refuse tests

**Checkpoint**: Scenario B green; SC-001 met; mid-run policy shrink covered

---

## Phase 5: User Story 3 - Entitlement mirroring for product actions (Priority: P1)

**Goal**: Federate/broker mirroring pre-hook; empty entitlements deny; brokered check before shared-grain wield

**Independent Test**: Brokered fake; user lacks action A → deny zero wields; action B in entitlements → allow once; federate path without standing product secret (quickstart Scenario D)

### Tests for User Story 3

- [x] T039 [P] [US3] Add `tests/component/test_entitlement_mirroring.py` for broker deny (missing entitlement), broker allow, federate allow, empty-entitlements deny
- [x] T040 [P] [US3] [GATE:fail-closed] Assert `mirroring_denied` + zero product wields on deny paths (SC-003)
- [x] T041 [P] [US3] [GATE:correlation] Assert `mirroring_decision` audited under correlation ID
- [x] T042 [P] [US3] [GATE:no-secret-leak] Assert no shared-grain secret values in audit/spans/messages
- [x] T043 [P] [US3] Cover mid-run entitlement shrink: second invoke observes stricter set in `tests/component/test_entitlement_mirroring.py`
- [x] T044 [P] [US3] [GATE:fail-closed] Deny when `product_action` ∈ live entitlements but ∉ `live_effective.product_actions` (reason `authority_insufficient`, zero wields) in `tests/component/test_entitlement_mirroring.py`

### Implementation for User Story 3

- [x] T045 [US3] Implement `fake_product_api` in `tests/harness/fake_product_api.py` with wield counters and federate/broker enforcement hooks for tests
- [x] T046 [US3] Implement mirroring pre-hook in `src/core/hooks/mirroring.py` per `contracts/entitlement-mirroring.md` (order: after authority gate, before `other`); entitlements check only — product_action ∈ `live_effective` already enforced by authority hook
- [x] T047 [US3] Ensure broker path in `src/core/hooks/mirroring.py` + `tests/harness/fake_product_api.py` resolves user entitlements **before** any shared-grain wield
- [x] T048 [US3] Re-resolve entitlements from fabric on every invoke (no wider cache) in `src/core/hooks/mirroring.py`
- [x] T049 [US3] Export `fake_product_api` from `tests/harness/__init__.py`

**Checkpoint**: Scenario D green; SC-003 met; ADR-0044 pre-check covered

---

## Phase 6: User Story 4 - Authority and identity failures deny (fail closed) (Priority: P1)

**Goal**: Identity/exchange/entitlement/ceiling faults refuse start or deny invoke; never allow; no secrets

**Independent Test**: Inject fabric faults; refuse/deny; zero executions; audited; `assert_no_secret_values` (quickstart Scenario F)

### Tests for User Story 4

- [x] T050 [P] [US4] Add `tests/component/test_authority_fail_closed.py` for identity unavailable, exchange failed, ceiling lookup error, entitlement resolve error at start and at invoke
- [x] T051 [P] [US4] [GATE:fail-closed] Assert every injected fault → refuse or deny with zero tool-body / product wields (SC-004)
- [x] T052 [P] [US4] [GATE:no-secret-leak] Assert no secret markers on fault paths in `tests/component/test_authority_fail_closed.py`
- [x] T053 [P] [US4] [GATE:fail-closed] Cover authority/mirroring audit-append failure on **invoke** pre-path → deny with `InvokeResult.evidential_gap=True` (002 posture); start-path failures remain raise + non-ACTIVE (T027)

### Implementation for User Story 4

- [x] T054 [US4] Map fabric failure modes to reason codes `identity_unavailable` / `exchange_failed` / `internal_error` in manufacture and hooks
- [x] T055 [US4] Extend `fake_identity_fabric` fault-injection flags for all US4 cases in `tests/harness/fake_identity_fabric.py`
- [x] T056 [US4] Ensure user-facing messages use safe reason codes only (FR-014) in `src/core/tools/invoke.py` / authority errors without dumping other users' entitlements

**Checkpoint**: Scenario F green; SC-004/SC-006 for fault paths

---

## Phase 7: User Story 5 - Short-lived authority expires; harness asserts narrowing (Priority: P2)

**Goal**: TTL expiry denies invokes; no auto-refresh; `assert_scope_narrowed` importable and fails on amplified fixtures

**Independent Test**: Advance frozen clock past TTL → deny; helper passes on narrowed / fails on amplified (quickstart Scenarios E, G)

### Tests for User Story 5

- [x] T057 [P] [US5] Add `tests/component/test_authority_expiry.py` advancing `frozen_clock` past 15-minute TTL; assert `authority_expired` deny before body (SC-005)
- [x] T058 [P] [US5] Add `tests/unit/test_assert_scope_narrowed.py` proving helper passes on narrowed token and fails on amplified fixture
- [x] T059 [P] [US5] Add/extend `tests/unit/test_harness_exports.py` importing `fake_identity_fabric`, `fake_product_api`, `frozen_clock`, `assert_scope_narrowed` from `tests.harness`
- [x] T060 [P] [US5] [GATE:correlation] Assert expiry denial audited as `authority_expired` under correlation ID

### Implementation for User Story 5

- [x] T061 [US5] Enforce `clock.now() >= expires_at` → deny `authority_expired` in `src/core/hooks/authority.py`; no auto-refresh
- [x] T062 [US5] Document that re-manufacture requires a new `start_governed_run` in `tests/harness/README.md`
- [x] T063 [US5] Update `tests/harness/README.md` for all new 003 exports and narrowing helper contract
- [x] T064 [US5] [GATE:conformance] Confirm authority + mirroring hooks remain governance-first via existing `assert_hook_order` probe or extend `tests/component/test_governance_order.py`

**Checkpoint**: Scenarios E and G green; SC-005 met; FR-012 binding complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Inner-loop green, docs, 002 regression, security-review readiness

- [x] T065 [P] Update `docs/development/testing.md` if any 003 helper usage examples are missing (`assert_scope_narrowed`, fakes, frozen clock)
- [x] T066 [GATE:no-secret-leak] Scan new fixtures under `tests/` for plausible secret-like values; keep only harness markers
- [x] T067 Confirm `src/core` still imports no agent frameworks; authority modules stay framework-agnostic (`tests/unit/test_core_import.py` if needed)
- [x] T068 Run `make check` green (unit + component) including 002 regressions; fix typing/lint in touched files
- [x] T069 Walk quickstart Scenarios A–H and record results in the `feat/003` PR description
- [x] T070 Open `feat/003-per-task-authority` implementation PR only after this tasks PR merges (if separate) / after analyze; request security-maintainer review (sealed core identity/authority + attestation-relevant)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Setup — **blocks all user stories**
- **Phase 3 (US1)**: Depends on Foundational — MVP; T026 migrates 002 callers with T025
- **Phase 4 (US2)**: Depends on Foundational; prefer after US1 manufacture path exists; T035 needs fabric policy shrink from T023
- **Phase 5 (US3)**: Depends on Foundational + US1 run bind (needs subject + fabric on run); T044 needs T037 product_action bound
- **Phase 6 (US4)**: Depends on Foundational + fabric/hooks from US1/US3
- **Phase 7 (US5)**: Depends on US1 clock bind + authority hook; helper can draft earlier
- **Phase 8 (Polish)**: Depends on US1–US5 complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — MVP increment (issue + allow)
- **US2 (P1)**: Foundational; independently testable refuse/deny once manufacture + authority hook exist
- **US3 (P1)**: Needs bound run + registry product metadata; independently testable mirroring
- **US4 (P1)**: Fault injection on manufacture + mirroring paths
- **US5 (P2)**: Expiry + harness export freeze

### Parallel Opportunities

- T004–T007, T009–T010 in Foundational (different files)
- Within a story: test modules marked [P] can be drafted in parallel before implementation
- After US1 checkpoint: US2 refuse tests and US5 helper unit tests can proceed in parallel with US3 mirroring implementation

### Parallel Example: After Foundational + US1 MVP

```bash
# Developer A: US2 refuse/deny + Scenario B
# Developer B: US3 mirroring + fake_product_api
# Developer C: US5 expiry + assert_scope_narrowed unit tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup
2. Complete Phase 2 Foundational
3. Complete Phase 3 US1
4. **STOP and VALIDATE**: Scenario A, `assert_scope_narrowed`, `make check`
5. Demo ready as library behavior before deny/mirroring/expiry polish

### Incremental Delivery

1. Setup + Foundational → types, intersection, refuse unit tests
2. US1 → issue + allow + salt hashing (MVP)
3. US2 → amplification refuse + insufficient deny
4. US3 → entitlement mirroring (federate/broker)
5. US4 → identity/exchange fail-closed
6. US5 → expiry + harness public API freeze
7. Polish → security-maintainer review on feat PR

### Notes

- Eval gate type omitted (N/A).
- Default TTL pinned at **15 minutes**; no auto-refresh in 003.
- Empty product entitlements deny (never unrestricted).
- Reason codes pinned in research.md — do not invent soft “or equivalent” aliases in tasks.
- Analyze remediations (I1/I2/C1 + pins): `live_effective = issued ∩ current_policy` each invoke (T028/T037/T035); dual-bound product_action (T037/T044); mandatory migrate 002 `start_governed_run` callers (T026); `hashing.py` + pinned `fabric.py` (T017/T013); FR-011 run-state assert (T022); evidential-gap split start vs invoke (T027/T053).
- Re-analyze polish: quickstart US↔scenario mapping corrected; T019 wording uses `live_effective.tool_names`.
- Residual LOW polish: Task IDs renumbered monotonic T001–T070; Performance Goals marked N/A (no SLO); FR-011 specializes FR-001 for run/checkpoint persistence (not duplicate work).
