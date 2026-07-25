# Data Model: Developer Toolchain Scaffold

**Feature**: `specs/001-dev-toolchain`
**Date**: 2026-07-24

This feature has no persistent runtime data store. Entities are contributor-facing contracts and layout reservations.

## Entities

### Inner-loop check

| Attribute | Description |
| --- | --- |
| Command | `make check` |
| Steps | lint (ruff), typecheck, unit tests (pytest smoke) |
| Success | exit code 0 |
| Failure | non-zero; no external services required |

**Validation**: Must succeed on a fresh `uv sync` with zero product features (FR-002, FR-009).

### Fast lane (CI)

| Attribute | Description |
| --- | --- |
| Trigger | every pull request targeting `main` |
| Steps | dependency install; inner-loop check; secret scan; DCO verification; license compliance; spec-artifact lint if `specs/` changed |
| Privileges | none required (fork-safe) |

**Validation**: Workflow present and executes on PRs (FR-006, SC-002). Branch protection enablement is out of band.

### Stub make target

| Attribute | Description |
| --- | --- |
| Names | `conformance`, `test-full`, `dev-up` |
| Behavior | stderr message stating not implemented / stub; exit code ≠ 0 |
| Forbidden | exit 0 while claiming suite success |

**Validation**: FR-005, SC-003, edge cases for Docker/`dev-up`.

### Package layout stub

| Path | Role | Marker |
| --- | --- | --- |
| `src/core/` | Sealed core (empty) | `__init__.py`, `py.typed`, SPDX |
| `src/adapters/` | Framework adapters (empty) | same |
| `src/surfaces/` | Transports (empty) | same |
| `tests/harness/` | Future fakes/assertions (semver seam) | `__init__.py` + README |
| `packs/`, `hooks/`, `providers/`, `portal/` | Extension / portal reservation | README only |

**Validation**: FR-003, FR-004 (core has no agent-framework imports); portal has no Node toolchain files.

### Per-file license notice

| Attribute | Description |
| --- | --- |
| Form | `SPDX-License-Identifier: Apache-2.0` |
| Applies to | Every source file introduced by this feature |

**Validation**: FR-011.

## Relationships

```text
Contributor --runs--> Inner-loop check
CI Fast lane --includes--> Inner-loop check
CI Fast lane --includes--> Stub-independent gates (secrets, DCO, licenses)
Package layout stub --hosts--> future sealed-core / extension code
tests/harness --will-provide--> fakes used by later Inner-loop / Full tiers
```

## State transitions

Not applicable (no durable entities). Stub targets remain in `stub` state until a later feature replaces their Makefile recipes.
