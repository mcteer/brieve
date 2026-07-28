# Feature Specification: Northbound API Operations

**Feature Branch**: `spec/011-api-operations`

**Path**: `specs/011-api-operations/spec.md`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Widen the northbound API to the operations its consumers actually need. Four operations exist. A pending authority change cannot be collected, runs cannot be listed, a run's output cannot be retrieved, a run cannot be stopped, agent definitions cannot be enumerated, and threads have no representation. Every operation lands on both transports."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R15 (four transports, one authorization core — every operation added here lands on both implemented surfaces or fails the parity row). R2 / R3 (per-task authority — the authenticated human remains the subject of every operation, including the new reads). R7 (fail-closed — a read that cannot establish scope refuses rather than returning less). R4 / R10 / R13 (evidence — these operations are audited like every other, and one of them *is* an evidence read). |
| **ADRs touched** | **ADR-0033** (the parity row grows with the catalogue rather than being satisfied by a smaller comparison), **ADR-0034** (the portal is the consumer these operations exist for; threads are its state), ADR-0035 (evidence stays a read path that cannot mutate or mask), ADR-0016 (collecting an authority decision is a read and must not become a way to make one), ADR-0049 (stopping a run must not reintroduce the human-in-the-loop pause it removed), ADR-0050 (agent definitions are real records now, which is what makes enumerating them meaningful). |
| **Evidence class** | **Audit-critical, and newly so in one direction.** Most of this feature adds *reads*, and 008 established that reading evidence is itself audited. Listing runs and enumerating definitions are new read classes over data that has never been enumerable — a tenant boundary that held for a single-record lookup has to hold for a list, which is a different question. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A requester learns what happened to their authority change (Priority: P1)

Someone requests a claim-to-role mapping change. Control Groups gate it. Later, they ask
the platform whether it was approved, and the platform tells them.

**Why this priority**: It is the only gap in this feature that is a **defect rather than an
absence**. 008 reasoned explicitly about returning 202 rather than 403 — *"a client that
reads 403 stops asking, so a change approved twenty minutes later is never collected"* — and
then shipped no operation to ask again. The design anticipated the exact failure it caused.

Every other gap here is work nobody has done. This one is work that was argued for and then
not done, which makes it both the smallest and the most clearly owed.

**Independent Test**: Submit a mapping change that gates, approve it out of band, and assert
the requester can observe the disposition change from pending to approved without being told.

**Acceptance Scenarios**:

1. **Given** a submitted change still awaiting quorum, **When** the requester asks, **Then**
   they are told it is pending — not that it failed, and not that it does not exist.
2. **Given** a change approved after submission, **When** the requester asks, **Then** they
   are told it was approved, with no out-of-band notification required.
3. **Given** a change submitted by someone else in another tenant, **When** a requester asks
   for it, **Then** the platform answers as it would for a change that does not exist. The
   existence of another tenant's request is itself information.
4. **Given** the collect operation, **When** anyone calls it, **Then** it **cannot approve,
   deny, or advance** anything. Reading a decision must never become a way to make one.

---

### User Story 2 — A person sees the work they have started (Priority: P2)

Someone returns to the platform and asks what runs they have started. They get their runs.

**Why this priority**: `GET /runs/{run_id}` requires already knowing the id, which is
precisely what a returning user does not have. Without this, every consumer must keep its
own record of ids it has seen — which means the platform's account of what happened and the
client's disagree the moment a client loses state, and the platform's is the one that is
supposed to be authoritative.

**Independent Test**: Start three runs as one subject and one as another, list as the first
subject, and assert exactly three come back.

**Acceptance Scenarios**:

1. **Given** runs started by this subject in this tenant, **When** they list, **Then** they
   see those runs and no others.
2. **Given** runs in another tenant, **When** a subject lists, **Then** those runs are
   absent — and the response does not reveal that anything was withheld.
3. **Given** more runs than one response should carry, **When** a subject lists, **Then**
   the result is bounded and the caller can obtain the rest without the platform holding
   per-caller state between calls.
4. **Given** a subject with no runs, **When** they list, **Then** they get an empty result
   rather than an error. Nothing to show is an answer.

---

