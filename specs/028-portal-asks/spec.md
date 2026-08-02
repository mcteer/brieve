# Feature Specification: The portal learns to ask

**Feature Branch**: `spec/028-portal-asks`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "The portal learns to ask — the deferral four features have carried, and the surface where a person actually is."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R10** (observability — a person asking through the portal must be as visible in the trail as one asking through MCP). **R2/R3** are consumed rather than extended: the credential is brokered by the API surface (027) and nothing about it changes here. |
| **ADRs touched** | **ADR-0034** — **the load-bearing one**: the portal is a thin client that relays to the API as the signed-in person and holds no business logic. This feature tests whether that still holds when the thing being relayed is slow and shaped four different ways. **ADR-0039** (*ask answers, it never acts*) — inherited structurally, because the portal reaches the API and the API's ask path holds no tool. **ADR-0035** (estate answers bounded by the asker's own entitlements) — consumed. **ADR-0018** (grounded reporting — the same discipline applied to an answer). **None amended, expected.** |
| **Evidence class** | **Operational, with an attestation-relevant edge.** The answer is not evidence, but *who asked and what they were shown* is — and this is the first surface where the person reading an answer is not the person who composed the request. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Someone signs in and asks a question (Priority: P1)

A person opens the portal, signs in the way they already do to see their threads, types a question,
and gets an answer whose every claim they can check.

**Why this priority**: it is the whole feature, and it closes a deferral four features have carried.
024 built answering and recorded *"not through the portal, and that is a scope decision rather than
an oversight"*. 025 extended it to the estate, 026 governed it, 027 made it work in a deployment —
and on 2026-08-02 a real question through the served surface returned a cited answer. Every one of
those features left the capability reachable only by someone holding an MCP client or a bearer token
and a command line, which is not the person the portal exists for.

**Independent Test**: sign in, ask a question the corpus supports, read an answer where every claim
carries a citation that resolves.

**Acceptance Scenarios**:

1. **Given** a signed-in person, **When** they ask a question the pinned guidance supports, **Then**
   they are shown claims with citations they can follow to the source.
2. **Given** a signed-in person, **When** they ask about their own estate, **Then** they are shown
   claims resting on records **they** were entitled to read, and the answer says which records.
3. **Given** a question that fits neither source, **When** it is asked, **Then** the person is told
   both doors were considered and neither fits — never that the documentation does not cover a
   question about their estate.

---

### User Story 2 - The person is told what happened, not that something went wrong (Priority: P2)

An ask can fail in ways that send different people to different places. Whoever is looking at the
page learns which.

**Why this priority**: three features' work is discarded the moment the portal renders one page for
every failure. 027 made `unqualified_cell` (nobody has qualified a model for this), 
`credential_unavailable` (the platform holds no authority to call the vendor) and
`provider_unavailable` (the vendor did not answer) distinguishable in the trail, and each names a
different person to go to. A portal that flattens them re-creates, at the surface a human actually
reads, the exact confusion the platform spent a feature removing underneath.

**Independent Test**: arrange each failure and read the page; the three are distinguishable without
opening a log.

**Acceptance Scenarios**:

1. **Given** an ask refused because no model is qualified, **When** the page renders, **Then** it
   says so in terms an operator can act on, and does not suggest the platform is broken.
2. **Given** an ask refused because the platform holds no authority to call the vendor, **When** the
   page renders, **Then** it is distinguishable from the above and from an outage.
3. **Given** the API cannot be reached at all, **When** the page renders, **Then** the person is
   told the platform could not be asked — never shown an empty or successful-looking answer.

---

### User Story 3 - Asking leaves the same trace as asking anywhere else (Priority: P3)

A person asking through the portal is as visible to an investigator as one asking through MCP.

**Why this priority**: it delivers nothing a user sees, and it is what keeps the portal from becoming
a way to ask unobserved. 022 established that a read leaves a record; the portal has no exemption,
and a surface that quietly did would be the most attractive one to use.

**Independent Test**: ask through the portal, then read the trail — the record names the person who
signed in, not the portal.

**Acceptance Scenarios**:

