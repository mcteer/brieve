# Feature Specification: Asking binds to the Qualified Model Matrix

**Feature Branch**: `spec/026-ask-binds-to-matrix`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Bind ask to the Qualified Model Matrix — the answering path calls a model without asking whether the cell is qualified, and a contract already says it does not."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — a merged contract asserts a refusal that nothing performs, which is the exact shape this requirement exists to forbid). **R10** (observability and attestation — the trail records which model answered and cannot say whether it was allowed to). |
| **ADRs touched** | **ADR-0022 / ADR-0039** (the Qualified Model Matrix — **consumed, not amended**: `ask` is already in the closed `Role` vocabulary, and the resolution mechanism already exists). **ADR-0039** again for *ask answers, it never acts* — a matrix read must not become a way to reach a registry. **ADR-0033** (whatever refuses, refuses identically on both surfaces). **ADR-0047** (a gate row that cannot bind is absent or an explicit skip — never a passing claim, which is what 024's contract currently carries). |
| **Evidence class** | **Attestation-relevant, and it is about a governance claim being false.** Principle VIII is a MUST. Two merged features assert this refusal in their success criteria and conformance contract; measurement on 2026-08-02 found no code performing it and no test asserting it. |

## Clarifications

### Session 2026-08-02

- Q: What supplies the cell an ask must bind to? → A: **An ask binding record in the trust fabric**,
  operator-authored and read-only to the platform, alongside the ceiling and the matrix itself.
  Runs bind through agent definitions because runs *have* definitions; an ask has none, and
  inventing a synthetic one would be worse than admitting the difference. Deployment-level
  configuration was rejected for putting a governance decision in a jobspec — the split between
  operator-authored governance and deployment assembly is what Principle VIII rests on.
- Q: What happens when no `ask` cell exists — the matrix's state today? → A: **Every ask refuses.**
  Principle VIII is a MUST and "no qualified cell" means no model may be consulted. **The measured
  cost is near zero**: no deployment configures an ask provider (`served.py` sets neither
  `ask_model` nor `ask_provider`), so the operation already answers 503 wherever it is deployed.
  Only test fixtures change, and they arrange what they need.
- Q: Do the guidance and estate halves bind the same cell? → A: **Separate cells, named per
  source.** An operator can qualify a model to summarise a tenant's records without also licensing
  it to cite documentation. It also resolves the corpus-has-no-pack problem cleanly: the record
  *names* each cell rather than deriving one from a pack the corpus does not belong to.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An unqualified model is never reached (Priority: P1)

Someone asks a question. Before any provider is contacted, the platform establishes that the model
it is about to consult holds a **green cell for the `ask` role**. If it does not, the ask is
refused and the refusal is recorded — the provider is never called, so an unqualified model is not
merely unused but **unreachable**.

**Why this priority**: it is the Principle VIII obligation, it is what 024's SC-006 already
promises, and every other story is a variation on it.

**Independent Test**: point the answering path at a model with no qualified cell and observe that
the provider records zero calls.

**Acceptance Scenarios**:

1. **Given** a matrix with no cell for the answering model, **When** someone asks anything,
   **Then** the ask is refused, the refusal is recorded, and **the provider was never called** —
   verified by the provider, not by the response.
2. **Given** a matrix whose cell for that model is **withdrawn**, **When** someone asks, **Then**
   the same refusal occurs. A withdrawn cell is not a qualified one.
3. **Given** a qualified cell, **When** someone asks, **Then** the answer is produced and the
   record names the cell that authorised it.
4. **Given** the matrix cannot be read at all, **When** someone asks, **Then** the ask is refused
   **distinguishably from "no qualified cell"** — an outage and a governance decision send an
   operator to different places.

---

### User Story 2 - A substituted model is visible, never silent (Priority: P2)

When the pinned cell is unavailable and another qualified cell is used instead, the trail says so.
Nobody reading an answer later has to wonder which model produced it.

**Why this priority**: it is the second half of ADR-0022's guarantee. Runs already record this;
asks record nothing, so an ask that quietly used a different model is currently indistinguishable
from one that used the named one.

**Independent Test**: make the pinned cell's model unavailable, ask, and find the substitution in
the trail with both cells named.

**Acceptance Scenarios**:

1. **Given** a pinned cell whose model is unavailable and another qualified `ask` cell that is
   available, **When** someone asks, **Then** the answer is produced **and** a substitution record
   names the pinned cell, the used cell, and why.
2. **Given** no qualified alternative, **When** the pinned cell is unavailable, **Then** the ask
   refuses rather than falling back to something unqualified.

---

### User Story 3 - The contract stops claiming something untrue (Priority: P3)

024's conformance contract asserts *"An unqualified cell refuses before any provider call."* Either
a row makes that true, or the contract says plainly that it is owed. It may not keep asserting it.

**Why this priority**: it delivers no capability, and it is the reason this feature exists now. A
contract that asserts an unperformed refusal is worse than one that admits a gap — it stops anyone
looking.

**Independent Test**: the row exists and fails when the check is removed.

**Acceptance Scenarios**:

1. **Given** the binding check is deleted, **When** the conformance rows run, **Then** they fail.
2. **Given** the feature is complete, **When** 024's contract is read, **Then** its assertion is
   backed by a named row rather than by nothing.

---

### Edge Cases

- **The matrix has no `ask` cell at all** — today's actual state, measured. Every ask refuses
  (FR-004), and the measured operational cost is nil: no deployment configures an ask provider, so
  every deployed surface already answers 503.
- **The matrix is unreadable.** Distinct from empty (US1 scenario 4): treating an outage as "no
  qualified cells" would make every model look unqualified during an incident.
- **A cell qualified for another role.** A `plan` cell must not authorise an ask — the matrix is
  per pack × model × **role**, and roles exist precisely so one green cell does not license
  everything.
- **The routed source has no pack.** Guidance consults a corpus belonging to no pack while the
  matrix is keyed by pack — which is why the binding record **names** each cell rather than
  deriving one (FR-005).
- **A binding naming a cell the matrix does not contain.** The binding is operator-authored and the
  matrix is operator-authored; they can disagree, and the disagreement must refuse rather than
  resolve to whichever was written last.
- **An ask refused for an unqualified cell must still record that someone asked** — 022's rule that
  a boundary probeable without trace is the thing that prevents.

## Requirements *(mandatory)*

### The refusal

- **FR-001**: Before any provider is contacted, the answering path MUST establish that the model it
  would consult holds a **green, un-withdrawn cell for the `ask` role**. An unqualified model MUST
  be **unreachable**, not merely unused — ordering is the requirement, as it is for runs.
- **FR-002**: A refusal for an unqualified cell MUST be **recorded**, and MUST be distinguishable
  in the trail from a refusal because the matrix could not be read.

### What binds

- **FR-003**: The cell an ask binds to MUST come from an **ask binding record in the trust fabric**
  — operator-authored, read-only to the platform, refused loudly when absent rather than resolving
  to a default. A default binding is an ungoverned model choice, which is the same defect as an
  ungoverned tool choice one level up.
- **FR-003a**: The binding MUST NOT be supplied by deployment configuration. Where a model is
  *reachable from* is assembly; **which model is permitted** is governance, and the trust fabric is
  where this platform keeps that distinction.
- **FR-004**: Where **no qualified cell** resolves for the routed source, the ask MUST be refused —
  before any provider is contacted. There is no degraded mode that answers from an unqualified
  model.
- **FR-004a**: This refusal MUST apply even when a provider has been injected. A configured
  provider is not a qualification, and the path where one is present but unqualified is precisely
  the gap this feature closes.
- **FR-005**: The binding record MUST name a cell **per source** — one for guidance, one for
  estate. A model qualified to summarise a tenant's records is not thereby qualified to cite
  documentation, and the eval suites already score those separately.
- **FR-005a**: A source with no cell named MUST refuse for that source alone. Guidance being
  bound does not license estate answering, or the reverse.

### Substitution

- **FR-006**: Where the pinned cell is unavailable and another qualified `ask` cell is used, the
  substitution MUST be recorded naming the pinned cell, the used cell, and the reason.
- **FR-007**: Fallback MUST only ever reach **another qualified cell**. There is no path from
  unavailability to an unqualified model.

### The record

- **FR-008**: The ask record MUST carry **which cell authorised the answer** and whether it was the
  pinned one. It already carries the model; the model alone cannot say whether it was allowed.

### What must not change

- **FR-009**: The blocking eval lane MUST remain runnable with **no vendor credential** (024's
  FR-016). Whatever this adds is scorable hermetically.
- **FR-010**: The answering path MUST NOT gain the ability to act. Reading the matrix is a read of
  an authorization fact; it must not become a route to a registry or a grant (ADR-0039).
- **FR-011**: Both surfaces MUST refuse identically — same verdict, same reason (ADR-0033).

### The contract

- **FR-012**: 024's conformance contract MUST stop asserting a refusal nothing performs. Either a
  named row makes it true, or the contract records it as owed.

### Key Entities

- **Ask binding**: an operator-authored trust-fabric record naming, per source, which qualified
  cell an ask may use. Read-only to the platform; absent means refuse.
- **Qualified cell**: pack × model × role, green, un-withdrawn — **existing**, unchanged here.
- **Substitution record**: pinned cell, used cell, reason. Runs record one; asks record none today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no qualified `ask` cell, the provider records **zero calls** for any question on
  either surface. Verified at the provider, not at the response.
- **SC-002**: A withdrawn cell refuses exactly as an absent one does.
- **SC-003**: A cell qualified for a different role does not authorise an ask.
- **SC-003a**: A binding for one source does not authorise the other — guidance bound and estate
  unbound refuses estate questions while still answering guidance ones.
- **SC-003b**: No deployment value can supply a binding. Configuring a provider without a
  trust-fabric binding refuses.
- **SC-004**: An unreadable matrix refuses distinguishably from an empty one.
- **SC-005**: Every produced answer's record names the cell that authorised it.
- **SC-006**: A substitution is recorded with both cells named; no substitution reaches an
  unqualified cell.
- **SC-007**: Both surfaces refuse identically.
- **SC-008**: An ask refused for an unqualified cell still records that someone asked.
- **SC-009**: Deleting the binding check fails a named row.
- **SC-010**: The blocking lane still runs with no vendor credential.

## Assumptions

- **The resolution mechanism is reused, not rebuilt.** It already returns a present, un-withdrawn,
  role-matching cell or raises — with no third branch — and that property is what makes the
  equivalent guarantee true for runs.
- **`ask` is already a role.** The vocabulary is closed and already contains it; nothing is
  invented.
- **Refusing every ask costs nothing operationally, and that was measured** rather than assumed:
  `served.py` configures neither an ask provider nor an ask model, so every deployed surface
  already answers 503. What changes is test fixtures, which arrange their own bindings.
- **Operators author cells; evaluation earns them.** This feature qualifies no cell and does not
  change how one is earned. Whether the matrix record gains `ask` cells as part of this work is a
  deployment question, not a spec one.
- **The substitution record's existing shape assumes a run.** Asks have none — the same collision
  024 hit when its record could not reuse the run-shaped model-gate event. Resolving it is design,
  not scope.
- **Deferred and NOT in scope, recorded so the next planner finds them**: the portal's answering
  surface, corpus refresh scheduling, and ADR-0035's team-granularity scope.
