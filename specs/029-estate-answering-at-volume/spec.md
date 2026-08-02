# Feature Specification: Estate answering at real volume

**Feature Branch**: `spec/029-estate-answering-at-volume`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Estate answering at real volume — three defects found by the first person to use it, all in code merged since 025 and green the whole time."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R10** (observability — an estate answer is the platform reporting on itself, and it has been reporting from the wrong evidence). **R2/R3** consumed unchanged: the tenant bound and the role-derived type narrowing decide what a caller *may* see, and nothing here moves either. |
| **ADRs touched** | **ADR-0035** — the governed read path and its access records, **consumed and not amended**: a narrowed request is still what the trail shows. **ADR-0018** (the read path holds no verdict and composes nothing) and **ADR-0039** (never-acts) — both inherited. **An amendment may be needed** if the read gains a second bound beyond `limit`; see FR-004. |
| **Evidence class** | **Attestation-relevant.** These are defects in what the platform reports about itself, and every one of them produced an answer that was honest, well-formed, and about the wrong evidence. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A question about my estate reaches my estate (Priority: P1)

Someone asks about their own activity in the words they would naturally use, and the platform reads
their records rather than declining because it did not recognise the phrasing.

**Why this priority**: it is the cheapest defect and the most damaging, because the person cannot
tell it happened. A decline that names both doors is honest when a question genuinely fits neither;
it is a **false negative** when the question was about the asker's estate and the platform simply
did not understand it — and both produce the same page.

**Measured 2026-08-02**: 4 of 12 plainly estate-shaped questions routed to `neither` and declined
without reading a single record — *"Which tools were used?"*, *"What did the planner agent do?"*,
*"Were any secrets read?"*, *"Which agents are active?"* — while *"Which runs were denied?"* and
*"What ran today?"* routed correctly.

**Independent Test**: a set of estate-shaped questions, asked as a person would phrase them, all
reach the evidence plane.

**Acceptance Scenarios**:

1. **Given** a question about the asker's own runs, tools, agents or reads, **When** it is asked,
   **Then** it is routed to the estate and the records are read.
2. **Given** a question that genuinely fits neither source, **When** it is asked, **Then** it still
   declines naming both doors — the fix must not turn every unrecognised question into an estate
   read.
3. **Given** a routing outcome, **When** the trail is read, **Then** which door was opened is
   recorded, as it is today.

---

### User Story 2 - The answer rests on the records the question is about (Priority: P1)

The evidence a question is answered from is evidence relevant to that question, rather than
whatever happened to fit in a fixed number of rows.

**Why this priority**: it is the defect that makes estate answering unusable at real volume, and it
is invisible at test volume. It shares P1 with US1 because either one alone leaves the capability
broken — a question that routes correctly and then receives the wrong thousand records declines
just as surely as one that never routed.

**Measured 2026-08-02**: *"What ran today?"* routed to the estate, obtained a credential, reached
the evidence plane, and declined. The scoped read returned **1,000 of 63,947** entries the asker was
entitled to, composed as:

| Type | Count |
| --- | --- |
| `effect_observed` | 383 |
| `pre_decision` | 302 |
| `tool_chosen` | 86 |
| `post_decision` | 74 |
| `tool_outcome` | 74 |
| **`run_start`** | **60** |
| `run_resumed` | 19 |
| `step_reobserved` | 2 |

Sixty run records buried in 940 pieces of per-step machinery, because the read bounds by **row
count** and every visible type competes for the same slots. The model declined correctly on what it
was given.

**Independent Test**: at a volume where the read truncates, a question about runs receives records
about runs.

**Acceptance Scenarios**:

1. **Given** a tenant with far more readable records than any read returns, **When** a question
   about runs is asked, **Then** the evidence it is answered from is predominantly about runs.
2. **Given** the same, **When** a question about tool use is asked, **Then** the evidence is
   predominantly about tool use.
3. **Given** any question, **When** the read happens, **Then** it never returns a record the asker
   could not already see — this changes which subset arrives, never the set.

---

### User Story 3 - A truncated read shows the present, not the distant past (Priority: P2)

