# Feature Specification: Task-scoped authority manufacture

**Feature Branch**: `spec/016-task-scoped-authority`

**Created**: 2026-07-31

**Status**: **PARKED by [ADR-0057](../../docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md) (2026-08-01)** — see [README.md](README.md) for what is kept, what was pruned, and where the built substrate went.

> This document states what was *wanted*. It is retained because if `write` or `act` scopes ever
> enter a ceiling, this is the framing to re-specify against — not a plan to resume. The
> read-scope narrowing it specifies was answered rather than dropped: ADR-0056 found Vault
> cannot perform the exchange, and ADR-0057 found the narrowing is the wrong control for agents
> that must read widely to advise well.

**Input**: User description: "Task-scoped authority manufacture — narrow a run's credential to the task it was launched for, using RFC 8693 token exchange and RFC 9396 rich authorization requests that Vault validates as an OAuth resource server."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R2, R3 |
| **ADRs touched** | ADR-0056 (implements), ADR-0026 (two-level authority — consumed), ADR-0044 (federate-or-broker doctrine — extended one layer in), ADR-0048 (names this chain as the only supported path), ADR-0050 (the ceiling record this narrows against — unchanged), ADR-0054 (constrains model-written call graphs) |
| **Evidence class** | attestation-relevant |

## Clarifications

### Session 2026-07-31

- Q: The grant narrows a run's authority, but Vault's RAR type can only express path access while the ceiling also covers tools. What should the grant cover? → A: Path access only; tool authority stays with the in-process hooks
- Q: How should a task's entailed scope be computed at launch? → A: Derived from the run's requested tools and the packs behind them
- Q: On resume nobody is present to authenticate — what carries the launch-time grant? → A: Re-mint from the run record under the platform's own attested identity, bounded by the recorded expiry

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run holds only what its task needs (Priority: P1)

A person asks the platform to do a specific piece of work. The platform decides, at that
moment and while the person is present, whether they may have that work done on their behalf
— and issues the run a credential reaching only the resources that work needs. A run launched
to read one product's state cannot reach another product's secrets, even though the agent
definition that serves it is permitted to reach both for other tasks.

**What this narrows is resource access, not tool selection.** Which tools a run may invoke is
already decided and enforced per action; this narrows what the run's credential can *reach*,
which is the half that can be enforced outside the process.

**Why this priority**: This is the feature. Everything else here supports it or reports on
it. Without this story the platform's central claim — that authority is manufactured per
task — remains a sentence in the constitution with a role binding standing in for it.

**Independent Test**: Launch a run whose task needs one path, then attempt a second path that
the agent definition's ceiling permits but the task does not. The second attempt is refused,
and the refusal comes from the trust store rather than from the platform's own code.

**Acceptance Scenarios**:

1. **Given** an agent definition whose ceiling permits resources A and B, **When** a run is
   launched for a task entailing only A, **Then** the run's credential reaches A and is
   refused B.
2. **Given** that same run, **When** the refusal of B is examined, **Then** it was issued by
   the trust store evaluating the credential, not by an in-process check that could be
   bypassed.
3. **Given** a task entailing both A and B, **When** the run is launched, **Then** both
   succeed — narrowing never refuses work the task legitimately entails.

---

### User Story 2 - The person is asked once, at the start (Priority: P1)

Consent is sought when the person is there to give it. The platform establishes who they are
against their organization's own identity provider, decides whether they may have this task
performed, and records that decision as the run's authority. Nothing re-asks them mid-run,
because they have gone.

**Why this priority**: Equal to US1 because it is the same act seen from the other side —
this is *when* the narrowing decision happens, and getting it wrong (per action) would make
the platform interrogate an absent human, or (never) make the narrowing unattributable.

**Independent Test**: Launch a run and observe that exactly one authorization decision is
made, at launch, attributed to the authenticated person; then observe that subsequent steps
consume that decision rather than making new ones.

**Acceptance Scenarios**:

