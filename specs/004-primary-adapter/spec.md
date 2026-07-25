# Feature Specification: Primary Adapter

**Feature Branch**: `spec/004-primary-adapter`

**Path**: `specs/004-primary-adapter/spec.md`

**Created**: 2026-07-25

**Status**: Planned

**Input**: User description: "Deliver the primary agent-framework adapter on top of the governed core and per-task authority: a thin binding to the Accepted primary framework (ADR-0017) that maps exactly four concepts onto core machinery (tools → hook-wrapped governed tool calls; state → durability seam; interrupts → approval hooks; run context → identity and correlation), with governance running first among co-resident capabilities and failing closed. Success means a scripted or stub-model agent run through the adapter exercises the existing hook pipeline and authority binding, with conformance-asserted governance-first ordering and no logic beyond the four mappings. Demonstrate with deterministic tests and the conformance suite (`make conformance`). Out of scope: second (LangGraph) adapter, full durability provider/resume product, Control Groups UI, capability packs, northbound product surfaces (CLI/API/MCP/portal), live models, production IdP/Vault fabric, multi-tenancy, code mode, deferred-tool-disclosure productization, and real managed-product APIs."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R16 (sealed adapters / versioned seams — thin primary adapter as sealed-core glue). R7 (fail-closed governance on the adapter path). R5 / R11 as implicated by total interception of tool calls that leave the agent through the adapter (Principle II) — without claiming full registry lifecycle (R6) or all four northbound transports (R15). Builds on R2/R3 (003 authority) and R4/R10/R13 (002 evidence) without re-owning them. |
| **ADRs touched** | ADR-0001 (framework-agnostic core; exactly four adapter mappings; core never imports a framework), ADR-0017 (Pydantic AI is the primary and reference adapter; LangGraph demand-driven), ADR-0019 (adapter on framework capabilities; GovernanceCapability runs first and fails closed; conformance-asserted), ADR-0006 (in-process fail-closed enforcement — adapter must not open a bypass), ADR-0047 (conformance gate rows attach as their features land — governs which Quality Gate rows are in force for this adapter, and makes the Deferred section of `contracts/conformance-adapter.md` authoritative rather than advisory). Related deferred: ADR-0024 (durability provider depth), ADR-0040/0041 (deferred disclosure / code-mode parity — out of scope productization here). |
| **Evidence class** | Conformance / attestation-adjacent — governance-first order and fail-closed adapter-path denials are conformance-asserted; audit join and authority records remain owned by 002/003 and must still be reachable for runs started through the adapter |

## Clarifications

### Session 2026-07-25

- Q: Traceability omits ADR-0047, which now governs which Quality Gate rows are in force for this adapter. Declare it? → A: Yes — added to ADRs touched; it is what makes the contract's Deferred section authoritative, and constitution Development Workflow item 2 requires every spec to declare the ADRs it touches.
- Q: `contracts/conformance-adapter.md` invariant 1 asserts conformance failures are merge-blocking, but no requirement carries that property — extend FR-011 or add a new one? → A: New **FR-015**. FR-011 keeps its narrower scope (the command executes the cases); merge-blocking is a distinct, separately testable property, and conflating them would hide either behind the other.
- Q: The spec frames 004 as adapter glue, but plan and tasks extend core seams (durability, approvals, a required `agent_definition_id`). Amend the Assumption, or add a bounding requirement? → A: Both — Assumption amended, and **FR-016** enumerates the permitted core extensions so anything beyond them is visibly out of scope at review time.
- Q: FR-012 (no live models, IdP, Vault, or product APIs in tests) has no verification, while comparable FR-010 has three. Guard test, or is convention sufficient? → A: Automated guard required — FR-012 extended. A prohibition nothing checks is a convention, and this one protects test determinism.
- Q: FR-016 is verified only by review, with no Success Criterion — leave it, or make it measurable? → A: Added **SC-008**. Every other FR is measurable; a scope bound that only exists in review prose is the first thing to erode under delivery pressure.
- Q: How is FR-012's guard actually implemented, given `pydantic-ai` pulls an HTTP client in transitively? → A: Two checks — an `ast` scan of test *source* for direct denylisted imports (not `sys.modules`, which would fail on every adapter test), plus an assertion that adapter tests resolve only stub models. `pytest-socket` is stronger but adds a regulated-tree dependency; escalate only if a live call slips through.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scripted agent through the adapter completes an in-scope governed call (Priority: P1)

An operator (or test) starts work through the primary adapter on behalf of a requesting user against an agent definition. A scripted or stub-model agent issues one registered, in-scope tool call. The call reaches the existing governed pipeline and authority binding; it is allowed once; the run's correlation ID joins the adapter-started run to hook decisions and audit records.