When a read cannot return everything, it returns the most recent evidence rather than the oldest.

**Why this priority**: **already fixed and held for this feature** rather than shipped as an
orphan patch, because it was found while diagnosing US2 and is necessary but demonstrably not
sufficient — both windows contained run records and the ask declined anyway.

**Measured 2026-08-02**: 236,581 readable entries against a limit of 1,000. Both `EvidenceQuery`
implementations sorted ascending and took the first N — the *oldest* window — so every estate
question was answered from evidence three days stale.

**Why nothing caught it**: the two implementations were wrong **identically**, so the differential
row that exists to catch divergence passed. Agreement is evidence only when the implementations
could have disagreed.

**Independent Test**: a truncated read returns the newest window, still oldest-first, and the two
implementations are shown able to disagree before being shown to agree.

**Acceptance Scenarios**:

1. **Given** more readable records than the limit, **When** a read happens, **Then** the most
   recent are returned.
2. **Given** the same, **When** a caller reads the result, **Then** it is still oldest-first —
   selecting the newest is not the same as reversing, and only the first was the defect.
3. **Given** both implementations, **When** one is changed and the other is not, **Then** a row
   fails.

---

### Edge Cases

- **A person asks about something they may not see.** Measured: `authority_denied` is absent from
  the `operator` role's visible set and present in `compliance-analyst`'s, so *"which runs were
  denied?"* is unanswerable for an operator at any limit and in any window — the decline was
  correct and complete. **Not proposed as a change here** (see FR-009), but the person cannot
  currently tell "you may not see that" from "there is nothing to see", and those are different
  facts.
- **The read truncates and nobody is told.** A silently bounded read presents a partial answer as a
  complete one. The asker has no way to know they were shown a window.
- **A question is about a type the asker may see but which is rare.** Any bound that fills with
  common types crowds out rare ones, and the emptiness looks like "nothing happened".
- **Routing becomes too eager.** Widening the router until everything is an estate question would
  trade false negatives for reads nobody asked for, each leaving an access record.
- **Volume grows further.** Whatever bound is chosen must not have a new cliff a few multiples up.

## Requirements *(mandatory)*

### Reaching the estate

- **FR-001**: A question about the asker's own runs, tools, agents, secrets-access or evidence MUST
  reach the evidence plane, in the phrasings a person actually uses.
- **FR-002**: A question that fits neither source MUST still decline naming both doors. Widening
  the router MUST NOT be achieved by making the estate the default destination.
- **FR-003**: Which door was opened MUST remain recorded on every ask, unchanged.

### What the answer rests on

- **FR-004**: The evidence an estate question is answered from MUST be **relevant to that
  question**, bounded **per record type** rather than per read: the question determines which types
  it concerns, and the read takes the most recent N *of each* rather than N overall.

  **The defect is competition, not size.** Sixty run records lost to 940 pieces of step machinery
  is not a limit that was too small — at any row count, common types crowd out rare ones, and a
  question about the rare one is answered from the common ones. Per-type bounding removes the
  competition rather than raising the ceiling.

  **The read stays declarative.** No ranking, no scoring, no model in the read path — the question
  names types, the store returns rows. Two alternatives were rejected: *summarising* high-volume
  types would make the read path compose (ADR-0018 says it does not, and a claim resting on a
  summary cites nothing an investigator can check), and *reading twice* — a cheap survey then a
  detailed pull — would double the latency of an already two-minute path and leave the trail with
  an access record for a read nobody asked a question about.

  Accepted cost: the question-to-types mapping is a new thing to maintain, and getting it wrong is
  a false negative that looks like an honest empty answer. FR-001's rows and SC-007's named
  questions are what keep it honest.
- **FR-005**: A read MUST NOT return any record the asker could not already see. Every change here
  concerns which subset of an already-scoped read arrives; the tenant bound and the role-derived
  type narrowing are untouched and MUST be asserted as untouched.
