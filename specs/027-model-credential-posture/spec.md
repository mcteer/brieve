# Feature Specification: How the platform holds a model credential

**Feature Branch**: `spec/027-model-credential-posture`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "How the platform holds a model credential — the decision three features routed around, and it is platform-wide rather than ask-shaped."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R2, R3** (zero standing credentials; authority per task — this feature is about the one credential the platform has never had a posture for). **R10** (observability — a model call's authority should be as legible in the trail as a tool call's). |
| **ADRs touched** | **ADR-0044** — **the load-bearing one, and it already contains the rule**: *credential translation federates where the product validates external identity, and brokers only where it cannot*. A model vendor does not validate workload identity, so models fall in the broker branch by that rule rather than by a new judgement. **An amendment is expected**, because ADR-0044 names TFE and says nothing about models. **ADR-0022 / ADR-0039** (the Qualified Model Matrix decides *which* model; this decides how the credential to call it is obtained — consumed, not revisited). **ADR-0026** (task-scoped authority that evaporates). **Constitutional amendment likely** — see FR-002. |
| **Evidence class** | **Attestation-relevant, and it is about the platform's own posture.** Every prior feature manufactured authority per task from attested identity. This one confronts the single dependency where that mechanism does not reach, and the platform has been silent about it through three features that needed it. |

## Clarifications

### Session 2026-08-02

- Q: How should the platform hold a model credential? → A: **Broker it, on the TFE pattern.** The
  platform holds one rotated, Control-Group-governed vendor credential and issues short-lived
  material per task. **ADR-0044's own rule routes models here** rather than this being a fresh
  judgement: federate where the product validates external identity, broker where it cannot — and
  a model vendor authenticates with a static key and validates no workload identity. A gateway was
  rejected because it moves the key outward rather than removing it, while adding an operated
  component Principle VI would want a named trigger for. Doing nothing was rejected because it
  leaves three merged features as a capability nobody can turn on.
- Q: Whose authority is a model call made under? → A: **The platform's own.** A model call has no
  product side whose entitlements could be mirrored, so there is nothing for per-subject scoping to
  be faithful *to* — the asker's identity belongs in the trail, which already carries it, rather
  than in the authority. Per-tenant scoping is a real want (billing, rate limits, per-tenant
  revocation) and is recorded as owed rather than approximated.
- Q: Does this posture govern the eval lane's credential? → A: **No — the lane stays exempt**, and
  the boundary is stated rather than left implicit. Qualification is a human-run activity with a
  named runner; coupling it to the deployed posture would make earning a cell depend on the thing
  that uses one being configured.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A person asks a question and gets an answer (Priority: P1)

Someone asks the deployed platform a question. It answers — because the surface obtained
authority to call a model the way it obtains authority for everything else, and the trail shows
what it obtained and on whose behalf.

**Why this priority**: it is the capability three features built and none delivered. 024 built
answering, 025 extended it to the estate, 026 gated it — and a deployed ask still refuses before
reaching a model, because no workload has any way to hold a model credential.

**Independent Test**: a real question through the served surface returns a real answer, with the
model call's authority visible in the trail.

**Acceptance Scenarios**:

1. **Given** a qualified cell and a configured credential posture, **When** someone asks through
   the deployed surface, **Then** they receive an answer and the trail records the model call's
   authority — not merely that a model was named.
2. **Given** the same, **When** the credential cannot be obtained, **Then** the ask refuses
   **distinguishably** from an unqualified cell and from an unreachable model.
3. **Given** an agent run whose definition binds a real model, **When** it runs, **Then** it
   obtains model authority by **the same mechanism** the surface used. Two mechanisms for one
   question is the fragmentation Principle VII forbids.

---

### User Story 2 - An operator can revoke a model credential and see it take effect (Priority: P2)

Whoever holds the credential can withdraw it, and the platform stops calling that model —
immediately, unilaterally, and visibly.

**Why this priority**: it is what makes the posture a posture rather than a config value.
Principle IV requires revocation to be unilateral and immediate; a key pasted into a jobspec
satisfies nothing of the kind, and a platform that cannot demonstrate revocation has not really
decided how it holds anything.

**Independent Test**: revoke, ask again, observe refusal — with no restart and no redeploy.

**Acceptance Scenarios**:

1. **Given** a working answering path, **When** the credential is revoked, **Then** subsequent
   asks refuse without a restart, and the refusal names the cause.
2. **Given** revocation, **When** the trail is read, **Then** the moment authority stopped is
   locatable.

---

### User Story 3 - The platform can say what its posture is (Priority: P3)

The constitution, the decision record, and the running system agree about how a model credential
is held. Nobody has to read a jobspec to find out.

