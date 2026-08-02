# Feature Specification: Estate-state answering — the answer is bounded by who is asking

**Feature Branch**: `spec/025-estate-state-answering`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Estate-state answering — a compliance analyst asks which workspaces violate a control, an operator asks what changed last night, and the answer is bounded by the asker's own entitlements."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — this feature's whole subject is answering from records rather than from a model's recollection, and the failure mode it must refuse is a confident estate claim nothing supports). **R10** (observability and attestation — reading the evidence plane to answer a question is itself an act the trail must carry, which 022 established and this consumes). |
| **ADRs touched** | **ADR-0035** — **the load-bearing one, and the first time its central claim becomes executable.** *"Estate-state queries are a third conversation class, differentiated by scope algebra rather than per-persona interfaces: everyone asks in the same place, and the answer is bounded by the asker's own entitlements."* Decided 2026-07-01, amended by 022, and until now **implemented by nothing**. **ADR-0039** (*ask answers, it never acts* — inherited structurally from 024, not re-argued). **ADR-0018** (grounded reporting — *"evidence with citations, never a verdict"* is the same discipline applied to an estate question). **ADR-0034** (the portal stays a thin client, so this is an API operation). **ADR-0033** (whose parity row therefore grows again). **ADR-0022 / ADR-0039** (the Qualified Model Matrix — the `ask` cell's live qualification is currently blocked on this feature's suite). **Amendment expected to ADR-0035 only if scope turns out to need a dimension the ADR does not name** — see Clarifications. |
| **Evidence class** | **Attestation-relevant, and it reads the attestation plane itself.** Every prior feature either wrote records or read them for an operator. This one turns a person's question into a read of the evidence plane and hands back what it found — so a scoping error surfaces as a **wrong answer to a real person**, which is the failure ADR-0035 predicted would be "visible rather than silent". That prediction has never been tested. |

## Clarifications

### Session 2026-08-02

- Q: What does an estate-state question actually read? → A: **The evidence plane only.** The
  existing `estate_state` cases asking *"which secrets engines are mounted?"* are reauthored as
  records-based questions. Those cases were authored in 013 for a capability that did not exist —
  they are the same authored-for-nothing material 024 was written to eliminate, so reauthoring them
  follows that finding rather than conceding to it.
- Q: What dimension bounds an estate answer? → A: **Tenant and the subject's roles.** Both already
  exist on the authenticated subject and are claim-mapped, with *empty means refuse*. No new
  vocabulary, no ADR amendment. Tenant alone would have made SC-001 vacuous — two analysts in one
  tenant would receive identical answers, which is not the property ADR-0035 describes.
- Q: How does an estate question reach the platform? → A: **The existing `ask`, routed by the
  platform.** A person asks in one place and the platform decides what the question needs. This
  makes routing a component of the feature rather than a detail, so it is specified and scored
  rather than assumed.
- Q: How does the harness decide which source a question needs? → A: **Deterministically, and the
  decision is recorded.** No model routes. Scorable in the blocking lane with no credential, which
  FR-011a requires, and a misroute is a bug with a failing test rather than a judgement call.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A compliance analyst asks which part of the estate violates a control (Priority: P1)

An analyst asks, in the same place everyone else asks, which workspaces breach a control they are
responsible for. They get back **what the records show, with references they can follow** — and
nothing about parts of the estate they are not entitled to see. They do not get told the estate is
"compliant"; that is their call to make, and the platform has no standing to make it.

**Why this priority**: it is the scenario ADR-0035 was written for, it is the one where a scoping
error is most damaging, and it exercises both halves of the feature — bounding and citation — in a
single request. Everything else is a narrower case of it.

**Independent Test**: two subjects with different entitlements ask the identical question and
receive different answers, each traceable to records that subject could have read directly.

**Acceptance Scenarios**:

1. **Given** a tenant whose records show violations across two scopes, and an analyst entitled to
   one of them, **When** they ask which parts of the estate violate the control, **Then** the answer
   names only the entitled scope, and every claim carries a reference that resolves to a record.
2. **Given** the same estate and an analyst entitled to both scopes, **When** they ask the identical
   question, **Then** the answer names both — proving the bounding is the subject's, not the
   question's.
