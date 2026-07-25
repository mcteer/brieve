# Research: Developer Toolchain Scaffold

**Feature**: `specs/001-dev-toolchain`  
**Date**: 2026-07-24

## Decision: Package manager and lockfile

- **Decision**: Use `uv` with a root `pyproject.toml` and committed `uv.lock`. Documented install remains `uv sync`.
- **Rationale**: Already normative in CONTRIBUTING; fast, reproducible, regulated operators get a lockfile for review.
- **Alternatives considered**: Poetry (heavier, not documented); pip-tools alone (no single documented sync story matching CONTRIBUTING).

## Decision: Packaging layout

- **Decision**: Installable packages under `src/core`, `src/adapters`, `src/surfaces` via a uv workspace or src-layout discovery so `import core` / `import adapters` / `import surfaces` (or `from core import …`) works in tests. Prefer explicit package names matching directory names (`core`, `adapters`, `surfaces`) without a conflicting top-level `src` package.
- **Rationale**: Matches AGENTS repository map; keeps core importable for FR-004 smoke without frameworks. A future rename to a branded namespace (product name is TBD per ADR-0028) would be a breaking seam change and rides the deprecation process; the bare names are accepted as stable for now.
- **Alternatives considered**: Nested `harness_core` naming (extra rename vs docs); deferring installable packages (fails US2 independent test).

## Decision: Linter / formatter

- **Decision**: `ruff` for lint and format (replaces flake8/isort/black).
- **Rationale**: One tool, fast, lean dependency tree (Principle VI).
- **Alternatives considered**: black+isort+flake8 (more moving parts); biome (not Python-primary).

## Decision: Type checker

- **Decision**: `mypy` in strict-ish mode for the stub packages. Record the chosen pin in `pyproject.toml` during `feat/001`.
- **Rationale**: Typed Python is required by CONTRIBUTING; stubs still benefit from a green typecheck in `make check`.
- **Alternatives considered**: `ty` (Astral) — revisit via ordinary PR when stable; not part of 001; pyright-only (Node-adjacent tooling); no typecheck until product code (weakens FR-002 contract).

## Decision: Test runner and smoke test

- **Decision**: `pytest`; one unit smoke test that imports `core` and asserts no agent-framework modules are imported as dependencies of that package.
- **Rationale**: Satisfies FR-002/FR-004 with deterministic tests (TESTING.md).
- **Alternatives considered**: unittest stdlib only (less ergonomic for later suites); skipping tests until product code (fails green-check story).

## Decision: Stub make-target semantics

- **Decision**: `conformance`, `test-full`, and `dev-up` print a clear message to stderr and exit with code `2` (misuse/not implemented), never `0`. `check` runs the real inner loop and exits `0` on success.
- **Rationale**: FR-005 requires fail-closed stubs — no silent success implying suites passed.
- **Alternatives considered**: exit `0` with warning (rejected by spec); missing targets (fails SC-003).

## Decision: Secret scanning

- **Decision**: Prefer `gitleaks` in CI (official action) and a light pre-commit hook; no custom secret patterns that embed plausible secrets in fixtures.
- **Rationale**: FR-006/FR-010; works on forks without privileged secrets.
- **Alternatives considered**: GitHub secret scanning alone (less portable locally); trufflehog (heavier).

## Decision: DCO verification

- **Decision**: CI job using a DCO check action against PR commits; CONTRIBUTING already requires `Signed-off-by`.
- **Rationale**: FR-006; aligns with Apache/DCO posture in README.
- **Alternatives considered**: Manual review only (not automated); CLA bot (README says no separate CLA).

## Decision: License compliance

- **Decision**: CI step using `pip-licenses` with an in-repo allowlist config; inventories runtime/dev dependencies and fails on GPL/AGPL/BUSL/SSPL family per CONTRIBUTING supply-chain rules.
- **Rationale**: FR-006; CONTRIBUTING already states license CI check.
- **Alternatives considered**: `uv tree` + custom allowlist script; `licensecheck`; defer until first third-party dep beyond tooling (risks drift); FOSSA SaaS (adds operated dependency — Principle VI).

## Decision: Spec-artifact lint

- **Decision**: When CI detects changes under `specs/`, run a small check that required files exist for numbered feature dirs (`spec.md`) and that `[NEEDS CLARIFICATION` markers are absent on `main`-bound PRs (warn or fail — prefer fail).
- **Rationale**: FR-006 conditional lint; cheap guardrail for Spec Kit workflow.
- **Alternatives considered**: Full markdown lint suite (out of scope); no check (weaker FR-006).

## Decision: Pre-commit hooks

- **Decision**: `.pre-commit-config.yaml` with ruff (format+check), trailing whitespace, end-of-file fixer, and a secrets hook. Document `pre-commit install` (already in CONTRIBUTING).
- **Rationale**: FR-007; reduces CI thrash.
- **Alternatives considered**: Format-only in CI (worse local DX); husky/Node (wrong ecosystem for 001).

## Decision: NOTICE file

- **Decision**: Add a minimal Apache-2.0 `NOTICE` if still absent when implementing, because README already references it.
- **Rationale**: Doc/license honesty; trivial.
- **Alternatives considered**: Remove README reference (broader doc churn; out of scope preference).

## Decision: CI trigger

- **Decision**: Workflow on `pull_request` to `main` (required for SC-002). Optionally also `push` to `main` for continuity; not required by spec.
- **Rationale**: SC-002 is PR-centric; fork PRs must run without secrets.
- **Alternatives considered**: push-only (misses fork PRs); workflow_dispatch only (fails SC-002).