### User Story 3 — A person sees what a run produced (Priority: P3)

A run finishes. The person who started it asks what it produced, and gets the result rather
than a trail to reconstruct it from.

**Why this priority**: Today the only path to a run's output is reading its evidence and
reassembling it. That is a **forensic** path — it exists so an investigator can determine
what happened — and using it as the product path puts the burden of interpretation on every
client, guarantees each one interprets slightly differently, and makes the audit trail's
shape a compatibility surface.

**Independent Test**: Complete a run with a known result, retrieve it, and assert it comes
back without the caller parsing audit entries.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** its subject asks for the result, **Then** they get it.
2. **Given** a run that is still executing, **When** its subject asks, **Then** they are told
   it is not finished — distinguishable from a run that finished and produced nothing.
3. **Given** a run that stopped or was refused, **When** its subject asks, **Then** they get
   the disposition and the reason, not an empty result. A run that failed is not a run that
   returned nothing.
4. **Given** a run in another tenant, **When** someone asks for its result, **Then** the
   platform answers as it would for a run that does not exist.

---

### User Story 4 — A person can stop a run they started (Priority: P4)

Someone starts a run they did not mean to start, and ends it.

**Why this priority**: The most delicate operation in this feature, and the reason it is not
higher. ADR-0049 removed parking and made suspension automatic on the principle that
**consent to start a run is consent to finish it** and no run waits on a human. A stop
operation is in obvious tension with that, and implemented carelessly it becomes the pause
that ADR-0049 deliberately removed — wearing a different name.

The distinction that resolves it: ADR-0049 forbids a run *waiting* on a human. It does not
forbid a human **withdrawing** their own request. Stopping is terminal and unilateral; it
is not a hold, it does not await anything, and nothing resumes afterwards.

**Independent Test**: Start a long run, stop it, and assert it reaches a terminal state with
the reason recorded and nothing waiting on anyone.

**Acceptance Scenarios**:

1. **Given** a run this subject started, **When** they stop it, **Then** it reaches a
   terminal state with the reason recorded as a deliberate stop by that person.
2. **Given** a stopped run, **When** anything examines it, **Then** it is **not resumable**
   and no sweeper will resume it. A stop that could be undone by a recovering dependency
   would be a pause.
3. **Given** a run started by someone else, **When** a subject tries to stop it, **Then**
   they are refused. Withdrawing consent is something only the person who gave it can do.
4. **Given** a run already terminal, **When** a subject stops it, **Then** the operation
   reports the existing state rather than failing — asking twice is not an error.
5. **Given** a stop, **When** the audit trail is read, **Then** the stop is attributable to
   the person who requested it and distinguishable from a stop caused by a bound.

---

### User Story 5 — A person sees which agents they may start (Priority: P5)

Someone asks what agents exist and which they can use, and gets an answer shaped by their
own authority.

**Why this priority**: 010 made agent definitions real — registered in the trust fabric with
ceilings an operator authored — and nothing exposes them. So the first thing a new user
needs is the one thing the platform cannot answer, and every consumer hardcodes a list or
asks a human.

It is P5 rather than higher because a consumer can function with a configured list, badly.
The others have no workaround at all.

**Independent Test**: Enumerate definitions as two subjects with different roles and assert
the results differ according to what each may actually start.

**Acceptance Scenarios**:

1. **Given** registered definitions, **When** a subject enumerates, **Then** they see the
   ones they could start.
2. **Given** a definition whose ceiling excludes everything this subject's scope permits,
   **When** they enumerate, **Then** the platform is clear about whether they may start it —
   an entry a person cannot use, presented without qualification, is worse than its absence.
3. **Given** enumeration, **When** the response is examined, **Then** it exposes **no
   credential-issuance detail** — no policy names, no secret paths. Those are the other
   jurisdiction (ADR-0044/ADR-0050) and are nobody's business on this surface.

---

### User Story 6 — A conversation survives (Priority: P6)

Someone has a conversation with the platform, closes the tab, comes back, and the
conversation is still there.

**Why this priority**: ADR-0034 makes threads tenant-scoped run state, persisted like any
other run state and auditable by correlation ID. It is last because it is the only story
whose consumer does not exist yet — the portal is its own feature — and building a thread
model before the thing that uses it is how a shape gets guessed wrong.

