# Research: Primary Adapter

**Feature**: `specs/004-primary-adapter`
**Date**: 2026-07-25

## Decision: Package boundary and dependency shape

- **Decision**: Implement the primary adapter under `src/adapters/pydantic_ai/`.
  Declare **`pydantic-ai-slim==2.18.0`** under
  **`[project.optional-dependencies] adapters`** in
  `pyproject.toml` (not a uv `[dependency-groups]` entry — those remain for `dev`).
  Install with `uv sync --extra adapters`. `src/core` MUST NOT import `pydantic_ai`
  or any agent framework. After 004 lands, contributor/CI inner loop for `make check`
  and `make conformance` **always** sync with `--extra adapters` so adapter tests are
  never silently skipped (see Decision: CI sync).
- **Rationale**: ADR-0001 (core never imports a framework); ADR-0017 (Pydantic AI is
  primary); Principle VI (lean core import graph / justified dep at the adapter edge);
  AGENTS.md sealed-adapter layout; `--extra` is the PEP 621 optional-dep knob and
  coexists with existing `[dependency-groups] dev`.
- **Slim, not the meta package** (resolved 2026-07-25 from the package index): `pydantic-ai`
  2.18.0 resolves to `pydantic-ai-slim[anthropic,cli,evals,google,logfire,mcp,openai,
  retries,web]==2.18.0`, installing the Anthropic, Google, and OpenAI SDKs plus a CLI and
  logfire. 004 calls no model — every one of those is unused weight in a regulated
  dependency tree (Principle VI), and FR-012's denylist is materially easier to hold when
  live model SDKs are not installed at all. `pydantic-ai-slim` brings `httpx`, `pydantic`,
  `pydantic-graph`, `opentelemetry-api`, `genai-prices`, `griffelib`,
  `typing-inspection` — and `TestModel` / `FunctionModel` plus the capability and toolset
  APIs 004 binds are all in the slim core. **Consequence to settle at implement time**: slim
  requires `pydantic>=2.12` and `opentelemetry-api>=1.28`, above this project's `>=2.10` /
  `>=1.27` floors, so the with-extra and without-extra environments resolve differently
  unless the base pins are raised (T002).
