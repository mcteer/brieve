# Feature Specification: Production Identity Fabric

**Feature Branch**: `spec/010-identity-fabric`

**Path**: `specs/010-identity-fabric/spec.md`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Production identity fabric: resolve authority from a real source instead of a test double. `IdentityFabric` is the seam through which every governed run resolves user scope, agent ceiling, policy, and product entitlements. The only implementation in the repository is `FakeIdentityFabric` under `tests/harness/`. ROADMAP.md records this as Unassigned and says nothing downstream of it is proven against a real identity source."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2 / R3 (per-task authority — this is the source of the ceiling that authority cannot exceed, and it has never been read from anywhere real). R7 (fail-closed — a fabric that cannot answer must refuse, and it now has network-shaped ways to fail that a dictionary did not). R16 (sealed core — `src/core/authority/` changes shape). R4 / R10 / R13 (evidence — a resolution refusal is a governance decision and is recorded as one). |
| **ADRs touched** | **ADR-0015** (the control-plane Vault is the agent registry and trust fabric — this is the feature that finally *reads* from it rather than only writing to it at bring-up), **ADR-0044** (two authorization domains both checked; entitlement mirroring becomes a real lookup — credential translation does not, and stays out of scope), ADR-0016 (consumed: claim-mapping changes are already quorum-gated by 007), ADR-0048 (the fabric authenticates by presenting an attested workload identity, like every other store), ADR-0026 as amended by ADR-0049 (grant issuance draws on a resolved ceiling, so the ceiling's provenance is the grant's provenance). |
| **Evidence class** | **Attestation-relevant and authorization-critical.** This is the first feature where the numbers behind every prior authorization assertion come from outside the test suite. A fabric that resolves a wider ceiling than the registry holds does not fail — it permits, silently, and every existing row still passes. |

## Clarifications

### Session 2026-07-28

