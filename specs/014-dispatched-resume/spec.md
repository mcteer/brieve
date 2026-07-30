# Feature Specification: Wire resume into the dispatched path

**Feature Branch**: `spec/014-dispatched-resume`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "Wire resume into the dispatched path — 005's completion. `resume_run` has no caller anywhere in `src/`. The chain is closed except at its last link: a fabric outage suspends, the sweeper re-dispatches, `step_index` is carried through the sweeper, the dispatcher, and the jobspec — and the entrypoint never reads it, calling `start_governed_run` and looping from zero. 005's five conformance rows are demonstrated of the function and not of the dispatched path."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R3** (per-task authority — a resumed run manufactures fresh authority from the resuming allocation's own attested identity, and nothing carries authority across the disruption). **R4** (evidence over claims — the resume decision and its reason reach the trail; this feature exists because a claim outran its evidence). **R8 / R9** (durable execution and exactly-once effects — the guarantees 005 built, reached from production for the first time). |
| **ADRs touched** | **ADR-0026** (checkpoints hold state, never credentials — honoured on a new path, not extended). **ADR-0048** (Nomad is the substrate; a resumed run is a new allocation with a new attested identity, which is *why* re-authentication is structural rather than remembered). **ADR-0049** (consent to start is consent to finish — grant expiry stops terminally; `SUSPENDED` waits on a machine condition, never a person). **ADR-0047** (a row must not read as more than it is — the record this feature repairs). ADR-0024 (the durability seam these guarantees sit above). |
| **Evidence class** | **Attestation-relevant, and correcting rather than extending.** Everything prior added evidence. This makes an existing claim true: 005's contract asserts that a disrupted run resumes and completes, and that assertion is currently about a function nothing calls. An attestation resting on a row whose scope is narrower than its wording is the failure this feature closes. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A disrupted run finishes what it started (Priority: P1)

A person asks for work. Partway through, the trust fabric becomes unreachable and the run
suspends. The fabric recovers. The run continues from where it stopped and completes — and the
steps it had already finished happened exactly once.

**Why this priority**: It is the feature, and it is the promise 005's contract already makes.
Everything else here is a failure mode of this story.

**Independent Test**: Dispatch a multi-step run, disrupt it mid-flight, let the recovery sweep
re-dispatch it, and observe the completed steps' effects exactly once across both allocations.

**Acceptance Scenarios**:

1. **Given** a dispatched run that suspended after completing some steps, **When** its
   dependency recovers and the sweep re-dispatches it, **Then** the new allocation continues
   from the recorded position rather than from the beginning.
2. **Given** a resumed run, **When** it completes, **Then** every step that had already taken
   effect shows **exactly one** execution across the whole run — not one per allocation.
3. **Given** a resumed run, **When** its authority is examined, **Then** it was manufactured
   fresh from the resuming allocation's own attested identity, and no credential crossed the
   disruption.
4. **Given** a run that was never disrupted, **When** it is dispatched, **Then** its behaviour
   is unchanged from before this feature — a fresh dispatch is not a resume.

---

### User Story 2 - An interrupted step is resolved by asking, not by assuming (Priority: P1)

A step with an external effect is interrupted at the worst moment: the effect may or may not
have landed, and the record cannot say which. The platform finds out by observing external
state rather than by guessing in either direction.

**Why this priority**: Shares P1 because the alternative to observing is choosing — and both
choices are wrong. Assuming it happened silently drops work; assuming it did not duplicates an
effect. 013 made this consequential by introducing the first non-repeatable tools with
observers, and nothing on the dispatched path consults them.

**Independent Test**: Dispatch a run using a non-repeatable tool, interrupt it between the
opening and closing of its effect bracket, resume, and confirm the outcome was determined by
observation — with the opposite external state producing the opposite decision.

**Acceptance Scenarios**:

1. **Given** an interrupted step whose effect **did** land, **When** the run resumes, **Then**
   the step is not re-executed.
2. **Given** an interrupted step whose effect **did not** land, **When** the run resumes,
   **Then** the step proceeds.
3. **Given** an interrupted step whose outcome **cannot be determined**, **When** the run
   resumes, **Then** it is not resumed by assumption in either direction; the run suspends
   naming what it could not observe.
4. **Given** a non-repeatable tool, **When** its step is resumed, **Then** the observer the
   platform already holds for that tool is what answered the question.

---

### User Story 3 - A suspended run names something that can recover it (Priority: P1)

A run suspends because a product is unreachable. When that product comes back, the run resumes
— without anyone noticing, reporting, or pressing anything.

**Why this priority**: P1 because a suspension nobody can match to a recovery is not a
suspension; it is a run that never finishes. The recovery sweep matches on **products**, and a
suspension that names a **tool** is never matched — so this story is the difference between
automatic recovery and a silent hang.

**Independent Test**: Dispatch a run whose tool reaches a product, make that product
unreachable, confirm the suspension names the product, restore the product, and confirm the
sweep resumes it without intervention.

**Acceptance Scenarios**:

1. **Given** a suspension caused by an unreachable product, **When** the suspension is
   recorded, **Then** it names the **product**, in the vocabulary the recovery sweep searches.
2. **Given** a suspended run and a recovered product, **When** the sweep next runs, **Then** the
   run is re-dispatched with no human action.
3. **Given** a suspension, **When** nothing recovers, **Then** the run stays suspended and
   waits — it does not escalate to a person and does not time out into completion.

---

### User Story 4 - Withdrawn consent ends a run rather than pausing it (Priority: P2)

A run is disrupted. By the time it could resume, the person's consent has expired. The run
stops, the reason is recorded, and renewed consent does not revive it.

**Why this priority**: P2 because it is a bound rather than the main path, and the bound is
already decided (ADR-0049). It is here because the dispatched path must honour it, and a path
that resumed under lapsed consent would be the one failure this feature could introduce while
appearing to work.

**Independent Test**: Dispatch a run under a short-lived grant, disrupt it, let the grant
expire, and confirm the resume stops with its reason recorded and zero subsequent steps.

**Acceptance Scenarios**:

1. **Given** a disrupted run whose grant has expired, **When** resume is attempted, **Then** the
   run **stops** with the reason recorded, and no further step executes.
2. **Given** a run stopped for expired consent, **When** consent is renewed, **Then** the run
   does **not** revive — the stop is terminal.
3. **Given** a resume refused for any reason, **When** the refusal happens, **Then** the reason
   is recorded and the run does not afterwards hold a claim on itself.

---

### User Story 5 - Two instances never both act on one run (Priority: P2)

A disruption leaves an old instance believing it still owns a run while a new one takes over.
Only one of them can act.

**Why this priority**: P2 because the mechanism exists and is tested; this story is about it
holding on the dispatched path. A superseded instance that could still write would corrupt the
very record resume depends on.

**Independent Test**: Arrange an overlap between a superseded instance and its replacement, and
confirm the superseded one's effects and state writes are rejected.

**Acceptance Scenarios**:

1. **Given** a resumed run, **When** a superseded instance attempts a tool call or a state
   write, **Then** it is rejected — zero side effects, zero state mutation.
2. **Given** a resumed run, **When** ownership is claimed, **Then** the claim happens before
   anything is observed or acted on, so an observation cannot be invalidated by a writer that
   was still running when it was made.

---

### Edge Cases

- **A resume with no record to resume from.** The state saying where the run got to is missing.
  Guessing is the failure observation exists to prevent — and this is not a condition that
  recovers, so it must not be treated as one.
- **A resume whose model binding is no longer available.** The binding the definition pinned was
  withdrawn between the original dispatch and the resume. Substituting another qualified binding
  is permitted and must be recorded; substituting an unqualified one is not.
- **A resume of a run that already finished.** The candidate list can lag the record. A finished
  run that gets re-dispatched must not re-enter its work.
- **A suspension whose product never recovers.** The run waits indefinitely by design. What must
  not happen is a silent expiry that reads as completion.
- **A step interrupted before its bracket opened.** There is nothing to resolve, so the step
  never began and simply proceeds.
- **A fresh dispatch carrying a resume's identifiers.** Position and identity arrive as
  metadata; a fresh run and a resume must be distinguishable, or a first dispatch could skip
  work it never did.

## Requirements *(mandatory)*

### Functional Requirements

**The dispatched path takes the resume path**

- **FR-001**: A dispatched run that is a **resume** MUST take the resume path — loading the
  recorded position, resolving what already happened, and continuing — rather than starting
  fresh.
- **FR-002**: A dispatched run that is **not** a resume MUST behave exactly as it does today. A
  fresh dispatch is not a resume, and the two MUST be distinguishable from what the dispatch
  carries.
- **FR-003**: Every outcome the resume decision can reach MUST be honoured: continue with the
  work that remains, **stop** with a recorded reason, or **suspend** naming what is awaited. An
  unhandled outcome MUST NOT default to proceeding.
- **FR-004**: Work the record shows already took effect MUST NOT be re-executed. Work the record
  shows did not take effect MUST proceed.

**Observation, not assumption**

- **FR-005**: An interrupted step's outcome MUST be determined by **observing external state**,
  never by assuming in either direction (005 FR-006).
- **FR-006**: The observers the platform already holds for its tools MUST be what answers that
  question — a resumed run MUST NOT resolve an interrupted step without consulting the observer
  registered for the tool that step used.
- **FR-007**: A step whose outcome **cannot** be determined MUST NOT be resumed by assumption.
  The run MUST suspend, naming the dependency it could not observe (005 FR-008).

**A suspension names what can recover it**

- **FR-008**: A suspension MUST name the **product** the awaited tool reaches, in the same
  vocabulary the recovery sweep searches. A suspension naming only a tool MUST NOT occur where a
  product is known.
- **FR-009**: A suspended run MUST resume automatically when its named dependency recovers, with
  no human action and no escalation (ADR-0049).

**Authority across the disruption**

- **FR-010**: A resumed run MUST manufacture authority **fresh**, from the resuming instance's
  own attested identity (005 FR-004, R3).
- **FR-011**: **No path MAY carry authority across the disruption.** There MUST be no parameter,
  field, or metadata by which a pre-disruption credential reaches a resumed run.
- **FR-012**: Recorded state MUST NOT contain credential, token, or secret material — including
  any state the resume path newly reads or writes (005 FR-003, ADR-0026).
- **FR-013**: If consent has expired when resume is attempted, the run MUST **stop** with the
  reason recorded, and the stop MUST be terminal — renewed consent MUST NOT revive it (ADR-0049,
  amending 005 FR-005's original "park").
- **FR-014**: A resume refused for any reason MUST record that reason and MUST NOT leave the run
  holding a claim on itself.

**Exactly one actor**

- **FR-015**: Exactly one instance MUST be able to act on a run at a time; a superseded
  instance's effects and state writes MUST be rejected (005 FR-009).
- **FR-016**: Ownership MUST be claimed **before** anything is observed or acted on, so no
  observation can be invalidated by a writer still running when it was made.

**Evidence**

- **FR-017**: The resume decision and its reason MUST reach the audit trail, so a resumed run, a
  stopped run, and a suspended run are distinguishable afterwards by record rather than by
  inference.
- **FR-018**: A resumed run that used a different qualified model binding than the one originally
  pinned MUST record that substitution. Substituting an unqualified binding MUST remain
  impossible.

**How this is proven**

- **FR-019**: 005's five resume properties MUST be asserted **through a real dispatch** —
  driving the scheduler, disrupting a running instance, and observing the outcome end to end.
  Function-level assertions MUST NOT be the only evidence for any of them.
- **FR-020**: The record MUST stop scoping 005's resume rows to the function once they are
  asserted through a dispatch, and MUST continue to say so for any property that remains
  function-only.

### Key Entities

- **Resume position**: where a run got to — the identity of the run's durable state and the step
  it had reached. Carried to a resuming instance as metadata, never as authority.
- **Effect bracket**: the pair of records around a step with an external effect. An opening
  record with no closing one is precisely the interrupted case that must be resolved by
  observation.
- **Resume decision**: what the platform concluded about a disrupted run and why — continue,
  stop, or suspend — with the work already done, the work remaining, and the reason when it is
  not continuing.
- **Awaited dependency**: the product a suspended run waits on, named so a recovery can be
  matched to it.
- **Ownership claim**: the single-writer assertion over a run, held by exactly one instance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of disrupted-and-resumed dispatched runs complete, and every step that had
  already taken effect shows **exactly one** execution across the whole run.
- **SC-002**: Zero resumed runs reuse a pre-disruption credential; 100% manufacture fresh
  authority from the resuming instance's own attested identity.
- **SC-003**: Zero credential, token, or secret values appear in any recorded run state,
  including state the resume path reads or writes.
- **SC-004**: 100% of interrupted non-repeatable steps are resolved by observation. Zero are
  resolved by assumption in either direction.
- **SC-005**: Zero suspensions name a tool where the product it reaches is known; 100% name the
  product the recovery sweep searches for.
- **SC-006**: 100% of suspended runs whose dependency recovers are resumed without human action.
- **SC-007**: A resume under expired consent stops with its reason recorded in 100% of cases,
  with zero subsequent steps, and renewed consent revives zero of them.
- **SC-008**: A superseded instance achieves zero side effects and zero state mutations.
- **SC-009**: **Every one of SC-001 through SC-008 is demonstrated through a dispatch**, not only
  through a direct call. Zero of 005's five resume properties remain evidenced solely at the
  function level.
- **SC-010**: The resume path has a caller in the shipped source. Zero of the three pieces this
  feature consumes — the tool-to-product mapping for suspensions, the tool observers, and the
  resume refusal handling — remain wired to nothing.
- **SC-011**: Runs that were never disrupted behave identically to before this feature, measured
  as zero changes in outcome across the existing dispatched suites.

## Assumptions

- **The machinery exists and is tested; only the wiring is missing.** 005 built the resume
  decision, the effect brackets, the observation resolution, and the single-writer claim, and its
  rows pass against them. This feature does not redesign any of it — it connects it to the path a
  dispatch actually takes, which is why the scope is one integration rather than a subsystem.
- **The recovery sweep already runs.** A supervisory loop sweeps on dependency recovery and
  re-dispatches suspended runs, carrying position and identity faithfully. The gap is entirely at
  the receiving end.
- **Three orphaned pieces are consumed rather than built.** The tool-to-product mapping for
  suspensions, the tool observers, and the resume refusal handling all exist and are reachable
  from nothing today. Their existence is why this is a wiring change; their being orphaned is
  evidence the wiring was the missing part.
- **This is not a live defect today, and the feature must not be justified as one.** Fixture
  tools are repeatable, re-recording an effect bracket is a no-op, and dispatched tool invocation
  is opt-in and used today only by a conformance row. Redoing steps currently costs nothing
  observable, which is exactly why five features did not notice. What changed is that 013
  introduced non-repeatable tools whose observers exist for this purpose.
- **The failure being repaired is a claim, not a crash.** 005's rows are not stubs — they assert
  real behaviour of a real function. Their scope is narrower than the contract's wording, and
  that is the defect. A feature that fixed the wiring and left the record unscoped would fix half
  of it.
- **Grant expiry stops rather than parks.** 005's original wording said park; ADR-0049 inverted
  it. This feature implements the amended rule, and the older text is superseded rather than
  reconciled.
- **Disruption is producible on demand in the test environment.** Asserting these properties
  through a dispatch requires interrupting a running allocation deliberately, which the substrate
  permits.

## Out of Scope

- **Shipping the audit trail off-host** (ADR-0055). Accepted and unbuilt; unrelated to this
  wiring.
- **Portal answering.** Unblocked by 013 and its own feature.
- **Report fidelity** (ADR-0018) and the **deviation register** (ADR-0023), both still owed.
- **Widening availability gating beyond one transport.** Inherited from 009 and recorded as owed;
  this feature does not change which transports consult dependency health.
- **Redesigning any durability guarantee.** The seam, the decision outcomes, the bracket shape,
  and the single-writer claim are all as 005 built them.
