# Feature Specification: An answer is useful — primary response, supporting citations

**Feature Branch**: `spec/046-answer-usefulness`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: Ask currently returns a citation-led list of one-sentence claims.
People asking for guidance (including illustrative code such as a Terraform template) should
receive a **primary answer** first; citations must remain, but only as support for what that
answer used. Closes the unnumbered ROADMAP entry *"An answer can be true, cited, on-subject and
useless"* (raised 2026-08-08) without re-opening 043's relevance-judge floor.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4, R13 (evidence)** — citations remain the reader's audit trail for what the answer rested on; this feature changes *how* an answer is composed and judged useful, not whether claims must resolve. **R7 (fail-closed)** — inventing unsupported substance (including uncited code) must still decline; a helpful-looking template with no corpus footing is confabulation. **R12 (eval gates)** — usefulness must be expressible as a suite that can fail, not only as a walkthrough observation |
| **ADRs touched** | **ADR-0039** (*ask answers, it never acts* — unchanged; illustrative code in an answer is not an action; writing a repository / opening a PR remains authoring). **ADR-0004** (pinned / endorsed corpus — still the only material an answer may rest on). **ADR-0067 / ADR-0052** (relevance judge — **not** retuned; ROADMAP forbids starting here). **ADR-0034** (thin portal — renders the platform's answer shape; does not invent usefulness). **ADR-0033** (API / MCP / portal parity for the ask path). **ADR-0047** (any new gate must be able to fail). Consumes 024/028/035/043 answer pipeline |
| **Evidence class** | **attestation-relevant.** The surface still asserts that what it says is supported by pinned (or endorsed) material. Changing the answer's shape or sufficiency bar changes what that assertion covers |

## What is actually wrong

**Two failures, one surface.**

1. **Shape (observed 2026-08-13).** Ask is contracted as a JSON array of *"one factual
   sentence"* claims, each with nested citations. The portal renders that list as the answer.
   A person asking *"Create a terraform template that can deploy vault to an aws cluster
   group"* receives a stack of cited fragments — or a decline — rather than a primary response
   that may include illustrative code, with citations underneath for what informed it.

2. **Usefulness (ROADMAP, measured 2026-08-08).** An endorsed standard answers *"how long are
   logs kept?"* with *"Acme maintains its own internal standard that defines how long
   operational logs are kept."* The document says **400 days**. The answer does not. It is
   true, cited, on-subject, relevance-checked — and useless. Every existing gate passed.

**What this is not.** Tightening the relevance judge so thin-but-on-subject claims fail. 043
measured that direction: Opus scored **7/10** by over-refusing partial answers, and the prompt
line *"relevant even if … only says where the full answer is documented"* exists because of
those calls. Re-tightening re-breaks 043. The gap is that **nothing asks whether the answer is
useful**, and the answer contract never asks for a primary response that carries the substance
(or honest disclosure when it cannot).

**Authoring is out of scope.** Returning illustrative code in Ask is not `author_file`, not a
PR, and not `terraform plan`. Those remain the change-proposal / authoring path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The answer is primary; citations support it (Priority: P1)

Someone asks a guidance question the corpus can support. They receive a coherent primary
answer they can read as the response. Citations appear as the sources that informed that
answer — not as a substitute for it.

**Why this priority**: This is the walkthrough defect. A citation list is not what people ask
for.

**Independent Test**: Ask a covered guidance question through the portal; confirm a reader can
state the answer without opening a citation, and that every substantive claim still has
followable support.

**Acceptance Scenarios**:

1. **Given** a question the corpus supports, **When** Ask answers, **Then** the primary
   response is prose (or prose plus illustrative code) that a reader can use without following
   a link first.
2. **Given** that answer, **When** the reader inspects sources, **Then** citations are present
   for the material the answer used, and every citation still resolves against the pin (or
   endorsed version).
3. **Given** the same question on API and MCP, **When** both answer, **Then** the answer shape
   and disposition match (parity) — the portal only renders what the platform returned.

---

### User Story 2 — Illustrative code when asked, when the corpus supports it (Priority: P1)

Someone asks for an example, template, or configuration sketch. When the pinned or endorsed
corpus supports that content, the primary answer includes illustrative code. The platform still
does not write files, open PRs, or claim to have applied anything.

**Why this priority**: This is the missed guidance that produced the Terraform-template ask.
People reasonably expect snippets; they must not get silent refusal-by-shape.

**Independent Test**: Ask for an illustrative Terraform (or equivalent) fragment the corpus
actually covers; confirm the primary answer contains code and citations to the sections used;
confirm no repository side effect occurred.

**Acceptance Scenarios**:

1. **Given** a request for an example/template the corpus supports, **When** Ask answers,
   **Then** the primary response includes illustrative code grounded in cited sections.
2. **Given** that answer, **When** audit/trail is inspected, **Then** the disposition is an
   answer (not an action), and no authoring or product tool ran.
3. **Given** a request for a template the corpus does **not** support, **When** Ask runs,
   **Then** it declines or answers only what the corpus establishes — it does not invent
   uncited configuration to be helpful.

---

### User Story 3 — Useful means the reader learns the fact they asked for (Priority: P1)

Someone asks a question whose answer is a specific fact in a document (a number, a required
setting, a named procedure). When that fact was available to the path, the primary answer
includes it — rather than a true-but-empty locator sentence that names the document and omits
the figure. When the fact was not available, a thin primary answer may still pass relevance
(Q1-C); the sufficiency suite does not punish that case.

**Why this priority**: The ROADMAP case. Gates that cannot fail on uselessness train a quiet
defect.

**Independent Test**: A sufficiency case (endorsed-standard retention or equivalent) where the
fact was available: a true/cited/on-subject answer that omits the figure **fails**; an answer
that includes the figure passes. No mandated “locates only” disclosure form (Q1-C).

**Acceptance Scenarios**:

1. **Given** a document that states a concrete fact the question asks for, **When** Ask
   answers from that material, **Then** the primary answer includes that fact.
2. **Given** material that only locates where a fact is documented and does not contain it in
   what was offered, **When** Ask answers and relevance passes, **Then** a thin primary answer
   is still allowed (clarification Q1-C); the sufficiency suite is what fails fact-omitting
   answers when the fact *was* available to use.
3. **Given** a suite of sufficiency cases, **When** the eval gate runs, **Then** a true /
   cited / on-subject / fact-omitting answer fails the suite.

---

### User Story 4 — Existing safety and grounding do not regress (Priority: P1)

Must-deny, must-decline, citation accuracy, relevance, and never-acts remain green. A richer
answer shape must not become a path to uncited invention or to action.

**Why this priority**: Usefulness must not be bought by weakening 024/043/ADR-0039.

**Independent Test**: Existing answering eval suites and the never-acts conformance row remain
blocking and green; a new sufficiency suite is additive.

**Acceptance Scenarios**:

1. **Given** the current must-deny / must-decline / citation-accuracy / relevance cases,
   **When** this feature lands, **Then** they still pass (or are deliberately reauthored with
   recorded cause if the answer shape requires it — never silently weakened).
2. **Given** an ask that looks like an instruction to act, **When** it is handled, **Then**
   the path still never obtains tools or authority to act.

### Edge Cases

- Question asks for a full production-ready module the corpus only partially covers — answer
  what is supported; do not pad with invented resources.
- Multi-turn follow-up ("add the KMS key section") — primary answer still useful; citations
  still only for material used this turn.
- Estate questions ("which runs were denied?") — out of scope for shape change (Q2-B); estate
  continues to answer from harness/enclave records only and keeps today's presentation.
- Very long illustrative code — answer remains readable; citations remain followable; no
  secret values from credentials or estate records appear in snippets.
- Relevance judge still runs after grounding; a primary answer that is off-subject still
  declines — usefulness does not override relevance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ask MUST return a **primary answer** a reader can use without first following a
  citation, whenever the disposition is answered.
- **FR-002**: Every substantive part of a primary answer MUST remain grounded: guidance (and
  endorsed-guidance) citations MUST resolve, and relevance MUST still be established under the
  existing 043 rules without retuning the judge's subject-vs-sufficiency instruction. Estate
  record grounding is unchanged and out of shape scope for this feature (Q2-B).
- **FR-003**: Citations MUST be presented as support for the primary answer (sources used),
  not as the sole or primary content of the response.
- **FR-004**: When the asker requests an example, template, or configuration, and the corpus
  supports it, the primary answer MUST be allowed to include **illustrative code**. Ask MUST
  NOT write files, open proposals, or run plan/apply.
- **FR-005**: When the corpus does not support requested substance (including code), Ask MUST
  decline or limit the answer to what is supported — never invent uncited configuration,
  numbers, or procedure steps to appear helpful. Thin primary answers remain allowed when
  relevance passes and the asked-for fact was not available (Q1-C); that is not a licence to
  invent.
- **FR-006**: The platform MUST be able to fail an answer that is true, cited, on-subject, and
  missing the asked-for fact — via a dedicated sufficiency evaluation (case shape carrying the
  required fact), not by tightening the 043 relevance prompt.
- **FR-007**: API, MCP, and portal MUST expose the same answered/declined/refused dispositions
  and the same primary-answer-plus-support shape for guidance asks (portal remains a thin
  renderer).
- **FR-008**: Trail/audit records for an ask MUST remain content-free of question and answer
  text (`ask_answered` doctrine), and MUST still carry the authorising cell, corpus digest,
  disposition, and relevance-gate metadata that identify what authorised the ask. Per-citation
  source lists belong on the response/conversation outcome, not in `ask_answered`. The path
  MUST still not act (ADR-0039).
- **FR-009**: Tightening or re-prompting the relevance judge to refuse "locator" answers as
  irrelevant is **out of scope** (ROADMAP measurement from 043).
- **FR-010**: Retrieval quality (whether the answering path is offered the section that holds
  the fact vs a preamble) MUST be measured and recorded **before claiming ROADMAP closure or
  SC-002** (named-runner measurement in quickstart / live legs). If preamble preference means
  the fact-bearing section was never offered, the specify must not pretend a presentation-only
  fix closed the ROADMAP case — stop and open a retrieval follow-on.

### Key Entities

- **Primary answer**: The reader-facing response body for an answered ask — prose and, when
  appropriate, illustrative code — that carries the substance of the reply.
- **Supporting citation**: A resolvable pointer into pinned or endorsed material that informed
  the primary answer; not a substitute for it.
- **Sufficiency case**: An eval case that names the fact(s) (`must_contain`) a useful answer
  must include in the primary answer when that fact was available to the path. Thin locator
  answers when the fact was unavailable remain allowed (Q1-C); they are not scored as
  sufficiency failures.
- **Illustrative code**: Example configuration or template text inside the primary answer;
  not a repository work product.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a guided walkthrough of three covered guidance questions, a reader who does
  not open citations can correctly restate the substance of each answer (pass/fail per
  question; 3/3 required for the demo bar).
- **SC-002**: For a fixture or endorsed case that encodes a concrete fact (e.g. retention =
  400 days) **in material the path may use**, a useful answer includes that fact in the
  primary response in **≥ 9 of 10** live samples under the bound ask cell. Thin locator
  answers remain allowed when relevance passes and the fact was not available (Q1-C); the
  sufficiency suite fails the case when the fact was available and omitted.
- **SC-003**: A dedicated sufficiency suite fails a hand-authored true/cited/on-subject /
  fact-omitting answer (the suite can fail — ADR-0047).
- **SC-004**: At least one ask that requests an illustrative template the corpus supports
  returns code in the primary answer with resolvable citations, with zero authoring side
  effects (no PR, no `author_file`, no plan/apply).
- **SC-005**: Existing must-deny, must-decline, citation-accuracy, and relevance gates remain
  blocking and green (or are reauthored with an explicit recorded reason in this feature's
  artifacts — never silently dropped).
- **SC-006**: API and MCP agree on disposition and answer shape for the same guidance ask
  (parity row).

## Assumptions

- This feature numbers and closes the ROADMAP entry *"An answer can be true, cited, on-subject
  and useless"*; the answer-first / code-snippet requirement from the 2026-08-13 walkthrough is
  in the same specify because both are failures of "the answer a person can use."
- Ask remains never-acts (ADR-0039). Illustrative code is content in an answer, not agency.
- The Terraform change-proposal / authoring demo remains a separate feature; this specify does
  not deliver plan gates or PRs.
- The 043 relevance judge prompt and seed floor are not retuned to chase sufficiency.
- Customer-endorsed and validated-design provenance continue to surface on citations as today.
- Estate asks remain a separate path: harness/enclave records only, never product-doc
  guidance. This feature does not reshape estate answers (clarification Q2-B).

## Out of Scope

- Authoring workflows, `author_file`, `open_proposal`, `terraform plan` / apply, or any path
  that mutates a customer's repository.
- Reshaping estate answers (record-based asks). Estate stays on today's claim/reference
  presentation; it never needed product docs and is not mixed into this feature's corpus path.
- Multi-tenancy (ADR-0046).
- Replacing term-overlap retrieval with embeddings or a new index (measurement may recommend
  follow-on work; shipping a new retriever is not required to close SC-001–SC-004 unless
  research shows presentation-only changes cannot close the ROADMAP case).
- Changing which model cells are bound for ask/relevance.
- Portal visual redesign beyond what is required to render primary answer + supporting sources
  honestly.
- Declining or specially labelling thin locator answers at the relevance gate (Q1-C; 043 judge
  untouched).

## Clarifications

### Session 2026-08-13

- Q1: When the platform cannot put the asked-for fact in the primary answer from what it may
  use, must it decline, disclose as locator-only, or allow a thin primary answer? → **C — allow
  a thin primary answer if relevance passes.** Usefulness when the fact *was* available is
  enforced by the sufficiency suite (FR-006 / SC-002 / SC-003), not by retuning the 043 judge.
- Q2: Does primary-answer-plus-support apply to estate asks? → **B — guidance and endorsed
  guidance only.** Estate answers from internal harness/enclave records and keeps today's
  presentation; this feature does not teach estate to read product docs and does not reshape it.
