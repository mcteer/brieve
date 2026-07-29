# Feature Specification: The Conversational Portal

**Feature Branch**: `spec/012-conversational-portal`

**Path**: `specs/012-conversational-portal/spec.md`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "The conversational portal — the transport ADR-0034 describes, and the fourth surface over the one authorization core. Threads are the substance of this feature. Parity binds this surface too. The portal is over the API, not beside it. A person opens the portal, sees the agents they may start, starts one inside a thread, watches it reach a result, and asks a follow-up that knows what the first run produced."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R15** (four transports, one authorization core — and this is the transport that makes "one core" hardest to hold, because it is the one a human looks at). R2 / R3 (per-task authority — the authenticated human is the subject of every turn, and a thread must not become a way for turn two to inherit turn one's authority). R7 (fail-closed — a turn that cannot establish scope declines rather than answering with less). R4 / R10 / R13 (evidence — a thread is auditable by correlation ID, which is a claim ADR-0034 makes and nothing has yet tested). |
| **ADRs touched** | **ADR-0034** (this feature *is* that record, built), **ADR-0033** (the parity row and the no-static-keys rule), **ADR-0032** (the ungoverned local loop this surface is most likely to manufacture by accident), ADR-0035 (evidence stays a read path that cannot mutate or mask), ADR-0049 (a thread must not reintroduce the human-in-the-loop pause it removed), ADR-0039 (per-role model bindings, if the portal answers rather than only dispatches), ADR-0016 (an authority change requested in conversation is still Control-Group gated). |
| **Evidence class** | **Audit-critical, and it introduces a new shape.** Every prior surface audits discrete operations. A thread is a *sequence* whose meaning is partly in the ordering — "what did this person ask before they started that run" is a question the trail has never had to answer. If threads are run state (ADR-0034), they are as auditable as a run; if they are anything else, they are a side channel, which is the failure that record exists to prevent. |

## Clarifications

### Session 2026-07-29

- Q: Does this feature ship the browser client, or the thread substrate with the client as its own feature? → A: **Substrate and the full product UI.**
  *(The largest of the three options, chosen deliberately. It is what makes ADR-0034's security-critical rule testable rather than asserted — SC-006 compares against a delivered client, and there is nothing to compare against otherwise. The cost is exactly what ADR-0034 named: a second technology stack with its own build, test, dependency, and accessibility obligations, none of which this repo has carried before. The gates that come with it are new, not inherited.)*
- Q: Which of ADR-0034's three conversation classes does this feature serve? → A: **All three** — governed actions, estate-state questions, and grounded guidance with visible citations.
  *(Also the largest option. Guidance requires a corpus, an ingestion path, and citation machinery that do not exist in this repository; estate-state requires answering over ADR-0035's read path, which exists, with a model interpreting it, which does not. The prioritisation below reflects this: governed actions are P1, and the two answering classes are P3 and P4 — not because they matter less, but because they are separable and each is large enough to land on its own.)*
- Q: Is the portal a third implementation of the operation catalogue, or a consumer of the API? → A: **A consumer.** Parity stays API/MCP; a new row asserts the portal exposes no capability the API does not.
  *(ADR-0034's thin-client rule forbids business logic, and implementing the catalogue is business logic by definition — a third copy of the authorization path is what ADR-0033 exists to prevent. Thread operations still land on API and MCP, so the parity row still grows, exactly as 011 recorded it would. What changes is the shape of the portal's own conformance obligation: not "does it agree with the others" but "does it add anything at all", which is a containment claim rather than an equivalence one.)*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a run from a conversation, and watch it finish (Priority: P1)

A person opens the portal, sees which agents they may start, describes what they want in
their own words, and a run starts. They watch it reach a result without leaving the
conversation or holding onto an identifier.

**Why this priority**: It is the smallest thing that is recognisably a portal rather than a
form. Everything else in this feature is a refinement of it, and if this does not work the
rest is decoration.

**Independent Test**: A person with a valid session starts a run through the portal and
sees its result, with no run identifier ever visible to them and no operation reached
except through the API.

**Acceptance Scenarios**:

1. **Given** a person authenticated against the organization's provider, **When** they open
   the portal, **Then** they see the agent definitions they may start, and those they may
   not, flagged — the same disclosure 011 settled, rendered rather than re-decided.
2. **Given** a person who has described what they want, **When** a run starts, **Then** it
   starts through the same operation the API exposes, with the person as its subject.
3. **Given** a run that is still working, **When** the person waits, **Then** the
   conversation reflects its progress without the person polling or refreshing.
4. **Given** a run that has finished, **When** the person looks, **Then** they see what it
   produced, distinguishable from "not finished" and from "ended without a result" — the
   three dispositions 011 established, not collapsed for display.

---

### User Story 2 - A second turn that knows about the first (Priority: P1)

The person asks a follow-up. It lands in the same thread, and what the first run produced
is available to it — so the person does not restate context the platform already holds.

**Why this priority**: This is the actual difference between a conversation and a sequence
of independent submissions, and it is the reason threads exist at all. It shares P1 with
US1 because a portal that cannot do this is the form it was supposed to replace.

**Independent Test**: A person starts a run, waits for a result, then asks a follow-up that
refers to that result without repeating it — and the second run receives it.

**Acceptance Scenarios**:

1. **Given** a thread whose first run produced a result, **When** the person sends a second
   message, **Then** the second turn has access to that result.
2. **Given** a thread with several completed turns, **When** the person sends another,
   **Then** what carries forward is bounded — a thread does not grow without limit and does
   not silently drop the earliest thing it needs.
3. **Given** a turn whose authority differs from the previous turn's, **When** it runs,
   **Then** it is authorized on its own terms. **A thread must not let turn two inherit
   turn one's authority**, which is the specific way a conversational surface becomes a
   standing grant.

---

### User Story 3 - The thread survives, and is accountable (Priority: P2)

The person closes the browser and comes back. Their threads are there, in the state they
left them, including runs that finished while they were away. An investigator can later
reconstruct the whole exchange from the trail.

**Why this priority**: ADR-0034 asserts threads are tenant-scoped run state, persisted like
any other, auditable by correlation ID. That claim has never been tested against a real
conversation. P2 because US1 and US2 are demonstrable within a session, but a thread that
does not survive is not run state — it is a cache with an ADR describing it as something
else.

**Independent Test**: Start a thread, restart the serving process, return, and find the
thread and its runs intact — then reconstruct the same exchange from the audit trail alone.

**Acceptance Scenarios**:

1. **Given** a thread with completed and in-flight runs, **When** the serving process
   restarts, **Then** the thread and every run's state are unchanged.
2. **Given** a thread, **When** an investigator reads the trail by correlation ID, **Then**
   they can reconstruct which person asked what, in what order, and which runs resulted.
3. **Given** a thread belonging to another tenant, **When** anyone asks for it, **Then**
   they are answered as though it does not exist — not refused in a way that confirms it
   does.
4. **Given** a run started in a thread that has since been abandoned, **When** it finishes,
   **Then** its result is still recorded and still reachable. **A thread nobody is watching
   is not a run nobody consented to.**

---

### User Story 4 - Stopping, and the pause that must not appear (Priority: P2)

A person who started something they did not mean to can stop it from the conversation. What
they cannot do — and what nobody can build into this surface — is make the agent wait for
their approval mid-run.

**Why this priority**: ADR-0049 removed the human-in-the-loop pause deliberately, and a
conversational surface is the single most likely place for it to come back, because "just
ask the user first" is so natural to write here that it will not feel like a decision.

**Independent Test**: Stop a run from the conversation and observe the same withdrawal
semantics the API has — current step completes, no further step begins, terminal. Then
confirm no mechanism exists by which a run can solicit input mid-flight.

**Acceptance Scenarios**:

1. **Given** a running turn, **When** the person stops it, **Then** it stops exactly as
   `POST /runs/{run_id}/stop` stops it — the current step finishes and nothing further
   begins.
2. **Given** any run started from a thread, **When** it executes, **Then** there is no path
   by which it can pause awaiting the person's answer. Consent to start remains consent to
   finish.
3. **Given** a stopped run in a thread, **When** the person continues the conversation,
   **Then** the next turn is a new run authorized on its own terms, not a resumption.

---

### User Story 5 - The surface declines what it is not for (Priority: P3)

Someone asks the portal something outside its domain. It declines gracefully rather than
attempting an answer.

**Why this priority**: ADR-0034 makes this the thing that keeps quality measurable — a
bounded assistant can be evaluated against its domain, an unbounded one only against
everything. P3 because it is meaningless until there is something to be off-topic
*relative to*.

**Independent Test**: Ask something plainly outside the estate and the products; receive a
decline that reads as a boundary rather than a malfunction.

**Acceptance Scenarios**:

1. **Given** an off-topic request, **When** the portal responds, **Then** it declines and
   says what it is for, without appearing broken.
2. **Given** a request that is in-domain but exceeds the asker's scope, **When** the portal
   responds, **Then** it refuses on scope — a *different* answer from off-topic, because
   conflating them tells someone their access is fine when it is not.

---

### User Story 6 - Ask what the estate actually looks like (Priority: P3)

A person asks a question about their own estate — what ran, what changed, what a control
looks like in practice — and gets an answer drawn from evidence they are entitled to see.

**Why this priority**: It is the second of ADR-0034's three conversation classes, and the
cheaper of the two answering classes: the governed read path already exists (ADR-0035), so
what is new is interpretation rather than access. P3 because it is separable from US1–US4 and
lands on its own.

**Independent Test**: Two people in the same tenant with different scopes ask the same
estate question and receive answers that differ by exactly what each may see.

**Acceptance Scenarios**:

1. **Given** a person asking about their estate, **When** the portal answers, **Then** the
   answer is drawn only from evidence within that person's scope.
2. **Given** two subjects with different scopes, **When** both ask the same question,
   **Then** neither answer contains anything the asker could not have read directly.
3. **Given** a question whose answer would require evidence outside the asker's scope,
   **When** the portal responds, **Then** it says the scope is insufficient rather than
   answering from the part it can see. **A partial answer presented as complete is the
   fail-open of an answering surface.**
4. **Given** any estate answer, **When** the trail is read, **Then** the underlying evidence
   read is recorded as an evidence read, indistinguishable from one made through the API.

---

### User Story 7 - Guidance, with visible citations (Priority: P4)

A person asks how something is meant to work — from vendor documentation and validated
designs — and gets an answer that shows where each claim came from.

**Why this priority**: The third conversation class, and the largest. It requires a corpus,
an ingestion path, and citation machinery, none of which exist in this repository. P4
because everything above it is deliverable without it, and it is the part most likely to
warrant its own feature if the sequencing proves it.

**Independent Test**: Ask a documented question, receive an answer in which every
substantive claim carries a citation a person can follow to its source.

**Acceptance Scenarios**:

1. **Given** a question answerable from the corpus, **When** the portal answers, **Then**
   every substantive claim carries a visible citation resolving to its source.
2. **Given** a question the corpus does not cover, **When** the portal responds, **Then** it
   says so rather than answering without grounding. **An uncited answer is worse than no
   answer here, because the surface's whole claim is that its answers are checkable.**
3. **Given** a corpus document that changes, **When** the same question is asked again,
   **Then** the answer reflects the current document and cites it.

---

### Edge Cases

- **Two tabs, one thread.** The same person has a thread open twice and sends from both.
  What happens to ordering, and does either one silently lose a turn?
- **A run outlives the thread's usefulness.** The person stops caring; the run does not
  stop. Its result is still recorded (US3), but nothing surfaces it — is that acceptable, or
  does an unattended completion need somewhere to land?
- **A result too large to show.** 011 bounded a result and refuses rather than truncating.
  What does a conversation do with a refusal that exists to protect it?
- **Authority changes mid-thread.** A person's roles change between turn one and turn three.
  The thread must not carry the old scope forward (US2 scenario 3), and the person should
  understand why the same request now answers differently.
- **The API is unreachable.** The portal is a thin client with nothing to fall back on. Does
  it say so, or does it look like the platform is empty?
- **A thread referencing a run the person may no longer read.** Roles narrowed after the
  fact. The thread holds a reference; the operation refuses. Which wins, and does the
  refusal leak what the run was?

## Requirements *(mandatory)*

### Functional Requirements

**The surface and its boundary**

- **FR-001**: The portal MUST reach every capability through the northbound API, and MUST
  NOT reach the governed core directly. A second path to the core is the thing ADR-0033
  exists to prevent, and this is the surface where building one would be easiest to justify.
- **FR-002**: The portal MUST NOT perform orchestration or call models from the browser.
  ADR-0032's ungoverned local loop must not be manufacturable by opening a developer
  console.
- **FR-003**: Every operation MUST authenticate the human against the organization's OIDC
  provider. No static API key appears anywhere in this surface, including in any
  server-to-server hop it makes on a person's behalf.
- **FR-004**: The portal MUST be a **consumer** of the operation catalogue, not a third
  implementation of it. It exposes no capability the API does not, and this MUST be asserted
  by comparison rather than by inspection.
- **FR-004a**: The parity row continues to bind across API and MCP, and thread operations
  MUST land on both. **The portal's own conformance obligation is containment, not
  equivalence**: the question is not "does it agree with the other transports" but "does it
  add anything at all". A capability reachable in the portal and absent from the API is the
  fourth authorization path ADR-0033 exists to prevent, wearing a friendlier name.

**Threads**

- **FR-005**: A thread MUST be tenant-scoped run state, persisted like any other run state,
  surviving process restarts.
- **FR-006**: A thread MUST be auditable by correlation ID, such that an investigator can
  reconstruct who asked what, in what order, and which runs resulted.
- **FR-007**: A thread MUST belong to exactly one subject in exactly one tenant, and a
  thread outside the asker's tenant MUST be answered as absent rather than refused.
- **FR-008**: A turn in a thread MUST be authorized on its own terms. Authority MUST NOT
  carry forward from an earlier turn.
- **FR-009**: What a thread carries forward into a later turn MUST be bounded, and the
  bound MUST be explicit rather than emergent from a context limit.
- **FR-010**: A run started in a thread MUST complete and record its result regardless of
  whether anyone is still watching the thread.

**Runs, in conversation**

- **FR-011**: Starting a run from a thread MUST use the same operation, subject, and
  authorization path as starting one from any other transport.
- **FR-012**: The portal MUST present the three run dispositions distinguishably — not
  finished, produced a result, ended without one — rather than collapsing them for display.
- **FR-013**: Stopping from a thread MUST have the same semantics as stopping through the
  API: the current step completes, no further step begins, and the run is terminal.
- **FR-014**: The portal MUST NOT provide any mechanism by which a run solicits input from
  the person mid-flight. Consent to start is consent to finish (ADR-0049).
- **FR-015**: A person MUST be able to see which agent definitions they may start and which
  they may not, using 011's settled disclosure rather than a new one.

**Bounds and scope**

- **FR-016**: Per-user rate limits and loop bounds MUST apply. ADR-0034 names this the
  easiest surface on which to consume resources accidentally.
- **FR-017**: The portal MUST decline out-of-domain requests gracefully, and MUST
  distinguish an out-of-domain decline from an out-of-scope refusal.
- **FR-018**: An authority change requested in conversation MUST remain Control-Group gated
  (ADR-0016), and collecting its disposition MUST remain a read.
- **FR-019**: Evidence reached through the portal MUST remain a read path that cannot
  mutate or mask (ADR-0035).

**The client**

- **FR-020**: This feature MUST deliver the browser client, not only the substrate behind
  it. The client is what makes FR-002 and SC-006 verifiable — a thin-client rule with no
  client is an assertion nobody can test.
- **FR-020a**: The client MUST meet a stated accessibility standard, and that standard MUST
  be asserted by a gate rather than reviewed by eye. ADR-0034 names accessibility as one of
  the obligations this second technology stack carries; an obligation with no gate is a
  preference.
- **FR-020b**: The client MUST hold no capability that survives the loss of the person's
  session, and MUST NOT persist anything that would let it act on their behalf later.

**Answering — estate-state and guidance**

- **FR-021**: The portal MUST serve all three of ADR-0034's conversation classes: governed
  actions, estate-state questions, and grounded guidance.
- **FR-022**: An estate-state answer MUST be drawn only from evidence within the asker's
  scope, and the underlying read MUST be recorded as an evidence read — indistinguishable in
  the trail from the same read made through the API.
- **FR-023**: When a question cannot be fully answered within the asker's scope, the portal
  MUST say the scope is insufficient rather than answering from the visible part. A partial
  answer presented as complete is this surface's fail-open.
- **FR-024**: Every substantive claim in a guidance answer MUST carry a visible citation
  that resolves to its source.
- **FR-025**: When the corpus does not cover a question, the portal MUST say so rather than
  answering without grounding.
- **FR-025a**: The corpus is **HashiCorp Validated Patterns**. Because those documents carry
  no version or revision metadata, the platform MUST detect a changed source by its content
  rather than by anything the source asserts about itself, and a citation MUST resolve to the
  section it supports rather than to the document containing it.
- **FR-026**: Model selection for answering MUST follow the per-role bindings ADR-0039
  establishes, not a portal-local choice.
- **FR-027**: Answering MUST NOT become a path to any capability the operation catalogue
  does not expose. A model that can read and summarise must not thereby be able to act.

### Key Entities

- **Thread**: A tenant-scoped, subject-owned, persisted sequence of turns. Auditable by
  correlation ID. Survives restarts. Carries context forward under an explicit bound; does
  not carry authority forward at all.
- **Turn**: One exchange within a thread — what the person asked and what resulted. A turn
  that does work has a run; a turn that is declined has a reason.
- **Thread context**: The bounded set of prior results a later turn may see. Distinct from
  the thread itself, because what is *stored* and what is *carried forward* have different
  limits and different failure modes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has never used the platform can start an agent and see its
  result without being given, or having to record, any identifier.
- **SC-002**: A follow-up turn that refers to a previous result succeeds without the person
  restating that result.
- **SC-003**: A thread and its runs survive a restart of every serving process, with zero
  turns lost and zero run states changed.
- **SC-004**: An investigator can reconstruct a complete thread — subject, order, and
  resulting runs — from the audit trail alone, without reading thread storage.
- **SC-005**: Zero capabilities are reachable from the portal that are not reachable through
  the API, verified by comparison rather than by inspection.
- **SC-006**: Zero model calls and zero orchestration decisions originate in the browser,
  verified against the delivered client.
- **SC-007**: A run started from a thread is indistinguishable, in the trail, from the same
  run started through the API — same subject, same authorization path, same events.
- **SC-008**: No sequence of turns produces a run that waits for human input mid-flight.
- **SC-009**: A thread belonging to another tenant is indistinguishable from one that does
  not exist, across every operation that can name a thread.
- **SC-010**: Per-user rate limits bound a runaway conversation without operator
  intervention.
- **SC-011**: The delivered client meets its stated accessibility standard, verified by a
  gate that fails the build rather than by review.
- **SC-012**: Two subjects with different scopes asking the same estate question receive
  answers differing by exactly what each may see, with neither containing anything its asker
  could not have read directly.
- **SC-013**: Every substantive claim in a guidance answer resolves to a source a person can
  open, and a question outside the corpus produces a stated gap rather than an uncited
  answer.
- **SC-014**: No answering capability reaches an action. A model that can read cannot start,
  stop, or change anything except through the same operations a person uses.

## Assumptions

- **The operation catalogue is sufficient for everything except threads.** 011 shipped ten
  operations specifically so this feature would not have to widen the API for run
  lifecycle, results, or definitions. If it turns out to, that is a finding worth recording
  rather than absorbing.
- **Threads take their shape from this surface.** 011 deliberately did not model them,
  recording that a persistence model built without a consumer is a shape guessed rather
  than derived. This feature is that consumer, and the shape is therefore this feature's to
  settle.
- **The parity row grows again.** 011's clarification recorded that deferring threads means
  the row grows twice rather than once, and that it binds both times. This is the second
  time.
- **"Sees progress without polling" is a user-facing claim, not a transport choice.** How
  the conversation stays current is a design decision, not a requirement — the requirement
  is that the person does not refresh.
- **No new authorization concepts.** Every refusal in this surface is one the core already
  makes. If the portal needs a decision the core cannot express, that is a finding about the
  core, not a portal feature.
- **This feature is large enough to warrant splitting, and that call belongs to planning.**
  The clarifications chose the largest option twice: a full product UI and all three
  conversation classes. By this repository's own precedent that is roughly three features —
  ADR-0033 split four transports into four features precisely because building several
  surfaces in one pass means getting parity right across things that are all still moving.
  The story priorities encode the seam: **P1–P2 (US1–US4) is a portal that governs actions
  and is deliverable alone; P3 (US6) adds estate-state answering; P4 (US7) adds grounded
  guidance and the corpus it needs.** Planning should sequence these as increments rather
  than one landing, and if it concludes P4 should be its own numbered feature, that is a
  finding worth acting on rather than absorbing.
- **The corpus is sourced: HashiCorp Validated Patterns.** Named 2026-07-29, and it closes
  what this section previously recorded as US7's *unsourced* dependency —
  [developer.hashicorp.com/validated-patterns](https://developer.hashicorp.com/validated-patterns),
  33 field-tested documents (Vault 15, Terraform 12, Packer 4, Nomad 1, Boundary 1) over
  exactly the estate this platform governs. It is still unbuilt: no ingestion path exists.
  Four properties, checked against the documents rather than assumed, because each shapes
  the work:

  1. **Stable per-section anchors**, so FR-024's citation can resolve to a section rather
     than a page — which is the difference between a citation a person can check and one
     they have to search.
  2. **No publication date, no revision date, no version, anywhere.** US7's third scenario —
     "a corpus document changes, the answer reflects the current one" — therefore cannot be
     satisfied from metadata. Change detection has to be content-based. This is the single
     most consequential fact about the source and it is invisible until you look.
  3. **Section counts vary from 8 to 29**, so chunking cannot assume a uniform document
     shape.
  4. **Named authors, no editorial version.** Attribution is available; provenance over time
     is not.

- **Terms of use for ingesting the corpus are unresolved.** Serving answers derived from a
  vendor's documentation is a different act from linking to it, and this feature does the
  former. Flagged for planning rather than assumed either way.
- **Accessibility is a new gate class.** Every quality gate this platform has is about
  governance, authority, or durability. An accessibility gate asserts something about a
  rendered interface, which no existing lane can run.

## Out of Scope

- Capability packs, real brokered credential translation, and RFC 8693 + RAR authority
  manufacture — each its own roadmap entry.
- Multi-tenancy. The registry is one per deployment and carries no tenant of its own
  (011's FR-013a); this feature inherits that limit rather than closing it.
- The CLI, tabled 2026-07-28.
- Any general-purpose assistant capability. ADR-0034 is explicit that scope is enforced,
  and an unbounded assistant is the failure mode it names.