1. **Given** an authenticated person launching a task, **When** the run starts, **Then** one
   authority decision is recorded, naming the person and the task.
2. **Given** a run in progress, **When** it performs many steps, **Then** no further
   authorization decision is sought from the person's identity provider.
3. **Given** a person whose own entitlements do not cover the task, **When** they launch it,
   **Then** the run is refused at launch and the refusal is recorded — an agent never exceeds
   its human.

---

### User Story 3 - A disrupted run resumes without a person present (Priority: P2)

A run interrupted by an outage resumes and finishes. Nobody is there to re-consent, and the
platform does not invent consent: the authority the person granted at launch is what the
resumed run operates under, bounded by the same expiry.

**Why this priority**: P2 because US1 delivers the property and this preserves it across the
platform's existing durability behaviour. A narrowing that evaporated on resume would make
long-running work either fail or silently widen — both worse than not narrowing.

**Independent Test**: Disrupt a run mid-task, let it resume, and confirm the resumed run
holds the same narrowed authority as the original — no wider, and not refused for lack of a
present human.

**Acceptance Scenarios**:

1. **Given** a run disrupted mid-task, **When** it resumes, **Then** it operates under the
   authority granted at launch, with the same scope.
2. **Given** a run whose granted authority has expired, **When** it attempts to resume,
   **Then** it stops for re-consent rather than resuming — an expired grant is a withdrawn
   permission.
3. **Given** a resumed run, **When** its authority is examined, **Then** nothing durable was
   stored that could re-mint authority without the original grant.

---

### User Story 4 - An operator can see which protection is actually in force (Priority: P2)

The strength of this control depends on what the organization's identity provider can do. An
operator can ask the platform which arrangement is in force and get a plain answer, including
when the answer is the weaker one.

**Why this priority**: P2 because the control works either way, but an operator who believes
they have the stronger arrangement when they do not is holding a false assurance — the
failure mode this platform legislates against elsewhere.

**Independent Test**: Configure an estate each way and read the reported posture; the report
distinguishes them and names the reason.

**Acceptance Scenarios**:

1. **Given** an identity provider that can issue task-scoped authority itself, **When** the
   posture is read, **Then** it reports the federated arrangement.
2. **Given** an identity provider that cannot, **When** the posture is read, **Then** it
   reports the platform-issued arrangement and says why, rather than reporting the stronger
   one or reporting nothing.
3. **Given** an estate where the narrowing is not configured at all, **When** the posture is
   read, **Then** it says so plainly rather than defaulting to something that reads as
   protected.

---

### User Story 5 - A task cannot quietly widen its own authority (Priority: P3)

An agent that decides mid-run it needs something outside what was granted is refused. The
work stops or asks for new consent; it does not proceed on authority nobody granted.

**Why this priority**: P3 because it is the enforcement consequence of US1 rather than a
separate capability — but it is separately testable, and it is where a well-meaning
implementation is most likely to soften the control to avoid a support ticket.

**Independent Test**: Launch a run, have it attempt work outside the granted scope, and
confirm the refusal is recorded and the run does not proceed with that work.

**Acceptance Scenarios**:

1. **Given** a run with a granted scope, **When** it attempts work outside that scope,
   **Then** the attempt is refused and recorded.
2. **Given** that refusal, **When** the trail is read, **Then** it distinguishes "outside the
   granted task" from "outside the agent's ceiling" — different causes with different
   remedies.

### Edge Cases

- What happens when the organization's identity provider is unreachable at launch? The run
  does not start, and the failure says the identity provider was unreachable rather than
  presenting as a permission problem.
- What happens when a task's entailed scope cannot be determined? The launch refuses rather
  than granting broadly to be safe.
- What happens when a task entails nothing — an agent that reaches no external system? The
  granted scope is empty, and that is a valid grant rather than an error.
- What happens when the narrowing feature is not activated on the trust store? The platform
  reports the protection as absent rather than behaving as though it were present.