3. **Given** a control the records fully satisfy, **When** an analyst asks, **Then** the answer says
   the records show no violations **and does not declare the estate compliant**.
4. **Given** a question phrased as an instruction ("fix the workspaces that violate this control"),
   **When** it is asked, **Then** it is answered or declined and **nothing in the estate changes**.

---

### User Story 2 - An operator asks what changed last night (Priority: P2)

An operator asks what happened in a window of time. They get an account assembled from records,
each claim pointing at the record behind it, bounded the same way — an operator sees operator scope.

**Why this priority**: it is the second persona ADR-0035 names, and it is the one that proves the
answer is assembled from the trail rather than from a model's memory of it. It is lower than US1
only because it does not exercise the differential-entitlement property that makes US1 the sharper
test.

**Independent Test**: ask about a window whose records are known, and check the answer against them
— including that a record outside the window is absent.

**Acceptance Scenarios**:

1. **Given** records inside and outside a window, **When** an operator asks what changed in that
   window, **Then** only what falls inside it is described.
2. **Given** a window with no records the asker may see, **When** they ask, **Then** the platform
   says so plainly, and the answer is **indistinguishable from the same question asked about a
   window that is genuinely empty** — see Edge Cases for why that is deliberate.

---

### User Story 3 - A maintainer can tell whether estate answers are actually right (Priority: P3)

`estate_state` stops scoring authored recordings and starts scoring what the product produced, the
way `citation_accuracy` and `must_decline` did in 024. Correctness here is a **fixture question** —
does the query return the right set? — so it is checkable without a model deciding whether an answer
reads well.

**Why this priority**: it does not deliver a user-visible capability, which is why it is P3 rather
than P1. It is nonetheless the reason this feature exists on the schedule now: `estate_state` is the
**last prompt-scoring suite still scoring material nothing produced**, named as this feature's
obligation in 024's conformance contract, and a gate in that state asserts nothing.

**Independent Test**: a deliberately wrong estate answer fails the suite. Before this feature, it
could not — the suite replayed a string.

**Acceptance Scenarios**:

1. **Given** the suite, **When** it runs in the blocking lane, **Then** it scores output the product
   produced and needs **no vendor credential**.
2. **Given** an answer that names a scope the fixture estate does not contain, **When** the suite
   runs, **Then** it fails.
3. **Given** an answer that omits a violation the fixture estate does contain, **When** the suite
   runs, **Then** it fails — because recall and precision are different failures and a suite that
   caught only one would pass a platform that under-reports.

---

### Edge Cases

- **The asker is entitled to nothing in the question's scope.** The answer must not distinguish
  "nothing happened" from "not yours" *to the caller* — 022 established that the distinction lives
  in the trail, where an investigator can see it, and never in the response, where it becomes an
  existence oracle.
- **A control that does not exist** versus **a control with no violations**. These are different
  answers to the person asking and must not collapse into one.
- **A question spanning tenants.** There is no tenant parameter to widen; the only reachable path is
  narrowing to a stream belonging to someone else, which 022 already made recordable.
- **A question the records cannot answer at all.** Declining is required, and must be
  distinguishable from a failure to reach the store — a reader sent to the wrong person by that
  confusion is the same defect 024 refused for provider failures.
- **An estate that is empty.** A new tenant with no records must produce a clean "nothing recorded"
  rather than an error or an empty success that reads as "no violations".
- **The window is enormous.** A question about all time must not become an unbounded read.
- **A question that reads as both** — *"what does the pattern say I should have done about last
  night's change?"* Routing must pick one and the decline must say which, so the asker can rephrase
  rather than conclude the platform has nothing.
- **A question that is neither.** Routing must not force a source onto a question that fits no
  source; that is a decline, not a coin flip.
- **A model that invents a workspace.** The claim must not ship, on the same principle as an
  unresolvable citation in 024: an invented estate reference reads as evidence and is worse than no
  answer.

## Requirements *(mandatory)*

### What the platform must answer

- **FR-001**: A person MUST be able to ask an estate-state question in the **same place** they ask
  every other question, and receive an answer assembled from records.
