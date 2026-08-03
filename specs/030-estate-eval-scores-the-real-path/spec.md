# Feature Specification: The estate eval scores the path a person's question takes

**Feature Branch**: `spec/030-estate-eval-scores-the-real-path`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "The estate eval scores a path production does not take — and a cell earned against it is qualified for something no operator can reach."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R10** (observability — what a qualified cell *means* is a claim the platform makes about itself). |
| **ADRs touched** | **ADR-0022 / ADR-0039** — **the load-bearing pair**: a qualified cell means evaluation demonstrated this combination, and this feature is about whether that sentence is currently true for the estate role. **ADR-0035** (the governed read and its access records) — consumed, and a scoring run that starts driving it raises a question about what it writes. **ADR-0018** (the read composes nothing) — inherited. **No amendment expected**, but Principle VIII's meaning is the subject. |
| **Evidence class** | **Attestation-relevant.** A `qualified_by = "live"` cell is the platform's own claim that a model was demonstrated fit for a role. Two such cells exist, both earned 2026-08-02, and both are bound and answering real questions today. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A qualified cell means what it says (Priority: P1)

Whoever reads the Qualified Model Matrix can rely on `qualified_by = "live"` meaning the model was
demonstrated on the path a person's question actually travels, for a role the platform grants.

**Why this priority**: it is the whole feature, and it is a governance property rather than a
capability. Principle VIII permits model use only through eval-gated promotion — so a cell whose
evidence is partly unreachable weakens every claim resting on the matrix, including claims made to
somebody outside the team.

**Measured 2026-08-02**: the vault pack's fixture estate holds five records — `run_start`,
`run_stopped`, `tool_outcome`, `authority_denied`, `authority_issued`. `operator` is granted
neither authority type; `compliance-analyst` is granted both. **Three of the five `estate_state`
cases depend on the two an operator cannot see**: *"Which runs were denied?"*, *"Who was granted
write authority?"*, and *"Were any reads denied during the nightly apply?"*

**Independent Test**: every case in the estate suite is answerable by the role the suite is scored
for, and that role is one the platform grants.

**Acceptance Scenarios**:

1. **Given** the estate suite, **When** it is scored, **Then** every case rests on records the
   scored role would actually receive.
2. **Given** a case that role cannot answer, **When** the suite runs, **Then** that is a **failure
   or an explicit exclusion**, never a silent pass on records production would withhold.
3. **Given** the matrix, **When** a cell says `qualified_by = "live"`, **Then** the evidence behind
   it was gathered for a role the platform grants.

---

### User Story 2 - The eval exercises what stands between a question and its records (Priority: P1)

The suite drives the path a person's question travels, so a defect anywhere along it fails an eval
rather than waiting to be found by somebody asking.

**Why this priority**: it shares P1 because it is the reason US1's defect existed at all, and
because the same gap will hide the next one. **This is 024's finding one layer in.** That feature
exists because the live lane was qualifying an `ask` cell against a path the product does not take;
the scorer moved onto the product's answering *function* and stopped one call short of the path
itself.

**Measured**: `EstateAnsweringScorer` hands `answer_estate_question` the fixture's records
directly. So role scoping never narrows, the governed read never runs (no access record, no
narrowed request), temporal windows never resolve, and the per-type bound never applies.

**029 measured why that matters rather than merely being untidy**: what the read hands the model is
what decides whether it can answer at all — a question about runs that received sixty run records
under 940 pieces of step machinery declined correctly and uselessly. **No eval could have caught
that**, because the eval hands the model a curated five records with no read in between.

**Independent Test**: a defect introduced between a question and its records fails the estate
suite.

**Acceptance Scenarios**:

1. **Given** the estate suite, **When** it scores a case, **Then** the record selection a person's
   question would trigger has happened.
2. **Given** a deliberate defect in that selection, **When** the suite runs, **Then** it fails.
3. **Given** the blocking lane, **When** the suite runs, **Then** it needs no vendor credential and
   no enclave, exactly as today.

---

### User Story 3 - The two live cells are re-examined against the corrected evidence (Priority: P2)

The cells earned on 2026-08-02 are held to whatever this feature establishes, rather than
grandfathered because they already exist.