**Why this priority**: Without a working allow path through the adapter, the four-mapping contract and conformance bar cannot be demonstrated against a real framework binding.

**Independent Test**: Start a run via the adapter with fakes for identity/ceiling and a stub model or scripted tool sequence; invoke one in-scope tool; assert allow, one execution, correlated audit/hook evidence, no secret values, and that the tool path went through the governed entry (not a framework-native bypass).

**Acceptance Scenarios**:

1. **Given** a requesting user, agent definition/ceiling, and registered in-scope tool, **When** a scripted or stub-model agent run is started through the primary adapter and issues that tool call, **Then** pre-hooks allow, the tool executes exactly once, and the call completes successfully.
2. **Given** that successful call, **When** an investigator queries audit by the run's correlation ID, **Then** they find joined records for the run and the tool decision under that same ID (002/003 evidence plane still holds for adapter-started runs).
3. **Given** that successful call, **When** authority narrowing helpers are applied, **Then** `assert_scope_narrowed` (or the 003 equivalent property) still holds for the bound task authority.

---

### User Story 2 - Adapter-path denials produce zero tool side effects (Priority: P1)

Through the adapter, the agent attempts a tool that is unregistered, outside scope, outside live effective authority, or otherwise denied by the existing core gates. The outcome is deny before tool-body execution. No product side effect occurs. The denial is audited and correlated.

**Why this priority**: The adapter must not weaken 002/003 deny properties; an adapter-shaped bypass would falsify Principle II and ADR-0006.

**Independent Test**: Scripted agent through the adapter requests an unregistered, out-of-scope, or authority-insufficient tool; assert deny, zero executions, correlated audit denial, no secret leakage.

**Acceptance Scenarios**:

1. **Given** an adapter-started run, **When** the agent invokes an unregistered or out-of-scope tool name, **Then** the call is denied before any tool body runs and the denial is audited under the run's correlation ID.
2. **Given** an adapter-started run whose effective authority excludes a tool, **When** the agent invokes that tool, **Then** the call is denied with zero side effects (same posture as 003 authority denials).
3. **Given** either denial, **When** side-effect counters or fakes for the tool are inspected, **Then** they show zero executions.

---

### User Story 3 - Governance runs first and fails closed on the adapter path (Priority: P1)

When the adapter composes governance with any co-resident capability behavior, governance/enforcement runs first. If governance or a required enforcement dependency errors, the tool call is denied — never allowed through. Conformance tests observe both properties on the primary adapter.

**Why this priority**: ADR-0019 and the constitution make governance-first + fail-closed conformance assertions the load-bearing guarantees of the adapter seam.

**Independent Test**: Install ordered probes / co-resident capability fixtures on an adapter-built agent; invoke one tool; assert governance-first order. Inject a governance/enforcement fault; assert deny and zero tool-body executions.

**Acceptance Scenarios**:

1. **Given** an adapter-configured agent with governance and at least one additional co-resident capability, **When** a tool is invoked, **Then** governance/enforcement is observed before non-governance capability work on that call.
2. **Given** that configuration, **When** a required governance/enforcement step errors, **Then** the outcome is deny with zero tool-body executions (fail closed).
3. **Given** those properties, **When** the conformance suite for the primary adapter runs, **Then** both ordering and fail-closed assertions are exercised and would fail if inverted or weakened.

---

### User Story 4 - Adapter contents are only the four mappings (Priority: P2)

A reviewer inspecting the primary adapter can classify every behavior as one of the four permitted mappings (tools → governed tool calls; state → durability seam; interrupts → approval hooks; run context → identity/correlation). No product policy, authority manufacture, audit schema, or registry logic lives in the adapter beyond glue onto core.

**Why this priority**: ADR-0001's four-mapping rule is the review bar that keeps governance from drifting into framework-shaped forks.

**Independent Test**: Conformance or review checklist asserts that adapter-reachable tool calls enter the governed core entry; durability and interrupt paths bind to core/provider seams rather than reimplementing them; run context carries correlation and identity into core start/invoke.

**Acceptance Scenarios**:

1. **Given** the primary adapter, **When** a framework tool call is issued, **Then** it enters the governed tool-call path (hook pipeline + authority) rather than executing as an ungoverned framework-native call.
2. **Given** framework run context for an adapter-started run, **When** the run begins, **Then** identity and correlation required by 002/003 are present on the governed run (including an agent-definition identifier usable for ceiling resolution in fakes).
3. **Given** framework state and interrupt surfaces exercised in this feature's suite, **When** they are used, **Then** they bind to the durability seam and approval-hook path respectively — without a second, adapter-local enforcement engine.

---