**Why this priority**: it delivers no capability, and it is why this feature exists rather than a
configuration change. Principle IV currently says *"static API keys are prohibited without
exception"*, and any posture that involves a vendor key must either satisfy that sentence or
amend it deliberately. A platform silently violating its own constitution is worse than one that
amended it in the open.

**Independent Test**: the posture is written where a reader looks for it, and a check fails if the
running system contradicts it.

**Acceptance Scenarios**:

1. **Given** the decided posture, **When** the constitution is read, **Then** it describes what
   the platform actually does.
2. **Given** a deployment that contradicts the posture, **When** the checks run, **Then** they
   fail.

---

### Edge Cases

- **The credential is withdrawn mid-run.** *(Restated at implement — see FR-010.)* A static vendor
  key has no expiry, so authority never goes stale on its own; what can happen is an operator
  rotating or deleting it while a run holds it. That run completes on what it holds, and the next
  task refuses — the same rule every per-task grant here follows. A resume re-authenticates rather
  than replaying, which the existing checkpoint discipline already requires.
- **The vendor is unreachable versus the credential is refused.** Different causes, different
  people; they must not share a refusal.
- **Two tenants, one credential.** If the platform holds one vendor account, every tenant's asks
  are billed and rate-limited together, and one tenant's misuse degrades another's service. That
  is a real property of whatever is decided and must be stated rather than discovered.
- **The eval lane already reads a key from a developer's `.env`.** That is a dev-lane secret with
  a named runner, and it is not what this feature governs — but the boundary must be explicit, or
  the lane becomes the loophole.
- **A model call's cost and content.** Whatever is decided must not put secret values into model
  context, and must not put model content into the trail.

## Requirements *(mandatory)*

### The posture

- **FR-001**: A model credential MUST be **brokered**, on the pattern ADR-0044 already establishes
  for products that cannot federate: the platform holds one vendor credential, governed and rotated
  the way the existing named exception is, and a workload obtains it **per task** rather than
  holding it standing.
- **FR-001a** *(amended at implement — research F2, plan Complexity Tracking)*: **No workload ever
  persists the credential.** It is obtained at task start under the workload's own attested
  identity, held in process memory for that task, and evaporates with it. It never enters a
  checkpoint, a log, the trail, or model context.

  **The original wording promised derivation, and a model vendor makes derivation impossible.** It
  read *"a workload obtains short-lived material per task rather than the credential itself…
  neither can read what it was derived from"*. Vault mints lesser material for products that expose
  a credential API — a scoped database role, a short-lived certificate — and a model vendor exposes
  none: there is nothing to derive *from*, so the material a workload uses **is** the key. Building
  to the original sentence would have required a proxy holding the key on the workload's behalf,
  which relocates it and removes nothing, and which the precedent this feature reasons from does
  not do either.

  **So the guarantee is lifetime, not scope**, and the amendment is here rather than in a comment
  because a spec claiming a property the system cannot have is the exact defect this feature was
  written to stop one level up.
- **FR-001b**: The vendor credential MUST be **rotatable without redeploying anything**, on the
  same reasoning as the existing exception: a credential whose rotation requires a deployment is
  one nobody rotates.
- **FR-002**: The decided posture MUST be reconciled with Principle IV's *"static API keys are
  prohibited without exception"*. If the posture involves a vendor key anywhere inside the
  boundary, that sentence MUST be **amended in the open** rather than read around.
- **FR-003**: The posture MUST hold **identically on the run path and the answering path**. A
  model call is a model call; two mechanisms would be the fragmentation Principle VII forbids.

### Authority and its limits

- **FR-004**: Model authority MUST be obtained **per task** and MUST NOT outlive it, on the same
  discipline as every other authority this platform manufactures.
- **FR-005**: A model call is made under **the platform's own authority**, not the asker's. There
  is no product side whose entitlements could be mirrored, so per-subject scoping would be a shape
  without a referent.
- **FR-005a**: The asker MUST still be identifiable **in the trail** for every model call. Calling
  as the platform must not make "who this was for" unanswerable — that is the whole distinction
  between acting as yourself and acting anonymously.
- **FR-005b**: **Per-tenant scoping is owed, not built.** One vendor account means shared billing,
  shared rate limits, and revocation that cannot single a tenant out. Recorded because it is a
  property people discover late, and because the next feature to want it should find it named.
- **FR-006**: Revocation MUST be **unilateral and immediate** — no restart, no redeploy — and the
  moment authority stopped MUST be locatable in the trail.

### The record

- **FR-007**: The trail MUST show a model call's **authority**, not merely which model was named.
  Today it records the cell; it does not record how the call was permitted to happen.
