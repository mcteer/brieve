# Feature Specification: Deployment Module Tree

**Feature Branch**: `spec/006-deployment-module-tree`

**Path**: `specs/006-deployment-module-tree/spec.md`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Deployment module tree: the enclave as the product's front door rather than a proof directory. One parameterized tree applied to a workstation and to customer infrastructure, with the substrate as the only permitted delta (ADR-0025, Principle VII). Closes three gaps: the parameterized tree itself, including the production posture dev deliberately lacks (TLS, HA, real unseal shape, root-token revocation); running the conformance suite as a Nomad job so the attestation path is exercised by the tests rather than proven separately; and a stated contract for what `make dev-up` guarantees on exit. Vault is never a Nomad job (ADR-0048). Out of scope: Kubernetes substrate implementation, multi-region/DR, a CI lane running the enclave, Control Groups, northbound surfaces, packs and eval gates, multi-tenancy."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2 / R3 (per-task authority — this feature makes the attestation chain the thing tests exercise rather than a thing proven alongside them). R12 (lean deployment — one tree, substrate as the only delta). R7 as implicated by fail-closed provisioning: a partially applied trust fabric must refuse rather than leave a half-configured control plane. Supports R4 / R10 / R13 (evidence) by making the environment those guarantees are proven against reproducible. |
| **ADRs touched** | ADR-0025 (enclave is the default topology — this is the tree that ADR implies, with the substrate as the only permitted delta), ADR-0048 (Nomad is the agent execution substrate; the trust store is provisioned by Terraform and is never a scheduled job; bootstrap order Terraform → Vault → Nomad → harness), ADR-0015 (control-plane Vault as trust fabric, including the bootstrap-credential revocation the dev proof skips), ADR-0007 (Lean and Federated profiles). Related deferred: ADR-0046 (multi-tenancy). |
| **Evidence class** | Attestation-relevant. The tree provisions the identity fabric every per-task authority claim rests on, and this feature is what makes the durability conformance rows run under a real attested identity rather than a development token. |

## Clarifications

### Session 2026-07-25

- Q: FR-015 permits the proof directory to be "explicitly retained with a recorded reason", but SC-010 requires exactly one supported way to stand up an environment. Which governs? → A: SC-010. The tree replaces the proof directory as the supported path. If any of it is kept it is kept as *reference material that cannot be applied* — not a second working tree. Two applicable trees is the fragmentation this feature exists to end, and a "recorded reason" is too weak a guard against it. FR-015 reworded to match.
- Q: SC-001 compares configurations across two substrates. Does verifying it require customer infrastructure? → A: No. The comparison is over the *configuration the tree produces*, so a plan-level application against a second substrate is sufficient and is the expected method. Requiring real infrastructure would make the central success criterion unverifiable in development, which would mean it never gets checked.
- Q: Does the development substrate become multi-node? → A: Not by this feature unless it implements availability under FR-010. The development enclave remains single-node, and 005's conformance caveat — fencing and parking proven against single-node behaviour, multi-node partition not exercised — persists until that changes. Recorded so landing this feature is not misread as having closed it.
- Q: What happens to the existing `dev-up` / `dev-down` / `dev-status` commands? → A: They become the tree's entry points rather than separate tooling. The bring-up contract in FR-008 is the contract those commands publish.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The same configuration produces a workstation enclave and a customer one (Priority: P1)

An operator applies the deployment tree to their laptop and gets a working enclave. A field
engineer applies the same tree to a customer's infrastructure and gets a working enclave there.
The two differ in where things run and nowhere else: trust fabric, agent registry, ceiling
policies, secrets engines, and dynamic roles are identical.

**Why this priority**: This is the feature. Anti-fragmentation (Principle VII) is only a real
constraint if one artifact serves both cases. Two trees that happen to agree today will not agree
in six months, and the disagreement will be discovered in a customer environment.

**Independent Test**: Apply the tree with the development substrate and with a second substrate;
compare the resulting control-plane configuration — auth methods, roles, policies, registry
entries, secrets engines — and assert it is identical. Assert every configuration difference
between the two invocations lives in the substrate layer.

**Acceptance Scenarios**:

1. **Given** the deployment tree, **When** it is applied with the development substrate, **Then**
   an enclave is produced with the trust fabric fully configured.
