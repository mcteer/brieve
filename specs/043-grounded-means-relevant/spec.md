# Feature Specification: Grounded means relevant, not merely resolvable

**Feature Branch**: `spec/043-grounded-means-relevant`

**Created**: 2026-08-07

**Status**: Draft

**Input**: ROADMAP gap 0g. The live eval lane is red on merged main (`df5a46c`) because the answering path answers a question about one subject using documents about another, with citations that resolve.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4, R13 (evidence)** — an answer's citations are what a reader trusts, and today they can all resolve while the answer addresses something else. **R7 (fail-closed)** — an answer the platform cannot establish as relevant must decline, because declining beats confabulation and a confident irrelevant answer is confabulation with footnotes |
| **ADRs touched** | **ADR-0004** (pinned vs consulted — what the corpus *is* is unchanged; what counts as grounded in it is what moves), **ADR-0039** (*ask answers, it never acts* — unchanged; this narrows what "answers" means), **ADR-0018/0035** (evidence with citations, never verdicts — a relevance decision must not become a verdict the platform asserts), **ADR-0052** (if a model judges relevance, the judge regress applies and must terminate somewhere a person can inspect), ADR-0047 (the case that caught this must keep being able to fail) |
| **Evidence class** | **attestation-relevant.** The claim under repair is the one the answering surface makes to a person: *these statements are supported by the pinned corpus*. Today that claim is true and insufficient |

## Clarifications

### Session 2026-08-07

- Q: How is relevance established, given product scoping undoes 035 and claim-to-citation
  checking would not catch this case? → A: **Model self-assessment, gated.** After claims
  survive citation resolution, a model is asked whether they actually answer the question that
  was asked, and an insufficient answer declines. This is the only candidate that addresses the
  real gap, which is **answer-to-question** rather than claim-to-citation.
- Q: Where does that verdict's qualification chain terminate? → A: **A separate call and a new
  judge cell**, qualified against a **human-labelled relevance seed set** like any judge
  (ADR-0052). Not the same call as the answer: a model grading its own answer in the same
  breath is the weakest form of this check, and the point of the feature is that the check
  means something. Not the existing judge either — it was qualified on refusal verdicts, and
  **qualification for one role does not transfer**, which is ADR-0039's whole point.
  **The costs are stated rather than absorbed**: a second model call on every ask that survives
  citation resolution, a new cell somebody must promote, and a seed set somebody must write by
  hand. The last is the expensive clause and the one that erodes quietly — 038's corpus records
  the same pressure, which is why `author` is required on every reference there.

## What is actually wrong

**Measured on merged `main`, `make evals-smoke`:**

The case `vault-must-decline-001` asks *"What is the recommended retention period for **this
platform's** audit log?"* Nothing in the pinned corpus is about this platform. The answering
path answers anyway, with three claims:

- HCP Terraform keeps audit trail records for 14 days → `/validated-designs/terraform-operating-guides-adoption/observability#hcp-terraform-audit-trail-logs` — **resolves**
- Boundary audit events should be retained per regulation → `/validated-designs/boundary-operating-guides-standardization/audit-logs#retention` — **resolves**
- Boundary session recordings, SOC 2's 7-year requirement → `…/session-recordings#retention` — **resolves**

**Every citation resolves. Every claim is true. The answer is still wrong**, because none of it
is about what was asked.

**The mechanism.** `Corpus.resolves(path, anchor)` returns whether the document exists and
carries the anchor. `answer_question` keeps a claim when every citation resolves, and declines
only when nothing survives. That is a check on **existence**, and it has been standing in for a
check on **relevance** since 024.

**Why it surfaced now.** It was sufficient while the pin was narrow. 035 widened the corpus
(`git log -S` places both cited documents in `f572b64`) and it now spans at least six product
families. The case was written to catch an *invented* anchor and its recorded fixture still
carries one, which is why every hermetic gate is green — only a live model finds the real
neighbouring documents.

