# Feature Specification: Per-Task Authority

**Feature Branch**: `spec/003-per-task-authority`

**Path**: `specs/003-per-task-authority/spec.md`

**Created**: 2026-07-25

**Status**: Planned

**Input**: User description: "Deliver per-task authority on top of the governed core: manufacture short-lived credentials for each governed run so effective authority equals the intersection of requesting user, agent ceiling, task scope, and policy — an agent never exceeds its human. Enforce entitlement mirroring for product actions. Hold no standing credentials to managed products. Demonstrate with deterministic tests and harness helpers (including assert_scope_narrowed). Out of scope: production IdP/Vault fabric (use fakes), Control Groups UI, adapters, capability packs, durability/resume, northbound surfaces, live models, and real managed-product APIs."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2, R3 (per-task authority, zero standing credentials to managed products, effective authority intersection). R7 (fail-closed when identity, exchange, ceiling, or entitlement checks error). Builds on R4/R10/R13 correlation/evidence already landed in 002. |
| **ADRs touched** | ADR-0015 (control-plane trust fabric — ceilings and exchange as the source of authority bounds), ADR-0026 (per-step / short-lived tokens under a grant; checkpoints hold state never credentials — binding for any authority material this feature introduces), ADR-0044 (two authorization domains; entitlement mirroring; federate-before-broker; confused-deputy pre-check for brokered grain), ADR-0006 (enforcement-path errors deny, including identity/exchange unavailable) |
| **Evidence class** | Attestation-relevant — authority decisions, denials for amplification/mirroring failures, and credential lifecycle events join the run's correlation ID and audit trail |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - In-scope task receives narrowed authority and may proceed (Priority: P1)

An operator (or test) starts a governed run on behalf of a requesting user against an agent definition with a ceiling. The platform manufactures short-lived task authority that is at most the intersection of the user's entitlements, the agent ceiling, the declared task scope, and applicable policy. An in-scope registered tool call that stays within that effective authority is allowed through the existing hook pipeline; the authority decision is audited and correlated.

**Why this priority**: Without a working manufacture-and-allow path that still proves narrowing, denials cannot be shown as the exception to a correct baseline.

**Independent Test**: With fakes for identity and ceilings, start a run whose task scope is a strict subset of the user and ceiling; invoke one in-scope tool; assert allow, `assert_scope_narrowed`, correlated audit of the authority decision, no secret credential values in audit/spans/model context.

**Acceptance Scenarios**:

1. **Given** a requesting user, an agent ceiling, and a task scope that does not exceed either, **When** a governed run starts, **Then** short-lived task authority is issued whose effective scope is within user ∩ ceiling ∩ task scope ∩ policy.
2. **Given** that run, **When** the agent invokes a registered in-scope tool within effective authority, **Then** the call is allowed once through the hook pipeline and completes successfully.
3. **Given** that successful path, **When** an investigator inspects audit by correlation ID, **Then** they find the authority-issuance (or binding) record and the tool decisions joinable to the same ID.
4. **Given** issued task authority, **When** credential material is inspected in audit, spans, logs, and any model-visible context, **Then** only references or redacted metadata appear — never raw secret values.

---

### User Story 2 - Amplification and out-of-ceiling scope are denied (Priority: P1)

A run is requested with a task scope wider than the user, wider than the agent ceiling, or otherwise outside policy. The platform refuses to issue amplified authority. If a tool call would require authority beyond the effective set, it is denied before execution with no product side effects.

**Why this priority**: "Agent never exceeds human" and "scopes only narrow" are the platform's central authority claims (glossary *effective authority*, ADR-0044).

**Independent Test**: Attempt run start or tool invoke that would amplify beyond the user or ceiling; assert deny or refuse-start, zero side effects, `assert_scope_narrowed` holds on any issued token (or no token issued), audited denial, no secret leakage.

**Acceptance Scenarios**:

1. **Given** a user and ceiling, **When** a run is requested with a task scope that exceeds the user or the ceiling, **Then** run start is refused (fail closed) and no task credential is issued.
2. **Given** an active run with narrowed authority, **When** the agent attempts a tool call requiring broader authority than the effective set, **Then** the call is denied before the tool body runs.
3. **Given** either refusal, **When** side-effect counters for product fakes are inspected, **Then** they show zero executions.

---

### User Story 3 - Entitlement mirroring for product actions (Priority: P1)

When a tool acts in a managed product (via test doubles), harness-domain and product-domain checks both apply. For a brokered-style product fake (shared-grain credential), a pre-tool-use check resolves the requesting user's own effective product entitlements and enforces them before any shared-grain credential is wielded — no amplification, no arbitrary reduction relative to that user. A user with narrower product permissions than the shared grain cannot perform what the grain would otherwise allow.

