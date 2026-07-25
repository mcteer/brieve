# Feature Specification: Durable Execution

**Feature Branch**: `spec/005-durable-execution`

**Path**: `specs/005-durable-execution/spec.md`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Durable execution depth: make the durability seam 004 stubbed into a real guarantee, with the harness semantics defined above the provider interface (ADR-0024) and the long-running-execution rules of ADR-0026 enforced. Two-level authority (delegation grant as the durable object, per-step tokens under it); checkpoints hold state never credentials; resume re-authenticates; park on grant expiry; resume is re-observation never re-execution; single-writer lease with fencing; bounded execution; idempotency with stable keys. Success means the seven durability conformance scenarios named in the constitution's Quality Gates run and pass against a reference provider and would fail if the guarantee were weakened. Deterministic tests only; disruption simulated in-process. Out of scope: dedicated workflow-engine provider, Control Groups re-consent UX, second adapter, northbound surfaces, capability packs and eval gates, multi-tenancy, code mode, deferred-disclosure productization, production IdP/Vault, real managed-product APIs."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2 / R3 (per-task authority — the delegation grant is the durable authority object and per-step tokens are manufactured under it; resume re-exchanges rather than replays). R16 (sealed core, versioned seams — durability is sealed core, and this feature defines the semantics that hold above the provider interface). R7 as implicated by fail-closed behaviour on the resume path (a run that cannot re-authenticate parks or refuses; it never proceeds on stale authority). Builds on R4 / R10 / R13 (002 evidence) for the receipts re-observation depends on, without re-owning them. |
| **ADRs touched** | ADR-0024 (durability is a provider seam; harness semantics defined above the interface; the Lean default is a library, not a service), ADR-0026 (delegation grants, per-step tokens, resume as re-observation, single-writer lease with fencing, bounded execution, park on grant expiry), ADR-0018 (grounded reporting — re-observation reuses the same receipts), ADR-0047 (gate rows attach as their features land — this feature is what attaches the durability row). Related deferred: ADR-0028 (named trigger required before a dedicated workflow engine attaches), ADR-0016 (Control Groups re-consent UX — parking is in scope, the consent surface is not). |
| **Evidence class** | Conformance / attestation-relevant — the seven durability scenarios are conformance-asserted; re-observation records and intent/result brackets become part of the audit trail an investigator walks, so evidence integrity from 002 must survive interruption and resume. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An interrupted run resumes without re-doing its work (Priority: P1)

An operator starts a long task on behalf of a requesting user. Partway through, the process
hosting the run is interrupted. When work resumes, the run continues from where it left off:
completed steps are not repeated, and the run reaches the same outcome it would have reached
without the interruption.

**Why this priority**: This is the feature. Without kill-and-resume, everything else in this
spec is machinery with no demonstrated purpose.

**Independent Test**: Start a governed run that performs several steps; simulate disruption
in-process partway through; resume; assert the run completes, that already-completed steps
executed exactly once in total, and that the audit trail spans both segments under one
correlation ID.

**Acceptance Scenarios**:

1. **Given** a run that has completed some steps and checkpointed, **When** the run is
   disrupted and later resumed, **Then** it continues from the checkpoint and finishes.
2. **Given** that resumed run, **When** side-effect counters for already-completed steps are
   inspected, **Then** each shows exactly one execution across the whole run, not one per segment.
3. **Given** that resumed run, **When** an investigator queries audit by correlation ID,
   **Then** they find a single joined trail covering both the pre- and post-resume segments.

---

### User Story 2 - Resume re-authenticates rather than replaying a credential (Priority: P1)

When a run resumes, it obtains fresh authority under the requesting user's surviving consent.
The credential the run held before the interruption is never reused, and no credential was
written to the checkpoint for it to reuse.

**Why this priority**: A checkpoint that carries a credential, or a resume that replays one,
defeats the entire per-task authority model (Principle IV). This is the property most likely
to be quietly violated by an implementation optimizing for convenience.

**Independent Test**: Resume a disrupted run with a valid grant; assert new task authority was
manufactured, that the pre-disruption credential is not accepted, and that no credential
material appears anywhere in the checkpoint.

**Acceptance Scenarios**:

1. **Given** a disrupted run whose consent is still valid, **When** it resumes, **Then** fresh
   task authority is manufactured under that consent and the previous credential is not reused.
2. **Given** any checkpoint written by any provider, **When** its contents are inspected,
   **Then** they contain no credential, token, or secret material.
3. **Given** a resumed run, **When** the pre-disruption credential is presented directly,
   **Then** it is rejected rather than honoured.

---

### User Story 3 - A run whose consent has expired parks instead of resuming (Priority: P1)