- Q: The registry's ceiling policy governs secret paths; `AuthorityScope` governs tool names and product actions. Where should the tool-authorization ceiling live? → A: **As its own first-class field on the agent definition**, alongside the credential-issuance policy rather than derived from it.
  *(This corrects the spec's original framing. It described a "shape mismatch" between a compiled policy and an authority scope, and asked how to translate between them. Checking what a registered ceiling actually contains — `allowed_paths = ["secret/data/demo/*"]` — showed the premise was wrong: that is a secret path, not a tool. The two do not describe one thing in two shapes; they describe **different jurisdictions**, which is what ADR-0044 requires when it says "policy jurisdictions are disjoint... no rule is duplicated across engines." There is no translation to get right, because there is nothing to translate. Recorded at length because the original framing was plausible enough to survive a spec draft, and the thing that dislodged it was reading one line of `variables.tf`.)*
- Q: Is the product-entitlement seam in this feature, given that products stay faked? → A: **Build the seam; keep the products behind it faked.** The interface that asks a product what a user may do is ours and does not exist; the product's own authorization system is outside our boundary and correctly stays a fake.
  *(The line is between the two, and it is worth stating why it falls there. Deferring the whole thing to the credential-translation feature was tempting — that is where the coarse credential this compensates for actually appears — but it would leave one of the fabric's four resolutions on the test double while the feature claimed to have replaced the double. A success criterion that is true of three quarters of a seam is not true.)*
- Q: What happens when the trust fabric becomes unreachable mid-run, in a run that already holds a valid grant? → A: **Suspend, awaiting the trust fabric**, exactly as ADR-0049 treats any unreachable dependency. The sweeper resumes it when the fabric returns.
  *(Chosen over stopping, which would lose hours of work to a transient blip that a product outage would have survived, and over caching within a freshness bound, which buys fewer interruptions by letting a policy narrowing take up to one interval to bite — weakening the guarantee 005 asserts in order to reduce network cost. If the mid-run shrink is worth asserting, it is worth reading.)*
  *(**The consequence this exposes**: the trust fabric is unlike every other dependency 009 monitors, because **the monitor depends on it.** The health checker and the sweeper reach their store with credentials the fabric issues, so while the fabric is down they are degraded too. The recovery path still terminates — fabric returns, the checker obtains credentials, records healthy, the sweeper resumes — but it terminates in that order and only that order, and nothing currently says so. Recorded as a requirement rather than left to be rediscovered.)*


## User Scenarios & Testing *(mandatory)*

### User Story 1 — An agent's ceiling comes from the registry (Priority: P1)

An operator registers an agent definition in the control-plane Vault with a ceiling. A run
starts under that definition. The authority manufactured for its first task is bounded by
**the ceiling the registry holds**, not by one a test supplied.

**Why this priority**: Principle IV's whole claim is that authority cannot exceed the
ceiling. Every conformance row asserting it today asserts it against a dictionary in
`FakeIdentityFabric`. The behaviour is almost certainly correct; what has never happened is
any of it running against the thing an operator actually configures.

**What the registry holds today is not this ceiling.** Its `ceiling_policy` bounds which
secrets a run's token may read — `allowed_paths = ["secret/data/demo/*"]` — which is the
credential-issuance jurisdiction, and a different one from tool authorization. So this
feature adds the tool-authorization ceiling to the agent definition as its own field rather
than deriving it from the policy. The two stay disjoint, per ADR-0044.

The risk this carries, stated plainly because it is the cost of the decision: two fields on
one definition can be edited independently, so an agent can be granted a tool whose secrets
it cannot read, or secrets for a tool it cannot call. That is not a defect — the
jurisdictions genuinely differ — but it is a coherence question an operator will hit, and
nothing currently reports it.

**Independent Test**: Register two definitions with different ceilings in a live enclave,
start a run under each, and assert the manufactured authority differs accordingly and that
neither exceeds what the registry holds. Delivers the first end-to-end proof that a
configured ceiling reaches a running agent.

**Acceptance Scenarios**:

1. **Given** a definition registered with a ceiling permitting one tool, **When** a run
   under it requests two, **Then** authority is manufactured for the permitted one and the
   other is refused with the reason recorded.
2. **Given** an agent definition id absent from the registry, **When** a run is started
   under it, **Then** the run refuses — an unknown definition never resolves to an open
   ceiling, or to a default one.
3. **Given** a definition registered with a credential-issuance policy but **no**
   tool-authorization ceiling, **When** it is resolved, **Then** it refuses. The absence of
   one jurisdiction must never be filled in from the other, in either direction — that
   substitution is how a secrets grant would quietly become a tool grant.
4. **Given** a registered ceiling naming a tool the platform does not know, **When** it is
   resolved, **Then** resolution refuses and names the unknown entry. A ceiling referring to
   nothing is a configuration error, and silently dropping the entry narrows a ceiling
   without telling anyone.
5. **Given** a ceiling changed in the registry, **When** the next run starts, **Then** it is
   bounded by the changed ceiling without restarting anything.

---

### User Story 2 — A person's harness scope comes from their identity (Priority: P2)

A user authenticates to a northbound surface. The harness-domain scope used to bound what
they may delegate to an agent is derived from **their identity claims**, through the
claim-to-role mappings the platform already governs.

**Why this priority**: Half of this is built. 008's token verification turns a presented
token into an authenticated subject carrying roles; `core/identity/claims.py` maps claims to
roles; 007 gates changes to those mappings behind multi-party approval. What does not exist
is the step from a resolved role to an authority scope — so today a real, verified,
correctly-mapped user still gets their scope from a fixture.

**Independent Test**: Authenticate as two users whose claims map to different roles, start
the same run under the same definition, and assert their manufactured authority differs.
Provable without touching ceilings, since the intersection narrows either way.

**Acceptance Scenarios**:

1. **Given** a user whose claims map to a role, **When** their scope is resolved, **Then**
   it reflects that role and no other.
2. **Given** a user whose claims map to no role at all, **When** their scope is resolved,
   **Then** the run refuses. An empty scope and an unresolvable one must not be
   indistinguishable — one is a person with no permissions, the other is a platform that
   does not know who is asking.
3. **Given** a role-to-scope binding changed through the governed path, **When** a
   subsequent run starts, **Then** it resolves the new binding without a restart.

---

### User Story 3 — Policy is read live, and a mid-run shrink is observed (Priority: P3)

Policy for an agent definition is narrowed while a run is in flight. The run's **next**
step is bounded by the narrowed policy.

**Why this priority**: 005 already asserts this against the fake, where a shrink is a
dictionary assignment. Against a real source it becomes a question nothing currently
answers: how fresh must a policy read be, and what does the platform do when the answer is
"we cannot tell right now"? The behaviour is specified; its cost and its failure modes are
not.

**Independent Test**: Start a run, narrow policy through the governed path mid-run, and
assert the next step is bounded by the narrower policy while the completed step is
untouched.

**Acceptance Scenarios**:

1. **Given** a run in flight, **When** policy narrows, **Then** the next step is bounded by
   the narrowed policy.
2. **Given** a run in flight, **When** policy cannot be read at all, **Then** the step
   refuses rather than proceeding on the last known value. A cached scope used past its
   freshness bound is a stale permission, and stale permissions are the failure this whole
   layer exists to prevent.
3. **Given** policy that widens mid-run, **When** the next step runs, **Then** it is still
   bounded by the grant issued at run start — widening does not retroactively enlarge a run.

---

### User Story 4 — The entitlement-mirroring check asks something real (Priority: P4)

Before a tool acts on a managed product, the requesting user's own effective entitlements
**in that product** are resolved and enforced, so an agent cannot exceed the person it acts
for.

**Why this priority**: ADR-0044 requires this specifically, as the compensating control for
a brokered credential coarser than the individual user. Today the answer comes from a
dictionary keyed by `(user, product)`. A managed product's authorization system is outside
this platform's boundary and is correctly faked — but **the seam that asks a product is
ours**, and it does not exist. The distinction matters: keeping the product faked is a
decision; having no way to ask one is a gap.

**So this feature builds the interface and leaves the products behind it faked.** It is last
in priority because the credential it compensates for — a brokered credential coarser than
the user — does not exist yet either; until credential translation ships, this check can
only ever agree with the harness domain. It is in scope anyway, because leaving it out would
make this feature's central claim false for a quarter of the seam.

**Independent Test**: Configure a faked product to report narrower entitlements for a user
than the credential in use, attempt an action within the credential's power but outside the
user's, and assert refusal with no side effect.

**Acceptance Scenarios**:

1. **Given** a user with narrower product entitlements than the credential being wielded,
   **When** they attempt an action outside their own entitlements, **Then** it is refused
   before execution and nothing is mutated.
2. **Given** a product that cannot be asked, **When** entitlements are resolved, **Then**
   the call refuses. Unknown entitlement is not empty entitlement and is certainly not full
   entitlement.
3. **Given** both authorization domains, **When** either refuses, **Then** the call is
   refused — the two checks are independent and both must agree.

---

### User Story 5 — The protocol stops obliging production code to implement test affordances (Priority: P5)

A production implementation of the identity fabric implements only what a production system
needs.

**Why this priority**: `IdentityFabric` currently declares two methods whose own docstrings
say "(fake only)" and "never for audit/spans". A production implementation would be forced
to implement them, and the honest implementation is a pair of methods that raise — which is
a protocol admitting it does not describe its own production case.

This is the shape this project keeps meeting: a seam built for exactly one caller, which
then does not fit the second. 009 recorded eight instances of it. This one is visible
*before* the second caller exists, which is the first time that has been true, and taking
it now costs a protocol change instead of a discovery.

**Independent Test**: Assert that the production implementation satisfies the protocol
without any method raising "not supported", and that nothing in `src/` depends on the
test-only affordances.

**Acceptance Scenarios**:

1. **Given** the production fabric, **When** it is checked against the protocol, **Then**
   every declared method is one it meaningfully implements.
2. **Given** the test fake, **When** fault-injection rows use it, **Then** they say so
   explicitly — a fake surviving for one purpose must not be mistaken for the default.

---

### Edge Cases

- **The two jurisdictions disagree.** A definition granted a tool whose secrets its policy
  does not cover, or secrets for a tool it cannot call. Legal, and a consequence of keeping
  them disjoint — but an operator will hit it, and whether anything reports the incoherence
  is an open question rather than a settled one.
- **A ceiling naming an unknown tool.** Refusing is specified above; the refusal must name
  the entry, or the operator has no way to fix it.
- **The control-plane Vault is unreachable when a run starts.** No authority can be
  manufactured, so nothing runs. This is not a degraded mode.
- **The control-plane trust fabric becomes unreachable mid-run.** Resolved by C3: the run
  suspends naming the fabric. The distinction from the above is real — a grant already
  exists, and only the reads fail.
- **The fabric is unreachable, so the thing that would notice its recovery is degraded too.**
  The health checker and sweeper hold fabric-issued credentials. Recovery terminates, but
  only in one order (FR-008b), and nothing else in this platform has this property.
- **A definition is removed from the registry while a run under it is in flight.** The
  ceiling that bounded the grant no longer exists.
- **A user is deprovisioned mid-run.** 007 already governs revocation; what is new is that
  the fabric is now the thing that notices.
- **Two definitions sharing a ceiling policy name.** Legal in the registry, and it means one
  edit changes two definitions' ceilings.
- **A resolved scope that is empty.** Distinguishable from unresolvable, per US2, and it
  must stay distinguishable through every layer that reports it.
- **Resolution succeeds but slowly.** A read on the invoke path has a latency budget that a
  dictionary did not, and exceeding it must fail closed rather than hang.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide a production implementation of the identity fabric
  that resolves user scope, agent ceilings, and policy from the control-plane trust fabric
  rather than from a test double.
- **FR-002**: The production fabric MUST authenticate to the trust fabric by presenting an
  attested workload identity. No static credential, token, or password may appear anywhere
  in its configuration.
- **FR-003**: An agent definition absent from the registry MUST refuse. It MUST NOT resolve
  to a default ceiling, an empty ceiling that later widens, or an open one.
- **FR-004**: The agent registry MUST hold each definition's tool-authorization ceiling as a
  **first-class field expressed in the core's own vocabulary** — tool names and product
  actions. The fabric MUST read that field directly.
- **FR-005**: The fabric MUST NOT derive a tool-authorization ceiling from a
  credential-issuance policy, or vice versa. The two jurisdictions stay disjoint (ADR-0044),
  and a definition missing either one MUST refuse rather than having it inferred from the
  other.
- **FR-005a**: A ceiling naming a tool or product action the platform does not know MUST
  refuse resolution and name the unknown entry. Silently dropping it narrows a ceiling
  without telling anyone, which is a change to authority that leaves no trace.
- **FR-006**: A user's harness-domain scope MUST be derived from their verified identity
  claims through the platform's governed claim-to-role mappings.
- **FR-007**: A user whose claims resolve to no role MUST cause refusal, and that refusal
  MUST be distinguishable in the record from a user resolved to an empty scope.
- **FR-008**: Policy MUST be resolved from the trust fabric on each step rather than served
  from a cache. A cached scope used past its freshness bound is a stale permission, and a
  policy narrowing that takes an interval to bite is weaker than the guarantee 005 asserts.
- **FR-008a**: When the trust fabric cannot be reached mid-run, the run MUST **suspend
  naming the trust fabric** rather than stopping or proceeding on a previously resolved
  value — the same disposition ADR-0049 gives any unreachable dependency, resumed by the
  same sweeper.
- **FR-008b**: The platform MUST record that the trust fabric is a dependency **of the
  mechanism that monitors dependencies**. The health checker and the sweeper reach their
  store with credentials the fabric issues, so a fabric outage degrades them too. The
  recovery ordering — fabric returns, checker obtains credentials, checker records healthy,
  sweeper resumes — MUST be asserted, because it is the only order in which it terminates.
- **FR-008c**: The trust fabric's health record MUST NOT be markable healthy by anything
  that did not successfully reach it. A monitor that cannot run must leave the state
  unknown, and unknown already refuses.
- **FR-009**: A mid-run policy narrowing MUST bound the next step. A mid-run widening MUST
  NOT enlarge the grant already issued.
- **FR-010**: The platform MUST resolve the requesting user's effective entitlements in a
  managed product before a tool acts on that product, and MUST refuse when the user's own
  entitlements do not permit the action — independently of whether the credential in use
  would permit it.
- **FR-011**: An entitlement lookup that cannot be answered MUST refuse. Unknown MUST NOT
  be treated as empty or as full.
- **FR-012**: Every refusal originating in identity resolution MUST be recorded with a
  reason code that distinguishes *who is asking is unknown*, *what they may do is unknown*,
  and *what they may do does not include this*.
- **FR-013**: The identity fabric protocol MUST NOT declare methods that exist only for
  tests. Any affordance the fake needs and production does not MUST live outside the
  protocol production code implements.
- **FR-014**: The test fake MUST survive for fault injection only, and every row that uses
  it MUST state that it is exercising a failure mode rather than standing in for the real
  source.
- **FR-015**: No production code path may import from `tests/`. The dispatched-run entrypoint
  that lives under `tests/harness/` today because it had no fabric to resolve through MUST
  move to `src/` or the reason it cannot MUST be recorded.
- **FR-016**: Identity resolution MUST NOT be reachable from any agent-governed tool. The
  trust fabric sits structurally outside every agent ceiling, and a tool able to ask it what
  a ceiling is has a path toward changing one.
- **FR-017**: The production fabric MUST be exercised by conformance rows running inside an
  allocation against a live control-plane trust fabric, not only by unit tests against a
  recorded response.
- **FR-018**: Resolution MUST fail closed on timeout, with a bounded wait. A resolution that
  hangs holds a step open, and a step held open indefinitely is a run that neither completes
  nor suspends.
- **FR-019**: The feature MUST state, in a conformance contract, which rows previously
  asserted against the fake now assert against the real fabric — and which do not, with the
  reason.
- **FR-020**: Adding a tool-authorization ceiling to the agent definition (FR-004) changes
  what the agent registry is for, and MUST be recorded as an **architecture decision** rather
  than made silently in a module. ADR-0015 describes the registry as holding identities,
  registration, and compiled ceiling policies; after this feature it also holds the
  harness-domain ceiling, and that is a change to what ADR-0015 describes.

### Key Entities

- **Agent definition**: A registered agent with an owner, a description, and a ceiling.
  Already exists in the registry; this feature is the first thing that reads it at runtime.
- **Ceiling**: The maximum authority any run under a definition may hold. Held by the
  registry in one representation and consumed by the core in another — the gap between them
  is this feature's central problem.
- **Harness-domain scope**: Tool names and product actions a principal may exercise, for
  both users and agent definitions.
- **Product-domain entitlement**: What a user may do *inside* a managed product. Owned by
  that product, not by this platform.
- **Resolution refusal**: A governance decision with a reason code, recorded like any other.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero conformance rows resolve an agent ceiling, a user scope, or a policy
  through a test double, except rows that exist specifically to inject a resolution failure
  and say so.
- **SC-002**: An agent definition registered with a given ceiling produces a run whose
  authority is bounded by that ceiling, demonstrated end to end against a live trust fabric
  under an attested identity.
- **SC-003**: A definition with a credential-issuance policy and no tool-authorization
  ceiling refuses 100% of the time, and 0% of resolutions infer either jurisdiction from the
  other. A ceiling naming an unknown tool refuses and names it.
- **SC-004**: Two users with different claim-derived roles produce measurably different
  manufactured authority for the same run request.
- **SC-005**: Every identity-resolution failure mode — unknown user, unknown definition,
  unreachable fabric, timeout, untranslatable ceiling — refuses with a distinct reason code,
  and none produces a permissive outcome.
- **SC-006**: A mid-run policy narrowing bounds the next step in a run executing against the
  live fabric, with zero steps served from a cached policy.
- **SC-006a**: A run whose trust fabric becomes unreachable mid-run suspends naming it, holds
  no container, and resumes automatically when the fabric returns — with zero operator
  actions between the outage and the resumption.
- **SC-007**: A user whose product entitlements are narrower than the credential in use
  cannot exceed themselves, with zero side effects on the attempt.
- **SC-008**: Zero production modules import from `tests/`.
- **SC-009**: The identity fabric protocol declares zero methods documented as test-only,
  and the production implementation raises "not supported" from none of them.
- **SC-010**: No static credential appears in the production fabric's configuration or
  environment — the same assertion the durability and evidence paths already carry.

## Assumptions

- **The control-plane trust fabric IS a monitored dependency in 009's sense, with one
  asymmetry.** A run that cannot resolve identity **at start** does not begin — there is no
  authority to manufacture, so there is nothing to suspend, and the failure is refusal. A run
  that loses the fabric **mid-run** suspends naming it and is resumed by the sweeper (C3).
  The asymmetry is not a special case: it falls out of a run existing or not existing yet.
  *(An earlier draft of this spec assumed the fabric was categorically not a monitored
  dependency, reasoning that identity is more fundamental than a product. It is more
  fundamental — and that argues for suspension being available, not against it.)*
- **Managed products and model providers stay faked**, per the constitution. This feature
  makes the *seam* real, not the products behind it — which is the whole of the C2 decision
  above, and the reason User Story 4 is in scope rather than deferred.
- **Claim-to-role mapping is already governed** by 007's approval gate; this feature consumes
  it and does not re-govern it.
- **The registry's current contents are adequate to test against.** The enclave already
  registers agent definitions with ceiling policies at bring-up.
- **Credential translation — federate versus broker — is a separate feature.** ADR-0044
  decides it; this feature implements only the entitlement-mirroring check that ADR-0044
  requires alongside it.
- **A new architecture decision is required**, not merely likely (FR-020). C1 settled that
  the registry gains a field, which is a change to what ADR-0015 says the registry holds.

## Resolved clarifications

All three forks this spec opened were resolved in the session recorded above. Kept here as a
pointer rather than deleted, because a spec that shows no sign of having had open questions
reads as one where nobody looked.

- **C1 — Ceiling representation.** Resolved: its own first-class registry field. The
  premise that a translation was needed turned out to be wrong.
- **C2 — Product entitlement seam.** Resolved: build the seam, keep the products faked.
- **C3 — Freshness and mid-run identity outage.** Resolved: read per step, suspend on
  outage, resume by sweeper — and the fabric is a dependency of its own monitor.

## Out of scope

- Real brokered credential minting against live products, and the federate-versus-broker
  implementation of ADR-0044's credential translation.
- The CLI and portal transports.
- Widening the northbound API beyond its current four operations.
- Capability packs and eval gates.
- Multi-tenancy beyond the tenant boundary 008 established.
- Replacing the faked product APIs and model providers.
- Row-level security on the evidence store, which remains recorded as its own gap.