**Why this priority**: ADR-0044's confused-deputy compensating control; silent failure here falsifies "acts with the user's authority" in the product domain.

**Independent Test**: Scripted agent on a brokered product fake; user entitlements narrower than the shared grain; assert deny for the excess action, zero product mutation, audited mirroring denial under the correlation ID.

**Acceptance Scenarios**:

1. **Given** a brokered product fake and a user whose product entitlements exclude action A, **When** the agent requests A under a shared-grain credential, **Then** the pre-tool-use mirroring check denies before the credential is wielded and A does not execute.
2. **Given** the same setup where action B is within the user's product entitlements and the harness effective authority, **When** the agent requests B, **Then** mirroring allows and B executes once.
3. **Given** a federated-style product fake that validates external identity without a shared-grain broker, **When** the agent acts within the user's mirrored entitlements, **Then** the call may proceed without introducing a standing product credential into the harness.

---

### User Story 4 - Authority and identity failures deny (fail closed) (Priority: P1)

If identity is missing, token exchange fails, ceiling lookup fails, entitlement resolution errors, or a required authority dependency is unavailable, the outcome is deny (or refuse run start) — never allow. Failures are audited without leaking secrets.

**Why this priority**: ADR-0006 and Principle III — allow-on-identity-error falsifies the platform.

**Independent Test**: Inject faults into fake identity fabric / exchange / entitlement resolver; assert deny or refuse-start, no tool execution, audited failure, `assert_no_secret_values`.

**Acceptance Scenarios**:

1. **Given** a otherwise-valid run request, **When** the identity or exchange dependency errors, **Then** the run does not become active with usable authority (refuse or deny-closed).
2. **Given** an active run, **When** a pre-tool entitlement or exchange refresh errors, **Then** the tool body does not execute and the outcome is deny.
3. **Given** any such failure, **When** audit, spans, and messages are inspected, **Then** they contain no secret values.

---

### User Story 5 - Short-lived authority expires; harness asserts narrowing (Priority: P2)

Task credentials expire. After expiry, further tool calls are denied until authority is re-manufactured under the same rules (no silent reuse of expired material). Contributors use `assert_scope_narrowed` and related harness helpers to prove narrowing in tests.

**Why this priority**: Expiry is load-bearing for blast-radius; the helper is already promised in TESTING.md and must bind to real guarantees.

**Independent Test**: Advance a frozen clock past TTL; assert next invoke denies; separately, unit/component tests import and apply `assert_scope_narrowed` successfully on narrowed tokens and fail when given an amplified token fixture.

**Acceptance Scenarios**:

1. **Given** an active run whose task credential has expired, **When** the agent invokes a tool, **Then** the call is denied before execution (fail closed on expiry).
2. **Given** the test harness, **When** a contributor writes an authority test, **Then** they can use `assert_scope_narrowed` under the documented `tests.harness` import path.
3. **Given** a fixture token amplified beyond the user, **When** `assert_scope_narrowed` is applied, **Then** the assertion fails.

### Edge Cases