The requesting user's consent to the task has a lifetime. If a run is disrupted and consent
expires before it resumes, the run does not resume — it parks, awaiting fresh consent, and
performs no further work in the meantime.

**Why this priority**: An expired grant is withdrawn permission. A run that resumes days later
under a consent the user has forgotten giving is the outcome ADR-0026 explicitly rejects.

**Independent Test**: Disrupt a run, advance the clock past consent expiry, attempt resume;
assert the run parks, performs zero further steps, and the parking is auditable.

**Acceptance Scenarios**:

1. **Given** a disrupted run whose consent has expired, **When** resume is attempted,
   **Then** the run parks rather than resuming, and no further step executes.
2. **Given** a parked run, **When** side-effect counters are inspected, **Then** they show no
   executions after the parking point.
3. **Given** a parked run, **When** fresh consent is supplied, **Then** the run may resume from
   its checkpoint under the new consent.

---

### User Story 4 - An interrupted step is resolved by looking, not by guessing (Priority: P1)

A run is interrupted in the middle of a step that changes something outside the platform. On
resume, the platform determines what actually happened by re-reading the external state, rather
than assuming the step succeeded or assuming it failed.

**Why this priority**: When steps change infrastructure, replaying risks a duplicate change and
skipping risks an incomplete run. Neither is acceptable, and only observation distinguishes them.

**Independent Test**: Interrupt a run between a step's intent record and its result record;
resume; assert the platform re-observes external state, does not re-execute a step it can see
completed, and does execute one it can see did not.

**Acceptance Scenarios**:

1. **Given** a step interrupted after it took effect but before its result was recorded,
   **When** the run resumes, **Then** the platform observes the effect and does not repeat it.
2. **Given** a step interrupted before it took effect, **When** the run resumes, **Then** the
   platform observes no effect and the step proceeds.
3. **Given** either case, **When** the audit trail is read, **Then** the intent record, the
   observation, and the resolution are all present and joined to the run.

---

### User Story 5 - A resumed run invalidates any instance still running elsewhere (Priority: P1)

A network partition leaves one instance believing it still owns a run that has already resumed
somewhere else. The resumed instance is the only one whose work counts; the stale instance's
attempts to act are rejected outright.

**Why this priority**: Two writers for one task means duplicate infrastructure changes under a
single consent. Losing a race is not sufficient — the stale writer must be refused.

**Independent Test**: Resume a run while a prior instance is still active; assert the prior
instance's subsequent tool calls and checkpoint writes are rejected, and that the rejection is
distinguishable from an ordinary denial.

**Acceptance Scenarios**:

1. **Given** a run resumed by a new instance, **When** the previous instance attempts a tool
   call, **Then** the call is rejected and no side effect occurs.
2. **Given** the same situation, **When** the previous instance attempts to write a checkpoint,
   **Then** the write is rejected and does not overwrite the current state.
3. **Given** either rejection, **When** the audit trail is read, **Then** the rejected attempt
   is recorded as such.

---

### User Story 6 - A run cannot consume authority indefinitely (Priority: P2)

A run that loops, stalls, or simply outlives its purpose is stopped by the platform rather than
continuing to hold and exercise the requesting user's authority.

**Why this priority**: Bounded execution is what stops a stuck run from becoming an open-ended
grant. It matters less than correctness on resume, but a durable run without bounds is worse
than a non-durable one.

**Independent Test**: Run past each bound in turn — maximum duration, step-count limit, and a
wait with no progress — and assert the run stops in each case with the reason recorded.

**Acceptance Scenarios**:

1. **Given** a run that exceeds its maximum duration, **When** the bound is reached, **Then**
   the run stops and performs no further steps.
2. **Given** a run that exceeds its step limit, **When** the bound is reached, **Then** the run
   stops with the limit recorded as the reason.
3. **Given** a run waiting with no progress beyond the watchdog threshold, **When** the
   threshold passes, **Then** the run stops rather than waiting indefinitely.

---

### User Story 7 - The durability guarantees hold for any provider (Priority: P2)

A reviewer replacing the durability implementation can confirm the platform's guarantees did
not change: the same conformance scenarios run against the new provider and assert the same
properties.

**Why this priority**: ADR-0024's central claim is that swapping durability backends changes
performance, never whether resume re-authenticates or whether a checkpoint could hold a
credential. That claim is only true if it is asserted rather than assumed.

**Independent Test**: Run the durability conformance scenarios against the reference provider;
confirm they are written against the seam rather than the implementation, such that a second
provider could be substituted without rewriting them.

**Acceptance Scenarios**:

1. **Given** the durability conformance scenarios, **When** they run against a provider,
   **Then** they exercise only the seam's behaviour and no provider-specific detail.