- What happens when a granted authority expires mid-run? The run stops for re-consent, at a
  step boundary, with nothing left half-done.
- What happens when the same task is launched twice by different people? Each run carries its
  own grant attributed to its own person; neither can act under the other's.

## Requirements *(mandatory)*

### Functional Requirements

**Deciding and granting**

- **FR-001**: The platform MUST decide, at run launch, whether the authenticated person may
  have this task performed, and MUST record that decision as the run's authority.
- **FR-002**: The granted authority MUST be narrowed to the resources the task entails, and
  MUST NOT convey the agent definition's full resource ceiling when the task entails less.
- **FR-003**: The granted authority MUST NOT exceed the intersection of the person's own
  entitlements, the agent definition's ceiling, and what the task entails.
- **FR-004**: The platform MUST refuse a launch whose entailed scope cannot be determined,
  rather than granting broadly.
- **FR-005**: Exactly one authorization decision MUST be made per run launch; steps within a
  run MUST NOT trigger further decisions with the person's identity provider.

**Who says what**

- **FR-006**: The person's identity MUST be established against the organization's own
  identity provider, and the platform MUST NOT substitute its own judgement about who they
  are.
- **FR-007**: The entailed scope MUST be computed by the platform, which is the only party
  holding the agent definition, its ceiling, and the task.
- **FR-007a**: The entailed scope MUST be derived from the run's requested tools and the packs
  behind them, so that no agent definition has to declare it separately and it cannot drift
  from the tools it describes.
- **FR-007b**: Where a tool's declared resources exceed what a particular run uses, the grant
  MAY be broader than strictly necessary — but it MUST remain a strict subset of the
  definition's ceiling whenever the requested tools are a strict subset of it.
- **FR-008**: The narrowed authority MUST be evaluated by the trust store when the run uses
  it, so that a workload cannot exceed its grant by declining to check itself.

**Enforcement and refusal**

- **FR-009**: An attempt outside the granted scope MUST be refused, and the refusal MUST be
  recorded.
- **FR-010**: A refusal MUST distinguish "outside the granted task" from "outside the agent's
  ceiling", because the remedies differ.
- **FR-011**: Existing per-action enforcement MUST continue unchanged; this feature adds a
  second place the boundary holds and replaces nothing.
- **FR-011a**: Tool authority MUST remain enforced where it is today. This feature does not
  move, restate, or narrow which tools a run may invoke — it narrows only what the run's
  credential can reach.

**Across disruption**

- **FR-012**: A resumed run MUST operate under the authority granted at its launch, with the
  same scope.
- **FR-013**: A resumed run MUST NOT require the person to be present.
- **FR-014**: A run whose granted authority has expired MUST stop for re-consent rather than
  resuming.
- **FR-015**: The grant's scope, subject, and expiry MUST be recorded at launch as data, and
  a resumed run's authority MUST be re-derived from that record under the platform's own
  attested identity.
- **FR-015a**: What is recorded MUST NOT itself be usable as a credential. A reader of the run
  record gains a description of the authority, never the authority.
- **FR-015b**: A re-derived authority MUST NOT outlive the recorded expiry, and MUST NOT be
  wider than the recorded scope — the record is a ceiling on the resume, not a seed for a
  fresh decision.

**Posture and honesty**

- **FR-016**: The platform MUST report which arrangement is in force — federated,
  platform-issued, or absent — and MUST NOT report a stronger arrangement than the one
  operating.
- **FR-017**: The report MUST name the reason for the arrangement in force, not only its
  name.
- **FR-018**: Where the narrowing is not configured or not activated, the reported posture
  MUST say so plainly rather than defaulting to a value that reads as protected.

**Secrets posture**

- **FR-019**: No new standing credential may be introduced. Any key the platform uses to
  assert authority MUST NOT be durably held by a platform service.
- **FR-020**: Authority to assert task scope MUST itself be a bounded, named grant, because
  whoever holds it can manufacture authority.

### Key Entities

