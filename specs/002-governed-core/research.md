# Research: Governed Core MVP

**Feature**: `specs/002-governed-core`
**Date**: 2026-07-24

## Decision: Invocation surface for 002

- **Decision**: Expose a single core entry point `invoke_tool(run, tool_name, arguments)` (name exact at implementation time may be `core.tools.invoke_tool`). Tests and `scripted_agent` call this API directly. No adapter, MCP surface, or CLI in 002.
- **Rationale**: Spec assumptions: core library + harness, exercised by deterministic tests. Adapters map onto this entry later (ADR-0001 four mappings).
- **Alternatives considered**: Shipping a minimal adapter now (pulls framework dep into critical path; deferred to 004); CLI-only demo (northbound surface deferred).

## Decision: Minimal in-process tool registry

- **Decision**: An in-process `ToolRegistry` mapping tool name → callable handler + enough metadata for existence and scope membership. Register/resolve only. No proposed→published lifecycle, transport determination, or semester review (explicitly deferred vs R6 / ADR-0037).
- **Rationale**: Spec Assumptions and FR-004/FR-005 need registered vs unregistered and in-scope vs out-of-scope only. Shipping full registry product contradicts Principle I / ADR-0008.
- **Alternatives considered**: Stub that always allows named tools (fails FR-004); full lifecycle now (out of scope; breaks lean MVP).

## Decision: Run scope representation

- **Decision**: `GovernedRun` carries an explicit allow-set of tool names (frozen set) as the declared scope for 002. Out-of-scope = name not in that set. Richer ceiling/entitlement models wait for 003.
- **Rationale**: Sufficient for FR-005 independent tests; avoids inventing authority semantics early.
- **Alternatives considered**: Risk-class scopes (needs registry metadata depth not yet specified); empty scope meaning “all registered” (too easy to misconfigure open; reject for fail-closed clarity).

## Decision: Correlation ID at initiation

- **Decision**: Caller supplies a non-empty opaque correlation ID when starting a run (UUID string recommended in quickstart; type is validated non-empty string). Missing/blank ID → run start fails closed (no uncorrelated work). Core propagates the same ID onto decisions, tool records, audit entries, and span attributes.
- **Rationale**: Spec edge case + FR-007; ADR-0009 join property. Minting IDs inside core is fine later, but refusing missing IDs is the load-bearing rule.
- **Alternatives considered**: Auto-mint when missing (hides caller bugs; rejected by spec); separate IDs per plane (breaks join).

## Decision: Hook pipeline shape and ordering

- **Decision**: Pipeline steps for each invoke: (1) registry resolve (failure → deny), (2) scope check (failure → deny), (3) pre-hooks in fixed order with **governance/enforcement first**, (4) if all pre allow → execute tool body exactly once, (5) post-hooks always when execution was attempted (including tool-body exceptions; FR-015), (6) audit + spans at each decision/outcome. Any pre-hook exception or deny → no tool body (FR-003/FR-006). Post-hook exception after execution → record failed/denied-closed post-path; audit still shows tool ran (spec edge case).
- **Rationale**: ADR-0006, ADR-0019, FR-001–FR-006, FR-011, FR-015.
- **Alternatives considered**: Gateway-anchored enforcement (forbidden by ADR-0006); configurable hook skip flags (forbidden); warn-mode default (spec: enforce/fail-closed for 002).

## Decision: Governance vs co-resident hooks in core tests

- **Decision**: Model a `capability_kind` on registered hooks: `governance` vs `other`. Engine sorts so all governance hooks run before non-governance on both pre and post phases. Tests install probe hooks to assert order (SC-006). Full framework `GovernanceCapability` object lands with the adapter; 002 proves the **core ordering guarantee** the adapter must not invert.
- **Rationale**: ADR-0019 requires conformance-observable governance-first order; core must own the property before an adapter exists.
- **Alternatives considered**: Only document order for later adapter tests (fails US4 independent test in 002); hard-code a single governance hook with no extension point (weaker Hook SDK direction).

## Decision: Audit schema and hash chain

- **Decision**: Each `AuditEntry` includes at least: `correlation_id`, `seq` (monotonic per run), `event_type`, `timestamp`, redacted payload/metadata, `prev_hash`, `entry_hash`. `entry_hash = SHA-256(canonical(prev_hash || entry_fields_excluding_entry_hash))`. Genesis entry uses a fixed `prev_hash` sentinel (exactly 64 ASCII `0` characters). Canonical encoding is pinned in contracts/audit-sink.md so independent implementations verify identically. Sink supports append and fetch-by-correlation-id in causal order; no update/delete API. `assert_audit_chain` verifies link integrity and no gaps.
- **Rationale**: FR-008 + ADR-0009 (“hash-chained per run”); schema is sealed — land chain now to avoid breaking change. SHA-256 is stdlib, widely understood for evidence chains.
- **Alternatives considered**: Merkle tree across runs (overkill for MVP); unsigned append-only list without hashes (fails FR-008); HMAC with a standing key (introduces credential-shaped secret — rejected under Principle IV for 002).