2. **Given** the same tree, **When** it is applied with a production-shaped substrate, **Then** the
   resulting trust configuration is identical to the development one.
3. **Given** either invocation, **When** the configuration is inspected, **Then** every difference
   between them is attributable to the substrate layer and nothing else.

---

### User Story 2 - The conformance suite runs under a real attested identity (Priority: P1)

The durability conformance rows execute inside a scheduled allocation. The test process presents
its own workload identity to the control plane, receives a short-lived state-store credential, and
runs. No static token exists anywhere for it to fall back on.

**Why this priority**: This closes the gap 005 left open. Those rows currently run on the host
against a development token, so the attestation path is proven *beside* the tests rather than *by*
them — a weaker claim than the conformance contract implies, and the only place a static token
still appears in the tree.

**Independent Test**: Run the conformance suite through the tree's supported entry point; assert it
executes as a scheduled workload, that its credential was minted for that workload's identity, and
that no static token is present in its environment, filesystem, or configuration.

**Acceptance Scenarios**:

1. **Given** a configured enclave, **When** the conformance suite is invoked, **Then** it runs as a
   scheduled workload with an identity of its own.
2. **Given** that run, **When** its credential source is inspected, **Then** the credential was
   issued to that workload's identity and is short-lived.
3. **Given** a workload with no valid identity, **When** it attempts the same run, **Then** it
   cannot obtain a credential and fails rather than falling back.
4. **Given** the repository after this feature, **When** it is searched for token-substituting
   development credential paths, **Then** none remain.

---

### User Story 3 - Standing up an environment tells you what it guarantees (Priority: P1)

Someone runs the documented bring-up command. When it returns successfully they know exactly what
is true: which services are reachable, that the trust fabric is configured, that the state store is
migrated. When it cannot deliver that, it fails and says which part is missing.

**Why this priority**: Test setup currently has to guess what it may assume. A bring-up that returns
success without stating what success means pushes that uncertainty into every suite depending on
it, and the failure then surfaces as a confusing test error rather than an environment one.

**Independent Test**: Run bring-up on a clean machine; assert each guarantee it claims actually
holds. Remove one prerequisite and assert bring-up fails naming that prerequisite rather than
returning success.

**Acceptance Scenarios**:

1. **Given** a clean machine with prerequisites present, **When** bring-up completes successfully,
   **Then** every guarantee in its stated contract holds.
2. **Given** a missing prerequisite, **When** bring-up runs, **Then** it fails and names what is
   missing.
3. **Given** an environment already up, **When** bring-up runs again, **Then** it succeeds without
   changing or destroying existing state.

---

### User Story 4 - Production posture is present or explicitly deferred, never silently absent (Priority: P2)

An operator preparing a customer deployment can see in one place which production hardening the tree
provides and which it does not: transport security, availability, how the trust store is unsealed,
and whether the bootstrap administrative credential still exists.

**Why this priority**: The development enclave deliberately lacks all four. That is fine while it is
labelled a proof and dangerous the moment it becomes the front door — the failure mode is an
operator assuming production posture they did not get. Below P1 because a tree honest about lacking
these is still useful; one silent about it is not.

**Independent Test**: For each of the four posture items, assert the tree either implements it or
carries a recorded deferral with a reason. Assert no item is simply missing.

**Acceptance Scenarios**:

1. **Given** the tree, **When** its production posture is reviewed, **Then** transport security,
   availability, unseal shape, and bootstrap-credential lifecycle are each either implemented or
   explicitly deferred with a reason.
2. **Given** a deferred item, **When** the deferral is read, **Then** it states what the operator
   must supply and the consequence of not supplying it.
3. **Given** configuration applied to a production-shaped substrate, **When** the bootstrap
   administrative credential's lifecycle is inspected, **Then** it does not survive configuration
   indefinitely.

---

### User Story 5 - The traps the proof already paid for do not have to be paid again (Priority: P2)

Someone standing up an environment for the first time does not rediscover the failures the proof
directory already hit — each of which failed with a message pointing somewhere other than its cause.

**Why this priority**: Six specific traps are already documented and cost real time to diagnose.
Carrying them as knowledge rather than as code means the second person pays the same price. Below
P1 only because the environment works once you know them.

**Independent Test**: For each recorded trap, assert the tree either prevents the condition or
detects it and reports the actual cause rather than the surface symptom.

