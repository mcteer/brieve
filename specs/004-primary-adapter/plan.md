# Implementation Plan: Primary Adapter

**Branch**: `spec/004-primary-adapter` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-primary-adapter/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Deliver the primary (Pydantic AI) adapter as sealed-core glue on top of landed 002/003:
map exactly four framework concepts onto core (tools → `invoke_tool`; state → thin
durability seam; interrupts → thin approval-hook path; run context → identity +
correlation + agent-definition id); expose a `GovernanceCapability` that always runs
first among co-resident capabilities and fails closed; start adapter runs through
`start_governed_run` (authority + audit join preserved); make `make conformance` execute
real primary-adapter governance-order and fail-closed cases. No second adapter, no
northbound surfaces, no full durability/resume product, no live models or IdP.

## Technical Context

**Language/Version**: Python 3.12+ (existing floor); fully typed; Pydantic models at
adapter/public boundaries; `src/core` remains free of agent-framework imports

**Primary Dependencies**: Existing (`pydantic`, `opentelemetry-api`). **New (justified)**:
`pydantic-ai-slim==2.18.0` under **`[project.optional-dependencies] adapters`** (not a uv
`dependency-groups` entry — `dev` stays a group). Slim, not the `pydantic-ai` meta package:
the meta resolves to `pydantic-ai-slim[anthropic,cli,evals,google,logfire,mcp,openai,…]`,
installing three live model-provider SDKs a feature that calls no model has no use for
(Principle VI; FR-012). Install with `uv sync --extra adapters`. **Floor consequence**:
slim requires `pydantic>=2.12` and `opentelemetry-api>=1.28`, above this project's `>=2.10`
and `>=1.27`, so with-extra and without-extra environments resolve differently until the
base pins are raised — settle at implement time (T002).
ADR-0017 primary adapter; Principle VI — not loaded into core import graph. Pin at
implement time with PR justification for the regulated dependency tree. CI and
contributor `make check` / `make conformance` always sync with `--extra adapters`.
Dev/test: `pytest`, `opentelemetry-sdk`, framework TestModel / FunctionModel (or
equivalent stub) — no live model API keys.

**Storage**: No durable credential store. Thin durability seam uses in-memory / noop
provider fakes; checkpoints/state blobs MUST NOT carry credential secret values
(ADR-0026). Audit continues via 002 `AuditSink`.

**Testing**: `pytest` unit + component under `tests/`; new `tests/conformance/adapter/`
lane. Harness: existing fakes/helpers + adapter builders; stub/scripted model paths only.
`make conformance` runs the conformance lane (no longer exit-2 stub for this path).

**Target Platform**: In-process library on contributor machines and CI; hermetic suite

**Project Type**: Sealed-core adapter package (`src/adapters/pydantic_ai/…`) importing
`core`; optional thin core protocol extensions (agent-definition on fabric; durability /
approval seam stubs) with no framework imports in `src/core`

**Performance Goals**: N/A — success is `make check` + `make conformance` green, not a
latency SLO

**Constraints**: Four mappings only (ADR-0001); core never imports the framework;
governance-first + fail-closed conformance-asserted (ADR-0019/0006); no adapter bypass
around `invoke_tool`; scopes/authority only via 003 core; least context across seams
(003 post-impl); sealed-core + security-maintainer review on `feat/004`; lean — framework
dep stays out of the core import path

