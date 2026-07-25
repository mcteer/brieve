# Contract: Make targets

**Feature**: `specs/001-dev-toolchain`  
**Audience**: Contributors and CI  
**Stability**: Target **names** are stable (CONTRIBUTING); recipes may evolve.

## Targets

| Target | Semantics | Exit codes |
| --- | --- | --- |
| `make check` | Inner-loop: format/lint, typecheck, unit tests | `0` success; non-zero on failure |
| `make conformance` | Reserved for adapter/provider conformance suite | Stub: non-zero (prefer `2`) + stderr explanation until suite exists |
| `make test-full` | Reserved for PR-tier suites (integration, scenario, fault, adversarial) | Stub: non-zero + stderr until suites exist |
| `make dev-up` | Reserved for local stack (identity fabric, Postgres, collector, harness) | Stub: non-zero + stderr; MUST NOT mutate remote/production environments |

## Invariants

1. All four names are defined in the root `Makefile` after this feature merges.
2. Stub targets never exit `0`.
3. `make check` does not require Docker, cloud credentials, live models, or product APIs.
4. `make check` does not import or depend on agent frameworks from `src/core`.

## Related docs

- [CONTRIBUTING.md](../../../CONTRIBUTING.md) — Development setup
- [../spec.md](../spec.md) — FR-005, SC-003