**It may belong in the portal's feature rather than here**, and that is a live question this
spec does not settle on its own; see the clarification below.

**Independent Test**: Create a thread, add to it, retrieve it in a separate session, and
assert its correlation ID ties it to the audit trail.

**Acceptance Scenarios**:

1. **Given** a thread, **When** it is retrieved later, **Then** its contents are intact.
2. **Given** a thread, **When** the audit trail is read by its correlation ID, **Then** the
   thread's activity is there — it is run state, not a separate log.
3. **Given** a thread in another tenant, **When** someone retrieves it, **Then** the platform
   answers as it would for one that does not exist.

---

### Edge Cases

- **A list that spans tenants.** Every read here is newly enumerable, and a boundary that
  held for "fetch this id" is not automatically a boundary that holds for "fetch all". The
  count is information too: a response that returns fewer results without saying so is
  correct, and one that says "3 of 7 withheld" has leaked the 7.
- **A run whose result is enormous.** Retrieval has to bound what it returns without
  silently truncating — a truncated result presented as complete is worse than a refusal.
- **Stopping a suspended run.** It is waiting on a dependency and a person wants it gone.
  The stop must win, and the sweeper must not later resume what a person ended.
- **Stopping a run that finishes concurrently.** Both are legitimate outcomes; the record
  must show one, not both.
- **A definition removed from the registry between enumeration and use.** Someone starts an
  agent that existed a moment ago.
- **Enumerating with no definitions registered.** Empty is an answer, not an error.
- **A collect on a change whose approvers have not acted.** Indefinitely pending is a
  legitimate state, and it must not look like failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A requester MUST be able to obtain the current disposition of an authority
  change they submitted, without out-of-band notification.
- **FR-002**: Collecting a disposition MUST be read-only. It MUST NOT approve, deny,
  advance, or otherwise alter the change, and MUST NOT count as an approval.
- **FR-003**: A subject MUST be able to list the runs they started within their tenant.
- **FR-004**: Every enumerable read MUST be tenant-scoped, and MUST NOT disclose that
  results were withheld — including by count, by pagination artefact, or by error class.
- **FR-005**: Enumerable reads MUST bound their response size and provide a way to obtain
  the remainder that does not require the platform to hold per-caller state between calls.
- **FR-006**: A subject MUST be able to retrieve what a run produced, without parsing the
  audit trail.
- **FR-007**: Retrieval MUST distinguish *not finished*, *finished with a result*, and
  *ended without one* — three states that a single empty response would conflate.
- **FR-008**: A subject MUST be able to stop a run they started, and the run MUST reach a
  **terminal** state.
- **FR-009**: A stopped run MUST NOT be resumable, and MUST NOT be resumed by the dependency
  sweeper. A stop that a recovering dependency could undo is a pause, which ADR-0049 removed.
- **FR-010**: Only the subject who started a run may stop it. Withdrawing consent is
  available only to whoever gave it.
- **FR-011**: Stopping an already-terminal run MUST report the existing state rather than
  failing. Asking twice is not an error.
- **FR-012**: A stop MUST be attributable in the audit trail to the person who requested it,
  and distinguishable from a stop caused by an execution bound.
- **FR-013**: A subject MUST be able to enumerate agent definitions, with the result shaped
  by what that subject may actually start.
- **FR-014**: Enumeration MUST NOT expose credential-issuance detail — policy names, secret
  paths, or anything from the other jurisdiction (ADR-0050).
- **FR-015**: **Every operation added by this feature MUST exist on both implemented
  transports** and MUST be recorded in the operations snapshot. An operation on one surface
  only fails the parity row, which is the correct outcome.
- **FR-016**: Every operation MUST authenticate the human against the organization's identity
  provider, and no static credential may appear on any path.
- **FR-017**: Every operation MUST be audited, and reads of evidence MUST remain audited as
  008 established.
- **FR-018**: Every operation MUST fail closed. A read that cannot establish the caller's
  scope MUST refuse rather than return a smaller result.
- **FR-019**: The parity row MUST be asserted over the **grown** catalogue. A comparison that
  still covers four operations after this feature would pass while testing a fraction of the
  surface.
