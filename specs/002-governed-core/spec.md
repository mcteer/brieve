# Feature Specification: Governed Core MVP

**Feature Branch**: `spec/002-governed-core`

**Path**: `specs/002-governed-core/spec.md`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Deliver the first security-critical vertical of the harness core: every agent-initiated external interaction is a registered tool call that passes an in-process, fail-closed pre- and post-execution hook pipeline; one correlation ID joins the run from initiation through hook decisions, tool invocation, and audit records; hook decisions emit observable spans; the audit trail for a run is append-only and walkable by that correlation ID. Success means these guarantees are demonstrated with deterministic tests and harness helpers — without yet implementing per-task credential manufacture, a production adapter, capability packs, or a northbound product surface. Out of scope: identity fabric / token exchange, Control Groups, durability/resume, multi-tenancy isolation beyond a single-run model, portal/UI, live models, and real managed-product tools."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R7 (fail-closed enforcement), R4 / R10 / R13 (correlation and evidence planes as implicated by audit/join). Others deferred to later features (notably R2/R3 authority). |
| **ADRs touched** | ADR-0001 (framework-agnostic core), ADR-0006 (in-process fail-closed enforcement), ADR-0009 (correlation ID joining observability planes; audit never sampled), ADR-0020 (OTel-only emission in core — spans for hook decisions) |
| **Evidence class** | Attestation-relevant — introduces the audit join and fail-closed denial records that later evidence paths will read |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - In-scope tool call is allowed and fully joined (Priority: P1)

An operator (or test) starts a governed run and the agent attempts a tool call that is registered and within the run's declared scope. Pre- and post-execution hooks run in-process, the tool executes once, and a single correlation ID appears on the run initiation, every hook decision, the tool invocation record, and the audit entries so an investigator can walk the chain both directions.

**Why this priority**: Without a working allow path that still produces joined evidence, fail-closed denials cannot be proven as the exception rather than the only behavior.

**Independent Test**: Scripted agent issues one in-scope registered tool call; assert allow, one execution, correlation ID present on hook decisions + audit entries, no secret values in records.

**Acceptance Scenarios**:

1. **Given** a run with a correlation ID and a registered in-scope tool, **When** the agent invokes that tool with valid arguments, **Then** pre-hooks allow, the tool executes exactly once, post-hooks run, and the call completes successfully.
2. **Given** that successful call, **When** an investigator queries audit by the run's correlation ID, **Then** they find ordered records for run start, pre-decision, tool outcome, and post-decision joinable to the same ID.
3. **Given** that successful call, **When** telemetry for the run is inspected, **Then** each hook decision is represented as a span (or equivalent structured observation) carrying the correlation ID.

---

### User Story 2 - Out-of-scope or unregistered tool call is denied with no side effects (Priority: P1)

The agent attempts a tool that is not registered, or is registered but outside the run's scope. The pipeline denies before execution. No product side effect occurs. The denial is audited and correlated.

**Why this priority**: This is the primary safety property of the governed core — interception with deny-by-default for anything outside the governed set.

**Independent Test**: Scripted agent requests an unregistered or out-of-scope tool; assert deny, zero tool side effects, audit denial record, correlation ID present.

**Acceptance Scenarios**:

1. **Given** a run and a tool name that is not registered, **When** the agent invokes it, **Then** the call is denied before any tool body runs and the denial is audited under the run's correlation ID.
2. **Given** a run whose scope excludes a registered tool, **When** the agent invokes that tool, **Then** the call is denied before execution and audited.
3. **Given** either denial, **When** side-effect counters or fakes for the tool are inspected, **Then** they show zero executions.

---

### User Story 3 - Enforcement errors deny (fail closed) (Priority: P1)

A hook, registry lookup, or required enforcement dependency errors mid-pipeline (exception, timeout simulation, or corrupt decision). The call is denied, never allowed through. The failure is audited without leaking secret values.

**Why this priority**: Constitution Principle III and ADR-0006 — allow-on-error falsifies the platform's central claim. This story is independently valuable even before rich policy engines exist.

**Independent Test**: Inject a fault into a pre-hook or registry resolution; assert deny, no tool execution, audited failure/denial, no secret leakage in error text or audit.

**Acceptance Scenarios**:

1. **Given** a run and an in-scope registered tool, **When** a pre-execution hook raises an internal error, **Then** the tool does not execute and the outcome is deny.
2. **Given** a run and an in-scope registered tool, **When** registry resolution for that tool fails, **Then** the outcome is deny with an audit record under the correlation ID.
3. **Given** any such failure, **When** logs, spans, and audit payloads are inspected, **Then** they contain no secret values (references/metadata only).

---

### User Story 4 - Governance order is fixed and observable (Priority: P2)

When multiple co-resident capabilities or hooks participate, governance/enforcement runs in a defined order with Governance first among co-resident capabilities (as required by the constitution). Tests can observe the order of hook invocation for a call.

**Why this priority**: Ordering bugs create bypass classes; proving order is part of the conformance bar called out in the constitution.

**Independent Test**: Install ordered probe hooks; invoke one tool; assert recorded order matches the mandated governance-first sequence.

**Acceptance Scenarios**:

1. **Given** a run with governance and at least one additional co-resident capability hook registered, **When** a tool is invoked, **Then** governance/enforcement decisions are observed before non-governance capability work on that call.
2. **Given** that invocation, **When** the ordered probe log is read, **Then** the sequence is deterministic across repeated runs with the same registration.

---

### User Story 5 - Contributors can assert governance properties via the test harness (Priority: P2)

A contributor writing later features uses public harness helpers to assert denial, correlation, audit-chain join, and absence of secret values — without reinventing fakes.

**Why this priority**: TESTING.md and AGENTS.md already promise these helpers; 002 is when they become real enough to gate the core.