## Decision: Audit sink interface vs durability

- **Decision**: Define `AuditSink` protocol in core; ship `InMemoryAuditSink`. No Postgres, SIEM export, or governed read path (ADR-0035) in 002. Interface is the stable seam for later providers.
- **Rationale**: Spec Assumptions; Principle VI.
- **Alternatives considered**: Embed Postgres now (operated component without ADR trigger for 002); filesystem JSONL only (fine later, not required if in-memory + interface exists).

## Decision: OpenTelemetry emission

- **Decision**: Core depends on `opentelemetry-api` only. Emit one span (or child span) per hook decision with attributes including correlation ID, tool name, decision (`allow`/`deny`), phase (`pre`/`post`), and capability kind. Use the global tracer provider; tests set `TracerProvider` + `InMemorySpanExporter` via `opentelemetry-sdk` (dev dependency). No vendor SDKs. No audit egress via OTel.
- **Rationale**: ADR-0020, FR-009, FR-010; Principle VI (API without forcing a backend).
- **Alternatives considered**: Custom span dataclass only (weaker ADR-0020 alignment); vendor SDK (forbidden); always-on OTLP exporter in core (credentials/egress — forbidden).

## Decision: Secret redaction posture for 002

- **Decision**: Audit payloads and span attributes store argument **keys**, content hashes or redaction tokens, and structured error codes — never raw argument values or exception messages that may embed secrets. Tool handlers used in tests may accept a sentinel “secret-like” string defined in harness fixtures; `assert_no_secret_values` scans audit/spans/logs for those fixture markers (and obvious patterns agreed in harness — without embedding plausible real secrets in the repo).
- **Rationale**: FR-010, FR-014, AGENTS “never write secrets”; TESTING.md helper contract.
- **Alternatives considered**: Full ML-based secret scanning in-process (out of scope); logging full args in debug mode (forbidden).

## Decision: Denial message shape

- **Decision**: User-visible denial carries a stable reason code (e.g. `unregistered`, `out_of_scope`, `hook_deny`, `internal_error`) plus a short safe message. No entitlement dump, no peer tool names outside scope, no secret material.
- **Rationale**: FR-014.
- **Alternatives considered**: Free-form exception strings to callers (leak risk).

## Decision: Pydantic at boundaries

- **Decision**: Add `pydantic` as a runtime dependency. Public run/invoke/audit/hook decision models are Pydantic models with validation that fails loudly (no coercion of required correlation ID or decision enums).
- **Rationale**: CONTRIBUTING / AGENTS code conventions; sealed schema benefit for audit entries.
- **Alternatives considered**: dataclasses + hand validation (more drift); typed dicts only (weaker boundary validation).

## Decision: Harness helper set for 002

- **Decision**: Implement exactly: `assert_denied_closed`, `assert_correlated`, `assert_audit_chain`, `assert_no_secret_values` (FR-012), and `assert_no_side_effect` (counter-based). Also ship supporting fakes named in TESTING.md that 002 needs: `scripted_agent`, `capture_audit`. Implement `assert_hook_order` in harness so governance-first is not asserted via private engine internals. Other TESTING.md helpers (`assert_allowed`, `assert_scope_narrowed`, …) may land as thin stubs or full helpers if trivial; scope narrowing is not required for 002 stories.
- **Rationale**: FR-012 exact names; US5; avoid reinventing per-test asserts.
- **Alternatives considered**: “Equivalent” helpers under new names (rejected by FR-012); only document helpers without implementing (fails US5).

## Decision: pytest layout and `make check`

- **Decision**: Keep `make check` as the gate; expand `tool.pytest.ini_options.testpaths` to include `tests/component` (and keep `tests/unit`). No change to stub `conformance` / `test-full` targets beyond what 002 needs — governance-order test may live under `tests/component` for now and migrate into `make conformance` when that suite exists.
- **Rationale**: 001 contracts; SC-006 must run in CI; full conformance makefile still a later feature.
- **Alternatives considered**: Put all 002 tests only under a new path excluded from check (would regress fast-lane evidence).

## Decision: Dependency justification (Principle VI)

- **Decision**: Justify in the feat PR: `pydantic` (boundary validation convention) and `opentelemetry-api` (ADR-0020 mandatory vocabulary). `opentelemetry-sdk` is dev-only for tests.
- **Rationale**: CONTRIBUTING — core deps are audited; these two are constitution/ADR-driven, not convenience.
- **Alternatives considered**: Zero new deps (fails Pydantic convention and OTel FR); heavier observability stacks (rejected).
