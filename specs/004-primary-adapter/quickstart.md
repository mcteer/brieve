# Quickstart validation: Primary Adapter

**Feature**: `specs/004-primary-adapter`
**Purpose**: Prove FR-001–FR-016 end-to-end after `feat/004-primary-adapter` lands.
**Not**: an implementation guide with full module bodies (see `tasks.md`).

Contracts: [four-mappings](./contracts/four-mappings.md),
[governance-capability](./contracts/governance-capability.md),
[conformance-adapter](./contracts/conformance-adapter.md). Model: [data-model](./data-model.md).

## Prerequisites

- `main` includes 002 governed core and 003 per-task authority
- Python 3.12+, `uv`, `make`
- `uv sync --extra adapters` (required for `make check` and `make conformance` after 004 —
  installs `pydantic-ai-slim` via `[project.optional-dependencies] adapters`; do not rely on
  a bare `uv sync` for the inner loop)
- No Docker, live IdP, Vault, collector, or live model API keys required

## Scenario A — Adapter allow path (US1)

```bash
uv sync --extra adapters
pytest tests/component/test_adapter_allow.py -q
```

**Expect**:

- `start_adapter_run` (or equivalent) binds `GovernedRun` + `AdapterRunContext`
- Scripted/stub-model tool call through the adapter allows once
- Audit trail joinable by correlation ID; `assert_scope_narrowed` holds
- No secret values in audit/spans/model-visible context

## Scenario B — Adapter deny path (US2)

```bash
pytest tests/component/test_adapter_deny.py -q
```

**Expect**: unregistered / out-of-scope / authority-insufficient through adapter → deny;
`assert_denied_closed` + `assert_no_side_effect`; correlated audit denial; deny messages
leak no secrets/entitlements (FR-013). Broker/federate mirroring through adapter:
missing entitlement → deny + zero wields (FR-005).

## Scenario C — Governance order + fail closed (US3)

```bash
make conformance
# or: pytest tests/conformance/adapter -q
```

**Expect**:

- Governance observed before co-resident probe capability
- Injected governance/mapping fault → deny, zero executions
- Break fixture with inverted order fails when run intentionally

## Scenario D — Four-mapping / definition plumbing (US4)

```bash
pytest tests/unit/test_adapter_mappings.py tests/component/test_adapter_definition_ceiling.py -q
```

**Expect**:

- Tool mapping delegates to `invoke_tool` (probe/counter)
- Blank or unknown `agent_definition_id` refuses start
- Per-definition ceiling fake keys distinct ceilings
- Durability save payload contains no credential/`run_salt` material
- Approval hook default denies interrupt path without ungoverned execution

## Scenario E — Inner loop still green

```bash
make check
```

**Expect**: lint, typecheck, unit+component suites pass with adapters extra available to
tests that need it; `src/core` import graph still free of `pydantic_ai`.

## Scenario F — Core does not import the framework

```bash
pytest tests/unit/test_core_import.py -q
# plus adapter-specific guard if added
```

**Expect**: core import smoke still passes; no agent-framework modules imported from
`core`.

## Scenario G — No live dependencies (FR-012)

```bash
pytest tests/unit/test_no_live_dependencies.py -q
```

**Expect**: no module under the feature's test paths imports a live-network client (HTTP
client, model SDK, IdP, or Vault client), and no adapter test resolves a real model
provider. Determinism is asserted, not assumed.

## Scenario H — Conformance is merge-blocking (FR-015)

```bash
grep -A2 'Inner-loop check' .github/workflows/ci.yml   # conformance step present
gh pr checks                                           # from an adapter-touching branch
```

**Expect**: the fast lane syncs with `--extra adapters` and runs `make conformance`; a
deliberately broken governance order fails the check, not just a local run. A passing
result pasted into a PR description is a pre-flight, never the gate.

## Mapping to user stories

| Story | Scenarios |
| --- | --- |
| US1 allow | A |
| US2 deny | B |
| US3 governance-first + fail closed | C |
| US4 four mappings only | D, F |
| US5 conformance command | C, E, H |
| Cross-cutting (FR-012 determinism) | G |