- **FR-002**: Every substantive claim in an estate answer MUST carry a **reference that resolves**
  to the record supporting it.
- **FR-003**: Where the records do not support an answer, the platform MUST **decline** and say so,
  distinguishably from a failure to reach the store.

### Bounding — 024's FR-004, carried here as promised

- **FR-004**: An estate answer MUST be bounded by **the asker's own entitlements**, through the
  governed read path rather than a parallel one. Two subjects asking the identical question MUST
  receive answers differing exactly by what each is entitled to see.
- **FR-004a**: The bounding dimension MUST NOT be accepted from the request. A caller-supplied scope
  is a request to widen, and the read path already refuses to offer one.
- **FR-004b**: Scope MUST be computed from **the subject's tenant and the subject's roles**, both of
  which the authenticated subject already carries. No new scope vocabulary is introduced.
- **FR-004c**: A subject with **no roles MUST be refused**, never given a default scope. The identity
  layer already treats an empty role set as a refusal, and an estate read is not the place to
  soften it.
- **FR-004d**: ADR-0035's **team-level** example (*"a team's developer asks about their team's
  estate"*) is **narrower than roles and is not built here**. It needs a subject attribute the
  platform does not have. Recorded as owed rather than silently satisfied by role scope, which is a
  different thing wearing a similar shape.

### Evidence, never a verdict — 024's FR-005, carried here as promised

- **FR-005**: An estate answer MUST surface **evidence with citations and never a verdict**. The
  platform MUST NOT declare any part of the estate compliant, passing, healthy, or safe.
- **FR-005a**: An answer MUST NOT carry the shape of a record the asker could not have read for
  themselves — including in counts, totals, or absences that imply what lies outside their scope.

### What the estate *is*

- **FR-006**: An estate question MUST be answered from **the evidence plane, through the governed
  read path**, and from nothing else. The answering path MUST hold no product credential and MUST
  NOT reach a product at answer time.
- **FR-006a**: The `estate_state` cases that ask about **live product configuration** MUST be
  reauthored as questions the evidence plane can answer. They were authored for a capability that
  did not exist; leaving them would keep a suite scoring questions the platform cannot answer, which
  is the defect this lineage exists to close.
- **FR-006b**: Questions about **product configuration the records do not hold** MUST be declined
  plainly rather than answered from inference. *"The records do not show this"* is a correct answer;
  a guess about a mount table is not.

### The rule that must not bend

- **FR-007**: Asking MUST NOT change anything. No effecting tool is reachable from the estate
  answering path — asserted by **exercising it**, including with instruction-shaped questions, and
  by reading what the path can reach rather than what its documentation claims.
- **FR-008**: Reading the evidence plane to answer a question MUST be recorded, as any other
  governed read is. A question a caller can ask without trace is the boundary 022 removed.

### Surfaces

- **FR-009**: Estate answering MUST be an API operation rather than portal logic, and MUST therefore
  hold **identically on every surface that implements it**.
- **FR-010**: An estate question MUST arrive through the **existing `ask` operation**. A person asks
  in one place; the platform decides what the question needs. No new operation is added, so
  ADR-0033's parity row grows by **zero**.

### Routing — a component, because it was made one

- **FR-010a**: Routing MUST be **deterministic**. No model decides which source a question needs, so
  routing is scorable in the blocking lane with no vendor credential and a misroute is reproducible.
- **FR-010b**: The routing decision MUST be **recorded** — which source was consulted, for a
  question that was asked. A route nobody can see is a decision nobody can audit.
- **FR-010c**: A decline MUST **name the source that was consulted**. Someone who asked about their
  estate must never be told *"the pinned corpus does not support an answer"* — that sends them to
  read documentation about a question they asked about their own records.
- **FR-010d**: Routing MUST be scored. Cases MUST include **estate-shaped questions that must not
  reach the corpus** and **guidance-shaped questions that must not reach the evidence plane** — the
  second because a misroute in that direction writes an evidence-access record for a question that
  had nothing to do with the estate.

### The gate

- **FR-011**: The `estate_state` suite MUST score **what the product produced**, not authored
  material. It is the last prompt-scoring suite in that state.