- **FR-006**: When a read is bounded and more matching records exist, **the answer MUST say so**,
  including roughly what was left out — not only the trail.

  A person reading *"3 runs failed today"* needs to know whether that is 3 of 3 or 3 of the 200
  examined out of 1,847, because it changes what they do next. The trail already carries the
  narrowed request and lets an investigator reconstruct the window, and that is the wrong audience:
  the asker is the one about to act on it.

  Accepted cost: the response shape changes, so both surfaces that render an answer must render
  this too.
- **FR-007**: A truncated read MUST return the **most recent** matching records, and MUST return
  them oldest-first so no consumer sees a different shape.

### What must not break

- **FR-008**: Both evidence-read implementations MUST change together, and a row MUST be able to
  observe them **disagreeing** — the reason FR-007's defect survived is that they agreed while both
  were wrong, so a row asserting agreement alone is not sufficient evidence.
- **FR-009**: Role visibility MUST NOT be widened by this feature. Whether `operator` should see
  authority records is a governance question, and the related finding — that 025's eval suite
  scores `estate_state` with a question no operator can ask — is **recorded for decision, not
  resolved here**.
- **FR-010**: The governed read path, its access records and its narrowed-request disposition MUST
  remain exactly as they are. An investigator must still see what was asked for.
- **FR-011**: The read path MUST continue to hold no verdict and compose nothing, and asking MUST
  continue never to act.

### Key Entities

- **Question**: what a person asked, in their words. Its shape decides which door opens and, as of
  this feature, what the read is bounded toward.
- **Scoped read**: what the asker may see — tenant plus role-derived types. **Unchanged.**
- **Window**: the subset of the scoped read that actually arrives when everything does not fit.
  This feature is about the window and nothing above it.

## Clarifications

### Session 2026-08-02

- Q: How should the read decide which records are relevant to a question? → A: **Bound per type,
  not per read.** The question names its types; the read takes the newest N of each. The defect is
  competition rather than size — at any row count common types crowd out rare ones. Rejected:
  summarising high-volume types (the read path would compose, which ADR-0018 forbids, and a claim
  resting on a summary cites nothing checkable) and a two-pass survey-then-detail read (doubles
  latency on a two-minute path, and leaves an access record for a read that answered no question).
- Q: When a read is bounded and more records exist, how should the person find out? → A: **The
  answer says so**, with roughly what was left out. The trail already lets an *investigator*
  reconstruct the window; the *asker* is the one about to act on the answer. Costs a response-shape
  change on both rendering surfaces.

## Success Criteria *(mandatory)*

- **SC-001**: Every estate-shaped question in a representative set reaches the evidence plane;
  questions fitting neither source still decline naming both.
- **SC-002**: At a volume where the read truncates, a question about a record type is answered from
  evidence predominantly of that type — and a **rare** permitted type is not crowded out by common
  ones, which is the measurable form of the 60-in-940 finding.
- **SC-003**: A truncated read returns the most recent matching records, oldest-first.
- **SC-004**: No read returns a record outside what the asker may see — asserted, not assumed.
- **SC-005**: A person shown a partial answer can tell it was partial, and roughly how partial,
  from the answer itself.
- **SC-006**: Changing one evidence-read implementation without the other fails a row.
- **SC-007**: The questions that failed on 2026-08-02 — *"Which tools were used?"*, *"What did the
  planner agent do?"*, *"Were any secrets read?"*, *"Which agents are active?"*, *"What ran
  today?"* — all answer against a tenant carrying real volume.

## Assumptions

- **The defects are in the read and the routing, not in the model.** Every measured decline was the
  model behaving correctly on the evidence it was handed.
- **Test volume hid all three.** 025's rows exercise tens of records, where a thousand-row bound
  never truncates and every window is every record. The deployed tenant holds 236,581 readable
  entries.
- **The ordering fix already exists**, verified to fail against the old behaviour and measured
  against the live table. It is held for this feature rather than merged alone.
- **`authority_denied` outside `operator` may be correct.** It is recorded as a decision to take,
  not a defect to fix.
- **Deferred and NOT in scope**: corpus refresh scheduling, ADR-0035's team-granularity scope,
  per-tenant model scope, submit-then-poll for the portal, and promoting any further matrix cell.