### User Story 5 - Contributors run adapter conformance via the documented command (Priority: P2)

A contributor changing the primary adapter can run the shared conformance path and get a real pass/fail for governance-first and fail-closed adapter properties — not a stub that always succeeds.

**Why this priority**: Constitution Quality Gates and ADR-0001 require every adapter to ship with and pass the conformance suite; `make conformance` is already the documented contract (001) and must stop being a no-op once an adapter exists.

**Independent Test**: `make conformance` (or the suite entry it invokes) executes adapter conformance cases for the primary adapter; at least one case fails if governance order is reversed or fail-closed is weakened in a deliberate break test.

**Acceptance Scenarios**:

1. **Given** a clean tree with the primary adapter, **When** a contributor runs `make conformance`, **Then** primary-adapter governance-ordering and fail-closed cases run and pass.
2. **Given** a deliberately inverted governance order (in a break/fixture test), **When** the same conformance assertions run, **Then** they fail.

### Edge Cases

- What happens when the adapter is asked to start a run without a correlation ID or without required identity/authority inputs? Start is refused fail-closed — same posture as 002/003; the adapter must not invent uncorrelated or unauthorized work.
- What happens when the framework would allow a tool call that core would deny? Core denial wins; the adapter must not catch-and-allow around governed denials.
- What happens when durability or interrupt mapping is exercised without a full resume/HITL product? Thin seam bindings and fakes are sufficient; full resume scenarios and Control Groups–gated approval UX remain later features — but the mapping entry points must exist and must not bypass governance.
- What happens when co-resident capabilities are absent? Governance still runs; an agent with only governance is valid; ordering assertions still hold vacuously relative to non-governance work.
- How are secret-like tool arguments and credentials treated on the adapter path? Same redaction rules as 002/003 — no raw secrets in audit, spans, logs, or model-visible context.
- Does this feature ship a second adapter? No — LangGraph remains demand-driven (ADR-0017); conformance may keep dual-adapter-shaped slots empty or skipped until that adapter exists, without weakening the primary adapter's bar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide a primary adapter that binds the Accepted primary agent framework (ADR-0017) to the governed core; the core MUST NOT import that framework (ADR-0001).
- **FR-002**: The adapter's permitted contents are exactly four mappings: (1) framework tools → hook-wrapped governed tool calls; (2) framework state → the durability seam; (3) framework interrupts → approval hooks; (4) framework run context → identity and correlation. Behavior beyond those mappings MUST NOT live in the adapter (ADR-0001).
- **FR-003**: Every tool call that leaves an adapter-driven agent as an external interaction MUST enter the existing governed tool-call path; there MUST be no supported adapter path that executes a tool body while skipping pre-hooks (builds on 002 FR-001; Principle II).
- **FR-004**: Governance MUST run first among co-resident capabilities on the adapter path and MUST fail closed; both properties MUST be asserted by the conformance suite against the primary adapter (ADR-0019).
- **FR-005**: Adapter-started runs MUST bind per-task authority using the 003 manufacture and live-effective rules (user ∩ ceiling ∩ task scope ∩ policy; entitlement mirroring where product actions apply). The adapter MUST NOT manufacture, widen, or replace authority outside core.
- **FR-006**: Adapter-started runs MUST carry exactly one correlation ID from initiation through hook decisions, tool records, audit entries, and hook-decision spans (002 join property preserved).
- **FR-007**: Run context mapping MUST supply the requesting-user identity and an agent-definition identifier sufficient for ceiling/policy resolution in the identity fabric fakes (per-definition ceiling posture recorded in 003; production fabric later). Missing required identity or definition inputs MUST refuse start.
- **FR-008**: Enforcement-path errors on the adapter path (governance/capability fault, missing required governance enforcement set, identity/authority failure) MUST deny or refuse start; they MUST NOT allow (ADR-0006).
- **FR-009**: Durability and interrupt mappings MUST bind to core/provider seams (fakes acceptable); they MUST NOT introduce an adapter-local second enforcement or credential store. Full durability resume scenarios and rich approval UX are not required for acceptance of the thin mappings.
- **FR-010**: Audit, spans, logs, and model-visible context on adapter-path runs MUST NOT contain raw secret or credential values — references, hashes, or redacted metadata only.
- **FR-011**: The shared conformance suite MUST include primary-adapter cases for governance-first ordering and fail-closed denial; `make conformance` MUST execute those cases (001 command contract becomes real for this adapter).
- **FR-012**: Deterministic tests for this feature MUST NOT call live models, live identity providers, live Vault, or live managed-product APIs; stub models / scripted agents and harness fakes are required. An automated check MUST assert this over the feature's test paths — convention alone is not sufficient verification.
- **FR-013**: User-facing denial and refusal messages on the adapter path MUST explain that the action was denied or unavailable without disclosing secrets or out-of-scope entitlements the requester must not see.
- **FR-014**: A second framework adapter MUST NOT ship in this feature (ADR-0017 demand-driven fast-follow remains later).
- **FR-015**: Primary-adapter conformance cases MUST be enforced in continuous integration for changes touching the adapter or its conformance lane; a locally-run result recorded in a pull-request description MUST NOT substitute for that gate (Principle IX — evidence over claims; `contracts/conformance-adapter.md` invariant 1).
- **FR-016**: Core changes in this feature are bounded to exactly three extensions: (1) a framework-agnostic durability protocol with an in-memory default; (2) a framework-agnostic approval-hook protocol with a deny-by-default double; (3) an agent-definition identifier required at governed run start and threaded into ceiling and policy resolution. Any other sealed-core change — hook algebra, audit schema, registry lifecycle, authority intersection — is out of scope for this feature and requires its own approved spec (Principle V).

