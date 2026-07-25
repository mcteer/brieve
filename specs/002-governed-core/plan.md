# Implementation Plan: Governed Core MVP

**Branch**: `spec/002-governed-core` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-governed-core/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the first security-critical vertical of the harness core as a framework-agnostic
library: an in-process, fail-closed pre/post tool-hook pipeline; a minimal in-process tool
registry (registered vs unregistered, in-scope vs out-of-scope only); a single correlation
ID joining run initiation, hook decisions, tool records, audit entries, and OTel hook
spans; an append-only, per-run hash-chained audit sink (in-memory implementation + stable
interface); and the public `tests/harness` helpers named in TESTING.md
(`assert_denied_closed`, `assert_correlated`, `assert_audit_chain`,
`assert_no_secret_values`) plus `scripted_agent` / `capture_audit` fakes needed to prove
FR-001–FR-015 deterministically. No identity fabric, adapters, packs, durability, or
northbound surfaces.

## Technical Context

**Language/Version**: Python 3.12+ (floor from 001; typed; Pydantic models at every public boundary)

**Primary Dependencies**: Existing toolchain (`uv`, `ruff`, `mypy`, `pytest`). New runtime:
`pydantic` (boundary models), `opentelemetry-api` (hook-decision spans; ADR-0020). Dev/test:
`opentelemetry-sdk` with in-memory exporter for span assertions. Hash chaining via stdlib
`hashlib` (SHA-256). No agent frameworks, no vendor observability SDKs, no product APIs.

**Storage**: No durable product store. Append-only audit via a stable sink interface with an
in-memory implementation (`capture_audit`) sufficient for tests; provider-backed storage
deferred.

**Testing**: `pytest` unit + component tests under `tests/unit` and `tests/component`;
deterministic only (`scripted_agent`, fakes, `frozen_clock` if time is needed). Harness
helpers under `tests/harness` are public API (semver). No live models or live managed-product
APIs. Governance-order and fail-closed cases are the start of the conformance bar (full
`make conformance` suite still later).

**Target Platform**: Library consumed in-process on Linux/macOS contributor machines and CI
(`ubuntu-latest`); no network dependency for the MVP suite.

**Project Type**: Multi-package Python library (sealed core under `src/core`, harness under
`tests/harness`); exercised without adapters or surfaces.

**Performance Goals**: Hot-path pipeline must remain simple enough that the 002 suite stays
inside the existing `make check` / fast-lane budget; no separate throughput SLO in this
feature.

**Constraints**: Fail closed on every enforcement error (ADR-0006); governance/enforcement
runs first among co-resident hooks (ADR-0019); correlation ID mandatory at run start;
audit never sampled and hash-chained per run (ADR-0009); core emits OTel only (ADR-0020);
no secret values in audit/spans/logs; `src/core` must not import agent frameworks; sealed-core
+ attestation-relevant → security-maintainer review on the `feat/002` PR; lean dependency
additions require PR justification (Principle VI / CONTRIBUTING).

**Scale/Scope**: Single-run model; minimal registry (not R6/ADR-0037 lifecycle); in-memory
audit; test doubles for identity presence only if needed for fail-closed paths; warn-mode
hooks deferred (enforce/fail-closed is the 002 bar).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*
*A failing gate stops planning — redesign or withdraw the spec; do not proceed to research.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Framework-agnostic core only; no gateway/registry product; no adapter framework imports |
| II — Total Interception; One Governed Tool Layer | Pass | Sole supported tool-body path is the hooked pipeline; unregistered/out-of-scope deny; full MCP lifecycle deferred by design |
| III — Fail-Closed, In-Process Enforcement | Pass | Pre/post in-process; error → deny; governance-first order conformance-asserted |
| IV — Zero Standing Credentials; Authority Per Task | Pass | No credentials manufactured or stored; identity deferred to 003; no standing secrets introduced |
| V — Sealed Core, Versioned Seams | Pass | Touches hook engine, minimal registry, audit schema — approved spec; security-maintainer review on feat PR; harness helpers are the semver seam |
| VI — Lean by Default | Pass | In-memory audit + OTel API only; no collector/Postgres/IdP in 002; two justified runtime deps (pydantic, opentelemetry-api) |
| VII — Anti-Fragmentation | Pass | One core pipeline; no substrate forks |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs, prompts, models, or policies |
| IX — Evidence Over Claims | Pass | Correlation join, hash-chained audit, OTel spans for hook decisions, redaction of secret values |
| X — The Decision Record Governs | Pass | Traceability binds ADR-0001, 0006, 0009, 0019, 0020; plan does not contradict Accepted ADRs |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1 artifacts (`research.md`, `data-model.md`, `contracts/`,
`quickstart.md`): still **PASS**. Contracts encode fail-closed, correlation join, hash
chain, OTel-only emission, and exact harness helper names; structure keeps sealed behavior
in `src/core` and public assertions in `tests/harness` without introducing adapters,
credentials, or vendor SDKs.

## Project Structure

### Documentation (this feature)

```text
specs/002-governed-core/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── hook-pipeline.md
│   ├── audit-sink.md
│   └── harness-helpers.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
src/core/
├── __init__.py
├── py.typed
├── errors.py                 # typed domain exceptions (include correlation ID when known)
├── correlation.py            # CorrelationId type / validation (refuse empty/missing)
├── run.py                    # GovernedRun start; declared scope; refuse uncorrelated start
├── registry/
│   ├── __init__.py
│   └── memory.py             # minimal in-process ToolRegistry (name → handler + metadata)
├── hooks/
│   ├── __init__.py
│   ├── types.py              # HookDecision, Pre/Post protocols, capability kind
│   ├── engine.py             # pipeline: resolve → scope → pre (gov first) → exec → post
│   └── governance.py         # built-in governance/enforcement hook (always first)
├── audit/
│   ├── __init__.py
│   ├── schema.py             # AuditEntry fields + hash-chain link
│   ├── chain.py              # append + verify (SHA-256, no mutate)
│   └── sink.py               # AuditSink protocol + InMemoryAuditSink
├── telemetry/
│   ├── __init__.py
│   └── spans.py              # emit OTel span per hook decision (correlation as attribute)
└── tools/
    ├── __init__.py
    └── invoke.py             # public invoke_tool(run, name, args) — only entry to tool bodies

tests/harness/
├── __init__.py               # export public helpers (semver seam)
├── README.md                 # document exact helper names + fakes
├── assertions.py             # assert_denied_closed, assert_correlated, assert_audit_chain,
│                             # assert_no_secret_values (+ assert_hook_order if needed for SC-006)
├── scripted_agent.py         # fixed tool-call sequences
├── capture_audit.py          # thin wrapper / factory over InMemoryAuditSink
├── fake_registry.py          # optional test helpers for registration
└── secrets.py                # known fixture markers for assert_no_secret_values (no plausible secrets)

tests/unit/                   # focused units: chain verify, registry, redaction, correlation refuse
tests/component/              # US1–US5 scenarios end-to-end through invoke_tool

# Unchanged in 002 (still out of scope):
src/adapters/                 # empty stubs
src/surfaces/                 # empty stubs
hooks/, packs/, providers/, portal/
```

**Structure Decision**: Expand sealed behavior under `src/core` (AGENTS map) with a single
public invocation entry (`tools.invoke`). Keep `tests/harness` as the versioned assertion
seam. No adapter, surface, or provider implementation in this feature. Contracts document
the pipeline, audit sink, and harness API rather than HTTP/CLI schemas.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
