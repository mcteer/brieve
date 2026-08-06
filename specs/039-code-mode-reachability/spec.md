# Feature Specification: Code mode becomes reachable

**Feature Branch**: `039-code-mode-reachability`

**Created**: 2026-08-05

**Status**: Draft

**Input**: Measured against merged main — 036 shipped code mode, ADR-0041's gate is satisfied, and no definition can enter it in the running platform.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11 (total interception)** — code mode becomes reachable without becoming a second way to reach a tool. **R7 (fail-closed)** — an environment without the capability must keep refusing with a stated reason. **R4, R13 (evidence)** — a program that runs in production leaves the same record one that runs in a test does. R12 (lean — the runtime stays a library behind an optional dependency) |
| **ADRs touched** | **ADR-0041** (code mode ships only with verified per-call hook parity — the gate is satisfied at the seam, and this feature must not weaken it while making the seam reachable), ADR-0040 (deferred disclosure — the catalog a model searches now contains a capability it can actually use), ADR-0054 (**stays Proposed** — its delegation half still has no substrate), ADR-0047 (a passing stub is worse than a missing one), ADR-0024/0026 (execution bounds, which a program consumes differently from a structured run) |
| **Evidence class** | **attestation-relevant.** A program is the recorded *cause* of the calls that follow it. Making programs reachable in production means the trail begins carrying model-written code that actually ran, rather than code that ran only in a test |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A definition can enter code mode at all (Priority: P1)

A definition whose ceiling names the program capability submits a program, and it runs. The submission is a governed decision like any other, and every call the program makes reaches execution the same way a directly-issued call would.

**Why this priority**: This is the entire gap. The seam, the ledger, the audit record and the parity assertions all exist; nothing makes them reachable. Until this works, the platform has a capability it cannot offer.

**Independent Test**: Give a definition the program capability, submit a program, and confirm it executed — through the same path any capability is reached by, not by calling the implementation directly.

**Acceptance Scenarios**:

1. **Given** a definition whose ceiling names the program capability, **When** it submits a program, **Then** the submission is a governed decision and the program runs.
2. **Given** a definition whose ceiling does **not** name it, **When** it attempts to submit, **Then** it is refused exactly as for any other capability outside a ceiling.
3. **Given** a program that ran, **When** the evidence is read, **Then** the program itself and each call it made are both recoverable.

---

### User Story 2 — Where the capability is absent, the refusal is honest (Priority: P1)

An environment that cannot run programs refuses a submission with a stated reason. It does not fail obscurely, and it does not silently succeed at something smaller.

**Why this priority**: The platform deliberately keeps this capability optional, so "absent" is a supported state rather than a broken one. A capability that is missing must **say so** — silence and an internal failure surfacing three layers down are the two outcomes ADR-0047 calls worse than an honest absence.

**Independent Test**: Remove the capability, submit a program, and confirm the refusal names what is missing rather than surfacing an internal error.

**Acceptance Scenarios**:

1. **Given** an environment that cannot run programs, **When** one is submitted, **Then** it is refused with a reason naming the absent capability.
2. **Given** that refusal, **When** the record is read, **Then** it is distinguishable from a policy denial and from a program that failed on its own terms.

---

### User Story 3 — Code mode does not become a second way to act (Priority: P1)

Everything a program does reaches execution through the same governed entry a directly-issued call uses. Making the capability reachable adds no path around it.

**Why this priority**: This is ADR-0041's whole gate, and the feature that makes code mode reachable is exactly the one that could break it. The property is currently proven against the seam in isolation; it must hold when a real definition drives it.

**Independent Test**: Drive a program through the reachable path and confirm every call it makes carries the same records a direct call would — including calls the program invents.

**Acceptance Scenarios**:

1. **Given** a program that calls a permitted capability, **When** it runs, **Then** that call is governed identically to the same call issued directly.
2. **Given** a program that calls something it may not — a denied capability, or a name that does not exist — **When** it runs, **Then** the decision is made by the same authority that decides every other call, and is recorded.
3. **Given** a program that reaches for something outside the platform entirely, **When** it runs, **Then** that attempt is a governed request and refuses like any other.

---

### User Story 4 — What a program costs is knowable before it is permitted (Priority: P1)

A program consumes the run's execution budget differently from a structured sequence of calls: the submission costs one step and each call inside costs another. Someone deciding whether to permit code mode can see what it will cost, and a program that exhausts the budget partway ends the run in a state a person can act on.

**Why this priority**: The arithmetic is recorded and has never been measured against a real budget. This is where a capability that works in a test quietly fails in production — not by breaking, but by running out of room partway and leaving a half-finished program with no clear disposition.

**Independent Test**: Run a program whose calls exceed the run's budget and confirm the outcome is recorded, distinguishable from a program that finished and from one whose calls were denied.

**Acceptance Scenarios**:

1. **Given** a program that submits and makes N calls, **When** it completes, **Then** the budget consumed is N+1 steps and the accounting is visible.
2. **Given** a program whose calls would exceed the run's budget, **When** the budget is exhausted, **Then** the **run** ends rather than the program merely being told no — because the budget bounds the run, not the call.
3. **Given** that outcome, **When** the record is read, **Then** it is distinguishable from a denial the program could have routed around.

---

### Edge Cases