- **FR-008**: No credential value MUST ever enter the trail, a log, a checkpoint, or model
  context. References only — the rule the platform already holds everywhere else.

### Failures

- **FR-009**: A credential that cannot be obtained MUST refuse **distinguishably** from an
  unqualified cell (026) and from an unreachable vendor. Three causes, three people.
- **FR-010** *(reconciled at implement — the condition it describes cannot arise)*: A run MUST NOT
  silently continue on **withdrawn** model authority.

  The original wording said *expired*, assuming derived material with a lifetime of its own. A
  static vendor key has no expiry, so nothing ever becomes stale — which means the risk this
  requirement was reaching for is **withdrawal**, not expiry, and that is FR-006's: rotate or
  delete the record and the next task's fetch refuses. A task already in flight completes on the
  authority it holds, exactly like every other per-task grant this platform manufactures, and a
  row asserts precisely that so nobody later satisfies revocation by reaching back into a running
  task.

  Recorded rather than deleted, because a requirement that quietly disappears between spec and
  merge is indistinguishable from one that was missed.

### What must not change

- **FR-011**: The blocking eval lane MUST remain runnable with **no vendor credential**.
- **FR-012**: The Qualified Model Matrix keeps deciding **which** model may be used. This feature
  decides only how the credential to call it is obtained.
- **FR-013**: The eval lane is **exempt, explicitly**. `make evals-live` keeps reading a dev-lane
  secret with a named runner: qualification is a human-run activity, and coupling it to the
  deployed posture would make *earning* a cell depend on the thing that *uses* one being
  configured.
- **FR-013a**: The exemption MUST be **written where the lane is**, not only here. An exemption a
  reader has to infer is the loophole it was meant not to be.

### Key Entities

- **Model credential**: the one vendor credential the platform holds, governed and rotated. Never
  reaches a workload.
- **Model authority**: what the trail carries to say **how a model call was permitted** — a
  reference of the form `vault:model-credentials/<vendor>@v<version>`, naming where the credential
  lives and which rotation generation was in force. **A reference, never a value, and never a hash
  of one.**

  Deliberately *not* the name for the material itself, which is what an earlier draft of this
  entity described. The material has no separate identity to name: it is the credential, held for
  one task (FR-001a). Two things called "model authority" — one a secret, one a trail field — would
  have an investigator reading the record expecting material.
- **Posture**: the platform's stated answer, written where a reader looks and checkable against a
  running deployment.

## Success Criteria *(mandatory)*

- **SC-001**: A real question through the deployed surface returns a real answer.
- **SC-002**: The same mechanism serves an agent run that binds a real model. *(Asserted
  structurally in the blocking lanes — both assemblies reach one reader and check in the same order
  — because the run path resolves authority under an attested workload identity that no hermetic
  row can hold. The behavioural half is owed by name at the deployed demonstration; see the
  conformance contract.)*
- **SC-003**: Revocation stops model calls with no restart, and the moment is locatable.
- **SC-004**: The credential does not outlive the task it was obtained for, and no workload
  persists it. *(Amended with FR-001a: the original said "cannot read the credential it was derived
  from", which described a derivation a model vendor cannot perform.)*
- **SC-004a**: Every model call's asker is identifiable in the trail, though the call is made under
  the platform's authority.
- **SC-005**: No credential value appears in the trail, logs, checkpoints, or model context.
- **SC-006**: Three failures — no credential, unqualified cell, unreachable vendor — are
  distinguishable in the trail.
- **SC-007**: The constitution describes what the platform does, and a check fails if a deployment
  contradicts it.
- **SC-008**: The blocking lanes still run with no vendor credential.

## Assumptions

- **The machinery already works; the posture is what is missing.** `make evals-live` calls a real
  vendor through the product answering path and passes. Nothing here is about whether a model can
  be called.
- **ADR-0044's rule is consumed, not re-argued.** *Federate where the product validates external
  identity; broker only where it cannot.* A model vendor authenticates with a static key and
  validates no workload identity, which places models in the broker branch by the existing rule.
- **The TFE broker is the precedent to reason from**, being the one named exception: a rotated,
  Control-Group-governed management token. Whether models earn the same treatment is FR-001's
  question, not an assumption.
- **One vendor account means shared billing and shared rate limits across tenants**, whatever is
  decided, until something says otherwise. Stated because it is a property people discover late.
- **Deferred and NOT in scope**: the portal's answering surface, corpus refresh scheduling,
  ADR-0035's team-granularity scope, and promoting the `ask` cell to `live` (which needs a clean
  full-lane run and is unrelated to posture).