1. **Given** a portal ask, **When** the trail is read, **Then** the record carries the signed-in
   person's own identity and is indistinguishable in kind from an ask made through another surface.
2. **Given** a portal ask that is refused, **When** the trail is read, **Then** the refusal is
   recorded too — a boundary a person can probe without trace is what 022 removed.

---

### Edge Cases

- **An answer takes far longer than any other portal page.** Measured 2026-08-02: roughly two
  minutes, because the model reasons before it answers and retrieval runs over an 856K corpus. Every
  other portal request completes in a second or two, and the portal's shared patience is ten seconds
  — chosen deliberately, because *"a page that hangs teaches people to reload, which turns one slow
  request into several"*. Whatever this feature does must not spend an ask's patience on a thread
  listing.
- **A person reloads, or asks twice.** A question is not an act, so asking again is safe — but each
  ask costs a real model call and leaves its own record, and the page must not invite that by looking
  broken while it is working.
- **An estate answer's references are not links.** A guidance citation resolves to a documentation
  URL; an estate reference is a record's content hash. Rendering a hash as a link produces a dead
  one; hiding it leaves a claim resting on something the reader cannot check.
- **The person's scope is empty.** They are entitled to see no records, so an estate ask has nothing
  it may rest on. That is a refusal with a cause, not an empty answer.
- **The answer is a decline.** The corpus genuinely does not cover the question. This must not look
  like a failure, because it is the platform being honest.

## Requirements *(mandatory)*

### Asking

- **FR-001**: A signed-in person MUST be able to ask a question from the portal and be shown the
  answer, without holding a token, running a command, or knowing which source will answer.
- **FR-002**: The portal MUST NOT decide anything about the ask. Routing between guidance and estate,
  governance, scope, and the credential all stay where they are (ADR-0034): the portal relays as the
  signed-in person and renders what it is told.
- **FR-003**: The portal MUST NOT acquire a way to act as a consequence of this feature. Asking
  answers and never acts (ADR-0039), and that must remain **structural** — a property of what this
  path can reach, not of an instruction given to a model.

### Waiting

- **FR-004**: An ask MUST be able to take substantially longer than any other portal operation
  without the person being shown a failure, and **without extending any other operation's patience**.
  The ask carries **its own patience**; every other operation keeps the ten seconds that exists for a
  stated reason.

  **Rejected: raising the shared timeout.** One number covering both would apply an ask's patience to
  a thread listing, so a listing against a wedged API would hang for two minutes instead of failing
  in ten — turning a deliberate choice into collateral damage from an unrelated feature.

  **Rejected for now: submit-then-poll.** It is the better experience and matches the precedent
  `events.py` already sets, and it requires the API to hold an in-flight ask, which it has no way to
  do — FR-014 says that is a finding to surface rather than a change to make quietly. Recorded as the
  next shape rather than dismissed.
- **FR-005**: While an ask is outstanding, the person MUST be able to tell it is working, so a slow
  answer does not read as a broken page and invite a reload that costs a second model call.
- **FR-005a**: The person MUST be told, before they wait, that an answer takes a while. A two-minute
  wait nobody warned them about is indistinguishable from a hang, and the reload it invites costs a
  real model call and leaves a second record.

### Rendering what came back

- **FR-006**: A guidance answer MUST render each claim with its citations, and each citation MUST be
  followable to the source it names.
- **FR-007**: An estate answer MUST render each claim with the records it rests on, identified so a
  person can carry the identifier to whoever can show them the record. It MUST NOT present a record
  reference as a followable link when it is not one.
- **FR-008**: A decline MUST be presented as an answer rather than a failure, and MUST name which
  source was consulted — so nobody who asked about their estate is told the documentation does not
  cover it.
- **FR-009**: The three refusal causes MUST be distinguishable to the person reading the page, in
  terms naming what to do rather than what broke.
- **FR-010**: An unreachable API MUST be distinguishable from any refusal. The platform declining and
  the platform being unaskable are different facts, and the portal already draws that line for every
  other operation.

### What must remain true

