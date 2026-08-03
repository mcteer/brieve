# Feature Specification: A real model drives a governed run

**Feature Branch**: `spec/031-real-model-runs`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "A real model drives a governed run — the founding promise, demonstrated, and the operator-visibility decision folded in."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R2/R3** (per-task authority — the first live exercise of the run path's brokered credential under an allocation's own attested identity). **R10** (the trail proves what the model chose and what governance did about it). |
| **ADRs touched** | **ADR-0022 / ADR-0039** — a `plan` cell must be **earned**, and 030 (ADR-0059) decided that evidence must match what a cell claims; this feature is the first to qualify a plan cell under that discipline. **ADR-0058** (the credential posture, consumed — its run half finally exercised). **ADR-0049** (a run that cannot proceed stops terminally). **ADR-0059** — its span changes if operator visibility changes, one deliberate step. **Possible amendment**: none expected; the trail vocabulary is consumed, not grown. |
| **Evidence class** | **Attestation-relevant.** This is the platform's central claim — a model chooses, governance intercepts, the trail proves both — demonstrated with a real model for the first time. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A dispatched run consults a real model, governed (Priority: P1)

An agent run is dispatched whose definition binds a real model. The allocation brokers the vendor
credential under its own identity, the model chooses each step's tool, every choice passes the
same governed entry a scripted one would, and the run completes with a trail that proves all of it.

**Why this priority**: it is the founding promise, and it has never happened. 020 built the
chooser and the interception; 027 wired the credential; every run to date has replayed a fixture.
The platform's story is *governed agent runs* — and the asking half is proven while the running
half is asserted.

**Independent Test**: dispatch a run bound to a real model; the trail shows `TOOL_CHOSEN` naming
that model, the credential reference under the allocation's identity, and every invocation through
the governed entry.

**Acceptance Scenarios**:

1. **Given** a definition binding a qualified real-model cell, **When** a run is dispatched,
   **Then** the allocation obtains the vendor credential under its own attested identity — the
   first live exercise of the run path's broker — and the model names each step's tool.
2. **Given** the same run, **When** the model names a tool outside the definition's ceiling,
   **Then** the choice is refused by the existing enforcement, the refusal is recorded, and the
   run proceeds or stops by the platform's existing rules — never by the model's insistence.
3. **Given** the credential is absent, **When** the run starts, **Then** it stops terminally with
   the cause recorded (never parks, never falls back to a fixture, never reads an ambient key).

---

### User Story 2 - The plan cell is earned, not written (Priority: P1)

The real model's `plan` cell enters the matrix through eval-gated promotion, with evidence that
matches what the cell claims — 030's discipline, applied to its first new cell.

**Why this priority**: it shares P1 because without it US1 is constitutionally impossible —
Principle VIII permits model use only through a qualified cell, and hand-writing one is the exact
thing the matrix exists to prevent. **Measured**: the live lane earns evidence under the `ask`
subject role only; the tool-choice suites (`must_deny`, `must_decline`) are precisely the
plan-shaped ones, and whether their evidence can carry a plan cell or the lane must score a plan
subject explicitly is this story's question to answer honestly.

**Independent Test**: the matrix holds a `qualified_by = "live"` plan cell whose evidence
provably exercised tool-choice behaviour under a plan-shaped subject.

**Acceptance Scenarios**:

1. **Given** the live lane, **When** it runs, **Then** it produces plan-role evidence — a real
   model choosing/refusing tools under the same constraints a dispatched run imposes.
2. **Given** that evidence, **When** the cell is promoted, **Then** what the cell claims matches
   what was scored — no evidence gathered under one role quietly carrying a cell for another.

---

### User Story 3 - The gates never meet the live cell (Priority: P1)

Every blocking lane and the full conformance gate keep running with no vendor credential and no
live cell reachable by any dispatched row — while the demonstration uses one.

**Why this priority**: it shares P1 because it is the constraint that makes US1 safe to ship. The
merge gate deliberately forbids a live cell in any role a dispatched run resolves; a demonstration
that weakened that gate would trade the platform's proof for a demo.

**Independent Test**: `make conformance` passes on an enclave whose seeded matrix holds no live
plan cell; the demonstration runs with one; the gate still passes afterwards.

**Acceptance Scenarios**:

