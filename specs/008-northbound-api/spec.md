# Feature Specification: Northbound API

**Feature Branch**: `spec/008-northbound-api`

**Path**: `specs/008-northbound-api/spec.md`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "First of the four transports ADR-0033 names, and the one the other three consume rather than reimplementing. Human authentication against the organization's own OIDC provider; machines by workload identity federation; no static API keys, ever. Carries the audit plane as a governed read path (ADR-0035): tenant-scoped, cannot mutate or mask, and evidence access is itself audited. Out of scope: MCP, CLI, portal — each its own spec; the MCP one additionally carries dependency health checks and the resume sweeper."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2 / R3 (per-task authority — surface authentication is the root of the delegation chain, so the authenticated human becomes the subject of every subsequent exchange). R5 / R11 / R15 (total interception — an API operation reaches tools through the same governed path, never beside it). R7 (fail-closed). R4 / R10 / R13 (evidence — audit becomes a *read* path here, and reading it is itself audited). R16 (sealed core, versioned seams). |
| **ADRs touched** | ADR-0033 (four transports over one authorization core; parity conformance-asserted; no static API keys), ADR-0035 (audit as a governed read path — tenant-scoped, cannot mutate or mask, evidence access audited), ADR-0016 (claim-to-role mapping is an authority change, gated), ADR-0015 (control-plane Vault). Related deferred: ADR-0034 (conversational web UI — the portal, its own spec). |
| **Evidence class** | Attestation-relevant and audit-critical. This is where a *human* identity enters the system and becomes the subject of everything downstream — non-repudiation depends on it. It is also the first path that lets someone **read** the audit trail, which is a new class of access the platform has never granted. |

## Clarifications

### Session 2026-07-27

- Q: Why is the API first among the four transports? → A: The other three consume it. A CLI or portal that reaches the authorization core directly is a second authorization path wearing a different name, and ADR-0033's parity guarantee would then be asserted between things that do not share an implementation. Building the API first makes "one authorization core" structural rather than aspirational.
- Q: Can surface parity be asserted by this feature? → A: No, and claiming otherwise would be a stub. Parity is a property *between* transports; with one surface there is nothing to compare. The owed gate row stays owed until a second transport lands, and this feature's job is to make that comparison possible — a documented operation set with recorded verdicts — rather than to declare the row satisfied.
- Q: Does the API introduce its own authentication? → A: No. Humans authenticate against the organization's own OIDC provider; machines use workload identity federation. **There are no static API keys, on any surface, ever** (ADR-0033). The platform holds no credential store, which is also why it cannot leak one.
- Q: Is reading the audit trail just another read? → A: No — it is a new class of access, and this feature is where it first exists. Evidence access is itself audited (ADR-0035): a meta-audit record of who reviewed which evidence and when, because the integrity of an audit trail includes knowing who read it.

- Q: What operations does the API actually expose? The first draft said "every operation that invokes a tool" without saying what the surface is. → A: **Run lifecycle and evidence, not direct tool invocation.** Start a governed run, query its state, and read audit. A caller invoking a tool directly through the API would be acting *beside* the agent rather than through it — a second path to the governed core, which is the shape Principle II exists to prevent. Tools are reached by an agent within a run; the API starts runs and reads what happened.
- Q: Then what does FR-007 govern, if the API does not invoke tools? → A: The run a caller starts. Everything that run does reaches tools through the governed path, and the API adds no route around it. Reworded so it constrains the right thing.
- Q: Does starting a run block until it finishes? → A: No. Runs are durable and long by design (005); an API that blocked until completion would contradict the feature that exists to let work outlive a process. Starting a run returns a handle, and state is queried. This also keeps the API honest about what it is — a way to *start* and *observe* work, not a way to *perform* it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A person authenticates as themselves, and stays themselves (Priority: P1)

Someone reaches the platform through the API using their organization's identity provider.
From that point on, every action taken on their behalf carries their identity — into
authority manufacture, into tool calls, into the audit trail.

**Why this priority**: This is the root of the delegation chain. If the subject is wrong or
missing here, every downstream guarantee is about the wrong person, and non-repudiation is
gone. Nothing else in this feature matters if this is wrong.

**Independent Test**: Authenticate through the API against a test identity provider; invoke
an operation; assert the authenticated subject appears as the subject of the manufactured
authority and in every audit record for that correlation ID.

**Acceptance Scenarios**:

1. **Given** a valid identity from the organization's provider, **When** an operation is
   invoked, **Then** the manufactured authority names that identity as its subject.
2. **Given** the same operation, **When** the audit trail is read, **Then** the identity
   appears in every record for that correlation ID.