- **FR-020**: Refusals MUST distinguish *no such thing*, *not yours*, and *not permitted* in
  the record — while presenting *not yours* indistinguishably from *no such thing* to the
  caller. The audit trail and the response answer different questions.

### Key Entities

- **Authority change record**: A submitted change, its requester, and its current
  disposition. Exists; nothing can read it back.
- **Run summary**: What a listing returns per run — enough to identify and choose, not the
  full state. Deliberately smaller than a run's detail.
- **Run result**: What a run produced, with its disposition. New; today only reconstructible
  from evidence.
- **Agent definition (public view)**: Display name, description, owner, and whether this
  subject may start it. **Not** its ceiling policies or paths.
- **Thread**: Tenant-scoped conversational run state, auditable by correlation ID (ADR-0034).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A requester can determine the outcome of an authority change they submitted
  with zero out-of-band communication.
- **SC-002**: A returning subject can enumerate their runs without having retained any
  identifier from a previous session.
- **SC-003**: 100% of enumerable reads return only the caller's tenant, and zero responses
  disclose the existence of withheld results.
- **SC-004**: A run's result is obtainable without the caller reading a single audit entry.
- **SC-005**: The three completion states — unfinished, finished with a result, ended without
  one — are distinguishable in 100% of cases.
- **SC-006**: A stopped run reaches a terminal state, and zero stopped runs are resumed by
  the sweeper.
- **SC-007**: Zero runs can be stopped by a subject other than the one who started them.
- **SC-008**: Two subjects with different authority enumerating definitions receive
  measurably different results.
- **SC-009**: Zero enumeration responses contain credential-issuance detail.
- **SC-010**: The operations snapshot grows by every operation this feature adds, and the
  parity row asserts over the grown set — verified by the row failing when an operation is
  added to one transport only.
- **SC-011**: Every operation appears in the audit trail attributed to the authenticated
  human.

## Assumptions

- **The portal is the consumer these exist for**, and it is a separate feature. This one
  widens the catalogue; nothing here renders anything.
- **The CLI is tabled** (2026-07-28), so "both transports" means API and MCP, and the parity
  row binds across that pair.
- **Threads are run state**, per ADR-0034 — not a new persistence concept. If they need one,
  that is a finding for the plan rather than an assumption here.
- **Stopping is withdrawal, not pausing.** ADR-0049 forbids a run *waiting* on a human; it
  does not forbid a person ending their own request. This spec treats that as settled and
  states it plainly enough to be argued with.
- **Enumerable reads are new attack surface** in a way single-record reads were not, and the
  tenant boundary needs asserting again rather than inheriting.
- **Existing operations do not change.** Nothing here alters the four that exist; if one has
  to change, that is a sealed-core-adjacent decision the plan should surface.

## Needs Clarification

- **C1 — Do threads belong in this feature?** [NEEDS CLARIFICATION: User Story 6 is the only
  story whose consumer does not exist yet. Building a thread model before the portal that
  uses it risks guessing the shape wrong; deferring it means the portal feature carries both
  its own surface and a new operation class. Which?]
- **C2 — What does "may start it" mean for enumeration?** [NEEDS CLARIFICATION: A definition
  a subject cannot start could be omitted, or returned with a flag. Omitting is simpler and
  leaks less; flagging tells a person what exists so they can request access, which is the
  difference between a platform that helps them ask and one that pretends nothing is there.]
- **C3 — Does stopping cancel in-flight work, or only prevent further steps?**
  [NEEDS CLARIFICATION: ADR-0049 makes a run's container end when its work ends. A stop that only
  prevents the *next* step is simpler and leaves the current one to finish; one that ends the
  allocation is faster and interacts with the intent-and-result bracketing 005 built for
  exactly this ambiguity.]

## Out of scope

- The conversational portal itself (ADR-0034 — its own feature).
- The CLI transport (tabled 2026-07-28).
- Capability packs and eval gates.
- Brokered credential translation, and RFC 8693 + RAR authority manufacture — both recorded
  as roadmap gaps by 010.
- Changing any of the four operations that exist.
- Row-level security on the evidence store, which remains its own recorded gap.
