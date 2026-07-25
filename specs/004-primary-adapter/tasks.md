# Tasks: Primary Adapter

**Input**: Design documents from `specs/004-primary-adapter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec FR-011/FR-012/FR-015, per-story Independent Tests, and constitution Quality
Gates require deterministic unit/component/conformance tests with stub models and fakes
only — include test tasks for every user story. No live models, IdP, Vault, or product
APIs, and that prohibition is itself asserted (T059) rather than left to convention.
Conformance is merge-blocking in CI (T055), not attested in a PR description.

**Scope bound**: FR-016 caps this feature's sealed-core changes at three — durability
protocol (T005/T006), approval-hook protocol (T007), and required `agent_definition_id`
(T008/T009). A fourth core change appearing during implementation is out of scope; stop
and open its own spec (T060 is the review that catches it).

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Adapter mapping faults, missing run/definition, governance errors | Denial/refuse on error; never catch-and-allow around core denials |
| **Conformance** | Primary adapter seam | Governance-first order + fail-closed cases under `make conformance` |
| **Correlation / evidence** | Adapter-started runs | Same correlation ID joins audit/tool decisions; 002/003 evidence preserved |
| **Eval** | N/A | No packs/models/policies |
| **No-secret-leak** | Adapter path, durability blobs, model-visible context | Secret markers / credentials / `run_salt` never appear |
| **Determinism** | Feature test paths | No live model, IdP, Vault, or product-API client reachable from tests (FR-012) |

## Path Conventions

- Adapter: `src/adapters/pydantic_ai/`
- Core seams: `src/core/durability/`, `src/core/approvals/`, `src/core/run.py`, `src/core/authority/fabric.py`
- Harness: `tests/harness/`
- Tests: `tests/unit/`, `tests/component/`, `tests/conformance/adapter/`
- Config: `pyproject.toml` (`optional-dependencies.adapters`), `Makefile`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Adapter package layout, optional framework dependency, conformance tree

- [X] T001 Create package skeleton `src/adapters/pydantic_ai/__init__.py` (public exports filled in story phases)
- [X] T002 Add `[project.optional-dependencies] adapters = ["pydantic-ai-slim==2.18.0"]` in `pyproject.toml` (**not** a `[dependency-groups]` entry — `dev` stays a group). **Pin `pydantic-ai-slim`, not `pydantic-ai`** — the meta package resolves to `pydantic-ai-slim[anthropic,cli,evals,google,logfire,mcp,openai,retries,web]`, dragging three live model-provider SDKs plus a CLI and logfire into a regulated tree for a feature that calls no model (Principle VI; and FR-012's denylist is far easier to hold when those SDKs are not installed at all). Slim's runtime deps are `httpx`, `pydantic`, `pydantic-graph`, `opentelemetry-api`, `genai-prices`, `griffelib`, `typing-inspection`. `TestModel` / `FunctionModel` and the capability + toolset APIs 004 needs are all in the slim core. **Check before committing**: slim 2.18.0 requires `pydantic>=2.12` and `opentelemetry-api>=1.28`, above this project's `>=2.10` / `>=1.27` floors — either raise the base pins to match so the with-extra and without-extra environments agree, or record why the divergence is acceptable. Verify the pin is still current at implement time (2.18.0 read from the index 2026-07-25); document ADR-0017 justification + the slim-vs-meta reasoning in the `feat/004` PR body; ensure `uv sync --extra adapters` resolves **and commit the regenerated `uv.lock` in the same change** — CI syncs with `uv sync --frozen --extra adapters`, which by definition will not update the lockfile, so a stale lock fails the fast lane before any test runs
- [X] T003 [P] Create `tests/conformance/__init__.py` and `tests/conformance/adapter/__init__.py`
- [X] T004 [P] Confirm `[tool.setuptools.packages.find] include` already covers `adapters*`; add any mypy overrides needed so adapter modules typecheck with the extra installed (document approach in PR if overrides are required)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Framework-agnostic seams (durability, approvals), per-definition ceiling plumbing,
adapter stubs, core import guard — all stories build on this

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Create `src/core/durability/types.py` with `CheckpointBlob` and `DurabilityProvider` protocol (`save` / `load`) per `data-model.md`
- [X] T006 [P] Create `src/core/durability/memory.py` with `InMemoryDurabilityProvider` and export from `src/core/durability/__init__.py`
- [X] T007 [P] Create `src/core/approvals/types.py` with `ApprovalHook` protocol and deny-by-default + injectable-allow test doubles; export from `src/core/approvals/__init__.py`
- [X] T008 Extend `IdentityFabric.resolve_ceiling` **and** `resolve_policy` in `src/core/authority/fabric.py` to require `agent_definition_id: str`; update `manufacture.py` callers accordingly (fakes may return global policy while accepting the id)
- [X] T009 Extend `start_governed_run` in `src/core/run.py` to require non-empty `agent_definition_id: str` and pass it into ceiling and policy resolution; blank/missing → refuse start (**breaking seam** vs 003 — migrate callers in T010; call out in feat PR)
- [X] T010 Migrate `tests/harness/fake_identity_fabric.py` and every `start_governed_run` caller under `tests/` to supply `agent_definition_id` (default fixture id ok) so `make check` stays green
- [X] T011 [P] Create `src/adapters/pydantic_ai/run_context.py` with `AdapterRunContext` fields per `data-model.md`
- [X] T012 Create stub modules `src/adapters/pydantic_ai/governance.py`, `tools.py`, `agent.py`, `durability.py`, `approvals.py` (behavior filled in story phases; framework imports only here)
- [X] T013 [GATE:fail-closed] Unit test `tests/unit/test_agent_definition_required.py` that blank/missing `agent_definition_id` refuses start with no usable run
- [X] T014 [P] Extend `tests/unit/test_core_import.py` to assert `core` (and its submodules imported by the smoke) never import `pydantic_ai` (layering guard — not an enforcement fail-closed gate)
- [X] T015 [P] Unit test `tests/unit/test_durability_no_credentials.py` that a checkpoint payload built from a fixture run state omits credential secrets and `run_salt` (structural / `assert_no_secret_values`)

**Checkpoint**: Seams importable; definition id required; 003 suite green after migration; core still framework-free

---

## Phase 3: User Story 1 - Scripted agent completes an in-scope governed call (Priority: P1) 🎯 MVP

**Goal**: Start adapter run with 003 authority bind; stub/scripted tool call through mapping
allows once; audit/correlation + `assert_scope_narrowed` hold

**Independent Test**: quickstart Scenario A — `tests/component/test_adapter_allow.py`

### Tests for User Story 1

- [X] T016 [P] [US1] Add `tests/component/test_adapter_allow.py` for adapter-started in-scope allow, exactly one tool-body execution
- [X] T017 [P] [US1] [GATE:correlation] Assert `assert_correlated` / `assert_audit_chain` on adapter allow path under the run correlation ID
- [X] T018 [P] [US1] [GATE:no-secret-leak] Assert `assert_no_secret_values` on adapter allow fixtures (audit, spans, model-visible context)
- [X] T019 [P] [US1] Assert `assert_scope_narrowed` on authority bound via adapter start in `tests/component/test_adapter_allow.py`

### Implementation for User Story 1

- [X] T020 [US1] Implement governed toolset mapping in `src/adapters/pydantic_ai/tools.py` that delegates every tool call to `invoke_tool(run, tool_name, arguments)` per `contracts/four-mappings.md`
- [X] T021 [US1] Implement `GovernanceCapability` skeleton in `src/adapters/pydantic_ai/governance.py` sufficient to compose the governed toolset (ordering hardened in US3)
- [X] T022 [US1] Implement `start_adapter_run` / `build_governed_agent` in `src/adapters/pydantic_ai/agent.py` calling `start_governed_run` with subject, definition id, scope, fabric, clock, registry, and **`include_governance=True`** (or omit the kwarg so default True cannot be overridden from the adapter)
- [X] T023 [US1] Add `tests/harness/adapter_fixtures.py` with stub/TestModel (or FunctionModel) helpers and a minimal registry tool for allow-path tests
- [X] T024 [US1] Export public adapter symbols from `src/adapters/pydantic_ai/__init__.py` and any harness helpers from `tests/harness/__init__.py`
- [X] T025 [US1] Update `.github/workflows/ci.yml`, `docs/development/testing.md`, and `CONTRIBUTING.md` so the documented/CI inner loop is `uv sync --extra adapters` (plus existing dev group); `make check` must collect and run adapter component tests — **no** importorskip that greens without the extra

**Checkpoint**: Scenario A green; SC-001/SC-004/SC-005 for allow path; MVP demoable

---

## Phase 4: User Story 2 - Adapter-path denials produce zero side effects (Priority: P1)

**Goal**: Unregistered / out-of-scope / authority-insufficient through adapter → deny; zero
executions; no catch-and-allow around core denials

**Independent Test**: quickstart Scenario B — `tests/component/test_adapter_deny.py`

### Tests for User Story 2

- [X] T026 [P] [US2] Add `tests/component/test_adapter_deny.py` for unregistered and out-of-scope tool names via adapter
- [X] T027 [P] [US2] Add authority-insufficient deny case in `tests/component/test_adapter_deny.py` (tool outside `live_effective`)
- [X] T028 [P] [US2] [GATE:fail-closed] Assert `assert_denied_closed` + `assert_no_side_effect` for all US2 cases
- [X] T029 [P] [US2] [GATE:correlation] Assert denial audited under the run correlation ID
- [X] T030 [P] [US2] [GATE:fail-closed] Assert mapping does not convert core deny into a successful side-effecting native tool result
- [X] T031 [P] [US2] [GATE:no-secret-leak] Assert adapter-path deny/refuse user-facing messages explain denial without secret or out-of-scope entitlement leakage (FR-013) in `tests/component/test_adapter_deny.py`
- [X] T032 [P] [US2] Add adapter-path entitlement mirroring case (broker or federate `product_mode` tool) in `tests/component/test_adapter_mirroring.py`: missing entitlement → deny + zero product wields; entitled → allow once (FR-005)

### Implementation for User Story 2

- [X] T033 [US2] Finalize deny surface in `src/adapters/pydantic_ai/tools.py`: core deny → failed tool outcome; never invoke registry handler outside `invoke_tool`; never swallow deny as empty success; messages satisfy FR-013
- [X] T034 [US2] Ensure start refuse paths (missing correlation / identity / definition) remain fail-closed when invoked via `start_adapter_run` in `src/adapters/pydantic_ai/agent.py`

**Checkpoint**: Scenario B green; SC-001/SC-002 for deny path; FR-005/FR-013 adapter-path coverage

---

## Phase 5: User Story 3 - Governance runs first and fails closed (Priority: P1)

**Goal**: GovernanceCapability always first among co-resident capabilities; faults deny;
conformance cases exist and would fail if order inverted

**Independent Test**: quickstart Scenario C — `tests/conformance/adapter/`

### Tests for User Story 3

- [X] T035 [P] [US3] [GATE:conformance] Add `tests/conformance/adapter/test_governance_order.py` asserting governance before co-resident probe capability on a tool call
- [X] T036 [P] [US3] [GATE:conformance] Add **self-verifying** break test in `tests/conformance/adapter/test_governance_order_break.py`: build an agent whose capability order is deliberately inverted (governance not first) via a test-only fixture, run the same ordering assertion T035 uses, and assert it raises `AssertionError`. **The test itself PASSES on a clean tree** — it proves the detector fires. It MUST NOT be an `xfail`, a skip, or anything that reports failure under `make conformance` (SC-007 requires that command green)
- [X] T037 [P] [US3] [GATE:fail-closed] Add `tests/conformance/adapter/test_fail_closed.py` injecting governance/mapping fault → deny, zero executions
- [X] T038 [P] [US3] [GATE:conformance] Assert adapter tool path reaches `invoke_tool` (shared probe/counter helper) in `tests/conformance/adapter/` — unit-level duplicate lives in T042

### Implementation for User Story 3

- [X] T039 [US3] Harden `build_governed_agent` in `src/adapters/pydantic_ai/agent.py` to always prepend `GovernanceCapability` per `contracts/governance-capability.md`
- [X] T040 [US3] Implement co-resident probe capability fixture for conformance in `tests/conformance/adapter/conftest.py` (or `tests/harness/adapter_fixtures.py`) that records order without bypassing tools
- [X] T041 [US3] Ensure GovernanceCapability / mapping exceptions deny (no allow-on-exception) in `src/adapters/pydantic_ai/governance.py` and `tools.py`

**Checkpoint**: Conformance adapter lane green when executed directly; SC-003 satisfied for cases

---

## Phase 6: User Story 4 - Adapter contents are only the four mappings (Priority: P2)

**Goal**: Prove tools/state/interrupts/run-context mappings; per-definition ceilings; no
adapter-local enforcement engine

**Independent Test**: quickstart Scenario D — mapping + definition ceiling tests

### Tests for User Story 4

- [X] T042 [P] [US4] Add `tests/unit/test_adapter_mappings.py` proving tool mapping delegates to `invoke_tool` via the same probe/counter helper as T038 (unit lane; conformance lane owns SC-003 order)
- [X] T043 [P] [US4] Add `tests/component/test_adapter_definition_ceiling.py` for distinct per-definition ceilings and unknown definition refuse
- [X] T044 [P] [US4] [GATE:no-secret-leak] Assert durability save in adapter path never persists credentials/`run_salt` in `tests/unit/test_adapter_durability_mapping.py`
- [X] T045 [P] [US4] Add approval default-deny interrupt mapping test in `tests/unit/test_adapter_approval_mapping.py` (no ungoverned execution)

### Implementation for User Story 4

- [X] T046 [US4] Implement state → durability mapping in `src/adapters/pydantic_ai/durability.py` onto `DurabilityProvider` (thin core protocol; `providers/` binding deferred with ADR-0024)
- [X] T047 [US4] Implement interrupt → `ApprovalHook` mapping in `src/adapters/pydantic_ai/approvals.py` (default deny)
- [X] T048 [US4] Extend `fake_identity_fabric` in `tests/harness/fake_identity_fabric.py` to key ceilings by `agent_definition_id` and accept `agent_definition_id` on `resolve_policy` (global policy fixture ok)
- [X] T049 [US4] Review `src/adapters/pydantic_ai/` for four-mapping-only contents; move any authority/audit/registry logic into `src/core` if found

**Checkpoint**: Scenario D green; FR-002/FR-007/FR-009 covered

---

## Phase 7: User Story 5 - Contributors run adapter conformance via make conformance (Priority: P2)

**Goal**: `make conformance` executes primary-adapter lane and passes; no longer exit-2 stub

**Independent Test**: quickstart Scenario C/E — `make conformance`

### Tests for User Story 5

- [X] T050 [P] [US5] [GATE:conformance] Confirm `tests/conformance/adapter/test_governance_order.py`, `test_governance_order_break.py`, and `test_fail_closed.py` are collected by the conformance command entrypoint
- [X] T051 [P] [US5] Document that LangGraph secondary slots are absent or a single explicit skip in `tests/conformance/adapter/` — never a silent green that weakens primary cases. Any skip marker MUST carry the deferring ADR reference in its reason string (e.g. `pytest.mark.skip(reason="second adapter demand-driven — ADR-0017")`), per constitution v1.0.1 / ADR-0047; the per-row citations are in `contracts/conformance-adapter.md`

### Implementation for User Story 5

- [X] T052 [US5] Replace Makefile `conformance` stub with `$(UV_RUN) pytest tests/conformance -q` per `contracts/conformance-adapter.md`, where `UV_RUN` is defined in T054 — the extra must be requested in the recipe, not left to a documented precondition
- [X] T053 [US5] Update `docs/development/testing.md` **Conformance section prose** to describe the primary-adapter lane, the intentional 004 slice (governance-order + fail-closed only), and `uv sync --extra adapters` as required for check/conformance. The **CI-tier table and test-type row already landed in PR #22** (conformance moved to the Fast lane, marked merge-blocking) — do not re-edit those; this task is the section prose only
- [X] T054 [US5] Ensure `make check` testpaths remain unit+component (conformance stays a separate command) in `pyproject.toml` / `Makefile`; **and** add `UV_RUN := uv run --extra adapters` to the Makefile, routing every `check` and `conformance` recipe line through it. `uv run` materializes the project environment from the default extra set, so a bare `uv run` does not guarantee the `adapters` extra is present — and T025 forbids `importorskip`, so a missing extra must fail loudly rather than skip green. **Sequencing**: `uv run --extra adapters` errors with "Extra `adapters` is not defined" until T002 lands, so this edit ships with or after T002, never before
- [X] T055 [US5] [GATE:conformance] Add a conformance step to `.github/workflows/ci.yml` (fast-lane, immediately after `Inner-loop check`) running `make conformance`, and change `Sync dependencies` to `uv sync --frozen --extra adapters`. Without this, `contracts/conformance-adapter.md` invariant 1 ("conformance failures are merge-blocking for adapter changes") is satisfied only by a human running the command locally and pasting output into a PR body — a claim, not a record (Principle IX). Fast-lane rather than a separate job: the lane is sub-second, and a second job re-pays checkout + sync for no isolation benefit. **Sequencing**: depends on T002 (extra defined) and T052/T054 (recipe real)

**Checkpoint**: SC-007 — `make conformance` green on clean tree with adapters extra, **and merge-blocking in CI** (T055)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Inner-loop green, docs, 002/003 regression, scope-bound verification (FR-016),
determinism guard (FR-012), security-review readiness

- [X] T056 [P] Update `tests/harness/README.md` with adapter fixture / stub-model usage
- [X] T057 [GATE:no-secret-leak] Scan new fixtures under `tests/` and adapter examples for plausible secret-like values; keep only harness markers
- [X] T058 Confirm `src/core` still imports no agent frameworks (`tests/unit/test_core_import.py`)
- [X] T059 [P] [GATE:determinism] Add `tests/unit/test_no_live_dependencies.py` asserting FR-012 mechanically, by **two** checks with a stated mechanism each:
      **(a) Direct-import scan.** Parse each test module under `tests/` with `ast` and assert none of them *directly* imports a network client from the denylist (`httpx`, `requests`, `urllib.request`, `aiohttp`, `hvac`, and any model-provider SDK). Scan module source, **not** `sys.modules` — `pydantic-ai` pulls an HTTP client in transitively, so a runtime check fails on every adapter test while proving nothing. Transitive framework dependencies are explicitly out of scope for this check; the property is "no test reaches for a live client itself."
      **(b) Model resolution.** Assert every adapter test builds its agent with a stub model (`TestModel` / `FunctionModel` or the harness wrapper) — e.g. the harness builder refuses a model argument that is not a stub, and a test asserts that refusal. This is what actually prevents a live call; (a) alone cannot.
      Convention is not verification — this is the FR-010-style guard FR-012 previously lacked. Note the deliberate limit in the module docstring: this catches reaching for a client, not a live call made through an already-imported one; escalate to a socket-blocking plugin only if that gap is ever exercised
- [X] T060 Review the `src/core` diff against FR-016's three permitted extensions (durability protocol, approval-hook protocol, required `agent_definition_id`). Anything else touched under `src/core` — hook algebra, audit schema, registry lifecycle, authority intersection — is out of scope: revert it or stop and open its own spec. This is the core-side counterpart to T049's four-mapping review of the adapter
- [X] T061 Run `make check` green (unit + component, including 002/003 regressions) after `uv sync --extra adapters` (same sync CI uses — no skip path)
- [X] T062 Run `make conformance` green locally as a pre-flight (CI enforcement is T055 — the PR body records the walkthrough, it does not substitute for the gate); walk quickstart Scenarios A–F and record results in the `feat/004` PR description
- [X] T063 Open `feat/004-primary-adapter` implementation PR only after spec/plan/tasks merge path per CONTRIBUTING; request **security-maintainer** review (sealed-core adapters + conformance); fill PR template **Breaking change** section for required `agent_definition_id` on `start_governed_run` (T009/T010 migration) — state the deprecation-window exemption explicitly (pre-1.0 at `version = "0.0.0"`, no external consumers of the seam), since Principle V otherwise requires one; confirm the regenerated `uv.lock` from T002 is committed; state in the PR that the `src/core` diff contains only FR-016's three permitted extensions (T060 verified)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Setup — **blocks all user stories**
- **Phase 3 (US1)**: Depends on Foundational — MVP allow path
- **Phase 4 (US2)**: Depends on Foundational + US1 tool mapping/start helpers
- **Phase 5 (US3)**: Depends on US1 agent builder; conformance cases can draft tests earlier but need builder for green
- **Phase 6 (US4)**: Depends on Foundational seams; can parallelize with US2 after US1 for tool mapping probe
- **Phase 7 (US5)**: Depends on US3 conformance tests existing; order within the phase is
  Makefile switch (T052/T054) then CI enforcement (T055) — never CI first, or the fast lane
  goes red before the recipe is real
- **Phase 8 (Polish)**: Depends on US1–US5 complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — MVP increment (adapter allow)
- **US2 (P1)**: Needs US1 mapping/start; independently testable deny suite
- **US3 (P1)**: Needs US1 builder; conformance is the load-bearing bar
- **US4 (P2)**: Seams from Foundational + mapping proof; independently testable
- **US5 (P2)**: Needs US3 cases; flips `make conformance` from stub to real and makes it
  merge-blocking in CI

### Parallel Opportunities

- T005–T007, T011, T014–T015 in Foundational (different files)
- Within a story: test modules marked [P] can be drafted in parallel before implementation
- After US1 checkpoint: US2 deny tests and US4 durability/approval mapping can proceed in parallel with US3 conformance hardening

### Parallel Example: After Foundational + US1 MVP

```bash
# Developer A: US2 adapter deny suite
# Developer B: US3 governance order + fail-closed conformance
# Developer C: US4 durability/approval mappings + definition ceilings
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup
2. Complete Phase 2 Foundational (definition id migration is mandatory)
3. Complete Phase 3 US1
4. **STOP and VALIDATE**: Scenario A, `assert_scope_narrowed`, `make check`
5. Demo ready as adapter allow path before deny/conformance polish