3. **Given** an absent, expired, or unverifiable identity, **When** an operation is
   attempted, **Then** it is refused and nothing executes.
4. **Given** a run whose work outlasts the request, **When** it is started, **Then** the
   response returns a handle while the run is still executing (FR-007a).
5. **Given** that handle, **When** run state is queried, **Then** it is returned without the
   caller having held a connection open.

---

### User Story 2 - There is no API key to steal (Priority: P1)

An operator looking for a way to automate against the platform finds workload identity
federation and no static key — because none exists to find.

**Why this priority**: ADR-0033 forbids static keys *on any surface, ever*, and the API is
where the temptation is greatest: automation wants a credential it can paste into a config.
A single exception here would become the way everyone integrates.

**Independent Test**: Search the implementation and its configuration for any long-lived
bearer credential the platform issues or accepts. Assert none exists, and that a machine
caller authenticates by federated workload identity.

**Acceptance Scenarios**:

1. **Given** the API, **When** its authentication paths are enumerated, **Then** none
   accepts a platform-issued static key.
2. **Given** a machine caller, **When** it authenticates, **Then** it does so by workload
   identity federation.
3. **Given** an attempt to configure a static credential, **Then** there is no supported
   way to do it.

---

### User Story 3 - An API operation cannot bypass governance (Priority: P1)

The API exposes no way to invoke a tool. Tools are reached by an agent within a run the
API started, through the same governed path as everything else — the same hooks, the same
authority checks, the same audit records.

**Why this priority**: A transport is exactly where a second execution path grows, because
it is easy to add "just this one endpoint" that calls a handler directly. Principle II
exists because that is the failure that ends the platform's guarantees quietly.

**Independent Test**: Walk the application's registered routes and assert none reaches a
tool body; then assert that a run started through the API reaches tools through the
governed path with its hooks intact.

**Acceptance Scenarios**:

1. **Given** the application's registered routes, **When** they are enumerated, **Then**
   none exposes direct tool invocation.
2. **Given** a run the API started, **When** it invokes a tool, **Then** the call passes
   through the governed path with its hooks.
3. **Given** a denied operation, **When** it is attempted, **Then** nothing executes and the
   denial is audited.
4. **Given** the implementation, **When** it is inspected, **Then** no route executes a tool
   body outside the governed path.

---

### User Story 4 - Someone can read the audit trail, bounded by what they may see (Priority: P1)

A compliance analyst asks a question about the estate and gets an answer bounded by their own
entitlements. A team's developer asks the same question and gets their team's slice.

**Why this priority**: ADR-0035 makes audit a governed read path, and this feature is where
that first exists. Before it, evidence was written and never read through the platform —
which means this is a new class of access, not an extension of an existing one.

**Independent Test**: Query the audit plane as two identities with different entitlements;
assert each sees only what their scope permits, and that neither can widen it.

**Acceptance Scenarios**:

1. **Given** two identities with different entitlements, **When** each queries the same
   audit range, **Then** each result is bounded by that identity's own scope.
2. **Given** any audit query, **When** it is attempted, **Then** it cannot mutate, delete,
   or mask any record.
3. **Given** a completed audit query, **When** the trail is examined, **Then** a record
   exists of who read which evidence, and when.

---

### User Story 5 - The API is describable enough to compare against (Priority: P2)

Someone building the second transport can see exactly which operations exist and what verdict
each produces, so parity is a comparison rather than an argument.

**Why this priority**: The owed parity gate row cannot be satisfied by this feature, but it
can be made *satisfiable*. An undocumented operation set means the second transport's parity
claim is asserted against whatever the first happens to do.

**Independent Test**: Assert every exposed operation appears in a machine-readable
description, and that the description is generated from the implementation rather than
maintained beside it.

**Acceptance Scenarios**:

1. **Given** the API, **When** its operations are enumerated, **Then** each appears in a
   machine-readable description.
2. **Given** an operation added without describing it, **Then** that is detectable.

### Edge Cases

- What happens when the identity provider is unreachable? Authentication fails closed. No
  cached identity is honoured past its validity, and no fallback credential exists — there
  is nothing to fall back to, by design.
- What happens when a token is valid but its claims map to no role? Refused. An unmapped
  claim is not a default role; claim-to-role mapping is governed configuration and its
  absence is not permission.
- What happens when someone queries audit for a tenant they do not belong to? They see
  nothing, and the attempt is itself audited. An empty result and a refused query must be
  distinguishable to an investigator.
- Can an audit query alter what it reads? No. The path has no capability to mutate, and that
  is enforced rather than merely unimplemented.