- What happens when the requesting user identity is absent at run start? Run start is refused; no uncorrelated and no unauthenticated authority work proceeds.
- What happens when task scope equals the user and ceiling exactly? Authority may issue at that bound; narrowing means "at most," not "strictly less."
- What happens when a post-issuance policy change would shrink authority mid-run? The next enforcement check must observe the stricter bound or deny; stale wider authority must not win (fail closed toward the narrower effective set).
- What happens when entitlement resolution returns empty for a brokered action? Deny; empty entitlements are not treated as unrestricted.
- What happens when credential manufacture succeeds but audit cannot record the issuance? The run must not proceed as a clean success with an incomplete evidence trail (same evidential-gap posture as 002 for un-auditable enforcement outcomes).
- Are standing credentials to managed products ever stored in run state or checkpoints? No — checkpoints and run state hold state only, never credentials (ADR-0026). This feature must not introduce a path that persists task credential values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each governed run that proceeds past start MUST bind short-lived task authority manufactured for that run; the harness MUST NOT rely on a standing credential to a managed product to authorize agent tool calls (ADR-0044 / Principle IV). The platform's sole named standing-credential exception (broker management token) is out of scope for introduction in this feature's deliverable — brokered behavior is exercised with fakes that do not embed standing secret values in the repository.
- **FR-002**: Effective authority for a run MUST be at most user ∩ agent ceiling ∩ task scope ∩ policy. No issued task authority may exceed the requesting user's authority (ADR-0044; glossary *effective authority*).
- **FR-003**: Scopes MUST only narrow along the authority binding for the run. Amplifying task scope above the user or ceiling MUST be refused at start or denied at enforcement (ADR-0026 act-chain narrowing as applicable to this single-run model).
- **FR-004**: Product-domain actions MUST apply entitlement mirroring: the agent acts with the requesting user's own product authority — no amplification and no arbitrary reduction — with harness-side and product-side checks agreeing independently in the test doubles (ADR-0044).
- **FR-005**: For brokered-style product fakes that use a shared-grain credential, a pre-tool-use check MUST resolve the user's own effective product entitlements and enforce them before that credential is wielded (ADR-0044 confused-deputy control).
- **FR-006**: Federate-before-broker MUST be reflected in the authority model: where a product fake can validate external identity, the path MUST NOT require a standing product credential in the harness; brokered paths are used only when federation is not available in the fake's configured mode (ADR-0044).
- **FR-007**: Errors in identity presence, ceiling resolution, token exchange, entitlement resolution, or other required authority dependencies MUST deny or refuse start; they MUST NOT allow (ADR-0006).
- **FR-008**: Expired task credentials MUST NOT authorize further tool execution; the next tool call after expiry MUST deny until authority is re-manufactured under FR-002–FR-003.
- **FR-009**: Authority issuance, denial, mirroring decisions, and expiry denials MUST appear in the run's append-only audit trail under the run's correlation ID (joining the 002 evidence plane).
- **FR-010**: Audit, spans, logs, and model-visible context MUST NOT contain raw credential secret values — references, hashes, or redacted metadata only.
- **FR-011**: Run state and any checkpoint-shaped structures touched by this feature MUST NOT persist credential secret values (ADR-0026).
- **FR-012**: The test harness MUST provide `assert_scope_narrowed` under `from tests.harness import …` as documented in docs/development/testing.md, and the helper MUST enforce the narrowing property against real authority objects produced by this feature.
- **FR-013**: Deterministic tests for this feature MUST NOT call live identity providers, live Vault, live models, or live managed-product APIs; fakes (`fake_identity_fabric` and related harness fakes) are required.
- **FR-014**: User-facing denial and refusal messages MUST explain that authority was denied or unavailable without disclosing secrets or out-of-scope entitlements the requester must not see.
- **FR-015**: When authority manufacture or a mirroring check cannot be audited (audit-append failure on that enforcement path), the outcome MUST NOT be clean success; the evidential-gap posture from the governed-core contract applies.

### Key Entities

- **Requesting user**: The human identity on whose behalf the run acts; the upper bound for amplification checks.
- **Agent ceiling**: The compiled maximum authority of the agent definition; no task scope may exceed it.
- **Task scope**: The declared scope for this run; must sit within user and ceiling.
- **Effective authority**: The intersection user ∩ ceiling ∩ task scope ∩ policy that authorizes tool calls for the run.
- **Task credential**: Short-lived authority material bound to the run; expires; never a standing product credential.
- **Product entitlement set**: The user's own effective permissions in a managed product, used for mirroring checks.
- **Identity / exchange fake**: Test double for registration, ceilings, and token exchange without a live control plane.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of suite cases that attempt task scope above the user or ceiling refuse start or deny without issuing amplified authority.
- **SC-002**: 100% of in-scope allow-path cases produce task authority for which `assert_scope_narrowed` passes against the requesting user bound.
- **SC-003**: 100% of brokered-mirroring denial cases (user lacks product entitlement) end in deny with zero product side effects.
- **SC-004**: 100% of injected identity/exchange/entitlement failures end in deny or refuse-start with zero tool-body executions.
- **SC-005**: 100% of post-expiry tool attempts in the suite are denied before tool-body execution.
- **SC-006**: Automated fixture assertions find zero raw credential secret values in audit, spans, logs, or model context produced by the suite.
- **SC-007**: For every authority issuance or authority denial in the suite, an investigator can retrieve a non-empty audit record under the run correlation ID that includes that decision.

## Assumptions

- This feature ships as **core library behavior + test harness fakes/helpers**, exercised by deterministic tests on top of the 002 governed run/hook/audit pipeline. Production IdP, control-plane Vault, and real product brokers are represented by fakes with recorded semantics.
- Control Groups (ADR-0016) continue to gate real ceiling/definition changes in production; **mutating ceilings via Control Groups is out of scope** here — tests supply ceiling fixtures as inputs.
- Full durability/resume (re-auth never replay, grant parking) remains a later feature; this feature still forbids persisting credential values in run state and covers expiry on an active run via a frozen clock.
- Multi-agent act-chain handoff across agents is out of scope; single requesting user → single agent run is the model.
- Warn-mode authority checks for local develop are out of scope; **003's default and test bar is enforce/fail-closed**.
- The TFE (or other) broker management token — the constitution's sole standing-credential exception — is **not** introduced as a real secret or client in this feature; brokered paths are simulated without embedding standing credentials in the tree.
