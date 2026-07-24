# Feature Specification: Developer Toolchain Scaffold

**Feature Branch**: `spec/001-dev-toolchain`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Contributors and agents need a minimal, reproducible development toolchain so every later feature can land behind the same quality gates. The project must provide a Python package layout matching the documented repository map (`src/core`, `src/adapters`, `src/surfaces`, `tests/harness`, etc. as empty-or-stub packages), dependency management via `uv`, the stable commands `make check` / `make conformance` / `make test-full` / `make dev-up` as documented contracts (stubs acceptable where no code exists yet), pre-commit hygiene, and CI that runs the fast lane on every PR. Success means a fresh clone can install and run the inner-loop check with zero product features implemented. Out of scope: identity fabric, hooks, adapters, packs, portal UI, live model calls."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R12 (lean default posture for what we operate and add), R16 (versioned seams / sealed-core layout boundaries). Others not implicated. |
| **ADRs touched** | ADR-0001 (framework-agnostic core and layout boundaries), ADR-0007 (lean profile as default), ADR-0011 (harness-first; SDKs at perimeter — layout implication only) |
| **Evidence class** | N/A — toolchain and contributor contract only; no attestation or compliance evidence plane |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh clone reaches a green inner loop (Priority: P1)

A new contributor (human or coding agent) clones the repository on a supported platform, installs project dependencies with the documented package manager, and runs the documented inner-loop check command. The check completes successfully even though no product features exist yet — empty or stub packages and a trivial smoke test are enough.

**Why this priority**: Without a reproducible install-and-check path, every later feature PR invents its own toolchain and the contributor contract in CONTRIBUTING.md is fiction.

**Independent Test**: On a clean machine (or clean CI job), clone → install → run inner-loop check → exit success. No identity fabric, models, or product APIs required.

**Acceptance Scenarios**:

1. **Given** a fresh clone of `main` after this feature merges, **When** the contributor follows the documented install steps, **Then** dependencies install without undocumented manual steps.
2. **Given** dependencies are installed, **When** the contributor runs the documented inner-loop check, **Then** the command exits successfully (lint/typecheck/unit smoke as defined by that contract).
3. **Given** the repository has no product features yet, **When** the inner-loop check runs, **Then** it still succeeds using stubs/placeholders rather than requiring live services or models.

---

### User Story 2 - Repository map matches documented layout (Priority: P1)

A contributor opening the tree finds the package and test directories named in AGENTS.md / CONTRIBUTING.md (`src/core`, `src/adapters`, `src/surfaces`, `tests/harness`, and the other extension points called out there) present as importable packages or documented stubs, so later specs can land code without inventing a conflicting layout.

**Why this priority**: Layout drift between docs and tree is a common source of review friction and sealed-core boundary mistakes.

**Independent Test**: Inspect the tree and import paths against the documented repository map; every required path exists and is reserved for its stated role.

**Acceptance Scenarios**:

1. **Given** the documented repository map, **When** a contributor lists the project root, **Then** each required top-level area exists (packages may be empty stubs).
2. **Given** a stub package under `src/core`, **When** a minimal unit smoke test imports it, **Then** the import succeeds without pulling in an agent framework.
3. **Given** extension-point directories (`packs/`, `hooks/`, `providers/`, `portal/` as applicable), **When** present as stubs, **Then** README or package markers state they are reserved extension points, not product logic.

---

### User Story 3 - Stable make targets and PR fast-lane CI (Priority: P2)

A contributor discovers the same four make targets documented in CONTRIBUTING (`check`, `conformance`, `test-full`, `dev-up`). Targets that cannot yet do real work still exist as named contracts and fail clearly or no-op with an explicit message — they are not silently missing. Continuous integration runs the fast lane (equivalent to the inner-loop check) on every pull request.

**Why this priority**: Named contracts prevent each PR from inventing scripts; CI makes the contract non-optional for merges.

**Independent Test**: `make -n` / help or running each target shows the contract exists; opening a PR triggers the fast-lane workflow.

**Acceptance Scenarios**:

1. **Given** a developer machine with the toolchain installed, **When** they invoke each of `make check`, `make conformance`, `make test-full`, and `make dev-up`, **Then** each target is defined (stub behavior with a clear message is acceptable where no backing implementation exists yet).
2. **Given** a pull request against `main`, **When** CI runs, **Then** the fast lane (install + inner-loop check) executes and must pass for the PR to be mergeable once branch protection is enabled.
3. **Given** `make conformance` or `make test-full` has no suite yet, **When** a contributor runs it, **Then** the outcome is an explicit stub/skip message — not a missing-target error and not a silent success that implies suites passed.

