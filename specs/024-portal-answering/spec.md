# Feature Specification: A question gets an answer, and the answer never acts

**Feature Branch**: `spec/024-portal-answering`

**Created**: 2026-08-01

**Status**: Draft

**Input**: The portal has threads, a client, and a deployment. It has no way to answer anything.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — an answer that cites nothing is the failure mode this whole platform is built against). **R10** (observability and attestation — a model verdict must be distinguishable in the trail from a human approval). |
| **ADRs touched** | **ADR-0039** (**the rule this feature will be tempted to bend, decided before it was built**: *ask answers, it never acts*). **ADR-0035** (estate-state queries as a third conversation class, bounded by the asker's own entitlements through the governed read path — extended by 022 and consumed here). **ADR-0034** (the portal is a thin client, so answering is an API operation rather than portal logic). **ADR-0033** (which makes it a parity row across surfaces). **ADR-0022 / ADR-0039** (the Qualified Model Matrix: an `ask` binding is inexpressible without a green cell). **ADR-0018** (grounded reporting — the same discipline, applied to an answer instead of a report). **None amended, expected.** |
| **Evidence class** | **Attestation-relevant.** An answer is cited in decisions. It is also the platform's **first product path that calls a model provider** — every prior model call has been an eval harness asking directly. |

## What already holds, and what does not

**Holds, and more than expected.** Measured on 2026-08-01:

- **The gates already exist.** `packs/terraform/evals/` and `packs/vault/evals/` each carry
  `estate_state`, `citation_accuracy`, `must_decline`, and `must_deny` — five cases apiece at a
  floor that refuses a suite below it. 013 built the machinery; `OWED` is empty.
- **`ask` is already a role.** `Role = Literal["ask", "plan", "write", "judge", "summarize"]`. The
  binding is expressible; nothing needs inventing.
- **A model can already be reached.** 020 put one in the run loop with its choice governed, and
  authored the first Qualified Model Matrix record this repository has ever had.
- **Reads are recordable.** 022 made every read of a run or thread leave a trail entry.

**Does not hold, and the shape of the gap is the important part.**

**There is no path from a person's question to an answer.** The portal can start runs and hold
threads. It cannot answer.

**And the gates that would govern answering are green over material nothing produced.** The
blocking lane replays a `recorded` string per case — described in the suite as *"what a
previously-observed run of this case produced"*. **No answering path exists, so no such run has
ever happened**; the recordings were authored. `evals-live` can ask a real model, and does so to
qualify a matrix cell — but it asks the model directly, not through any product path.

So the honest statement is: **four eval suites are in force over an answering capability that does
not exist.** This is the sixth instance of the shape ROADMAP gap 0d names, and the one where the
gate looks most convincing — the suites are real, the floors are enforced, and the cases are good.
They simply score something a person can never obtain.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Someone asks how something works and gets a cited answer (Priority: P1)

A person asks a question about the guidance corpus and receives an answer whose every claim
carries a visible citation. When the corpus does not support an answer, they are told so.

**Why this priority**: It is the smaller of the two classes and the one whose gates are most
developed. It also establishes the answering path the other class reuses.

**Independent Test**: Ask a question the corpus answers; check every claim is cited. Ask one it
does not; check the answer declines.

**Acceptance Scenarios**:

1. **Given** a question the corpus supports, **When** it is asked, **Then** the answer carries
   citations resolvable to a specific section, and a reader can follow them.
2. **Given** a question the corpus does not support, **When** it is asked, **Then** the platform
   **declines** rather than answering. Declining beats confabulation, and this is the row that
   makes that checkable.
3. **Given** the corpus changes, **When** the same question is asked, **Then** the citations
   reflect the current corpus. **The corpus carries no version metadata anywhere**, so change
   detection is content-based rather than version-based.

---

### User Story 2 - Someone asks what is true of the estate and the answer is bounded by their entitlements (Priority: P1)

A compliance analyst asks which workspaces violate a control; an operator asks what changed last
night. The answer covers what that person may see and no more.

**Why this priority**: Equal-first and the harder half. Correctness here is a **fixture question** —
does the control query return the right violation set — rather than a judgement one, which is why
its suite scores differently from citation accuracy.

**Independent Test**: Two askers with different entitlements ask the same question and receive
answers bounded differently, with the difference traceable to their entitlements rather than to
the question.

**Acceptance Scenarios**:

1. **Given** a question about the estate, **When** two people with different entitlements ask it,
   **Then** each answer is bounded by the asker's own scope, through the same governed read path
   every other evidence access uses.
2. **Given** an estate question, **When** it is answered, **Then** the answer presents **evidence
   with citations, never a verdict**. The platform lacks the standing to determine compliance, and
   a confident wrong verdict is worse than a well-cited set of facts.
3. **Given** the records do not support an answer, **When** the question is asked, **Then** the
   platform says so rather than inferring.

---

### User Story 3 - Asking never changes anything (Priority: P1)

Whatever is asked, nothing in any estate is created, modified, or deleted.

**Why this priority**: P1 because it is the rule ADR-0039 decided **in advance** precisely because
it would be tempted — the moment an answer is useful, "and could you also…" is one sentence away.
Listed separately because it is a property of the whole feature rather than of either class, and
because a feature that quietly acquired the ability to act would still pass both stories above.

**Independent Test**: Exercise every answering path and assert no tool with an effect is reachable
from it.

**Acceptance Scenarios**:

1. **Given** any question, including one phrased as an instruction, **When** it is answered,
   **Then** no effecting tool is invoked and nothing outside the platform changes.
2. **Given** a question that would require acting to answer, **When** it is asked, **Then** the
   platform declines and says why, rather than acting and reporting.

---

### Edge Cases

- **The model provider is unavailable.** Whether asking fails, degrades, or answers from records
  alone — and whether the person can tell which.
- **The model returns something unusable** — empty, malformed, or citing sections that do not
  exist. A citation that does not resolve is worse than no citation, because it reads as evidence.
- **A question spans both classes** — "which workspaces violate this control, and how should I fix
  it?" One half is records, the other is corpus, and they fail differently.
- **The corpus changes between the question and the answer.**
- **A question that is really an instruction.** Prompt content asking the platform to act is the
  adversarial case for US3, not a hypothetical.
- **An asker with no entitlements at all.** Whether they get an empty answer or a refusal, and
  whether the difference leaks what exists.
- **The answer is long, or the records are many.** Whether truncation is visible to the reader —
  021 already established that a truncated compilation must say so.

## Requirements *(mandatory)*

### Functional Requirements

**Answering**

- **FR-001**: A person MUST be able to ask a question through the portal and receive an answer.
- **FR-002**: An answer about guidance MUST carry citations resolvable to a specific section of the
  pinned corpus, and MUST NOT assert anything the corpus does not support.
- **FR-003**: Where the available material does not support an answer, the platform MUST **decline**
  and say so. An answer that cannot be traced is the failure this platform exists to prevent.
- **FR-004**: An answer about the estate MUST be bounded by the asker's own entitlements, through
  the same governed read path every other evidence access uses — not a parallel one.
- **FR-005**: An estate answer MUST present evidence with citations and MUST NOT issue a verdict on
  compliance.

**The rule that must not bend**

- **FR-006**: Asking MUST NOT change anything. No effecting tool is reachable from the answering
  path, in any estate, under any phrasing of the question.
- **FR-007**: A question phrased as an instruction MUST be answered or declined, never performed.
- **FR-008**: FR-006 MUST be enforced structurally rather than by prompt or convention, so that a
  later change granting the ability to act has to *add* something visible in review.

**The model, and what the trail says about it**

- **FR-009**: The model consulted MUST be the one the binding names, and an unqualified cell MUST
  refuse before any provider call.
- **FR-010**: The trail MUST distinguish a **model verdict** from a **human approval**. A model
  verdict may inform a step; it never satisfies an approval requirement policy assigns to a person.
- **FR-011**: A provider failure MUST be distinguishable from a decline. "The corpus does not
  support this" and "we could not reach the model" call for different actions.
- **FR-012**: Asking MUST leave a record of who asked and what was consulted, and MUST NOT record
  the answer's content in a way that copies corpus or estate material into the trail.

**Where it binds**

- **FR-013**: Answering MUST be an API operation, not portal logic (ADR-0034), and MUST therefore
  hold on every surface that implements it (ADR-0033).
- **FR-014**: The corpus MUST be pinned, and change MUST be detected by **content** — the corpus
  carries no version metadata anywhere, so a version-based check would be checking nothing.

**The gates**

- **FR-015**: The existing `estate_state`, `citation_accuracy`, and `must_decline` suites MUST
  score what the **product path** produces, not material authored to satisfy them. Their `recorded`
  fixtures currently describe runs that never happened, because no answering path existed.
- **FR-016**: A live provider lane MUST remain out of the blocking path, and the blocking lane MUST
  remain runnable with no vendor credential.

### Key Entities

- **Question**: What a person asked, and which class it falls in.
- **Answer**: What the platform returned — claims, citations, and what it declined to say.
- **Citation**: A resolvable pointer into the corpus or into records. Unresolvable means unusable.
- **Corpus pin**: The exact content answered from, identified by content rather than version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person asks a guidance question through the portal and receives an answer whose
  every claim carries a citation that resolves.
- **SC-002**: A question the corpus does not support is declined, and the decline is
  distinguishable from a provider failure.
- **SC-003**: Two askers with different entitlements receive differently bounded estate answers,
  and the difference traces to entitlements rather than to the question.
- **SC-004**: **No effecting tool is reachable from the answering path** — demonstrated by
  exercising it, including with instruction-shaped questions, not argued from structure.
- **SC-005**: The trail shows who asked and what was consulted, and distinguishes a model verdict
  from a human approval.
- **SC-006**: A definition binding an unqualified cell refuses **before** any provider call.
- **SC-007**: The blocking lane runs green with **no vendor credential**.
- **SC-008**: `estate_state`, `citation_accuracy`, and `must_decline` score output the product path
  produced. Verified by the recordings being regenerated from real runs rather than authored.
- **SC-009**: A corpus change is detected without any version metadata, and citations reflect it.
- **SC-010**: No answer's content is copied into the audit trail.

## Assumptions

- **The corpus is settled and is HashiCorp Validated Patterns** — 33 documents, stable per-section
  anchors, **no version metadata anywhere**. Recorded as an existing decision rather than a choice
  this feature makes.
- **The eval suites are reusable as they stand.** Their cases and floors are good; what changes is
  what produces the material they score. **This is an assumption worth checking early** — if the
  case shape does not fit a real answering path, that is a larger change than it looks.
- **`ask` needs no new role or matrix concept**, only a qualified cell and a binding.
- **This is the platform's first product-path provider call.** Every prior model call has been an
  eval harness asking directly, which means Principle VIII's gates become load-bearing here rather
  than advisory.
- **Two classes, one path.** Guidance and estate-state share an answering path and differ in what
  they consult and how they are scored. If they turn out to need separate paths, this feature is
  two features and should be split rather than widened.