### Key Entities

- **Primary adapter**: Thin sealed-core binding from the Accepted primary agent framework to harness core; four mappings only.
- **Governance capability**: The mandatory governance unit composed into the framework agent; runs first among co-resident capabilities and fails closed (glossary *GovernanceCapability*).
- **Co-resident capability**: Any additional capability composed alongside governance; must not precede governance on a tool call.
- **Adapter-started governed run**: A 002/003 governed run whose initiation and tool calls are reached through the adapter mappings.
- **Agent definition identifier**: Stable handle for the agent definition used to resolve ceilings/policy for the run (fake-resolved in this feature).
- **Durability seam (thin)**: The state-mapping target for framework state; full provider resume product is out of scope.
- **Approval-hook path (thin)**: The interrupt-mapping target; rich human-approval UX is out of scope.
- **Conformance suite (adapter lane)**: Shared suite cases that assert governance-first and fail-closed on the primary adapter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of in-scope allow-path adapter suite cases show exactly one tool-body execution when allowed, and zero when denied.
- **SC-002**: 100% of adapter-path denial and enforcement-error cases end in deny or refuse-start with zero tool-body executions (fail closed).
- **SC-003**: At least one conformance case fails if governance order on the primary adapter is reversed; at least one fails if an injected governance/enforcement error allows the tool body.
- **SC-004**: For every adapter-path tool allow or deny in the suite, an investigator can retrieve a non-empty audit trail by correlation ID that includes the decision for that call.
- **SC-005**: 100% of adapter-started allow-path cases that bind task authority satisfy the 003 narrowing property (`assert_scope_narrowed` or equivalent suite assertion).
- **SC-006**: Automated fixture assertions find zero raw secret or credential values in audit, spans, logs, or model-visible context produced by the adapter suite.
- **SC-007**: `make conformance` executes primary-adapter conformance cases (no longer a no-op stub for this lane) and passes on a clean tree, and the same command runs in CI on adapter-touching changes so a failure blocks merge.
- **SC-008**: The feature's `src/core` diff contains only the three extensions enumerated in FR-016; a reviewer can enumerate every changed core file and match each to one of them.

## Assumptions

- This feature ships as **adapter glue + conformance/deterministic tests + three bounded core-seam extensions** on top of landed 002 core and 003 authority. The core extensions are enumerated and capped by FR-016 (durability protocol, approval-hook protocol, required agent-definition identifier); the third is a **breaking change** to `start_governed_run` and is exempt from a deprecation window only because the project is pre-1.0 with no external consumers of that seam. Production IdP/Vault and real product APIs remain fakes.
- Naming the primary framework follows **Accepted ADR-0017** (Pydantic AI); that choice is a product decision already on the decision record, not an open implementation debate in this spec.
- Full durability/resume (ADR-0024 scenarios, re-auth-never-replay) remains a later feature; 004 only requires the thin state → durability-seam mapping with fakes sufficient for conformance.
- Rich human-in-the-loop approval UX, Control Groups (ADR-0016), capability packs, northbound surfaces (ADR-0033), multi-tenancy, code mode (ADR-0041), and deferred-tool-disclosure productization (ADR-0040) remain out of scope; interrupt and loading edges are thin mappings or explicitly deferred.
- Warn-mode for local develop remains out of scope; **004's default and test bar is enforce/fail-closed**.
- Conformance may retain placeholders for a future second adapter without implementing it; empty/skipped secondary slots must not weaken the primary adapter's required assertions.
- Dependency addition for the primary framework is expected and must be justified at implementation PR time per AGENTS.md / CONTRIBUTING (regulated dependency-tree bar) — the *decision* to depend is ADR-0017; the pin/justification is an implement-time duty.