- **Alternatives considered**: The `pydantic-ai` meta package (simpler name, but installs
  three model-provider SDKs for a feature that calls no model; rejected — revisit if a
  later feature needs a real provider, at which point the extra it needs is added
  explicitly rather than inherited); hard runtime dep on every bare `uv sync` (inflates core
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
- **Mechanism**: define `UV_RUN := uv run --extra adapters` in the Makefile and route every
  `check` and `conformance` recipe line through it. A bare `uv run` materializes the project
  environment from the *default* extra set, so it does not guarantee the `adapters` extra is
  present regardless of how the developer last synced; naming the extra in the recipe removes
  that dependence on ambient state. CI's `Sync dependencies` step likewise becomes
  `uv sync --frozen --extra adapters`.
- **Lockfile**: adding the extra to `pyproject.toml` requires committing the regenerated
  `uv.lock` in the same change. CI syncs with `--frozen`, which by definition will not update
  the lockfile, so a stale lock fails the fast lane before any test runs.
- **Sequencing constraint**: `uv run --extra adapters` and `uv sync --extra adapters` both
  error with "Extra `adapters` is not defined" until the extra exists in `pyproject.toml`.
  The Makefile and CI edits therefore ship with or after the dependency declaration, never
  before — otherwise they break `main` on the commit that introduces them.
- **Rationale**: silent skip is a governance hole; sealed adapter work must stay
  merge-blocking. Determinism about *which* environment the gates ran in is part of that —
  a gate that passes because a dependency was missing is worse than no gate.
- **Alternatives considered**: pytest skip / `importorskip` if the framework is missing
  (allows green without the adapter; rejected); adapters-only job separate from make check
  (splits the promised inner loop; rejected for 004); `[tool.uv] default-extras` instead of
  naming the extra per recipe (works, but makes the requirement invisible at the call site;
  rejected as less legible).

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
  land** (now authoritative under Accepted **ADR-0047** / constitution v1.0.1, with the
  per-row deferring ADR recorded in `contracts/conformance-adapter.md`); 004 must not add
  silent-green stubs for them.
- **Rationale**: FR-011; constitution Quality Gates; 001 reserved the command as
  fail-closed until real — 004 is when the **adapter governance** lane becomes real.
- **Alternatives considered**: Keep stub forever (fails SC-007); run full four-transport
  parity now (no surfaces yet; rejected); mark deferred rows xfail/skip-pass without
  documentation (weakens the suite; rejected).

## Decision: Conformance enforcement lives in CI, not the PR body

- **Decision**: `make conformance` runs as a step in the existing fast-lane job in
  `.github/workflows/ci.yml`, after `Inner-loop check`, with `Sync dependencies` changed
  to `uv sync --frozen --extra adapters`. A local run recorded in a PR description is a
  pre-flight, not the gate.
- **Rationale**: FR-015; `contracts/conformance-adapter.md` invariant 1 asserts
  merge-blocking, and Principle IX makes the distinction between a record and a claim
  load-bearing. A gate verified by a human pasting output is a claim.
- **Alternatives considered**: Separate conformance job (re-pays checkout + sync ~30s for
  a sub-second lane, no isolation benefit; rejected for 004 — revisit when the lane grows
  or needs a different environment); PR-description evidence only (the status quo this
  replaces; rejected); branch protection without a CI step (nothing to protect against).

## Decision: Core extensions capped at three, enumerated in the spec

- **Decision**: This feature's sealed-core changes are exactly: durability protocol +
  in-memory default; approval-hook protocol + deny-by-default double; required
  `agent_definition_id` at run start threaded into ceiling and policy resolution. Anything
  else in `src/core` is out of scope and needs its own spec.
- **Rationale**: FR-016. The spec previously described 004 as "adapter glue", which the
  task list contradicted — an unbounded licence to touch sealed core is exactly what
  Principle V exists to prevent. Enumerating the three makes a fourth visible at review.
- **Alternatives considered**: Leave the scope implicit in plan.md (review has nothing to
  hold a PR against; rejected); split the core seams into their own feature (correct in
  principle, but the adapter cannot be demonstrated without them — deferring would produce
  an untestable 004; rejected with the breaking-seam exemption recorded in Assumptions).

## Decision: FR-012 verified by an import guard, not convention

- **Decision**: Add `tests/unit/test_no_live_dependencies.py` with two checks:
  **(a)** an `ast`-based scan of test module *source* asserting no test directly imports a
  denylisted network client (`httpx`, `requests`, `urllib.request`, `aiohttp`, `hvac`,
  model-provider SDKs); **(b)** an assertion that adapter tests resolve only stub models
  (`TestModel` / `FunctionModel` or the harness wrapper).
- **Rationale**: FR-012 as amended. FR-010 (no secret values) carries three assertions;
  FR-012 carried none, so "no live calls" rested on reviewer attention. Determinism that
  nothing checks degrades silently — the first live call added is also the first flaky test.
- **Mechanism matters here.** A `sys.modules` check is wrong: `pydantic-ai` imports an HTTP
  client transitively, so every adapter test would trip it. Scanning source for *direct*
  imports scopes the property to what a test author controls — "no test reaches for a live
  client itself" — and (b) covers what (a) cannot, since the realistic path to a live call
  is a real model provider passed to an agent, not an import statement.
- **Known limit**: this catches reaching for a client, not a live call through an
  already-imported one. Accepted for 004 and recorded in the module docstring.
- **Alternatives considered**: `pytest-socket` (strictly stronger — blocks the call, not the
  import — but adds a dependency to a regulated tree that must be justified per Principle
  VI, for a gap the two checks above close in the realistic cases; escalate to it if a live
  call ever slips through); a `sys.modules` check (wrong for the transitive-import reason
  above; rejected); trust convention plus review (the status quo this replaces).

## Decision: `invoke_tool` entry asserted in two lanes, deliberately

- **Decision**: Both the conformance lane and the unit lane assert that the adapter tool path
  reaches `invoke_tool`, sharing one probe/counter helper. This is a duplicate assertion and
  is intended.
- **Rationale**: the lanes answer different questions and are run at different times. The
  conformance case is the merge-blocking governance assertion an adapter must satisfy
  (constitution Quality Gates); the unit case is the fast mapping-purity check that fails
  first and localizes the break during development. Collapsing them would either slow the
  inner loop or drop the property from the gate.
- **Alternatives considered**: conformance only (loses the fast local signal; rejected); unit
  only (the property stops being conformance-asserted, which ADR-0019 requires; rejected).

## Decision: Deny surface to the framework

- **Decision**: When `invoke_tool` returns deny, the toolset mapping raises or returns a
  structured tool error that the framework treats as a failed tool call — it MUST NOT
  retry into an ungoverned native handler and MUST NOT convert deny into a successful
  side-effecting call. Audit/correlation remain owned by core.
- **Rationale**: Edge case “framework would allow what core denies”; FR-003/FR-013.
- **Alternatives considered**: Swallow deny and return empty success (hides governance;
  rejected).