**Scale/Scope**: Single primary adapter; single-user → single-run model; thin durability
and approval mappings with fakes; LangGraph / packs / northbound / multi-tenancy /
code mode out of scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.0.1** (Quality Gates scoped by ADR-0047; re-check if the version
advances).*
*A failing gate stops planning — redesign or withdraw the spec; do not proceed to research.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Adapter is four-mapping glue onto `invoke_tool` (MCP transport deferred); core stays framework-agnostic; no gateway/registry product |
| II — Total Interception; One Governed Tool Layer | Pass | Framework tools route only through `invoke_tool`; no ungoverned tool-body path |
| III — Fail-Closed, In-Process Enforcement | Pass | GovernanceCapability first + fail closed; conformance-asserted; errors deny |
| IV — Zero Standing Credentials; Authority Per Task | Pass | Adapter starts runs via 003 manufacture; no standing product creds; state mapping forbids credential persistence |
| V — Sealed Core, Versioned Seams | Pass | Adapters are sealed core; approved spec; security-maintainer on feat PR; conformance validates seam. Core changes capped at three by FR-016; the required `agent_definition_id` is a breaking seam change, exempt from a deprecation window only because the project is pre-1.0 with no external consumers (recorded in spec Assumptions) |
| VI — Lean by Default | Pass | Framework dep optional (`adapters` extra); no new operated service; durability is thin library seam/fake |
| VII — Anti-Fragmentation | Pass | One adapter lane over one core; substrate deltas none for 004 |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs/models/policies promotion |
| IX — Evidence Over Claims | Pass | Adapter-started runs keep 002/003 correlation + audit join; secrets never in evidence |
| X — The Decision Record Governs | Pass | Binds ADR-0001, 0017, 0019, 0006, **0047** (gate rows attach as features land — sets which Quality Gate rows are in force here); defers 0024 depth / 0040 / 0041 productization, each row citing its deferring ADR in `contracts/conformance-adapter.md` |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1 artifacts: still **PASS**. Contracts pin four-mapping surface,
GovernanceCapability ordering, `invoke_tool`-only tool execution, agent-definition on
run start, thin durability/approval seams without credential persistence, and
conformance command behavior; structure keeps framework imports exclusively under
`src/adapters/pydantic_ai` and fakes under `tests/harness` / `tests/conformance`.

Re-checked again after the 2026-07-25 clarification session (constitution v1.0.1, spec
FR-015/FR-016, amended FR-012): still **PASS**, and two gates got stronger rather than
weaker. Principle IX — conformance is now enforced in CI (FR-015) rather than attested in
a PR description. Principle V — core changes are enumerated and capped (FR-016), so a
fourth sealed-core change is visible at review instead of arriving as a task. Principle
III is unchanged: nothing in this round touches enforcement ordering or fail-closed
behavior. No new violations; Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-primary-adapter/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── four-mappings.md
│   ├── governance-capability.md
│   └── conformance-adapter.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
src/adapters/
├── __init__.py
└── pydantic_ai/
    ├── __init__.py                 # public adapter exports
    ├── agent.py                    # build_governed_agent / start helpers
    ├── governance.py               # GovernanceCapability (framework capability)
    ├── tools.py                    # toolset → invoke_tool mapping
    ├── run_context.py              # deps: GovernedRun, identity, correlation, definition id
    ├── durability.py               # state → DurabilityProvider seam (thin)
    └── approvals.py                # interrupts → ApprovalHook path (thin)

src/core/
├── authority/
│   └── fabric.py                   # resolve_ceiling(agent_definition_id=…) (narrow extend)
├── run.py                          # start_governed_run(…, agent_definition_id=…)
├── durability/                     # thin protocol + memory default (providers/ later)
│   ├── __init__.py
│   ├── types.py                    # CheckpointBlob protocol/types (no credentials)
│   └── memory.py                   # InMemoryDurabilityProvider fake/default
└── approvals/
    ├── __init__.py
    └── types.py                    # ApprovalHook protocol; deny-by-default fake

tests/harness/
├── …                               # existing fakes/helpers
└── adapter_fixtures.py             # stub model + governed agent builders (optional)

tests/conformance/
├── __init__.py
└── adapter/
    ├── test_governance_order.py    # SC-003 order
    └── test_fail_closed.py         # SC-003 fail-closed

tests/component/                    # US1–US2 adapter allow/deny through agent path
tests/unit/                         # mapping purity / definition id plumbing
└── test_no_live_dependencies.py    # FR-012 import guard (no live model/IdP/Vault client)

Makefile                            # UV_RUN := uv run --extra adapters; conformance → pytest tests/conformance
pyproject.toml                      # optional-dependencies.adapters = [pydantic-ai-slim==2.18.0]; uv.lock regenerated
.github/workflows/ci.yml            # FR-015: sync --extra adapters; make conformance step (merge-blocking)
```

**Structure Decision**: Keep all framework imports under `src/adapters/pydantic_ai`.
Minimal core extensions only where 003 already anticipated them (per-definition ceiling
parameter) or where a framework-agnostic seam is required (durability/approval
protocols). Durability’s thin protocol lives in `src/core/durability/` for 004; a
`providers/` binding follows with full ADR-0024 depth. Tool mapping targets `invoke_tool`
— not an MCP client (northbound deferred). No Option-2/3 web split.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
