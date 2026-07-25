# Research: Primary Adapter

**Feature**: `specs/004-primary-adapter`
**Date**: 2026-07-25

## Decision: Package boundary and dependency shape

- **Decision**: Implement the primary adapter under `src/adapters/pydantic_ai/`.
  Declare `pydantic-ai` under **`[project.optional-dependencies] adapters`** in
  `pyproject.toml` (not a uv `[dependency-groups]` entry — those remain for `dev`).
  Install with `uv sync --extra adapters`. `src/core` MUST NOT import `pydantic_ai`
  or any agent framework. After 004 lands, contributor/CI inner loop for `make check`
  and `make conformance` **always** sync with `--extra adapters` so adapter tests are
  never silently skipped (see Decision: CI sync).
- **Rationale**: ADR-0001 (core never imports a framework); ADR-0017 (Pydantic AI is
  primary); Principle VI (lean core import graph / justified dep at the adapter edge);
  AGENTS.md sealed-adapter layout; `--extra` is the PEP 621 optional-dep knob and
  coexists with existing `[dependency-groups] dev`.
- **Alternatives considered**: Hard runtime dep on every bare `uv sync` (inflates core
  consumers; rejected for lean); uv `--group adapters` only (diverges from
  optional-dependencies / packaging extras; rejected); vendoring a fake framework
  (fails ADR-0017 reference adapter goal; rejected).

## Decision: Four mappings are the only adapter contents

- **Decision**: Every adapter module maps to exactly one of: (1) tools →
  `core.tools.invoke_tool`, (2) state → `DurabilityProvider` seam, (3) interrupts →
  `ApprovalHook` seam, (4) run context → identity/correlation/definition into
  `start_governed_run`. Review rejection criterion: any policy, authority algebra,
  audit schema, or registry lifecycle logic in the adapter is a move-to-core defect.
- **Rationale**: ADR-0001; FR-002; Constitution Principle I.
- **Alternatives considered**: “Thin enough” subjective review (rejected — four mappings
  are the objective bar); putting GovernanceCapability logic in core as framework types
  (would import framework into core; rejected).

## Decision: Mapping target is invoke_tool (MCP transport deferred)

- **Decision**: Constitution Principle I’s “hook-wrapped MCP calls” wording names the
  eventual transport shape; 004’s tool mapping target is **`invoke_tool`** (governed
  core entry). Northbound MCP surface and registry transport determination remain out
  of scope (Principle II / ADR-0037 later). No adapter-local MCP client.
- **Rationale**: Aligns ADR-0001 “hook-wrapped governed tool calls” with landed 002/003;
  avoids inventing a surface in the adapter.
- **Alternatives considered**: Require MCP round-trip in 004 (no northbound surface yet;
  rejected).

## Decision: Tool mapping via governed toolset + invoke_tool

- **Decision**: Expose registry tools to the framework through a custom/wrapper toolset
  whose `call_tool` (or equivalent) **only** delegates to
  `invoke_tool(run, tool_name, arguments)`. Allow → return tool result; deny / refuse →
  surface as a failed tool outcome without executing the registry handler a second time
  (core already gated execution). No framework-native tool body may call product APIs
  directly.
- **Rationale**: FR-003; 002 sole entry `invoke_tool`; Principle II.
- **Alternatives considered**: Pre-hook only inside framework without `invoke_tool`
  (duplicates pipeline; drift risk; rejected); monkey-patch model (fragile; rejected).

## Decision: GovernanceCapability as framework capability, always first

- **Decision**: Implement glossary *GovernanceCapability* as a Pydantic AI
  `AbstractCapability` (or current equivalent) that owns governance-related lifecycle
  hooks / toolset contribution required for interception. Public builder
  `build_governed_agent(..., capabilities: Sequence[...])` **always prepends**
  GovernanceCapability and rejects or reorders attempts to place non-governance
  capabilities before it. Conformance installs a probe co-resident capability and
  asserts observed order; a break fixture with inverted order must fail the suite.
- **Rationale**: ADR-0019; FR-004; constitution Quality Gates.
- **Alternatives considered**: Document-only ordering (rejected — must be
  conformance-asserted); single global monkeypatch (not capability-shaped; rejected).

## Decision: Fail closed on adapter-path faults

- **Decision**: Any exception in GovernanceCapability / tool mapping before core allow,
  missing governed run on deps, or core `internal_error` / deny propagates as deny —
  never catch-and-allow. Missing correlation ID or identity/definition inputs refuse
  start (delegate to `start_governed_run` / validation).
- **Rationale**: ADR-0006; FR-008; SC-002/SC-003.
- **Alternatives considered**: Retry/allow on framework errors (forbidden).

## Decision: Run context carries GovernedRun + agent_definition_id

- **Decision**: Adapter deps/run-context type holds at least: `governed_run: GovernedRun`,
  `correlation_id`, `subject_user_id`, `agent_definition_id: str`. Start helper calls
  `start_governed_run(..., agent_definition_id=..., include_governance=True)` (or omits
  the flag so the default True cannot be overridden from the adapter). Extend
  `IdentityFabric.resolve_ceiling(agent_definition_id: str)` **and**
  `resolve_policy(agent_definition_id: str)` so both take the definition id; fakes may
  return a global policy while still accepting the parameter. Omit/blank definition →
  refuse start. Unknown definition → unavailable/refuse (never an open ceiling).