**Independent Test**: A minimal unit/component test imports harness helpers and fails closed if misused; documentation in `tests/harness` matches the helpers shipped.

**Acceptance Scenarios**:

1. **Given** the test harness package, **When** a contributor writes a test for an out-of-scope deny, **Then** they can use documented helpers equivalent in purpose to `assert_denied_closed`, `assert_correlated`, `assert_audit_chain`, and `assert_no_secret_values`.
2. **Given** those helpers, **When** applied to the stories above, **Then** the same properties the helpers claim are what the core actually guarantees.

### Edge Cases

- What happens when a correlation ID is missing at run start? The run cannot proceed in an uncorrelated state — initiation fails closed (deny/refuse start), rather than inventing silent uncorrelated work.
- What happens when a post-execution hook errors after the tool already ran? The outcome is recorded as a failed/denied-closed post-path; the audit trail must still show the tool executed and the post-hook failure (no silent success). Side-effect fencing/idempotency beyond recording is deferred to durability features.
- What happens when two tool calls share a run? Both share the same correlation ID; per-call decisions remain distinct audit/span records under that ID.
- How are secret-like tool arguments treated in audit? Values are never written; redacted references or hashes/metadata only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every agent-initiated external interaction in a governed run MUST be represented as a tool call that enters the hook pipeline; there is no supported path to invoke a tool body while skipping pre-hooks.
- **FR-002**: The pipeline MUST run pre-execution hooks before tool execution and post-execution hooks after (when execution occurred), in-process in the harness core — not delegated to a gateway or mesh as the load-bearing control.
- **FR-003**: If any pre-execution enforcement step errors or returns deny, the tool body MUST NOT execute.
- **FR-004**: Unregistered tool names MUST be denied.
- **FR-005**: Tool calls outside the run's declared scope MUST be denied.
- **FR-006**: Enforcement-path errors (hook exception, registry resolution failure, missing required enforcement dependency) MUST deny; they MUST NOT allow.
- **FR-007**: Each governed run MUST have exactly one correlation ID from initiation; that ID MUST appear on hook decisions, tool invocation records, audit entries, and hook-decision spans for that run.
- **FR-008**: Audit records for a run MUST be append-only for that run's trail (no in-place mutation of prior entries) and MUST be retrievable by correlation ID in causal order.
- **FR-009**: Hook decisions MUST emit OpenTelemetry spans (or the core's standard span abstraction that exports as OTel); the core MUST NOT embed a vendor observability SDK.
- **FR-010**: Audit, logs, and spans MUST NOT contain secret values — references, hashes, or redacted metadata only.
- **FR-011**: Governance/enforcement MUST run first among co-resident capabilities on a tool call (conformance-observable order).
- **FR-012**: The test harness MUST provide assertion helpers covering deny-closed, correlation join, audit-chain walkability, and no-secret-values for the scenarios in this feature.
- **FR-013**: Deterministic tests for FR-001–FR-012 MUST NOT call live models or live managed-product APIs; scripted agents and fakes are required.
- **FR-014**: User-facing denial messages MUST explain that the action was denied without disclosing secrets or out-of-scope entitlements the requester must not see.

### Key Entities

- **Governed run**: A single unit of agent work with one correlation ID, a declared scope, and an append-only audit trail.
- **Correlation ID**: Opaque identifier joining run initiation, hook decisions, tool records, spans, and audit entries.
- **Tool registration**: Named tool known to the registry with enough metadata to decide existence and scope applicability (full risk-class lifecycle can deepen later).
- **Hook decision**: Allow or deny (plus failure-as-deny) produced by a pre- or post-execution hook, recorded for audit and telemetry.
- **Audit entry**: Append-only evidence record for a run event (decision, tool outcome, failure), joinable by correlation ID.
- **Scripted agent**: Test double that emits a fixed sequence of tool calls without a live model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of in-scope registered tool-call tests in this feature's suite show exactly one tool-body execution when allowed, and zero when denied.
- **SC-002**: 100% of denial and enforcement-error tests end in deny with zero tool-body executions (fail closed).
- **SC-003**: For every successful or denied tool call in the suite, an investigator can retrieve a non-empty audit trail by correlation ID that includes the hook decision(s) for that call.
- **SC-004**: 100% of hook decisions in the suite produce a span (or exported OTel equivalent) carrying the run correlation ID.
- **SC-005**: Automated secret-scan / fixture assertions find zero raw secret values in audit payloads, span attributes, or logged denial messages produced by the suite.
- **SC-006**: Governance-first ordering is asserted by at least one deterministic conformance-style test that fails if order is reversed.

## Assumptions

- This feature ships as **core library behavior + test harness fakes/helpers**, exercised by deterministic component/unit tests. A full northbound surface (CLI/API/MCP/portal) and a production agent-framework adapter are later features.
- "Registry" in this feature means a minimal in-process registration/resolution facility sufficient for registered vs unregistered and in-scope vs out-of-scope decisions — not a full enterprise registry product (ADR-0008).
- Durable multi-year audit storage, SIEM export, and the governed audit *read* path (ADR-0035) are not required to land in full; an append-only sink with an in-memory test implementation is sufficient if the interface is stable for later providers.
- Per-task credential manufacture, ceilings, and entitlement mirroring (003) are out of scope; runs may use test doubles for "identity present/absent" only as needed to exercise fail-closed paths.
- Warn-mode hooks for local `make dev-up` (ADR-0009 develop stage) may be represented as a mode flag later; **002's default and test bar is enforce/fail-closed**.
- Post-hook failure after a tool has executed records the failure in audit; full idempotent side-effect fencing belongs with durability (later).
- Named harness helpers may match TESTING.md names (`assert_denied_closed`, etc.) or clear equivalents documented in `tests/harness`.