- **The capability is present in one environment and absent in another.** The same definition must behave predictably in both — refusing honestly where it is missing, rather than appearing to work.
- **A program produces no calls at all.** Submitting a program that does nothing is a legitimate outcome and must be distinguishable from one that failed to start.
- **Every call a program makes is denied.** The program runs, each call is refused, and it completes having done nothing. That is not a platform failure and must not be recorded as one.
- **A definition may submit programs and call nothing else.** A coherent posture, and the refusals it produces should read as intended rather than as a misconfiguration.
- **The existing assertion that this is unreachable.** A live check asserts the capability is *not* reachable, deliberately, so its absence stays loud. This feature must **flip** that assertion rather than delete it — a check removed is a property nobody is watching.

## Requirements *(mandatory)*

### Functional Requirements

**Reaching it**

- **FR-001**: A definition MUST be able to submit a program through the same path every other capability is reached by.
- **FR-002**: Permission to use code mode MUST be decided by the definition's ceiling, exactly as for any other capability. Nothing about it may be reachable by a definition whose ceiling does not name it.
- **FR-003**: The environments where dispatched work actually runs MUST carry what code mode needs, or MUST refuse it honestly. **A capability reachable in testing and absent in production is the defect this feature exists to close, and closing half of it does not close it.**

**Staying governed**

- **FR-004**: Every call a program makes MUST reach execution through the same governed entry a directly-issued call uses. Making code mode reachable MUST NOT create a second path to acting.
- **FR-005**: A call to something the definition may not use, and a call to something that does not exist, MUST both be decided by the same authority that decides every other call — and MUST be recorded.
- **FR-006**: The program itself MUST be recoverable from the evidence as the recorded cause of the calls that followed it.

**Refusing honestly**

- **FR-007**: Where the capability is unavailable, a submission MUST be refused with a reason naming what is absent. It MUST NOT surface an internal failure, and MUST NOT partially succeed.
- **FR-008**: An unavailable-capability refusal, a policy denial, and a program that failed on its own terms MUST be distinguishable in the record. Three situations calling for three different responses must not read alike.

**Costing what it costs**

- **FR-009**: The execution budget a program consumes MUST be visible: the submission and each call it makes are each a step against the run's bounds.
- **FR-010**: A program that exhausts the run's budget MUST end the **run**, not merely receive a refusal it could route around. A bound a program can catch and continue past is not a bound.
- **FR-011**: The outcome of a budget-exhausted program MUST be distinguishable in the record from a program that completed and from one whose calls were denied.

**Not overreaching**

- **FR-012**: This feature MUST NOT decide which shipped definitions carry code mode. Whether the capability exists and who is granted it are separate questions, and only the first is in scope.
- **FR-013**: The existing assertion that code mode is unreachable MUST be **replaced by one asserting it is reachable**, never removed. A property that stops being watched is a property that stops holding.

### Key Entities

- **Program** — model-written code submitted as a single governed act. The recorded cause of everything that follows it.
- **Program submission** — the governed decision to run one. One step against the run's budget.
- **Inner call** — a request the program makes. Indistinguishable, once it reaches the governed entry, from a call issued directly.
- **Capability availability** — whether an environment can run programs at all. A supported state either way, and a fact the record must carry.
- **Execution budget** — what bounds a run. A program consumes it at a rate whoever permits code mode should be able to predict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A definition permitted to use code mode can submit a program and have it run **in the environment where dispatched work actually happens** — not only where tests run.
- **SC-002**: **100% of the calls a program makes are governed decisions** carrying the same records a direct call produces. No unaccounted calls, since one is the gap the governance model is claimed not to have.
- **SC-003**: A definition not permitted to use code mode **cannot submit a program**, demonstrated by attempting it.
- **SC-004**: An environment without the capability **refuses with a stated reason**, distinguishable from a policy denial and from a program failure.
- **SC-005**: A program's budget consumption is predictable from the number of calls it makes — demonstrated by measuring it rather than by asserting the arithmetic.
- **SC-006**: A program that exhausts the budget **ends the run**, and the outcome is distinguishable from completion and from denial.
- **SC-007**: The check asserting code mode is unreachable **has been replaced by one asserting it is reachable** — not deleted, and not left asserting something now false.

## Assumptions

- **The governance property is already built and proven, and this feature does not rebuild it.** 036 satisfied ADR-0041's gate at the seam; what is missing is reachability. This makes an existing property true of the running platform rather than establishing a new one.
- **Optional-by-default stays.** The runtime is a library behind an optional dependency rather than an operated component, so no named-trigger record is owed. Making it present where dispatched work runs changes what every run carries, and that cost is stated rather than absorbed.
- **Who gets code mode is not decided here.** 036 deferred that deliberately as configuration design. This settles only what reachability forces: the capability exists, and a ceiling decides who reaches it.
- **The delegation boundary stays unbuilt.** ADR-0054's second half has no substrate to govern, and governing an object that cannot be invoked would be a rule nothing exercises.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Sub-agent orchestration and the per-delegation boundary.** ADR-0054's second half. Still no substrate.
- **Streaming or incremental execution.** A program runs and returns; partial results are not surfaced mid-execution.
- **Optimizing what a model is shown during discovery.** Descriptions become more load-bearing once a model can compose capabilities into programs, but tuning that is its own work.
- **Which shipped definitions enable code mode.** Explicitly out of scope per FR-012.
- **Changing how programs are written, or what language they are written in.** The runtime is replaceable behind its seam by design; replacing it is not this feature.