- **Rationale**: FR-006/FR-007/FR-008; ADR-0015 per-definition ceilings; 003 watch note;
  spoofable `include_governance=False` must not be reachable via adapter start.
- **Alternatives considered**: Keep definition-agnostic fakes forever (blocks FR-007;
  rejected); key ceiling only and leave `resolve_policy` unkeyed (signature drift;
  rejected); put ceiling tables only in the adapter (authority logic in adapter;
  rejected).

## Decision: Thin durability seam (not full ADR-0024 suite)

- **Decision**: Add framework-agnostic `DurabilityProvider` protocol under
  `src/core/durability/` with an in-memory default implementation. Checkpoint / state
  payloads are opaque blobs plus metadata; **credentials and run_salt MUST NOT appear**
  in persisted blobs (asserted in tests). Adapter maps framework state/history save/load
  onto this seam. A fuller binding under `providers/` lands with ADR-0024 depth; 004 does
  not relocate the thin protocol there yet. Full kill/resume, double-resume fencing,
  grant parking, etc. remain later.
- **Rationale**: FR-009; Principle IV/ADR-0026 checkpoint rule; lean 004 scope; AGENTS
  `providers/` is the eventual extension home, not a blocker for an in-core protocol +
  memory default.
- **Alternatives considered**: Skip state mapping entirely (fails four-mapping rule;
  rejected); implement full durability conformance now (scope explosion; rejected);
  put only a stub under `providers/` with no core protocol (adapter would invent types;
  rejected).

## Decision: CI / make check always sync adapters extra

- **Decision**: Document and wire CI (`.github/workflows/ci.yml`) plus contributor docs
  so the inner loop is `uv sync --extra adapters` (with existing dev group as today).
  `make check` runs unit + component including adapter tests; `make conformance` runs
  `tests/conformance`. Do **not** use importorskip to make a bare sync “pass” by skipping
  adapter gates.
- **Rationale**: Analyze I2 — silent skip is a governance hole; sealed adapter work must
  stay merge-blocking.
- **Alternatives considered**: pytest skip if pydantic-ai missing (allows green without
  the adapter; rejected); adapters-only job separate from make check (splits the
  promised inner loop; rejected for 004).

## Decision: Thin approval / interrupt mapping

- **Decision**: Add `ApprovalHook` protocol under `src/core/approvals/` with a
  deny-by-default test double and an allow-injected test double. Map framework
  approval-required / deferred interrupt surfaces onto this protocol. No Control Groups
  UI, no portal, no human notification channel in 004.
- **Rationale**: FR-009; ADR-0019 interrupt analogue; out-of-scope HITL UX in spec.
- **Alternatives considered**: Auto-approve all interrupts (weakens future HITL;
  rejected for default); full approval product (out of scope).

## Decision: Deterministic agent execution without live models

- **Decision**: Tests use Pydantic AI’s TestModel / FunctionModel (or current documented
  stub equivalent) and/or direct invocation of the governed toolset call path. Never
  call live model providers; never require API keys in CI.
- **Rationale**: FR-012; TESTING.md; 001–003 precedent (`stub_model` / `scripted_agent`).
- **Alternatives considered**: Recorded HTTP cassettes to live APIs (nondeterministic /
  secret risk; rejected).

## Decision: Conformance command becomes real for the adapter lane

- **Decision**: Replace the Makefile `conformance` exit-2 stub with
  `uv run pytest tests/conformance -q` (adapters extra required). Suite includes
  governance-order and fail-closed primary-adapter cases (SC-003/SC-007). Secondary
  (LangGraph) slots are absent or explicitly skipped with a single documented skip —
  not a silent pass that weakens the primary bar. Constitution Quality Gates also name
  deferred-disclosure parity, four-transport surface parity, registry isolation depth,
  and full ADR-0024 durability scenarios — those rows **attach when those features
  land**; 004 must not add silent-green stubs for them.
- **Rationale**: FR-011; constitution Quality Gates; 001 reserved the command as
  fail-closed until real — 004 is when the **adapter governance** lane becomes real.
- **Alternatives considered**: Keep stub forever (fails SC-007); run full four-transport
  parity now (no surfaces yet; rejected); mark deferred rows xfail/skip-pass without
  documentation (weakens the suite; rejected).

## Decision: Deny surface to the framework

- **Decision**: When `invoke_tool` returns deny, the toolset mapping raises or returns a
  structured tool error that the framework treats as a failed tool call — it MUST NOT
  retry into an ungoverned native handler and MUST NOT convert deny into a successful
  side-effecting call. Audit/correlation remain owned by core.
- **Rationale**: Edge case “framework would allow what core denies”; FR-003/FR-013.
- **Alternatives considered**: Swallow deny and return empty success (hides governance;
  rejected).