1. **Given** the seeded dev estate, **When** any conformance lane runs, **Then** no dispatched row
   can resolve a live cell — asserted by the existing gate, unchanged in what it forbids.
2. **Given** the demonstration's live cell and binding, **When** the demonstration ends, **Then**
   the estate is back in its seeded state and the gate proves it.

---

### User Story 4 - The person who ran it can ask about it (Priority: P2)

The operator who dispatched the run can ask the platform *"which runs were denied?"* and see the
refusal the model's over-reach produced — because operator visibility of authority records is
decided here, deliberately.

**Why this priority**: it closes the loop the demonstration opens. A run whose refusals the
demonstrating operator cannot ask about is a half-proof: the model chose, governance refused, and
the person who caused it must go find a compliance analyst to see it. 029 recorded this decision
as owed; 030 built the machinery that makes changing it one deliberate step (visibility, the
estate suites' declared roles, and ADR-0059's span move together, pinned by a row).

**Independent Test**: after the demonstration, the operator asks about denials through the portal
and the answer cites the refusal record.

**Acceptance Scenarios**:

1. **Given** the visibility decision, **When** it is made, **Then** `ROLE_VISIBILITY`, the estate
   suites' declared roles and ADR-0059's recorded span change together — or all stay, together.
2. **Given** an operator granted denial visibility, **When** they ask *"which runs were denied?"*,
   **Then** the answer rests on the denial records their run produced.

---

### Edge Cases

- **The model chooses nothing.** `NONE` is a terminal answer today; a real model saying it must
  end the run by the existing rules, not retry forever against a paid API.
- **The model answers garbage.** A malformed choice is a provider fault, not a tool call; it must
  not be coerced into one.
- **The vendor is slow or down mid-run.** `ChooserUnavailable` stops the run terminally with the
  reason — never a silent fixture fallback, which would be 020's own defect restored at the worst
  moment.
- **Cost.** A real-model run bills per step; the demonstration's shape bounds how many steps and
  how many runs, and a runaway loop against a paid API is a failure mode the fixture world never
  had.
- **The demonstration is interrupted.** Whatever seeds the live cell and binding must be
  restorable to the seeded state even if the demonstration dies halfway.
- **Teardown is forgotten.** The gate must *fail* on a leftover live plan cell — which it already
  does; the demonstration's shape must make that the safety net, not the cleanup plan.

## Requirements *(mandatory)*

### The run

- **FR-001**: A dispatched run whose definition binds a real-model cell MUST obtain the vendor
  credential under the allocation's own attested identity, per allocation, from the trust store —
  never from the environment, a jobspec, or a fixture fallback.
- **FR-002**: Every tool the model names MUST pass the same governed entry a scripted choice does,
  with the existing refusal behaviour and recording — asserted against the real model, not only
  the recorded one.
- **FR-003**: A run that cannot obtain its credential, or whose provider fails, MUST stop
  terminally with the cause recorded. No parking, no fixture fallback, no retry loop against a
  paid vendor beyond the platform's existing bounds.
- **FR-004**: The trail of a real-model run MUST be distinguishable as one: the model the choice
  came from is already recorded (`TOOL_CHOSEN`), and the existing vocabulary MUST suffice — a
  payload addition is sealed core and this feature avoids needing one.

### The cell

- **FR-005**: The plan cell MUST be earned through the eval lane, never hand-written. **The live
  lane scores a plan-shaped subject explicitly**: the real model choosing tools against a ceiling,
  refusing over-reach, declining out-of-scope — `must_deny`/`must_decline` under a plan subject,
  new evidence gathered for exactly what the cell claims. Reusing the existing ask-role evidence
  was rejected as precisely the evidence-role mismatch 030 spent a feature ending; the cost of
  honesty is ~10 minutes of vendor time per lane run.
- **FR-006**: The qualification evidence and the cell's claim MUST agree on the role; `ask`-role
  evidence MUST NOT quietly carry a `plan` cell.

### The gates

- **FR-007**: Every blocking lane and `make conformance` MUST keep passing with no vendor
  credential and no live cell reachable by any dispatched row. The merge gate's prohibition is
  unchanged in what it forbids.