- What happens if a claim-to-role mapping change is attempted through the API? It is an
  authority change, gated by quorum (ADR-0016, 007). The API surfaces the request; it does
  not decide it.
- Does this feature assert surface parity? No. Parity is a property between transports and
  there is one. The row stays owed.
- Does the API pause a run to ask a human anything? No. Nothing in this platform does
  (ADR-0049, Proposed).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Human callers MUST authenticate against the organization's own OIDC identity
  provider. The platform MUST NOT operate its own credential store for human identities.
- **FR-002**: Machine callers MUST authenticate by workload identity federation.
- **FR-003**: The API MUST NOT accept or issue a static, long-lived credential of any kind.
  There MUST be no supported configuration that creates one.
- **FR-004**: The authenticated identity MUST become the subject of every subsequent
  exchange — authority manufacture, tool invocation, and every audit record for that
  correlation ID.
- **FR-005**: An absent, expired, or unverifiable identity MUST refuse the operation with
  nothing executed.
- **FR-006**: Claims that map to no role MUST refuse. An unmapped claim MUST NOT resolve to
  a default or implied role.
- **FR-007**: The API MUST NOT expose direct tool invocation. Tools are reached by an agent
  within a run; a caller invoking one directly would be acting beside the agent rather than
  through it, which is a second path to the governed core. Every tool call made by a run the
  API starts MUST reach the governed path, and no route may execute a tool body otherwise —
  asserted rather than reviewed.
- **FR-007a**: Starting a run MUST return a handle rather than blocking until completion,
  and run state MUST be queryable through that handle. Runs are durable and long by design;
  an API that blocked until a run finished would contradict the feature that exists to let
  work outlive a process.
- **FR-008**: Audit MUST be readable through the API as a governed read path, bounded by the
  querying identity's own entitlements.
- **FR-009**: The audit read path MUST NOT be able to mutate, delete, or mask any record.
- **FR-010**: Evidence access MUST itself be audited — who read which evidence, and when.
- **FR-010a**: Evidence-access records MUST be written to a **dedicated, stable
  evidence-access stream**, chained among themselves, and MUST name the correlation IDs they
  read. Two properties have to hold at once and each is easy to obtain by sacrificing the
  other. Appending to the queried run's chain would let reading evidence write into the
  evidence being read, which is what FR-009 protects. Minting a fresh correlation ID per read
  would leave every record a chain of one — linked to nothing, and therefore **deletable
  without detection**, which defeats the reason the record exists. A per-tenant stream gives
  both: records are tamper-evident against each other and touch no run's chain.
- **FR-010b**: If the evidence-access record cannot be written, the read MUST fail and
  return nothing. FR-010 says every access is audited; an access that succeeded while its
  record did not is exactly the case the requirement exists to prevent. This matches how run
  start already behaves — it refuses when its own audit write fails.
- **FR-010c**: Writing an evidence-access record MUST be safe under concurrent readers. The
  stream is shared by every reader in a tenant, so two simultaneous reads must not race for
  the same position, and neither may be silently dropped. Run chains have one writer each and
  never needed this; the evidence stream has one writer per reader, by design.
- **FR-010d**: Each stream's highest position MUST be recorded where the evidence read path
  cannot reach it, so that **truncation** is detectable. A hash chain proves that records were
  not modified and that none was removed from the middle; it cannot prove that the most recent
  records still exist, because a truncated chain remains internally valid. Deleting the latest
  entries is the likeliest tampering against a record of who read what.

- **FR-011**: A query that reaches beyond the caller's tenant MUST return nothing, and MUST
  be distinguishable in the audit trail from a query that legitimately found nothing.
  **The reachable form of this attempt must be the one tested**: the request carries no
  tenant parameter (a caller-supplied tenant would be a request to widen scope), so a
  cross-tenant attempt is made by narrowing to a correlation ID or run ID belonging to
  another tenant. A check written against a parameter the surface does not expose would
  assert something unreachable and pass regardless of behaviour.
- **FR-012**: Every exposed operation MUST appear in a machine-readable description
  generated from the implementation, so a later transport can compare against it.
- **FR-013**: Changing claim-to-role mapping through the API MUST be an authority change
  subject to quorum (ADR-0016), not an administrative edit.
- **FR-014**: This feature MUST NOT claim the four-transport parity gate row. Parity is a
  property between transports; with one surface there is nothing to compare, and a row
  claiming otherwise would be a stub (ADR-0047).
- **FR-015**: Nothing in this feature may pause, interrupt, or block a run awaiting a human.
- **FR-016**: If the identity provider is unreachable, authentication MUST fail closed. No
  cached identity may be honoured past its validity.