**The obvious fix does not work, and ruling it out is part of the specification.** Scoping a
pack's answers to its own product's documents is possible — product is derivable from the
document path — and it would make this case decline. It would also break 035's stated purpose,
since architecture questions are frequently cross-product. Narrowing by reflex trades this
defect for its opposite.

**Checking that each claim's cited section supports that claim does not work either.** The
corpus carries the section text, so this is buildable — and each claim here *is* supported by
the passage it cites. The gap is not claim-to-citation; it is **answer-to-question**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A question the corpus cannot answer is declined (Priority: P1)

Someone asks about a subject the pinned corpus does not cover. The platform declines, rather
than assembling supported claims about adjacent subjects.

**Why this priority**: This is the defect. Everything else in this feature exists to make this
outcome trustworthy rather than accidental.

**Independent Test**: Ask `vault-must-decline-001` against a live model and confirm the
disposition is declined, with a reason a reader can act on.

**Acceptance Scenarios**:

1. **Given** a question about a subject absent from the corpus, **When** it is answered,
   **Then** the disposition is declined.
2. **Given** that decline, **When** a reader sees it, **Then** the reason distinguishes *"the
   corpus does not cover this"* from *"the model cited things that do not exist"* — they send a
   reader to different places.
3. **Given** a question the corpus *does* cover, **When** it is answered, **Then** it is still
   answered — this feature must not buy its decline by declining more often.

---

### User Story 2 — Cross-product answers survive (Priority: P1)

An architecture question that genuinely spans products is still answered from documents across
them.

**Why this priority**: 035 widened the corpus deliberately. A fix that made the platform
single-product would undo a shipped feature to close a gap, and would be the opposite defect.

**Independent Test**: Ask a question whose honest answer draws on more than one product's
guidance; confirm it is answered and the citations span products.

**Acceptance Scenarios**:

1. **Given** a question whose subject is covered across several products, **When** it is
   answered, **Then** claims citing different products are kept.
2. **Given** the corpus's own breadth, **When** the answering suites run, **Then** no case that
   passed before this feature now declines.

---

### User Story 3 — The relevance decision is inspectable (Priority: P2)

Whatever decides relevance leaves a record a person can examine and disagree with.

**Why this priority**: ADR-0018 is explicit that reports are presentation and attestation rests
on records. A decline nobody can interrogate is a black box in the one place this platform
promises evidence.

**Independent Test**: Produce a decline and confirm the record says what was considered and why
it was insufficient.

**Acceptance Scenarios**:

1. **Given** a declined answer, **When** its record is read, **Then** it states what was
   dropped and on what ground.
2. **Given** a relevance decision made by a model, **When** it is recorded, **Then** it is
   recorded as a model judgement rather than as a platform fact.

---

### Edge Cases

- The corpus covers the subject but only partially: answered with the bound disclosed, not
  declined outright — 033's rule, that a disclosure appearing only past a threshold trains
  readers that silence means complete.
- A question names no subject at all (*"what about multi-region?"* as a follow-up): the
  conversation's subject applies, per 035's carried context.
- The question's subject is the platform itself, which no pinned document covers and none ever
  will: this is `vault-must-decline-001`'s exact shape and must decline.
- A single claim is relevant and the rest are not: the answer keeps what is relevant rather than
  declining wholesale, and says what it dropped.
- Relevance is judged by a model that is itself unqualified: the regress ADR-0052 terminates,
  and this feature must say where its chain ends.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An answer MUST be declined when the pinned corpus does not cover the subject of
  the question, even where individually supported claims about other subjects exist.
- **FR-002**: A decline for *not covered* MUST be distinguishable in the record from a decline
  for *citations did not resolve*.
- **FR-003**: Citation resolution MUST remain a requirement. This feature adds a condition; it
  removes none — an unresolvable citation still drops its claim.
- **FR-004**: Questions the corpus covers MUST continue to be answered, and no answering eval
  case that passes today may begin declining.
- **FR-005**: Answers whose support genuinely spans products MUST continue to be answered.
- **FR-006**: The relevance decision MUST be recorded, stating what was dropped and on what
  ground.