- **FR-011**: The record of a portal ask MUST carry the **signed-in person's** identity, not the
  portal's, and MUST be indistinguishable in kind from an ask made through any other surface.
- **FR-012**: No credential MUST reach the browser. The vendor credential never leaves the enclave
  and the person's session stays server-side — unchanged by this feature, and asserted because a new
  page is exactly where that would slip.
- **FR-013**: The question and the answer MUST NOT be written to the trail. The record carries the
  shape of an ask and never its content, for the reason 024 established: the corpus is somebody
  else's copyrighted documentation, and an append-only trail is the wrong place for it.
- **FR-014**: Nothing about the API's ask operation MUST change. If this feature needs the API to
  behave differently, that is a finding worth surfacing rather than a change to make quietly.

### Where asking lives

- **FR-015**: Asking MUST live on **its own page**, reachable from the portal's index, and MUST NOT
  be a kind of turn inside a thread.

  **The reason is the never-acts boundary, not layout.** A thread is where turns *act*; an ask never
  does. Putting them in one surface would make the difference a property of which button was pressed
  — legible to whoever wrote the code and invisible to the person using it. Separate pages keep
  ADR-0039's rule something a person can see rather than something they must be told.

  Accepted cost: two places to type a question.

### Key Entities

- **Question**: what a person typed. Never stored by the portal, never written to the trail.
- **Answer**: claims, each carrying either citations (guidance) or record references (estate), plus a
  disposition saying whether it was answered, declined, or refused.
- **Disposition**: what happened, in the vocabulary the platform already uses — the thing the page
  must render faithfully rather than summarise.

## Clarifications

### Session 2026-08-02

- Q: The portal's shared patience is ten seconds and a measured answer took roughly two minutes —
  how should it wait? → A: **Per-operation patience.** The ask gets its own, longer allowance and
  every other operation keeps the ten seconds it has for a stated reason. Submit-then-poll is the
  better experience and is deferred rather than dismissed: it needs the API to hold an in-flight ask,
  which it cannot do today, and FR-014 says that is a finding to surface rather than a change to make
  quietly. Streaming was rejected on a correctness ground rather than a cost one — citations resolve
  against the pin *after* the model finishes, so streamed text would show a person claims the pin may
  yet reject.
- Q: Where does asking live? → A: **Its own page**, not a kind of turn inside a thread. A thread is
  where turns act; an ask never does, and one surface holding both would make that difference a
  property of which button was pressed.

## Success Criteria *(mandatory)*

- **SC-001**: A person who can sign in can ask a question and read a cited answer using nothing but a
  browser.
- **SC-002**: Every claim shown carries something the reader can check — a citation that resolves, or
  a record reference they can take to someone who can show them the record.
- **SC-003**: The three refusal causes and an unreachable platform are four distinguishable outcomes
  on the page, not one.
- **SC-004**: A slow answer never presents as a failure, and **no other portal page becomes slower** —
  the second half is the measurable one, and it is what makes per-operation patience a design rather
  than a raised number.
- **SC-005**: A portal ask is visible in the trail under the asker's own identity, and a refused one
  is visible too.
- **SC-006**: Neither the question nor the answer appears in the trail.
- **SC-007**: The portal gains no capability to act.

## Assumptions

- **The API's ask operation is finished and works.** Demonstrated 2026-08-02 through the served
  surface: a real question returned a cited answer, and the record carried the asker, the authorising
  cell, and the credential's rotation generation. This feature relays to it; it does not extend it.
- **The portal already knows how to render a governed refusal.** It distinguishes *the platform
  decided* from *the platform could not be asked* for every existing operation, which is exactly the
  distinction an ask needs — so this extends an established pattern rather than inventing one.
- **The corpus is pinned and reachable from the deployed surfaces.** True as of 2026-08-02, and only
  since then: no deployed surface shipped a corpus before that.
- **A question is not an act**, so asking twice is safe. It is not free — each ask costs a real model
  call and leaves a record.
- **Deferred and NOT in scope**: corpus refresh scheduling, ADR-0035's team-granularity scope,
  per-tenant model scope (027's, and new), and promoting any further matrix cell.