- **FR-011a**: The suite MUST remain runnable in the **blocking lane with no vendor credential**,
  deterministically. 024's FR-016 is not relaxed here.
- **FR-011b**: Scoring MUST fail an answer that **names something the fixture estate does not
  contain** and an answer that **omits something it does**. One-sided scoring passes a platform that
  under-reports.
- **FR-012**: The `estate_state` live failure recorded on 2026-08-01 MUST be **identified by case**,
  and its outcome recorded. The `ask` cell's Qualified Model Matrix column stays `fixture` until it
  is, and "we do not know which cases failed" is not a state this feature may leave behind.

### Key Entities

- **Estate question**: what someone asked about the state of things. Carries no scope — scope comes
  from the subject.
- **Estate answer**: claims, each with a resolvable reference, or a decline. **Never a verdict**, and
  never persisted — like a report, it has no identity between requests.
- **Scope**: what this asker may see. Derived from the authenticated subject, never from the request.
- **Estate reference**: the pointer from a claim to the record behind it — the estate analogue of
  024's citation, and subject to the same rule that an unresolvable one is worse than none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two subjects with different entitlements ask the identical estate question and receive
  answers that differ **exactly** by their entitlements — verified by comparison, not by inspection.
- **SC-002**: Every claim in an estate answer resolves to a record the asker was entitled to read.
  An unresolvable reference fails.
- **SC-003** *(024's, carried here)*: An estate answer surfaces evidence with citations and contains
  **no verdict** — no claim that any part of the estate is compliant, passing, or safe.
- **SC-004**: No effecting tool is reachable from the estate answering path, demonstrated by
  exercising it with instruction-shaped questions, not argued from structure.
- **SC-005**: `estate_state` scores product output and passes in a lane with **no vendor
  credential**. A deliberately wrong answer — one extra scope, one missing violation — fails it.
- **SC-006**: The 2026-08-01 live `estate_state` failure is named by case id, with its cause
  recorded and its outcome stated either way.
- **SC-007**: Both surfaces return the same verdict for the same estate question — answering,
  declining, and failing.
- **SC-009**: An estate-shaped question never consults the corpus, and a guidance-shaped question
  never consults the evidence plane. Verified per question, and the second direction is checked by
  the **absence of an evidence-access record** — a misroute there reads someone's records for a
  question that was not about them.
- **SC-010**: A decline names the source that was consulted, so nobody who asked about their estate
  is told the documentation does not cover it.
- **SC-011**: A subject with no roles is refused rather than given a default scope.
- **SC-008**: A caller cannot distinguish "no records" from "not yours" in the response, while an
  investigator can distinguish them in the trail.

## Assumptions

- **The answering substrate exists and is reused, not rebuilt.** 024's path holds a source and a
  provider and no tool registry; this feature inherits that shape and its never-acts property rather
  than re-establishing either.
- **The governed read path is the only way in.** ADR-0035 says so and 022 made it recordable; a
  second read path would be the parallel one both explicitly refuse.
- **Entitlement bounding is enforced by the existing authorization core**, not by a filter applied to
  results after a broad read. A post-filter is how scope errors become silent.
- **Correctness is a fixture question.** The estate under test is arranged, so "did the query return
  the right set" is decidable without a judge — which is what keeps FR-011a satisfiable.
- **Deferred and NOT in scope, recorded so the next planner finds them rather than an absence**: the
  portal's own answering surface (024's other deferral), and corpus refresh scheduling with a
  staleness signal (raised during 024 implementation, recorded in `ROADMAP.md`).
- **No new persona or role vocabulary is invented** — confirmed at clarify. Scope uses the tenant and
  roles the authenticated subject already carries. ADR-0035's **team-level** example needs an
  attribute the platform does not have and is recorded as owed (FR-004d) rather than approximated by
  role scope, which is a different thing with a similar shape.
- **Routing is part of this feature, not a detail underneath it.** Asking in one place was chosen
  deliberately, which makes "which source does this question need" a decision the platform makes on
  a person's behalf — so it is deterministic, recorded, and scored in both directions.
