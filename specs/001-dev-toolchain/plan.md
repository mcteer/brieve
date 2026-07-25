# Implementation Plan: Developer Toolchain Scaffold

**Branch**: `spec/001-dev-toolchain` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-dev-toolchain/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Establish the contributor toolchain promised by CONTRIBUTING/AGENTS: a `uv`-managed typed Python workspace with the documented package layout as importable stubs, `make check` as a green inner loop (ruff + mypy + pytest smoke), named stub targets for `conformance` / `test-full` / `dev-up`, pre-commit hygiene, and a GitHub Actions fast-lane workflow covering install, inner-loop check, secret scan, DCO, license compliance, and conditional spec-artifact lint. No product behavior, identity fabric, hooks, adapters, packs, or portal toolchain.

## Technical Context

**Language/Version**: Python 3.12+ (floor from clarified spec)

**Primary Dependencies**: `uv` (package/workspace manager); `ruff` (lint + format); `mypy` (static types, strict-ish); `pytest` (unit smoke); `pre-commit`; GitHub Actions for CI; secret scanning via `gitleaks`; DCO via `probot/dco` or `action-dco`; license compliance via `pip-licenses` with an in-repo allowlist

**Storage**: N/A

**Testing**: `pytest` for unit smoke; component/contract tiers reserved under `tests/` but empty until later features

**Target Platform**: Linux and macOS contributor machines; Windows via WSL2; CI on `ubuntu-latest`

**Project Type**: Multi-package Python library/workspace (governed harness monorepo scaffold) with Make contracts and GitHub Actions

**Performance Goals**: Fresh clone → `uv sync` → `make check` under 15 minutes on a typical laptop (SC-001); fast-lane CI under 5 minutes when suites are still smoke-level

**Constraints**: No live models, identity fabric, or product APIs for check/CI; `src/core` must not import agent frameworks; SPDX one-line headers on new source files; stub make targets must not silently succeed; lean dependency tree (Principle VI)

**Scale/Scope**: Toolchain + layout stubs only; portal is a reserved directory without Node toolchain; branch protection enabling is out of band

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*
*A failing gate stops planning — redesign or withdraw the spec; do not proceed to research.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Scaffolds layout for adopt-first core; no gateway/registry product; no framework logic in core stubs |
| II — Total Interception; One Governed Tool Layer | N/A | No tools, transports, or egress introduced |
| III — Fail-Closed, In-Process Enforcement | Pass | Incomplete make targets fail with explicit stub messages (not silent success); no enforcement bypass paths |
| IV — Zero Standing Credentials; Authority Per Task | Pass | Fast lane needs no privileged secrets; no standing credentials introduced |
| V — Sealed Core, Versioned Seams | Pass | Empty/marker stubs only; security-maintainer gate deferred until behavior lands (spec FR-003); `tests/harness` reserved as future semver seam |
| VI — Lean by Default | Pass | Minimal toolchain deps; stub targets instead of standing up unused stacks; no Node toolchain in 001 |
| VII — Anti-Fragmentation | Pass | Single layout and command contract for all substrates later |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs, prompts, models, or policies |
| IX — Evidence Over Claims | N/A | No audit/correlation plane in this feature |
| X — The Decision Record Governs | Pass | Traceability cites Accepted ADRs 0001, 0007, 0017; layout follows AGENTS repository map |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1 artifacts: still **PASS**. Contracts document fail-closed stub semantics and secret-free CI; structure matches sealed-core boundaries without implementing sealed behavior.

## Project Structure

### Documentation (this feature)

```text
specs/001-dev-toolchain/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── make-targets.md
│   └── ci-fast-lane.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
pyproject.toml                 # uv workspace root; Python >=3.12; ruff/pytest/mypy config
uv.lock                        # committed lockfile
Makefile                       # check, conformance, test-full, dev-up
.pre-commit-config.yaml
.github/workflows/ci.yml       # fast lane on pull_request (+ push optional)
NOTICE                         # if still missing; Apache attribution (README already cites it)

src/
├── core/
│   ├── __init__.py            # SPDX; package marker; no framework imports
│   └── py.typed               # typed package marker
├── adapters/
│   ├── __init__.py
│   └── py.typed
└── surfaces/
    ├── __init__.py
    └── py.typed

tests/
├── harness/
│   ├── __init__.py
│   └── README.md              # reserved: shared fakes / assertion helpers (semver seam)
├── unit/
│   └── test_core_import.py    # smoke: `import core` succeeds (src-layout; `src` is not a package)
├── component/                 # reserved empty (.gitkeep)
├── contract/                  # reserved empty (.gitkeep)
└── integration/               # reserved empty (.gitkeep)

packs/
├── README.md                  # reserved extension point
hooks/
├── README.md
providers/
├── README.md
portal/
└── README.md                  # reserved stub only — no package.json / Node toolchain

# Optional packaging layout if uv workspace members are preferred:
# packages may remain under src/ via tool.uv.package or src layout with
# package discovery — see research.md Decision: packaging layout.
```

**Structure Decision**: Single repository root with `src/{core,adapters,surfaces}` packages (AGENTS layout), `tests/harness` as reserved public-API seam, extension roots as README stubs, Make + GitHub Actions as the contributor contracts. No Option-2/3 web/mobile split.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