**Acceptance Scenarios**:

1. **Given** a condition matching a recorded trap, **When** the tree encounters it, **Then** it
   either prevents it or reports the underlying cause.
2. **Given** a trust store whose data does not match its configured node identity, **When** bring-up
   runs, **Then** it reports that mismatch rather than appearing to start and never becoming
   available.
3. **Given** a sealed trust store, **When** configuration is applied, **Then** it refuses rather
   than proceeding and discarding its own record of what exists.

### Edge Cases

- What happens when the trust store is already initialized? It is unsealed, never re-initialized.
  Re-initializing discards the store and invalidates every credential derived from it, and is the
  most expensive mistake available in this system.
- What happens when the state store's data is destroyed but the trust store's is not? The two are
  coupled by credential rotation: the state store reverts to its bootstrap credential while the
  trust store holds the rotated one, so nothing can authenticate. They must be reset together, and
  the tree must say so rather than leaving an operator to infer it from an authentication failure.
- What happens when configuration is applied while the trust store is sealed? It must refuse. A
  configuration tool that cannot read concludes the resources are absent and discards its record of
  them; the next attempt then tries to create what already exists.
- What happens when a scheduled workload needs persistent state? The scheduler must be configured to
  permit it. That is agent-level configuration, not workload-level, so a correct workload definition
  fails with a message pointing at the wrong file.
- What happens when the conformance suite runs outside a scheduled allocation? It has no identity,
  so it cannot obtain a credential. It must fail plainly, naming the cause, rather than falling back
  to a development path — removing that fallback is the point.
- Does this feature implement an alternative substrate? No. The requirement that any alternative
  supply an equivalent attested identity and demonstrate the same conformance assertions is in
  scope; building one is not (ADR-0025).
- Does the enclave run in continuous integration? No. That remains a recorded gap from 005; the
  fork-safe lane cannot hold the licence required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The deployment tree MUST be a single parameterized artifact applied to both a
  development environment and a production one. Two trees, or a production tree derived by copying
  the development one, MUST NOT be the shape that ships.
- **FR-002**: Every difference between a development and a production application MUST be confined
  to the substrate layer. Trust fabric, agent registry, ceiling policies, secrets engines, and
  dynamic roles MUST be identical, and that identity MUST be asserted rather than assumed.
- **FR-003**: The trust fabric MUST be provisioned before the scheduler, and the scheduler before
  any agent workload. No supported path may invert this order.
- **FR-004**: The trust store MUST NOT be scheduled by the substrate whose access it constrains.
- **FR-005**: The conformance suite MUST be runnable as a scheduled workload holding its own
  attested identity, and that MUST be the supported way it runs against a real environment.
- **FR-006**: Workload access to the state store MUST use credentials issued to that workload's own
  identity. After this feature, no development credential path substituting a static token MUST
  remain in the repository.
- **FR-007**: A workload with no valid attested identity MUST fail to obtain a credential, and MUST
  fail visibly rather than degrading to any alternative path.
- **FR-008**: Bring-up MUST publish a contract stating what is true when it succeeds — at minimum
  which services are reachable, whether the trust fabric is configured, and whether the state store
  is migrated — and MUST fail naming the missing prerequisite when it cannot deliver that contract.
- **FR-009**: Bring-up MUST be repeatable without destroying existing state. Running it against an
  environment already up MUST NOT re-initialize the trust store or discard persisted state.
- **FR-010**: The tree MUST address transport security, availability, unseal shape, and bootstrap
  administrative credential lifecycle. Each MUST be either implemented or carried as a recorded
  deferral stating what the operator must supply and the consequence of not supplying it. Silent
  absence MUST NOT be acceptable for any of the four.
- **FR-011**: A production application of the tree MUST NOT leave the bootstrap administrative
  credential in place indefinitely after configuration is applied.
- **FR-012**: Applying configuration against a sealed trust store MUST be refused rather than
  attempted.
- **FR-013**: Each failure mode recorded in the existing proof MUST be either prevented by the tree
  or detected and reported with its actual cause. A failure whose message points at the wrong layer
  MUST NOT be left for the next operator to diagnose.
- **FR-014**: The tree MUST document what an alternative substrate is required to supply — an
  attested workload identity the trust store accepts, and the same conformance assertions — without
  implementing one.
