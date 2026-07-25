# Tasks: Developer Toolchain Scaffold

**Input**: Design documents from `specs/001-dev-toolchain/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec requires a green inner-loop with unit smoke — include test tasks for US1/US2.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Stub make targets | Non-zero exit + explicit message; never silent success |
| **Conformance** | N/A for 001 | Suites not implemented — stub only |
| **Correlation / evidence** | N/A | No run/audit paths |
| **Eval** | N/A | No packs/models |
| **No-secret-leak** | Toolchain/CI config | No secret values in configs, fixtures, or workflow logs |

## Path Conventions

- Repository root: `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/`
- Packages: `src/core/`, `src/adapters/`, `src/surfaces/`
- Tests: `tests/unit/`, `tests/harness/`, reserved `tests/component|contract|integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the uv Python workspace and baseline config files

- [x] T001 Create root `pyproject.toml` with Python `>=3.12`, package discovery for `src/core`, `src/adapters`, `src/surfaces`, and tool configs for ruff/pytest/mypy
- [x] T002 [P] Add `NOTICE` at repository root (Apache 2.0 attribution referenced by README) if missing — **SKIPPED: maintainer deferred NOTICE; README link adjusted**
- [x] T003 [P] Ensure `.gitignore` covers `.venv/`, caches, and lock-adjacent noise without ignoring `uv.lock`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Layout stubs, SPDX precedent, and real `make check` wiring that all stories reuse

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 [P] Create `src/core/__init__.py`, `src/core/py.typed` with `SPDX-License-Identifier: Apache-2.0`, and apply the same SPDX line to every new commentable file created in this feature (Makefile, workflow YAML, pre-commit config, TOML) per FR-011
- [x] T005 [P] Create `src/adapters/__init__.py`, `src/adapters/py.typed` with SPDX header
- [x] T006 [P] Create `src/surfaces/__init__.py`, `src/surfaces/py.typed` with SPDX header
- [x] T007 [P] Create `tests/harness/__init__.py` and `tests/harness/README.md` stating reserved public-API / semver seam role
- [x] T008 [P] Create reserved extension stubs `packs/README.md`, `hooks/README.md`, `providers/README.md`, `portal/README.md` (no `portal/package.json`)
- [x] T009 [P] Create reserved test dirs with `.gitkeep`: `tests/component/`, `tests/contract/`, `tests/integration/`
- [x] T010 [GATE:no-secret-leak] Audit new config/fixtures for secret-like values; keep workflows fork-safe (no required repository secrets)
- [x] T011 Run `uv sync` and commit `uv.lock`

**Checkpoint**: Packages importable; lockfile present; layout matches FR-003

---

## Phase 3: User Story 1 - Fresh clone reaches a green inner loop (Priority: P1) 🎯 MVP

**Goal**: `uv sync` + `make check` succeeds with zero product features

**Independent Test**: Clean env → `uv sync` → `make check` exits 0 (quickstart Scenario A)

### Tests for User Story 1

- [x] T012 [P] [US1] Add `tests/unit/test_core_import.py` smoke test importing `core` (must fail until packages installed on path)
- [x] T013 [P] [US1] [GATE:no-secret-leak] Assert test/fixtures contain no credential-like strings

### Implementation for User Story 1

- [x] T014 [US1] Implement `Makefile` target `check` running ruff + typecheck + pytest
- [x] T015 [US1] Wire ruff/typechecker settings in `pyproject.toml` so `make check` is green on stubs
- [x] T016 [US1] Confirm `src/core` has no agent-framework dependencies in the resolved environment (FR-004)
- [x] T017 [US1] Update CONTRIBUTING Development setup if any command flags diverge from reality (FR-008)

**Checkpoint**: Scenario A passes locally

---

## Phase 4: User Story 2 - Repository map matches documented layout (Priority: P1)

**Goal**: Documented paths exist and are reserved correctly

**Independent Test**: Directory checks from quickstart Scenario B; harness README present

### Implementation for User Story 2