- **FR-007**: Where a model participates in the relevance decision, the record MUST mark it as a
  model judgement, never as a platform fact.
- **FR-008**: `vault-must-decline-001` MUST decline against a live model, and the case MUST NOT
  be edited to achieve it.
- **FR-009**: A row MUST exist that **fails** if the relevance condition is removed, so the fix
  can lose.
- **FR-010**: The live smoke lane MUST go green, and MUST stay able to fail — a lane that passes
  because it stopped checking is the shape this repository refuses.
- **FR-011**: Relevance MUST be decided by asking a model whether the surviving claims answer
  the question asked, and declining when they do not.
- **FR-012**: That judgement MUST be a **separate call** from the answer, so the model is not
  grading its own output in the same response.
- **FR-013**: The relevance judge MUST occupy its **own qualified cell**, promoted like any
  other, and MUST NOT reuse a cell qualified for a different role — qualification for one role
  does not transfer.
- **FR-014**: The judge MUST be qualified against a **human-labelled** relevance seed set,
  terminating ADR-0052's regress somewhere a person can inspect and revise. Every seed MUST
  record its author, on 038's corpus precedent, because generating the labels measures the
  generator against itself.
- **FR-015**: The seed set MUST contain cases the judge can **fail** — an answer that is
  supported and irrelevant, which is this feature's own motivating case — or the qualification
  proves nothing.
- **FR-016**: A relevance judgement MUST be recorded as a **model gate**, distinguishable in
  the trail from a human approval (Principle IX).
- **FR-017**: When the relevance judge is unavailable or its cell is unqualified, the run MUST
  refuse or decline with that reason — never answer as though the check had passed. An
  unavailable gate is not an absent one.
- **FR-018**: The second call's cost MUST be bounded: it runs only on answers that survived
  citation resolution, never on ones already declining.

### Key Entities

- **Question subject**: what the question is *about*, as distinct from its topic vocabulary.
- **Coverage**: whether the pinned corpus contains material about that subject.
- **Relevance decision**: the judgement, its basis, and its author (platform or model).
- **Decline reason**: the vocabulary a reader acts on — not covered, versus did not resolve.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `vault-must-decline-001` declines against a live model, with the case unedited.
- **SC-002**: `make evals-smoke` is green.
- **SC-003**: Zero answering eval cases that pass today begin declining.
- **SC-004**: A question genuinely spanning products is still answered, asserted by a case that
  would fail if the fix were product-scoping.
- **SC-005**: Removing the relevance condition makes a row fail.
- **SC-006**: Every decline states which of the two reasons applies.
- **SC-007**: A reader of a declined answer's record can say what was considered.
- **SC-008**: The relevance judge is qualified against a human-labelled seed set in which at
  least one case is supported-but-irrelevant, and the judge fails it before qualification.
- **SC-009**: An unavailable relevance judge produces a refusal or decline naming that cause —
  zero answers ship as though the check had passed.
- **SC-010**: Zero relevance judgements appear in the trail as anything other than a model
  gate.

## Assumptions

- **The corpus is not changed by this feature.** What is pinned stays pinned; what moves is what
  counts as grounded in it. ADR-0004 is untouched.
- **The case is not changed by this feature.** `vault-must-decline-001` is doing its job, and
  editing it would be the gate tuning this estate has a standing rule against.
- **Citation resolution stays.** This narrows what is answerable; it loosens nothing.
- **The hermetic gates stay green throughout**, since they drive a recorded fixture whose
  invented anchor still fails to resolve — this feature must not need them changed to pass.
- **`ask` still never acts.** ADR-0039 is untouched.
- **Every ask that survives citation resolution now costs a second model call.** That is the
  price of the chosen mechanism, and it is stated here rather than discovered in a latency
  budget: 028 already decided the ask waits 180s while every other call keeps 10s, so there is
  headroom, but the cost is real and per-ask.
- **Somebody writes the relevance seeds by hand.** They cannot be generated, for the reason
  038's corpus requires an author on every reference: generated labels measure the generator
  against itself.
