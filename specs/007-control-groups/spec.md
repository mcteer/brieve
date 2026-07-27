# Feature Specification: Control Groups

**Feature Branch**: `spec/007-control-groups`

**Path**: `specs/007-control-groups/spec.md`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "Quorum-gated authority changes per ADR-0016: who may widen a scope, restore revoked access, register an agent, or change claim-to-role mapping. Humans authorize at design time — registering agents and managing tier-0 Vault policy — and are never in the loop during a run. Revocation is unilateral and immediate; only restoration requires quorum. Built on the control-plane Vault's own Control Groups, which the licence provides. Out of scope: run-time approval of any kind, northbound approval surfaces, parked-run resolution."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2 / R3 (per-task authority — this governs the *ceilings* that bound it, and who may change them). R7 (fail-closed — an authority change that cannot obtain quorum does not take effect). R16 (sealed core, versioned seams — the approval mechanism is the trust fabric's, consumed through a seam rather than reimplemented). |
| **ADRs touched** | ADR-0016 (Control Groups gate authority changes — this implements it), ADR-0015 (control-plane Vault as trust fabric — the quorum mechanism is Vault's own Control Groups), ADR-0048 (workload identity; agent registration is the act being gated). Related: ADR-0049 (**Proposed**) — consent to start is consent to finish, which is why nothing here is run-time. |
| **Evidence class** | Attestation-relevant and audit-critical. An authority change is the highest-consequence write in the system: it changes what an agent may become. Every request, approval, denial, and expiry must be reconstructable. |

## Clarifications

### Session 2026-07-26

- Q: Does this feature resolve 005's parked runs, as the roadmap claims? → A: No. Control Groups gate **authority**, not **runs**. Humans authorize at design time — registering agents, changing privileges, managing tier-0 Vault policy — and are never in the loop during a run (ADR-0049, Proposed). The roadmap entry claiming otherwise predates that reasoning and is corrected by this feature.
- Q: Is the quorum mechanism built here or consumed? → A: Consumed. The control-plane Vault provides Control Groups under the current licence, verified against the running enclave. Building a second approval mechanism beside the trust fabric's own would violate Principle I and put the authority record somewhere other than the trust fabric (ADR-0015).
- Q: What is gated, exactly? → A: What ADR-0016 names: ceiling changes, agent definition changes, manual control-plane writes, break-glass access, and reactivation of a suspended agent. Instance operations within an already-approved definition — scaling, restarting, scheduling, registering an instance — are **not** gated; the approval already happened at the definition.
- Q: Who establishes the first quorum policy, given that it gates its own changes? → A: Provisioning, before the bootstrap credential is revoked. The trust fabric (006) applies the initial policy during setup; production then revokes the bootstrap token, after which the policy can only be changed through itself. This is the same bootstrap shape as TLS in 006 — something outside the loop goes first — and it must be explicit, because a control that cannot be created without itself either never exists or has a permanent back door.
- Q: Does a pending request linger forever? → A: No. A request that has not reached quorum expires, and expiry means **the change does not happen**. That is fail-closed and safe: the risk of an expiring request is a change someone has to propose again, while the risk of an immortal one is an approval collected months after the context that justified it. FR-009 already forbids a timeout that *grants*; this is the opposite direction.
- Q: What happens to an in-flight request when the quorum policy changes under it? → A: It is evaluated against the policy in force when it completes, not when it was raised. Otherwise raising a request just before a tightening would let it through under the looser rule, which makes the tightening advisory.
- Q: Is revocation symmetric with restoration? → A: No, deliberately. Revocation is unilateral and immediate; any authorized individual acts alone. Only restoration requires quorum. Easy to make safe, hard to make permissive.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Widening an agent's authority requires more than one person (Priority: P1)

An operator proposes raising an agent definition's ceiling. The change does not take effect
on their say-so: it waits for the required number of approvals from authorized people, and
until it has them the agent's authority is unchanged.

**Why this priority**: This is the feature. An agent's ceiling is the outer bound on
everything it may ever do, and a single person able to raise it silently is the failure the
whole authority model is built to prevent.

**Independent Test**: Propose a ceiling widening; assert the agent's effective authority is
unchanged before quorum; supply approvals; assert it takes effect only then, and that every
step is in the audit trail.

**Acceptance Scenarios**:

1. **Given** a proposed ceiling change, **When** it has fewer approvals than required,
   **Then** the change has not taken effect and the agent's authority is unchanged.
2. **Given** the same proposal, **When** the required approvals are supplied, **Then** the
   change takes effect and the approving identities are recorded.
3. **Given** any outcome, **When** the audit trail is read, **Then** the request, each
   approval or denial, and the final disposition are present and joined.

---

### System boundary — nothing here happens during a run

Stated as a boundary rather than a story, because it is what the feature must *not* do.

Every scenario in this specification concerns **design-time** authority: registering an
agent, changing what it may become, restoring what was revoked. None of it interrupts, pauses,
or waits on a run.

An agent that has begun a run holds authority already granted; nothing in this feature can
pause that run to ask a person a question. Control Groups gate what an agent **may become**;
hooks gate what an agent **does** (ADR-0016). Conflating them would put a human in the path
of agent work, which ADR-0049 (Proposed) rejects and which this feature is explicitly not.

---

### User Story 2 - Revoking access needs no one's agreement (Priority: P1)

Someone discovers an agent is misconfigured, compromised, or simply should not have the
access it has. They revoke it immediately, alone.

**Why this priority**: Equal in priority to quorum, and inseparable from it. A control that
makes revocation as slow as granting is one people route around in an incident — and then
the routing-around becomes the norm.

**Independent Test**: Revoke an agent's authority as a single authorized individual; assert
it takes effect immediately with no approvals, and that a run started under the old
authority cannot manufacture new step credentials.

**Acceptance Scenarios**:

1. **Given** an authorized individual, **When** they revoke an agent's authority, **Then**
   it takes effect immediately without any approval.
2. **Given** a revoked agent, **When** it attempts to obtain new authority, **Then** it
   cannot.
3. **Given** a revocation, **When** the audit trail is read, **Then** who revoked what, and
   when, is recorded.

---

### User Story 3 - Restoring revoked access requires quorum (Priority: P1)

Access that was revoked does not come back the way it left. Restoration is proposed,
approved by the required number of people, and only then takes effect.

**Why this priority**: The asymmetry *is* the control. Symmetric revoke and restore would
mean whoever revoked could quietly restore, and an incident response would leave no trace
that mattered.

**Independent Test**: Revoke, then attempt restoration with one approver; assert it does not
take effect. Supply quorum; assert it does.

**Acceptance Scenarios**:

1. **Given** revoked authority, **When** restoration is proposed by one person, **Then** it
   does not take effect.
2. **Given** the same proposal with quorum, **When** approvals complete, **Then** authority
   is restored and the approvers are recorded.
3. **Given** a restoration, **When** the audit trail is read, **Then** it is
   distinguishable from an original grant.

---

### User Story 4 - Registering an agent is a governed act (Priority: P1)

Bringing a new agent definition into existence — with a ceiling, an owner, and a set of
permitted paths — requires quorum, because it creates authority that did not exist.

**Why this priority**: Registration is where authority originates. Gating changes to
definitions while leaving their creation ungated would be a control with a door beside it.

**Independent Test**: Register a definition with fewer approvals than required; assert no
agent can authenticate as it. Complete quorum; assert it can.

**Acceptance Scenarios**:

1. **Given** a proposed registration, **When** it lacks quorum, **Then** no workload can
   authenticate as that definition.
2. **Given** quorum, **When** approvals complete, **Then** the definition exists with its
   ceiling and is recorded in the agent registry.
3. **Given** an approved definition, **When** instances of it are scheduled or restarted,
   **Then** those operations require **no** further approval.

---

### User Story 5 - Operating within an approved definition is not gated (Priority: P2)

Scaling, restarting, scheduling, and registering instances of an already-approved definition
proceed without human involvement.

**Why this priority**: The counterweight to everything above. Gating routine operations would
make the platform unusable and would train people to approve without reading — which
destroys the value of the gate that matters.

**Independent Test**: With an approved definition, perform each instance operation; assert
none requires approval and none is blocked.

**Acceptance Scenarios**:

1. **Given** an approved definition, **When** an instance is scheduled, **Then** no approval
   is requested.
2. **Given** the same, **When** an instance is restarted or scaled, **Then** no approval is
   requested.
3. **Given** an operation that would change the *definition* rather than an instance,
   **Then** it is gated.

### Edge Cases

- What happens when quorum cannot be reached — approvers are unavailable, or decline? The
  change does not take effect. There is no timeout that grants by default, and no escalation
  that reduces the requirement. A change that cannot obtain quorum is a change that does not
  happen.
- What happens when an approver is also the requester? Self-approval must not count toward
  quorum; otherwise the requirement is one person with two hats.
- What happens when an authority change is approved while an agent is mid-run? The run
  continues under the authority it already holds. Nothing pauses it. A *narrowed* ceiling
  applies to authority manufactured after the change, which is the existing per-step model.
- What happens when authority is revoked mid-run? The run cannot manufacture new step
  credentials, so it stops at its next step boundary. It is not interrupted mid-step, and no
  human is asked anything.
- What happens if the approval mechanism itself is unavailable? Authority changes cannot
  proceed. Fail-closed: an unreachable gate does not become an open one.
- Does this feature build an approval UI? No. The surface people use to review and approve is
  northbound (ADR-0033), a later feature. This feature covers the gate itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Changes to an agent definition's ceiling MUST require approval by more than one
  authorized identity before taking effect.
- **FR-002**: Creating an agent definition MUST require the same approval as changing one.
  Authority that did not exist before is being created.
- **FR-003**: Manual writes to the control plane, and break-glass access, MUST be gated by
  the same mechanism.
- **FR-004**: Reactivating a suspended agent MUST be gated.
- **FR-005**: Operations on instances of an already-approved definition — scheduling,
  restarting, scaling, registering an instance — MUST NOT require approval.
- **FR-006**: Revocation of authority MUST take effect immediately on the action of a single
  authorized identity, with no approval required.
- **FR-007**: Restoration of revoked authority MUST require quorum.
- **FR-008**: The requester MUST NOT be able to satisfy the quorum requirement themselves.
- **FR-009**: A change that has not obtained quorum MUST NOT take partial effect, and MUST
  NOT take effect by timeout, default, or escalation.
- **FR-010**: If the approval mechanism is unavailable, authority changes MUST fail closed.
- **FR-011**: The request, every approval and denial with the identity responsible, and the
  final disposition MUST be recorded and joinable.
- **FR-012**: **No requirement in this feature may pause, interrupt, or block a run.** The
  gate applies to authority changes only. An agent mid-run holds authority already granted,
  and nothing here asks a human anything about it.
- **FR-013**: Authority narrowed by an approved change MUST apply to authority manufactured
  after it. Credentials already issued expire on their own schedule; the platform does not
  reach into a running step.
- **FR-014**: The quorum mechanism MUST be the control-plane Vault's own, consumed through a
  seam. A second approval mechanism MUST NOT be built beside it.
- **FR-015**: Quorum size and who may approve MUST be configurable per class of change, and
  that configuration MUST itself be gated — otherwise the control can be lowered by whoever
  it constrains.
- **FR-016**: The initial quorum policy MUST be established during provisioning, before the
  bootstrap credential is revoked. A control that cannot be created without already existing
  either never exists or keeps a permanent back door; naming the bootstrap explicitly is what
  avoids both.
- **FR-017**: A request that has not reached quorum MUST expire, and expiry MUST mean the
  change does not take effect. An immortal request invites an approval collected long after
  the context that justified it.
- **FR-018**: A request MUST be evaluated against the quorum policy in force when it
  completes, not when it was raised. Otherwise raising a request just ahead of a tightening
  would let it through under the looser rule, which makes tightening advisory.

### Key Entities

- **Authority change request**: A proposed change to what an agent may become — a ceiling, a
  definition, a registration, a restoration.
- **Approval**: One authorized identity's assent to a request. Recorded with who and when.
- **Quorum policy**: How many approvals a class of change requires, and who may give them.
  Itself a gated object.
- **Revocation**: A unilateral, immediate removal of authority. Requires no approval.
- **Suspended agent**: One whose authority has been revoked and which cannot obtain new
  authority until restored through quorum.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ceiling widenings, definition changes, registrations, break-glass
  grants, and reactivations require more than one approving identity; zero take effect on one.
- **SC-002**: Zero authority changes take effect by timeout, default, or escalation when
  quorum is not reached.
- **SC-003**: Zero requests are satisfiable by their own requester.
- **SC-004**: 100% of revocations take effect immediately with zero approvals required.
- **SC-005**: 100% of restorations require quorum; zero occur unilaterally.
- **SC-006**: Instance operations within an approved definition require approval in zero
  cases.
- **SC-007**: When the approval mechanism is unreachable, authority changes succeed in zero
  cases.
- **SC-008**: For every authority change, an investigator can retrieve the request, each
  approval or denial with its identity, and the disposition, joined.
- **SC-009**: **Zero runs are paused, interrupted, or blocked by anything in this feature**,
  measured across the whole suite.
- **SC-010**: A narrowed ceiling applies to 100% of authority manufactured after the change,
  and reaches into zero already-running steps.
- **SC-011**: After provisioning completes and the bootstrap credential is revoked, zero
  authority changes are possible outside the quorum mechanism.
- **SC-012**: 100% of requests that reach expiry without quorum result in no change.

## Assumptions

- This feature ships as **design-time authority governance**, on top of landed 002–006. It
  changes what may be *granted*, never what a running agent is doing.
- **The quorum mechanism is the control-plane Vault's Control Groups**, confirmed available
  under the current licence against the running enclave. This feature configures and consumes
  it; it does not build an approval engine. Building one would violate Principle I and would
  put the authority record somewhere other than the trust fabric ADR-0015 designates.
- The **surface** people use to review and approve is out of scope. Northbound transports are
  ADR-0033 and a later feature; this feature covers the gate, and approvals in test are
  exercised through the trust fabric directly.
- **The roadmap's claim that this unblocks "005's parked-run resolution" is not carried
  forward.** It assumed run-time consent, which ADR-0049 (Proposed) rejects. Control Groups
  gate authority, not runs.
- 004's approval hook — the adapter's interrupt mapping — is **not** productized here. Under
  ADR-0049's direction a run-time approval interrupt is the shape being removed, and settling
  that belongs to 0049 rather than this feature.
- Quorum policy is expected to be small (two or three approvers) in a first deployment.
  Nothing here assumes a particular number; FR-015 makes it configurable and gated.