---

### User Story 4 - Pre-commit hygiene on contributed changes (Priority: P3)

A contributor installs pre-commit hooks once and, on commit, automatic formatting and hygiene checks run so style and secret-scanning basics are consistent before CI.

**Why this priority**: Reduces CI thrash; secondary to a green `make check` path.

**Independent Test**: Install hooks, make a trivial whitespace change, commit, observe hooks run (or document the install command and verify config exists).

**Acceptance Scenarios**:

1. **Given** a clone with dependencies installed, **When** the contributor runs the documented pre-commit install command, **Then** hooks are registered for subsequent commits.
2. **Given** hooks are installed, **When** a commit introduces a formatting violation covered by the hook set, **Then** the commit is rejected or auto-fixed per hook policy before it lands unclean.

### Edge Cases

- What happens when a contributor uses an unsupported Python version? Install or check fails with a clear version requirement — not an opaque stack trace alone.
- What happens when `make dev-up` is invoked before any local stack exists? A clear "not implemented yet" / stub message; it must not attempt to mutate a production environment.
- What happens when CI runs on a fork without secrets? Fast lane still runs with no privileged credentials required.
- How does the system handle missing optional tools (e.g. Docker) for stub targets? Stub targets that need them say so; `make check` must not require them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Contributors MUST be able to install project dependencies with a single documented package-manager workflow after clone.
- **FR-002**: The repository MUST expose an inner-loop check command that succeeds on a fresh install with zero product features implemented.
- **FR-003**: The repository MUST provide the documented package layout areas as present stubs or packages: at minimum `src/core`, `src/adapters`, `src/surfaces`, `tests/harness`, plus reserved extension roots called out in contributor docs (`packs/`, `hooks/`, `providers/`, `portal/` as stubs where not yet built).
- **FR-004**: `src/core` MUST remain free of agent-framework imports in any code introduced by this feature (including stubs).
- **FR-005**: The four make targets `check`, `conformance`, `test-full`, and `dev-up` MUST exist as named contracts; incomplete targets MUST fail closed with an explicit stub message rather than being undefined.
- **FR-006**: Pull-request CI MUST run the fast lane (install + inner-loop check) on every PR.
- **FR-007**: The project MUST ship a pre-commit configuration and documented install step for local hygiene hooks.
- **FR-008**: Toolchain documentation in CONTRIBUTING (or linked setup section) MUST match the commands that actually exist after this feature merges.
- **FR-009**: No live model provider, identity fabric, or managed-product API MUST be required to complete install or the inner-loop check.
- **FR-010**: Secret-like values MUST NOT appear in toolchain config, fixtures, or CI logs introduced by this feature.

### Key Entities

- **Inner-loop check**: The single documented command contributors run before every commit; encompasses lint, typecheck, and unit smoke as one contract.
- **Fast lane (CI)**: The PR-required automation equivalent to install + inner-loop check.
- **Stub make target**: A named make target that documents a future contract and exits with an explicit non-success or clearly labeled stub status when the real suite/stack is absent.
- **Package layout stub**: An importable or clearly marked directory reserved for a documented role, containing no product behavior yet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor completes clone → install → successful inner-loop check in under 15 minutes on a supported platform (excluding network faults).
- **SC-002**: 100% of pull requests against `main` execute the fast-lane CI workflow after this feature merges (workflow present and triggered on `pull_request`).
- **SC-003**: All four documented make contracts (`check`, `conformance`, `test-full`, `dev-up`) are invocable by name; zero "missing target" failures.
- **SC-004**: A reviewer can map every path in the documented repository layout table to an on-disk directory without gaps for the areas listed in FR-003.
- **SC-005**: Inner-loop check and fast-lane CI require no credentials, live models, or external product estates.

## Assumptions

- Supported contributor platforms remain Linux and macOS natively, Windows via WSL2, as stated in CONTRIBUTING.
- Python 3.12+ is an acceptable default runtime pin unless a later sealed-core decision narrows it; the exact minor version is an implementation detail for the plan stage.
- `uv` is the package manager implied by existing contributor docs; this feature makes that real rather than choosing a different tool.
- Stubbing `conformance`, `test-full`, and `dev-up` is acceptable until later specs implement suites and the local stack.
- Portal TypeScript tooling may be a nested stub (`portal/` with a placeholder) without a full Node toolchain in 001, as long as the directory is reserved and documented.
- Enabling GitHub branch protection to require the fast-lane check is desirable but may be a maintainer settings step outside the repository files; the workflow file itself is in scope.
- No product ADRs beyond layout/lean posture are implemented by this feature.