2. **Given** a deliberately weakened provider (in a break fixture), **When** the scenarios run,
   **Then** they fail.
3. **Given** this feature has landed, **When** `make conformance` runs, **Then** the durability
   scenarios execute as in-force gate rows rather than deferred ones.

### Edge Cases

- What happens when a checkpoint cannot be written at all? The step does not proceed as though
  it had been recorded — an unrecorded step is indistinguishable on resume from one that never
  ran, so the run fails closed rather than continuing unrecorded.
- What happens when a checkpoint is unreadable or corrupt on resume? The run does not resume on
  partial state; it parks or refuses. Guessing at missing state is the failure re-observation
  exists to prevent.
- What happens when external state cannot be re-observed on resume — the system is unreachable?
  The step is not assumed complete or incomplete; the run parks until observation is possible.
- What happens when a step is interrupted and the external system offers no way to tell whether
  it took effect? Such a step cannot be safely resumed. It must be identified as unresolvable,
  and the run parks for human resolution rather than choosing.
- What happens when consent expires *mid-run* rather than during a disruption? Per-step
  authority is manufactured under the grant, so the next step cannot be authorized; the run
  parks at the same boundary it would on resume.
- What happens when two instances resume simultaneously rather than one after another? Exactly
  one acquires the lease; the other is refused rather than queued.
- Does this feature ship a workflow engine? No. A dedicated engine attaches through the same
  provider interface later, and only under ADR-0028's named-trigger rule.
- How is disruption simulated in tests? In-process, with the established fakes and frozen clock.
  Killing real infrastructure is not a test bar this repository has ever adopted and is not
  introduced here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST treat the requesting user's consent to a task as a durable
  object with its own lifetime, bounded by the agent definition's maximum run duration, and
  distinct from the short-lived authority used for any individual step.
- **FR-002**: Per-step authority MUST be manufactured under that consent as needed and expire
  normally. A run MUST NOT hold a single long-lived credential for its duration.
- **FR-003**: Checkpoints MUST NOT contain credential, token, or secret material of any kind.
  This MUST hold for every provider and MUST be asserted, not assumed.
- **FR-004**: On resume the platform MUST re-authenticate and re-exchange under the surviving
  consent. Replaying a credential held before the disruption MUST NOT be a supported path.
- **FR-005**: If consent has expired when resume is attempted, the run MUST park for fresh
  consent and MUST NOT resume. Parking MUST be recorded and MUST leave the run resumable if
  consent is renewed.
- **FR-006**: On resume the platform MUST determine what happened to an interrupted step by
  re-reading external state, not by assuming an outcome. A step observed to have taken effect
  MUST NOT be repeated; a step observed not to have taken effect MUST be able to proceed.
- **FR-007**: Steps whose effects are not naturally repeatable MUST be bracketed by an intent
  record written before the effect and a result record written after, so an interrupted step is
  resolvable by observation.
- **FR-008**: A step whose outcome cannot be determined by observation MUST NOT be resumed by
  guessing. The run MUST park for human resolution.
- **FR-009**: Exactly one instance MUST be able to act on a run at a time. A resumed run MUST
  invalidate any prior instance, whose subsequent tool calls and state writes MUST be rejected
  rather than raced.
- **FR-010**: Repeatable steps MUST carry a stable identity such that a repeat of the same step
  is recognizable as the same step rather than a new one.
- **FR-011**: Execution MUST be bounded by a maximum duration, a limit on steps taken, and a
  watchdog on waits that make no progress. Reaching any bound MUST stop the run with the reason
  recorded.
- **FR-012**: The guarantees in FR-001 through FR-011 MUST be defined above the provider
  interface and MUST hold identically for every provider. A provider MUST NOT be able to change
  whether resume re-authenticates or whether a checkpoint may hold a credential.
- **FR-013**: The shared conformance suite MUST include the seven durability scenarios named in
  the constitution's Quality Gates — kill-and-resume, re-observe-never-re-execute,
  re-authenticate-never-replay, fencing against double resume, parking on grant expiry,
  duplicate side-effect rejection, and drain-across-upgrade — and `make conformance` MUST
  execute them. The feature's conformance contract MUST record these rows as in force rather
  than deferred (ADR-0047).
- **FR-014**: Each durability conformance scenario MUST fail if its corresponding guarantee is
  weakened, demonstrated by a break fixture rather than asserted in prose.
- **FR-015**: Audit evidence MUST survive interruption: a resumed run's records MUST join to the
  same correlation ID as its pre-disruption records, and the hash chain MUST remain intact
  across the boundary.
- **FR-016**: Deterministic tests for this feature MUST NOT call live models, identity
  providers, Vault, or managed-product APIs, and MUST NOT require an operated service or
  container runtime. Disruption MUST be simulated in-process. As with FR-012 of 004, an
  automated check MUST assert this rather than relying on convention.