- **FR-015**: The tree MUST replace the existing proof directory as the supported way to stand up an
  environment. Any part of the proof retained MUST be retained as reference material that cannot be
  applied, never as a second working tree — two applicable trees is precisely the fragmentation this
  feature exists to end.
- **FR-016**: The tree's correctness MUST be demonstrated by applying it, not by inspection. A claim
  that development and production configurations match MUST be produced by comparing two
  applications rather than by reading the source.

### Key Entities

- **Deployment tree**: The single parameterized artifact that produces an enclave. The product's
  front door.
- **Substrate layer**: The only part permitted to differ between environments — where components run
  and what runs them.
- **Trust fabric**: The control-plane configuration establishing attested identity, ceiling policies,
  the agent registry, and credential issuance. Identical across environments by construction.
- **Bring-up contract**: The guarantees that hold when bring-up succeeds, and the named prerequisites
  whose absence makes it fail. Published by the tree's entry-point commands, which supersede the
  existing standalone `dev-up` / `dev-down` / `dev-status` tooling rather than sitting beside it.
- **Production posture item**: One of transport security, availability, unseal shape, or bootstrap
  credential lifecycle — each implemented or deferred with a reason, never silently absent.
- **Recorded trap**: A failure mode already diagnosed once, whose recurrence the tree prevents or
  explains.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Applying the tree to two different substrates produces control-plane configurations
  that compare as identical across 100% of configured elements — auth methods, roles, policies,
  registry entries, secrets engines. Verifiable without customer infrastructure: the comparison is
  over the configuration the tree *produces*, so a plan-level application against the second
  substrate suffices.
- **SC-002**: 100% of the durability conformance rows run as a scheduled workload under an attested
  identity when run against a real environment; zero use a static token.
- **SC-003**: Zero token-substituting development credential paths remain in the repository after
  this feature.
- **SC-004**: A workload without a valid attested identity obtains a credential in zero cases, and
  fails with a message naming that cause in 100% of them.
- **SC-005**: Every guarantee in the bring-up contract holds when bring-up reports success, verified
  on a clean machine; removing any named prerequisite produces a failure identifying it in 100% of
  cases.
- **SC-006**: Bring-up run against an already-configured environment destroys state in zero cases and
  re-initializes the trust store in zero cases.
- **SC-007**: All four production posture items are each implemented or carry a recorded deferral;
  zero are silently absent.
- **SC-008**: A production application leaves the bootstrap administrative credential active in zero
  cases after configuration completes.
- **SC-009**: For each recorded trap, the tree either prevents the condition or reports its actual
  cause, in 100% of the recorded cases.
- **SC-010**: Exactly one supported way to stand up an environment exists in the repository after
  this feature.

## Assumptions

- This feature ships as **infrastructure and provisioning**, on top of landed 002–005 and the
  existing proof directory. It changes no governed-core behaviour; what it changes is the environment
  those guarantees are proven against.
- The development substrate remains containers on a workstation. What generalizes is the trust
  fabric, which is already written to be substrate-independent.
- **The development enclave remains single-node** unless this feature implements availability under
  FR-010. 005's conformance caveat therefore persists — fencing and parking are proven against
  single-node behaviour, and multi-node partition is not exercised. Stated so that landing this
  feature is not misread as having closed that gap.
- The existing `dev-up` / `dev-down` / `dev-status` commands become the tree's entry points. They
  are where FR-008's contract is published, not separate tooling that happens to agree with it.
- Production availability means multi-node for both the trust store and the scheduler. Whether this
  feature implements that or defers it with a reason is a planning decision; FR-010 requires only
  that the answer be recorded, not which answer is given.
- The production unseal shape is expected to be an auto-unseal mechanism supplied by the operator's
  environment rather than a threshold of keys held by the deployer. This feature is expected to
  define the seam, not to implement every provider's variant.
- Continuous integration does not run the enclave. That gap is recorded in 005's conformance contract
  and is unchanged here; the durability rows remain merge-blocking for a human running them locally.
- **The proof directory is a starting point, not a template.** Its trust configuration is
  substrate-independent and should generalize; its substrate layer, single-node topology, and
  bootstrap shortcuts should not be carried forward by inertia.
- Multi-tenancy (ADR-0046) remains out of scope. A single enclave serves a single tenant, and nothing
  here should assume otherwise.