**Why this priority**: it delivers no mechanism, and skipping it would make the feature ceremonial.
Two `qualified_by = "live"` cells are bound and answering questions through the deployed portal
right now; if the evidence behind them was gathered for an unreachable role, that is a fact about
those cells and not only about future ones.

**Independent Test**: after the corrected suite runs, the matrix's live cells are confirmed,
re-earned, or withdrawn — and which happened is recorded.

**Acceptance Scenarios**:

1. **Given** the corrected suite, **When** it is run against the qualified model, **Then** the
   outcome decides whether the existing cells stand.
2. **Given** cells that no longer stand, **When** the matrix is read, **Then** they are withdrawn
   rather than left qualified on superseded evidence.

---

### Edge Cases

- **A case is answerable by one role and not another.** The suite scores *some* role; a case
  outside it must be excluded explicitly rather than passing on records that role would never see.
- **Scoring writes access records.** If the suite drives the governed read, every scored case
  performs a read that ADR-0035 says leaves a record. That is a property to decide about, not to
  discover — an eval run silently writing hundreds of access records into a real trail would be
  exactly the kind of surprise this platform exists to prevent.
- **The fixture estate is five records.** Nothing about five records exercises a bound, a window,
  or a competition between types — so a suite that drives the read may still not exercise what 029
  fixed.
- **Withdrawing a cell has consequences.** The ask binding names a live cell today; withdrawing it
  makes the deployed surface refuse until an operator rebinds. That is the mechanism working, and
  it must not be discovered by a person mid-question.
- **The blocking lane must stay hermetic.** Whatever the suite drives runs with no vendor
  credential and no enclave.

## Requirements *(mandatory)*

### What a qualified cell must mean

- **FR-001**: Every case in the estate suite MUST be answerable by the role the suite is scored
  for, using only records that role would receive in production.
- **FR-002**: **Each case MUST declare the role that could ask it**, and the suite MUST score each
  role against its own subset. Both `operator` and `compliance-analyst` are scored; no case is
  rewritten or discarded to fit one role.

  Chosen over scoring a single role because the platform grants both and a person holds one of
  them: qualifying only `compliance-analyst` would leave the path most users take unqualified,
  and qualifying only `operator` would rewrite three cases and leave authority-question answering
  unscored entirely. A case's role is a property of the case — *"who could ask this?"* — and
  writing it down is what makes the suite's assumption checkable instead of implicit.