- [x] T018 [P] [US2] Verify AGENTS/CONTRIBUTING layout table paths all exist on disk (script or checklist in PR description)
- [x] T019 [P] [US2] Strengthen `tests/harness/README.md` language: fakes/assertions public API under semver once populated
- [x] T020 [US2] Ensure `tests/unit/test_core_import.py` (or sibling) documents that core import pulls no agent framework

**Checkpoint**: Scenario B passes; SC-004 reviewable

---

## Phase 5: User Story 3 - Stable make targets and PR fast-lane CI (Priority: P2)

**Goal**: Four make contracts + fast-lane workflow per contracts/

**Independent Test**: Scenario C (stub exits) + open PR runs CI (Scenario E)

### Implementation for User Story 3

- [x] T021 [US3] [GATE:fail-closed] Add `Makefile` targets `conformance`, `test-full`, `dev-up` that print clear stub messages and exit non-zero
- [x] T022 [US3] Create `.github/workflows/ci.yml` for `pull_request` → install (`uv sync`), `make check`, secret scan, DCO, license compliance
- [x] T023 [US3] Add conditional spec-artifact lint step when `specs/**` changes (fail on `[NEEDS CLARIFICATION` in touched specs)
- [x] T024 [US3] [GATE:no-secret-leak] Confirm workflow runs on forks without secrets; document any optional tokens as optional
- [x] T025 [US3] Manually or via act/CI verify stub targets are not reported as success in logs

**Checkpoint**: Scenarios C and E satisfied; SC-002/SC-003 met for workflow presence

---

## Phase 6: User Story 4 - Pre-commit hygiene (Priority: P3)

**Goal**: Local hooks for format/hygiene before push

**Independent Test**: Scenario D — `pre-commit install` + hooks run on commit

### Implementation for User Story 4

- [x] T026 [US4] Add `.pre-commit-config.yaml` with ruff format/check, EOF/whitespace fixers, secrets hook
- [x] T027 [US4] Verify `pre-commit install` works after `uv sync` / documented pipx path
- [x] T028 [US4] Align CONTRIBUTING pre-commit line with actual install if needed (FR-008)

**Checkpoint**: Scenario D passes

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs consistency and quickstart validation

- [x] T029 [P] Walk `specs/001-dev-toolchain/quickstart.md` Scenarios A–D on a clean clone/worktree
- [x] T030 [P] Confirm README `NOTICE` link resolves — **SKIPPED: NOTICE deferred; README no longer requires NOTICE for local development**
- [x] T031 [P] Add changelog note only if project changelog exists; otherwise skip
- [x] T032 Open `feat/001-dev-toolchain` PR using `.github/PULL_REQUEST_TEMPLATE.md`, link governing spec, delete branch on merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)** and **US2 (Phase 4)**: After Foundational; can proceed in parallel after T011
- **US3 (Phase 5)**: After US1 (`make check` must be real before CI calls it)
- **US4 (Phase 6)**: After Setup tool pins exist; can parallelize with US3 once ruff config exists
- **Polish (Phase 7)**: After US1–US4

### User Story Dependencies

- **US1 (P1)**: Foundational only
- **US2 (P1)**: Foundational only (layout mostly done in Phase 2; verification story)
- **US3 (P2)**: Needs US1 `make check`
- **US4 (P3)**: Needs Phase 1 tool config

### Parallel Opportunities

- T004–T009 after T001
- T012–T013 together
- T018–T019 together
- T022–T023 after T021

---

## Parallel Example: User Story 1

```bash
Task: "Add tests/unit/test_core_import.py smoke test"
Task: "Audit fixtures for secret-like strings"
# then
Task: "Implement Makefile check target"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2
2. Complete Phase 3 (US1)
3. **STOP and VALIDATE**: Scenario A
4. Demo: green `make check` on empty product

### Incremental Delivery

1. US1 → green inner loop
2. US2 → layout review sign-off
3. US3 → CI fast lane + stub make contracts
4. US4 → pre-commit
5. Polish + `feat/001` PR

### Notes

- Implement on branch `feat/001-dev-toolchain` after this plan/tasks PR merges
- Do not land sealed-core behavior in stubs
- Prefer lean pins; justify any new core dependency in the feat PR template
