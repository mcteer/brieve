# Feature Specification: A question gets an answer, and the answer never acts

**Feature Branch**: `spec/024-portal-answering`

**Created**: 2026-08-01

**Status**: Draft

**Input**: The portal has threads, a client, and a deployment. It has no way to answer anything.

**Scope**: **Grounded guidance, through the API and MCP.** Two things are deferred to their own
features and recorded rather than dropped: **estate-state answering** (see Clarifications) and the
**portal's answering surface** (see below).

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — an answer that cites nothing is the failure mode this whole platform is built against). **R10** (observability and attestation — a model verdict must be distinguishable in the trail from a human approval). |
| **ADRs touched** | **ADR-0039** (**the rule this feature will be tempted to bend, decided before it was built**: *ask answers, it never acts*). **ADR-0035** (estate-state queries as a third conversation class, bounded by the asker's own entitlements through the governed read path — extended by 022 and consumed here). **ADR-0034** (the portal is a thin client, so answering is an API operation rather than portal logic). **ADR-0033** (which makes it a parity row across surfaces). **ADR-0022 / ADR-0039** (the Qualified Model Matrix: an `ask` binding is inexpressible without a green cell). **ADR-0018** (grounded reporting — the same discipline, applied to an answer instead of a report). **None amended, expected.** |
| **Evidence class** | **Attestation-relevant.** An answer is cited in decisions. It is also the platform's **first product path that calls a model provider** — every prior model call has been an eval harness asking directly. |

## Clarifications

### Session 2026-08-01

- Q: What does a reader get when the provider is unreachable? → A: **A** — **asking fails**, with a
  reason naming provider unavailability, rather than returning an answer-shaped decline. A reader
  cannot tell "I can't help with that" from "the corpus does not cover this", and one of those
  sends them to an operator while the other sends them to the corpus. Matches the platform's
  existing posture that *a failed read is not an empty list*. Rejected: answering from the corpus
  without the model, which degrades rather than fails and invents a second answering path no gate
  scores — which is how the authored-recordings problem started.
- Q: How do the gates come to score the real path? → A: **C** — the blocking lane drives the
  **product path** with a **fixture provider**, so the suite scores what the product actually
  produced, deterministically and with no vendor credential. This is 020's precedent exactly: its
  choice lane drives the real path with `fixture/...` cells replaying recordings. Rejected:
  regenerating `recorded` from live runs, which makes the gate a snapshot of one model on one day
  and needs a paid credential to refresh; and adding a second row beside the authored one, which
  leaves the suite still scoring the authored artifact — the defect, one layer along.
  **Consequence carried into design**: the answering path must accept an injected provider.
- Q: Does this ship as one feature or split? → A: **B** — **grounded guidance first; estate-state
  follows as its own feature.** Guidance is the smaller class, its gates are the most developed,
  and it establishes the answering path estate-state reuses. It also lands the two genuinely new
  risks — **the platform's first product-path provider call** and the **structural never-acts
  guarantee** — against a fixed corpus rather than against live records bounded by entitlements,
  where a scoping error leaks another tenant's data. Estate-state then inherits a proven path and
  adds only scoping.

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

A caller asks a question about the guidance corpus **through the API or an MCP client** and
receives an answer whose every claim carries a visible citation. When the corpus does not support
an answer, they are told so.

**Not through the portal, and that is a scope decision rather than an oversight** — see the
deferral below.

**Why this priority**: It is the smaller of the two classes and the one whose gates are most
developed. It also establishes the answering path the other class reuses.

**Independent Test**: Ask a question the corpus answers through the API or an MCP client; check
every claim is cited. Ask one it does not; check the answer declines.

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

### The portal's answering surface — DEFERRED to its own feature (analysis pass 3)

**This feature builds the answering capability, not a place to type a question.** Everything below
stops at the API, with MCP for parity — which makes answering immediately usable by an editor, and
leaves the portal for a slice that can be scoped properly.

**Why it is a slice rather than a line of work absorbed here.** `relay.py` is the only module in
`surfaces/portal` holding an HTTP client, and a conformance row asserts exactly that — so reaching
a new operation means work there, plus a route, plus something a person types into. The portal also
carries two gates this feature never mentions: `tests/conformance/portal/test_containment.py`, and
`make a11y` (WCAG 2.2 AA, a blocking lane). None of that is large; all of it is unscoped, and
absorbing it here would repeat the mistake clarify already avoided once.

**An earlier draft of this spec had SC-001 reading "through the portal" while no task touched the
portal at all** — the feature's own headline uncovered. Corrected by narrowing rather than by
quietly widening the work.

**ADR-0034 is the reason this is safe, and was nearly the reason it was missed.** The portal is a
thin client, which is why answering belongs in the API — and "thin" briefly became "absent".

---

### Estate-state answering — DEFERRED to its own feature (clarified 2026-08-01)

A compliance analyst asking which workspaces violate a control, and an operator asking what
changed last night, are **out of scope here**. That class reads records rather than a corpus,
must be bounded by the asker's own entitlements, and is where a scoping error leaks another
tenant's data — so it should inherit a proven answering path rather than land beside one being
built.

**What it inherits, and what it must not rediscover**: the answering path, the decline-over-
confabulate discipline, the never-acts guarantee, and the provider-failure posture. What it adds
is entitlement bounding through the governed read path (ADR-0035, extended by 022) and its own
`estate_state` suite. **ADR-0035's rule that it presents evidence with citations and never a
verdict is already decided** and carries forward unchanged.

**Recorded here rather than dropped**, so the next planner finds the split and its reason rather
than an unexplained absence.

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

- **The model provider is unavailable.** *Resolved — FR-011/FR-011a.* Asking fails and says so.
  No degraded path, because a path no gate scores is how this feature's own gates got into the
  state it exists to fix.
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
- **FR-004**: **Deferred with estate-state answering.** Entitlement bounding is that feature's,
  and it inherits ADR-0035's governed read path rather than a parallel one.
- **FR-005**: **Deferred with estate-state answering.** Evidence with citations, never a verdict —
  already decided by ADR-0035 and carried forward unchanged.

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
- **FR-011**: A provider failure MUST be distinguishable from a decline, and MUST NOT be delivered
  as an answer. Asking **fails**, naming provider unavailability. "The corpus does not support
  this" sends a reader to the corpus; "we could not reach the model" sends them to an operator, and
  a shared response shape would have them file the second as the first.
- **FR-011a**: There MUST NOT be a fallback answering path that omits the model. A second path
  would be one no gate scores — which is precisely how four suites came to be green over material
  nothing produced.
- **FR-012**: Asking MUST leave a record of who asked and what was consulted, and MUST NOT record
  the answer's content in a way that copies corpus or estate material into the trail.

**Where it binds**

- **FR-013**: Answering MUST be an API operation, not portal logic (ADR-0034), and MUST therefore
  hold on every surface that implements it (ADR-0033).
- **FR-014**: The corpus MUST be pinned, and change MUST be detected by **content** — the corpus
  carries no version metadata anywhere, so a version-based check would be checking nothing.

**The gates**

- **FR-015**: The `citation_accuracy` and `must_decline` suites MUST score what the **product
  path** produces, not material authored to satisfy them. Their `recorded` fixtures currently
  describe runs that never happened, because no answering path existed. `estate_state` stays as it
  is and is that feature's obligation.
- **FR-015a**: Every eval suite that scores a **response to a prompt** MUST either score product
  output or carry a written statement of why it does not, naming what would close it. The defect
  this feature exists to fix is a suite asserting over material nothing produced; fixing two suites
  and declaring the rest out of scope leaves the same defect with no owner.
- **FR-016**: A live provider lane MUST remain out of the blocking path, and the blocking lane MUST
  remain runnable with no vendor credential.
- **FR-016a**: The answering path MUST accept an **injected provider**, so the blocking lane can
  drive the real path with a fixture and score what the product produced. A path that could only
  reach a vendor would force the gate back onto authored material, which is the defect FR-015
  exists to close.

### Key Entities

- **Question**: What a person asked, and which class it falls in.
- **Answer**: What the platform returned — claims, citations, and what it declined to say.
- **Citation**: A resolvable pointer into the corpus or into records. Unresolvable means unusable.
- **Corpus pin**: The exact content answered from, identified by content rather than version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller asks a guidance question **through the API or an MCP client** and receives
  an answer whose every claim carries a citation that resolves. **The portal is deliberately not
  the path here** — see the deferral in User Scenarios.
- **SC-002**: A question the corpus does not support is declined, and the decline is
  distinguishable from a provider failure.
- **SC-003**: **Deferred with estate-state answering.**
- **SC-004**: **No effecting tool is reachable from the answering path** — demonstrated by
  exercising it, including with instruction-shaped questions, not argued from structure.
- **SC-005**: The trail shows who asked and what was consulted, and distinguishes a model verdict
  from a human approval.
- **SC-006**: A definition binding an unqualified cell refuses **before** any provider call.
- **SC-007**: The blocking lane runs green with **no vendor credential**.
- **SC-008**: `citation_accuracy` and `must_decline` score output the product path produced,
  rather than material authored to satisfy them.
- **SC-008a**: Every remaining prompt-scoring suite either does the same or carries a written
  disposition naming what would close it. Verified by reading the contract and finding no suite
  unaccounted for.
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