- **Task grant**: The authority established at launch — who consented, to what work, over
  what scope, until when. Recorded as **data, never as a credential**: a reader of the record
  gains a description of the authority and not the authority itself. The object a run and its
  resumptions operate under.
- **Entailed scope**: The resources a task requires in order to be performed, derived at
  launch from the run's requested tools and the packs behind them, intersected with the
  definition's ceiling and the person's entitlements. Covers resource access only — which
  tools a run may invoke is decided and enforced separately, as it is today.
- **Arrangement (posture)**: Which of the available protections is actually in force for this
  estate, and why — federated, platform-issued, or absent.
- **Refusal record**: An attempt that exceeded the grant, recorded with enough to tell which
  boundary was crossed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A run whose requested tools entail a strict subset of its agent definition's
  resource ceiling is refused the remainder, in 100% of attempts.
- **SC-002**: That refusal is issued by the trust store rather than by platform code, and is
  demonstrated by a check that bypasses the platform's own enforcement.
- **SC-003**: A run whose task legitimately entails a resource is never refused it — zero
  false refusals across the conformance corpus.
- **SC-004**: Exactly one authorization decision is made per run launch, regardless of how
  many steps the run performs.
- **SC-005**: A person launching a task beyond their own entitlements is refused at launch,
  and the refusal is recorded naming the person and the task.
- **SC-006**: A disrupted run resumes with a scope identical to the one granted at launch —
  neither wider nor narrower — with no person present.
- **SC-006a**: Nothing recorded for the resume is usable as a credential on its own: presented
  directly to the trust store, the recorded grant obtains nothing.
- **SC-007**: A run whose grant has expired stops for re-consent rather than resuming, at a
  step boundary with nothing left half-done.
- **SC-008**: The reported arrangement matches the one actually operating in 100% of
  configurations tested, including the unconfigured case.
- **SC-009**: The number of standing credentials held by the platform is unchanged by this
  feature.
- **SC-009a**: Tool authority decisions are byte-identical before and after this feature for
  the same run — the narrowing touches resource access and nothing else.
- **SC-010**: Every claim above is asserted against a real trust store with the narrowing
  activated and a real trusted issuer — not against a substitute, because a substitute cannot
  refuse anything the test does not tell it to.

## Assumptions

- **The organization operates an identity provider the platform can authenticate people
  against.** This is already true of the platform and is the deployment shape the product
  assumes; a customer plugs in their own.
- **Which arrangement an estate lands in depends on that identity provider's capabilities**,
  not on a platform preference. The weaker arrangement is expected to be the common case at
  first, and the feature is specified so that it works there and improves where the stronger
  one is available.
- **The existing ceiling record and its reader are unchanged.** This narrows against the
  ceiling; it does not relocate, redefine, or reinterpret it.
- **Per-action enforcement stays where it is.** The in-process checks continue to run
  unchanged, and this feature is a second boundary rather than a replacement — so a failure
  in this work degrades to today's behaviour rather than to no enforcement.
- **A task's entailed scope is derived from the run's requested tools**, not declared
  separately by a definition author. The platform already resolves requested tools and the
  packs behind them at launch, so the scope is computed from things that exist rather than
  from a new artifact that could drift from the tools it describes. Where it cannot be
  determined, FR-004 refuses.
- **The narrowing is therefore as tight as the tools' own declarations, and no tighter.** A
  tool declaring broader access than a given run needs makes that run's grant broader than
  strictly necessary. This is accepted for a first implementation: the grant is still a strict
  subset of the ceiling whenever the requested tools are, which is the property being bought.
  Tightening further is a later question about tool declarations, not about this mechanism.
- **Runs whose work is chosen dynamically are bounded by what was granted.** A model may
  choose the shape of the work; it may not choose authority. Where this bites, the run stops
  rather than widening.
- **The trust store's narrowing feature can be activated in the deployment.** It is currently
  inactive in the development enclave, and activating it is part of this work.