- **FR-008**: The demonstration is **seed, run, tear down, prove**: the live plan cell and the
  demonstration binding are written out of band (the same posture as the credential — never in
  the seeded Terraform variables, never in state), the bounded runs are dispatched, the seeded
  matrix is restored, and **the merge gate is then run as the proof of restoration**. The
  existing gate is the safety net, unchanged in what it forbids: a leftover live cell fails it.
  A standing demonstration definition with a gate exclusion list was rejected — exclusions on the
  platform's most safety-critical gate grow, and a permanent live cell in the estate is the state
  the gate exists to prevent.
- **FR-009**: The demonstration MUST be bounded in cost: a fixed small number of runs and steps,
  stated before it runs.

### The visibility decision (folded in)

- **FR-010**: **Decided: `operator` gains `AUTHORITY_DENIED` and `AUTHORITY_REFUSED` — and only
  those.** What happened to *your* runs becomes askable by the person who ran them;
  `AUTHORITY_ISSUED`, `AUTHORITY_EXPIRED` and the grant/change records stay analyst-only, because
  who-holds-what-authority is a different sensitivity than what-was-refused. Full visibility was
  rejected for flattening the role split; keeping the status quo was rejected because it leaves
  the demonstration's refusal invisible to whoever caused it — the half-proof this story exists
  to close.
- **FR-011**: Whatever is decided, `ROLE_VISIBILITY`, the estate suites' declared roles and
  ADR-0059's recorded span MUST change together or stay together — the agreement row makes drift
  fail a test, and this feature must not detune it.

### What must not change

- **FR-012**: The credential posture (ADR-0058) is consumed unchanged; the posture check keeps
  failing any jobspec carrying a vendor key.
- **FR-013**: The chooser's interception (020) is consumed unchanged: no second entry, no
  model-side execution.
- **FR-014**: No sealed-core touch: trail vocabulary and payloads as they are.

### Key Entities

- **The plan cell**: the matrix's claim that a real model was demonstrated fit to choose tools.
  Earned in US2, used by US1, invisible to the gates in US3.
- **The demonstration**: a bounded set of real-model runs with a stated cost, a restorable estate,
  and a trail a person can read afterwards.
- **The visibility span**: which roles see authority records — one decision, three artifacts
  moving together.

## Clarifications

### Session 2026-08-03

- Q: What earns the plan cell? → A: **The live lane scores a plan subject explicitly** — new
  evidence for exactly what the cell claims. Reusing ask-role evidence is the mismatch 030 ended.
- Q: The demonstration's shape? → A: **Seed, run, tear down, prove** — out-of-band cell and
  binding, bounded runs, restore, then the merge gate as the proof of restoration. The gate stays
  the safety net; no exclusion list.
- Q: Operator visibility? → A: **Denied and refused only.** Your runs' refusals become yours to
  ask about; grants stay analyst-only. `ROLE_VISIBILITY`, the estate suites' declared roles and
  ADR-0059's span move together, pinned by the existing agreement row.

## Success Criteria *(mandatory)*

- **SC-001**: A dispatched run bound to a real model completes with every choice governed, and its
  trail names the model, the credential reference, and each verdict.
- **SC-002**: The same run's over-reach — the model naming a tool outside the ceiling — is refused
  and recorded, with the real model, not a recording.
- **SC-003**: The plan cell in the matrix is `qualified_by = "live"` with plan-role evidence.
- **SC-004**: `make conformance` passes before and after the demonstration on the seeded estate,
  and a leftover live plan cell fails it.
- **SC-005**: The run path's credential broker is exercised live under the allocation's identity —
  027's owed behavioural half, closed.
- **SC-006**: The visibility decision is made and recorded; if visibility changed, the operator
  can ask about the demonstration's denials and the answer cites them.
- **SC-007**: The demonstration's total vendor cost is bounded and stated before it runs.

## Assumptions

- **The machinery works; what is missing is the exercise.** `make evals-live` proves the model
  answers through product paths; the chooser, interception, durability and credential wiring all
  have green rows against fixtures and structure.
- **One vendor, one model** — `anthropic/claude-opus@5`, the model already qualified for `ask`.
  No new vendor, no new model identifier.
- **The credential already sits in the store** (`model-credentials/anthropic`, written 2026-08-02)
  and the `agent-run` role already carries the read grant, applied and verified.
- **Deferred and NOT in scope**: corpus refresh, submit-then-poll, per-tenant model scope,
  ADR-0035 team granularity, and `write`/`judge`/`summarize` cells.