### Incremental Delivery

1. Setup + Foundational → seams + definition-keyed fabric
2. US1 → adapter allow + invoke_tool mapping (MVP)
3. US2 → adapter deny / no bypass
4. US3 → governance-first + fail-closed conformance cases
5. US4 → four-mapping completeness (durability, approvals, ceilings)
6. US5 → `make conformance` real (T052/T054), then merge-blocking in CI (T055)
7. Polish → security-maintainer review on feat PR

### Notes

- Eval gate type omitted (N/A).
- Framework dependency stays in `[project.optional-dependencies] adapters` — never
  imported from `src/core`; install with `uv sync --extra adapters` (not a
  `dependency-groups` entry).
- Constitution Quality Gates also name deferred-disclosure parity, four-transport
  surface parity, registry isolation depth, and full ADR-0024 durability scenarios —
  those rows **attach when those features land** (ADR-0047; constitution v1.0.1), each
  citing its deferring ADR in `contracts/conformance-adapter.md`. 004’s conformance slice
  is governance-order + fail-closed (+ invoke_tool entry); do not add silent-green stubs
  for deferred rows.
- `invoke_tool` entry is asserted in both the conformance and unit lanes (T038, T042) —
  a deliberate duplicate, rationale in `research.md`.
- Tool mapping targets `invoke_tool`; MCP transport / northbound surfaces remain later
  (Principle I “MCP calls” wording is not an adapter-local MCP client in 004).
- Full ADR-0024 durability matrix, LangGraph adapter, northbound surfaces, code mode, and
  deferred-disclosure productization are out of scope (explicit skips only where needed).
- Reason codes remain owned by core; adapter asserts deny + zero executions.
- Contribution class at implement: **sealed core (adapters)** — security-maintainer
  review mandatory.