- **FR-002a**: What a passing suite then means for the matrix MUST be settled deliberately, not
  inherited. The matrix's `role` is the **agent** role (`ask`, `plan`, …); the role a case declares
  is the **asker's** visibility. Whether a qualified cell records which visibility roles its
  evidence covers, or whether qualification simply requires every declared role to pass, is a
  change in what a cell *asserts* — and ADR-0022 says a qualified cell means evaluation
  demonstrated this combination. **A decision record is expected** (plan's obligation), because
  the alternative is the matrix quietly meaning something new.
- **FR-003**: A case a role cannot answer MUST be an explicit exclusion or a failure. It MUST NOT
  pass on records production would withhold.

### What the suite must exercise

- **FR-004**: The estate suite MUST apply **the scored role's visibility** to the fixture records
  before the answering function receives them — so a case is answered from what that role would
  actually be handed, and a case depending on records it cannot see fails rather than passes.

  **Deliberately not the full path.** Driving `estate_answer_for` would additionally exercise the
  governed read, the temporal window and the per-type bound — and would require the eval to hold
  an evidence store and write an access record per scored case, which is a change to what a
  scoring run *does* rather than to what it checks. Scope narrowing is the piece this feature's
  own finding is about, it needs no store, and it keeps the lane hermetic.

- **FR-004a**: What the suite still does **not** exercise MUST be recorded where the suite is read,
  not left to be rediscovered: the governed read and its access record, temporal window
  resolution, and the per-type bound (029). A five-record fixture could not exercise a bound in
  any case — stating the gap is what keeps the next person from assuming the suite covers it, and
  is the discipline whose absence produced this feature.
- **FR-005**: A deliberate defect in that selection MUST fail the suite. A suite that cannot fail
  on the thing it claims to cover is the defect this feature exists to end.
- **FR-006**: The blocking eval lane MUST remain runnable with **no vendor credential and no
  enclave**, and MUST remain deterministic.
- **FR-007**: If scoring performs governed reads, what those reads record MUST be a stated
  decision. An eval run MUST NOT write access records into a real tenant's trail as a side effect
  nobody chose.

### The cells that already exist

- **FR-008**: The two `qualified_by = "live"` cells earned 2026-08-02 MUST be re-examined against
  the corrected suite, and the outcome recorded — confirmed, re-earned, or withdrawn.
- **FR-009**: A cell that no longer stands MUST be withdrawn rather than left qualified on
  superseded evidence.
- **FR-010**: Withdrawal's consequence MUST be visible before it bites: the ask binding names a
  live cell, and an unbound surface refuses.

### What must not change

- **FR-011**: Role visibility MUST NOT be widened by this feature. Whether `operator` should see
  authority records was recorded as owed by 029 and stays owed — unless this feature's evidence
  answers it, in which case the answer is recorded as its own decision.
- **FR-012**: The governed read, its narrowing and its access records MUST behave as they do today.
  This feature changes what the *eval* exercises, not what the platform does.
- **FR-013**: Eval fixtures MUST stay data in the pack. A fixture that grew logic would be a second
  platform, scored against itself.

### Key Entities

- **Estate case**: a question, the records it should rest on, and the role that could ask it.
- **Scored role**: whose visibility the suite assumes — today implicit, and the source of the
  defect.
- **Qualified cell**: the matrix's claim that evaluation demonstrated a model for a role. The thing
  this feature is ultimately about.

## Clarifications

### Session 2026-08-02

- Q: Which role should the estate suite score, given 3 of 5 cases need records an operator cannot
  see? → A: **Both, with each case declaring the role that could ask it.** The platform grants
  both and a person holds one; scoring only `compliance-analyst` leaves the path most users take
  unqualified, and scoring only `operator` rewrites three cases and leaves authority-question
  answering unscored. Consequence accepted and recorded as FR-002a: what a passing suite then means
  for a matrix cell is a deliberate decision, and a decision record is expected — the matrix's
  `role` is the agent role, and the asker's visibility is a different axis.
- Q: How far down the real path should the suite drive? → A: **Scope narrowing only.** It is the
  piece this feature's finding is about, it needs no evidence store, and it keeps the blocking lane
  hermetic. Driving the full `estate_answer_for` would change what a scoring run *does* — an access
  record per scored case — rather than only what it checks. What stays unexercised (the governed
  read, the window, the per-type bound) is recorded at the suite rather than left implicit, since
  an unstated gap of exactly this kind is what produced this feature.

## Success Criteria *(mandatory)*

- **SC-001**: Every estate case is answerable by the scored role from records production would hand
  it.
- **SC-002**: The scored role is one the platform grants, and is stated in the suite.
- **SC-003**: A deliberate defect in **role narrowing** fails the estate suite — a case whose
  records the scored role cannot see does not pass.
- **SC-004**: The blocking lane still runs with no vendor credential, no enclave, and the same
  determinism.
- **SC-005**: The two existing live cells are confirmed, re-earned, or withdrawn — and which is
  recorded where the matrix is read.
- **SC-006**: What a scoring run records is a stated decision rather than a discovered behaviour —
  and with scope narrowing alone it records nothing new, which is itself the stated answer.
- **SC-006a**: What the suite does not cover is written where the suite is read.
- **SC-007**: No role's visibility is wider after this feature than before it.

## Assumptions

- **The defect is in what the eval exercises, not in the platform.** Production narrows by role,
  reads through the governed path, resolves windows and bounds per type. The eval skips all four.
- **The fixture estate is small on purpose** and stays that way unless a requirement needs
  otherwise; growing it is not a goal, and five records cannot exercise a bound.
- **Two live cells are in force and bound.** `anthropic/claude-opus@5` for the `ask` role, vault
  and terraform packs, earned 2026-08-02, currently answering through the deployed portal.
- **029's per-type bound and newest-window fix are merged**, so the path this suite would drive is
  the corrected one.
- **Deferred and NOT in scope**: corpus refresh scheduling, ADR-0035's team-granularity scope,
  per-tenant model scope, submit-then-poll for the portal, and the run path binding a real model.