### Key Entities

- **Authenticated subject**: The human or workload identity established at the surface. The
  root of the delegation chain, and the subject of every downstream record.
- **Claim-to-role mapping**: Governed configuration translating provider claims into platform
  roles. Changing it is an authority change.
- **Evidence query**: A read against the evidence plane, bounded by the querying identity's
  entitlements. Called this consistently across every artifact — "audit query" and "audit
  read" are the same thing and the drift is not meaningful.
- **Evidence-access record**: The meta-audit entry recording who read which evidence — because
  the integrity of an audit trail includes knowing who read it.
- **Run handle**: What starting a run returns. The thing a caller holds to ask what
  happened, rather than a connection they hold open while it happens.
- **Operation description**: The machine-readable enumeration a later transport compares
  against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of operations carry the authenticated identity as their subject into
  authority manufacture and every audit record.
- **SC-002**: Zero static credentials are accepted or issued by any API path.
- **SC-003**: 100% of absent, expired, or unverifiable identities refuse with zero
  executions.
- **SC-004**: 100% of unmapped claims refuse; zero resolve to a default role.
- **SC-005**: 100% of tool calls made by API-started runs reach the governed path; zero
  execute a tool body outside it, and zero API routes expose direct tool invocation.
- **SC-005a**: 100% of run starts return a handle without blocking; zero hold a connection
  open for the duration of a run.
- **SC-006**: For two identities with differing entitlements, 100% of audit query results are
  bounded by the querying identity's scope; zero leak across that boundary.
- **SC-007**: Audit queries mutate, delete, or mask records in zero cases.
- **SC-008**: 100% of evidence accesses produce a meta-audit record naming who and when.
- **SC-009**: A query narrowing to another tenant's correlation or run ID returns zero
  records and is distinguishable in the audit trail from a legitimately empty result, in
  100% of cases.
- **SC-009a**: 100% of evidence-access records land on the evidence-access stream and chain
  to their predecessor; zero are appended to the chain of a run they read, and zero are
  unchained singletons. Modifying a record and removing one from the middle are both detected
  by the chain; **removing the most recent records is detected by the recorded head**
  (FR-010d), which the chain alone cannot do.
- **SC-009b**: Under concurrent readers in one tenant, 100% of evidence-access records are
  written; zero are lost and zero collide. Zero reads succeed whose record failed to write.
- **SC-010**: 100% of exposed operations appear in the generated description; an operation
  added without one is detected.
- **SC-011**: Zero runs are paused, interrupted, or blocked by anything in this feature.
- **SC-012**: With the identity provider unreachable, authentications succeed in zero cases.

## Requirements without a dedicated user story

Three requirements are cross-cutting rather than story-shaped, and are recorded here so
their absence from the story list is a decision rather than an oversight.

- **FR-007a** (run start returns a handle) is exercised by US1's scenarios 4 and 5 — it is a
  property of starting a run, not a story of its own.
- **FR-013** (claim-to-role mapping is an authority change) and **FR-016** (fail closed when
  the identity provider is unreachable) are covered by the Edge Cases above and by the
  conformance rows. Neither describes a user's goal; both describe what must not happen.

## Assumptions

- This feature ships as **the first of four transports**, on top of landed 002–007. It adds a
  surface; it does not change what the core decides.
- **The other three transports consume this API** rather than reaching the core directly. A
  CLI or portal with its own authorization path would make ADR-0033's "one authorization
  core" a name rather than a fact.
- **Surface parity is not asserted here.** The owed gate row stays owed until a second
  transport exists. What this feature owes is making the comparison *possible* — FR-012.
- The identity provider in development is a test double; the production one is the customer's.
  That double must exercise real OIDC flows rather than short-circuiting them, or this
  feature's central guarantee ships unproven.
- **The audit read path is a new class of access.** Before this, evidence was written and
  never read through the platform. Treating it as an ordinary query would miss that reading
  evidence is itself an auditable act.
- Claim-to-role mapping changes route through 007's quorum gate. This feature surfaces the
  request; it does not decide it.
- **Every audit record carries a tenant, including records from runs no surface started.**
  The adapter and the existing test suites call `start_governed_run` directly and have no
  identity provider to draw a claim from, so the platform resolves a **configured default
  tenant** and a subject's claim overrides it where one exists. Without this, adding tenant
  to the audit entry would stop the adapter from starting a run at all.
- MCP, CLI, and portal are each their own spec. The MCP one additionally carries the
  dependency health checks and resume sweeper decided in ADR-0049 (Proposed), because both
  need a long-lived home and the MCP service is the persistent one.