- **FR-017**: A dedicated workflow-engine provider MUST NOT ship in this feature. It attaches
  later through the same interface, and only under a recorded named trigger (ADR-0028).
- **FR-018**: Core changes in this feature are bounded to the durability and authority seams
  named above — checkpoint schema and provider protocol, grant lifetime and per-step
  manufacture, lease and fencing, execution bounds, and the intent/result bracket. Any other
  sealed-core change is out of scope and requires its own approved spec (Principle V).

### Key Entities

- **Delegation grant**: The requesting user's durable consent to a task, with a lifetime
  ceilinged by the agent definition's maximum run duration. The human-meaningful unit.
- **Per-step authority**: Short-lived authority manufactured under a grant for an individual
  step. The technically-meaningful unit; expires normally and is never checkpointed.
- **Checkpoint**: Recorded run state sufficient to resume. Holds state, never credentials.
- **Intent record / result record**: The bracket around a step whose effect is not naturally
  repeatable, written before and after the effect so an interruption between them is resolvable.
- **Observation**: The re-read of external state on resume that determines what actually
  happened to an interrupted step.
- **Run lease**: The single-writer claim on a run, with fencing such that a superseded holder's
  writes are rejected.
- **Execution bounds**: Maximum duration, step limit, and stuck-wait watchdog.
- **Parked run**: A run stopped awaiting something only a human can supply — fresh consent, or
  resolution of a step whose outcome cannot be observed.
- **Durability provider**: The implementation behind the seam. Interchangeable without changing
  any guarantee in this spec.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of interrupted-and-resumed suite runs complete, with every already-completed
  step showing exactly one execution across the whole run.
- **SC-002**: 100% of resume paths in the suite manufacture fresh authority; zero reuse a
  pre-disruption credential.
- **SC-003**: Automated assertions find zero credential, token, or secret values in checkpoints
  produced anywhere in the suite.
- **SC-004**: 100% of resume attempts under expired consent park with zero subsequent step
  executions.
- **SC-005**: For every interrupted non-repeatable step in the suite, the platform's decision to
  repeat or not repeat it matches the observed external state in 100% of cases.
- **SC-006**: 100% of superseded-instance tool calls and checkpoint writes are rejected; zero
  produce a side effect or mutate current state.
- **SC-007**: Each of the three execution bounds stops a run that exceeds it, in 100% of suite
  cases, with the reason recorded.
- **SC-008**: For every resumed run in the suite, an investigator can retrieve a single joined
  audit trail by correlation ID spanning the disruption, with the hash chain intact.
- **SC-009**: `make conformance` executes all seven durability scenarios as in-force rows and
  passes on a clean tree; each scenario has a break fixture demonstrating it fails when its
  guarantee is weakened.
- **SC-010**: The full suite runs with no operated service, container runtime, or network access.

## Assumptions

- This feature ships as **durability and long-running-execution semantics plus a reference
  provider and conformance scenarios**, on top of landed 002, 003, and 004. Production IdP,
  Vault, and real product APIs remain fakes.
- The durability seam, `CheckpointBlob`, and the in-memory provider introduced by 004 are the
  starting point; this feature deepens them rather than replacing them.
- **The Lean default provider is deferred, and the reference provider used here is hermetic.**
  ADR-0024 names library-grade durable execution over an existing Postgres as the Lean default,
  but no feature to date has introduced an operated service and every suite is hermetic with no
  container runtime. This feature delivers the semantics and the conformance scenarios against a
  provider that is durable across process restart without requiring an operated service; the
  Postgres-backed Lean default attaches later through the same interface, and its absence is
  recorded as a deferred row rather than a silent gap. **This is the assumption most worth
  challenging at review** — it trades ADR-0024's named default for the repository's hermetic
  test bar, and reasonable reviewers may want the Postgres provider in scope instead.
- Re-observation reuses the receipts grounded reporting already depends on (ADR-0018). This
  feature consumes that evidence; it does not re-own or redefine it.
- Parking is in scope; the **consent surface** a human uses to grant, refuse, or renew is not.
  Control Groups (ADR-0016) and northbound surfaces (ADR-0033) remain later features. A parked
  run is observable and resumable programmatically, which is sufficient for the conformance bar.
- Tools requiring the intent/result bracket are those whose effects are not naturally repeatable.
  Identifying which registered tools qualify is part of this feature; retrofitting every future
  tool is an ongoing obligation, not a one-time task.
- Drain-across-upgrade is simulated as a controlled handover in-process, not by upgrading a
  running deployment.
- Warn-mode remains out of scope; the default and test bar is enforce/fail-closed, as in 002–004.
