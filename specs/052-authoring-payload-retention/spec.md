# Feature Specification: A finished authoring run leaves no proposal behind

**Feature Branch**: `052-authoring-payload-retention`

**Created**: 2026-08-27

**Status**: Draft

**Input**: Issue [#219](https://github.com/mcteer/brieve/issues/219). 041's FR-033 says a
finished authoring run leaves no subject content in the control plane.
`scrub_authoring_requests` delivers half of it — at terminal state it clears
`intents.arguments` for `author_file`, the tool whose arguments are a customer's file bodies.
The other half was never closed: the composed proposal is also written to
`checkpoints.payload`, and nothing clears it.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4 / R13 (evidence)** — the scrub must not remove what an attestation rests on; a run whose proposal cannot be reconstructed afterwards has traded one liability for another. **R7 (fail-closed)** — a scrub that cannot complete must stop and say so, never report a clean run over content it left behind. **R16 (sealed core, versioned seams)** — clearing a stored payload is a durability-provider concern, and the seam is versioned |
| **ADRs touched** | **ADR-0024** (durability is a provider seam — a scrub is a provider capability, not something a caller reaches into a store to do). **ADR-0026** (per-step tokens and resume-as-re-observation — the open/closed-bracket reasoning that made 041's intents scrub safe is what this feature must redo for a payload). **ADR-0018** (reports are compiled from records — so whatever survives the scrub has to be enough to compile one). **ADR-0038** (the agent authors and a person merges — the pull request is the durable artifact, and that is what makes clearing the platform's copy possible at all). **ADR-0047** (the conformance row reporting this is blocking from the moment its feature exists) |
| **Evidence class** | **attestation-relevant** — this deletes content that a run record currently contains, so what remains must still support a RunReport and a reviewer's reconstruction |

## Clarifications

### Session 2026-08-27

- Q: When is it safe to clear the payload? → **A: at the run's terminal state**, the same
  trigger the intents scrub uses. The reasoning is different from 041's and had to be
  established rather than inherited: the proposer handoff writes a **non-terminal** checkpoint,
  and terminal is reached only after `open_proposal` succeeds. So a run that can still resume
  has not been scrubbed, and a run that has been scrubbed will not resume — which is 040's
  open/closed-bracket property arriving at the same answer by a different route.
  **A run that never reaches terminal state is therefore never scrubbed**, and that gap is
  recorded rather than closed here (FR-011).
- Q: What exactly is cleared? → **A: the authored file bodies and the model-authored
  rationale.** Both are derived from the customer's repository. FR-032 already classes the
  rationale as content subject to the same containment the files get, so leaving it would
  contradict a decision this platform has already taken. Title and usage stay: they are prose
  *about* the change rather than extracts *from* it.
- Q: What must remain reconstructible? → **A: a path-and-digest manifest.** Each file keeps its
  path and the content digest the proposal's provenance already records. A reviewer can prove
  the merged pull request is byte-identical to what the run proposed while the platform holds
  none of the content. The cost is accepted deliberately: a path list is a partial fingerprint
  of the customer's tree, and it is the smallest thing that keeps the run self-describing.

### Session 2026-08-27 — `/speckit-analyze` remediation

- **FR-007** asked for something unobservable. A run refused at Judge returns before Propose and
  never composes a proposal, so a row asserting the scrub cleared it would pass without
  exercising anything. Restated as the property that can actually fail.
- **FR-014** described work that had already merged in #220. Restated as the non-regression
  obligation that remains.
- **FR-015** added. The backfill was designed in the plan and required by nothing: SC-001 admits
  no exception for content that predates the fix, and the acceptance row sweeps the whole store.
- **FR-011** sharpened. Its obligation — that the never-terminal gap is recorded — was
  dischargeable only by this document, which nobody reads while reading the code.

### Session 2026-08-27 — found at implementation

- **FR-008** widened to clear `usage`. Not a preference: the first acceptance sweep after the
  backfill failed on a `usage` field carrying a shell transcript with a credential-shaped
  assignment. Two analyze passes did not find this, because neither ran the sweep.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A completed Build leaves no copy of what it wrote (Priority: P1)

A person runs a Build against their private repository. The agent reads it, authors files, and
opens a pull request. When the run finishes, the platform's control plane holds no copy of the
file bodies it authored. The customer's content lives in the customer's repository and in the
pull request they can close, and nowhere the platform operator can read it indefinitely.

**Why this priority**: This is the requirement 041 wrote and did not finish. Everything else in
this feature is about not breaking something while closing it. A run observed today
(`propose-1df2fcf1bfa9663b`, state `completed`) still holds its whole authored file set,
including a generated test file, in the state store.

**Independent Test**: Complete a Build against a subject repository containing a distinctive
marker. Query the state store for that marker after the run reaches terminal state. Assert it
is absent. Assert it was present before the scrub ran, so the row can lose.

**Acceptance Scenarios**:

1. **Given** a Build that authored files and opened a pull request, **When** the run reaches
   terminal state, **Then** no authored file body remains in the state store.
2. **Given** a Build that authored files and was refused at Judge, **When** the run reaches
   terminal state, **Then** no authored file body remains — a refused proposal is content the
   platform has even less reason to keep.
3. **Given** a Build that authored nothing, **When** it finishes, **Then** the scrub completes
   without error and clears nothing.

---

### User Story 2 - The run stays attestable after its content is gone (Priority: P1)

An auditor reading a completed run's records six months later can still establish what the run
proposed, which files it touched, and that the proposal was the one the pull request carries —
without the file bodies being present.

**Why this priority**: **Equal first with US1, not second.** A scrub that satisfied US1 alone
would trade a retention gap for an attestation one, which is the trade ADR-0018 and Principle
IX exist to refuse. Shipping US1 without this is worse than shipping neither: the content is
gone *and* nobody can say what happened.

**Independent Test**: Compile a RunReport from a scrubbed run's records. Assert it validates
and names what was proposed. Assert the same report compiled before the scrub says the same
things about paths and outcome.

**Acceptance Scenarios**:

1. **Given** a scrubbed run, **When** a RunReport is compiled from its records, **Then** the
   report validates and states which paths were authored and how the run ended.
2. **Given** a scrubbed run, **When** an auditor reads the trail, **Then** the pull request the
   run opened is identifiable from the record.
3. **Given** a scrubbed run, **When** a report is compiled, **Then** it does not claim to carry
   content it no longer has.

---

### User Story 3 - An interrupted proposal still completes (Priority: P1)

A Build's proposer task is killed after Judge completes and before the pull request is opened.
The run resumes and opens the pull request with the same content it composed, unchanged.

**Why this priority**: **Also first, because it is the way this feature breaks the platform.**
041's intents scrub was safe because 040 had already established that resume reads arguments
only for pending steps. That reasoning does not transfer: the proposer reads the composed
proposal from the payload *after* Judge, and the checkpoint at that handoff is deliberately
non-terminal. A scrub that ran too early would make an interrupted publish resume with nothing
to publish — a durability defect wearing a retention fix's clothes, which is exactly what 041
warned about in the other direction.

**Independent Test**: Kill a run between Judge and `open_proposal`. Resume. Assert the pull
request opens carrying the same files, and that the scrub did not run before the resume.

**Acceptance Scenarios**:

1. **Given** a run killed between Judge and publish, **When** it resumes, **Then** the proposal
   is intact and the pull request opens with the composed content.
2. **Given** a run that has not reached terminal state, **When** the store is inspected, **Then**
   the payload still carries what a resumption needs.
3. **Given** a run whose publish failed terminally, **When** the run ends, **Then** the payload
   is scrubbed — a run that will not resume has no claim on the content.

---

### Edge Cases

- **The proposer is still reading when the scrub fires.** The narrowest failure and the one
  that would present as a mysterious empty pull request.
- **A scrub that partially completes.** Some rows cleared, some not, and the run reports clean.
  Worse than not scrubbing: the record says the content is gone and it is not.
- **The provider does not support clearing a payload.** 041 met this and answered it — an older
  provider is a deployment fact, not a reason to fail work already done — and the same answer
  may not be right here, because failing quietly leaves customer content behind.
- **A run that never reaches terminal state.** Killed, abandoned, or parked on a dependency
  that never recovers. Its payload is never scrubbed by a terminal-state trigger, and it holds
  exactly the content this feature exists to remove.
- **A resumed run scrubbed by its predecessor.** Two allocations, one run: if the first is
  declared terminal while the second is live, the second finds nothing.
- **The audit trail's own copy.** FR-013 refused the trail a copy nobody can delete. If the
  proposal reached the trail as well as the payload, this feature closes one door and leaves
  another, exactly as 041 did.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A finished authoring run's stored payload MUST NOT retain the file bodies it
  authored. This completes FR-033 rather than restating it: FR-033's obligation is already in
  force and is currently satisfied for one of the two places the content rests.
- **FR-002**: The scrub MUST NOT run while a resumption could still need what it clears. The
  trigger must be justified against the proposer handoff specifically, not inherited from the
  intents scrub's reasoning.
- **FR-003**: After the scrub, a run's records MUST still support compiling a RunReport that
  validates, names the paths authored, and states the run's outcome.
- **FR-004**: After the scrub, the pull request the run opened MUST remain identifiable from
  the run's records.
- **FR-005**: A scrub that cannot complete MUST stop with the reason recorded. Reporting a
  clean run over content still in the store is the failure this feature is least able to
  detect afterwards.
- **FR-006**: The scrub MUST be safe to run more than once, and MUST clear nothing when a run
  authored nothing — a successful run and an empty one may not take different cleanup paths.
- **FR-007**: A run that ends by refusal MUST leave no authored content either. **Measured, this
  holds by construction rather than by scrubbing**: a run refused at Judge returns before Propose
  and never composes a proposal, so its payload has no authored content to clear. The
  requirement is therefore stated as the property that is actually checkable — the refusal path
  writes no proposal — because a row asserting "the scrub cleared it" would pass without
  exercising anything. If the refusal path ever starts carrying a proposal, that row fails, and
  this requirement stops being satisfied for free.
- **FR-008**: The scrub MUST clear the authored file bodies and the model-authored **rationale
  and usage** text, and MUST NOT clear the title or the requester's task. All three cleared
  fields derive from the customer's repository; FR-032 already treats the rationale that way.
  **`usage` was added at implementation, on evidence**: the first acceptance sweep after the
  backfill found one carrying a shell transcript with a credential-shaped assignment, so the
  "prose about the change rather than an extract from it" line did not survive a real payload.
  `usage` and `rationale` are the same kind of thing — model-authored prose quoting the subject,
  travelling in the pull request body — and the pull request is the durable artifact, so a
  reviewer loses nothing.
- **FR-009**: Each authored file's **path and content digest MUST survive** the scrub. The
  digest is already recorded in the proposal's provenance, so this preserves rather than adds:
  a reviewer can establish that a merged pull request is the proposal the run made, with the
  platform holding none of the content.
- **FR-010**: The scrub MUST fire at the run's terminal state, which is reached only after the
  proposal is published or the run has failed terminally. A run that can still resume MUST NOT
  have been scrubbed.
- **FR-011**: A run that never reaches terminal state is not scrubbed by FR-010, and the
  platform MUST record that this case exists rather than let it read as covered. **Recorded
  where a reader of the platform will find it** — beside the scrub itself, and in the project's
  deferral list — not only in this specification, which nobody consults while reading the code.
  Closing it needs a sweeper and a staleness threshold, which is a separate decision.
- **FR-012**: The scrub MUST be scoped to authoring runs. 041 decided this deliberately for
  intents — a run whose arguments are a Vault path or a workspace name is not the case this
  exists for — and widening it here would re-decide that in a different feature.
- **FR-013**: A conformance row MUST observe the state store holding no authored content after
  a completed run, and MUST be able to fail — asserted against a store that held the content
  before the scrub ran.
- **FR-014**: The acceptance row MUST NOT regress to prose matching. **This is a
  non-regression obligation, not new work**: the matcher that decides whether content is present
  was corrected in [#220](https://github.com/mcteer/brieve/pull/220) — the row had been red for
  three weeks because it matched the English word *"secret"* in a Judge model's sentence, which
  masked the finding this feature exists to close. What remains is that this feature does not
  undo it, and that the row still asserts credential *shapes* rather than words when it goes
  green.

- **FR-015**: Authoring runs that reached terminal state **before** this feature existed MUST
  also be cleared. Six such checkpoints hold authored bodies today, and SC-001 admits no
  exception for content that predates the fix. The acceptance signal sweeps the whole store
  rather than runs created after the change, so a forward-only scrub leaves the finding open.
  This is a one-time, idempotent operation over terminal checkpoints — not a scheduled sweeper,
  which FR-011 deliberately leaves undone.

### Key Entities

- **Stored payload**: what a checkpoint carries for a run. Holds progress, result, and — for an
  authoring run — the composed proposal. The subject of this feature.
- **Composed proposal**: the authored file bodies, a model-authored rationale, usage text and a
  title. What the proposer reads and the pull request carries.
- **Terminal state**: the point at which a run will not resume. The intents scrub's trigger, and
  the candidate trigger here.
- **Scrub**: the act of clearing content from the control plane while leaving the record of what
  happened. Exists today for intents; this feature gives it a second subject.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No completed authoring run leaves an authored file body in the state store —
  100% of runs, observed rather than argued.
- **SC-002**: A RunReport compiled from a scrubbed run validates and names every path the run
  authored — 100%, and identical on those points to a report compiled before the scrub.
- **SC-003**: An interrupted publish that resumes opens a pull request carrying the same
  content — 100% of resumptions, with no run losing its proposal to the scrub.
- **SC-004**: Every failure mode in FR-005 stops with a distinct recorded reason; none reports
  a clean run over content it left behind.
- **SC-005**: The conformance row asserting SC-001 fails against a store holding pre-scrub
  content, demonstrated rather than assumed.
- **SC-006**: Issue #219's row passes, and `make conformance` is green.
- **SC-007**: For every scrubbed run, each authored path and its content digest are still
  readable from the record — 100%, and a reviewer can match them against the merged pull
  request without consulting the platform's copy, because there is none.

## Assumptions

- **The pull request is the durable artifact.** ADR-0038's shape — the agent authors, a person
  merges — is what makes clearing the platform's copy possible at all. The content is not being
  destroyed; it is being left in the one place its owner controls.
- **The audit trail does not carry the file bodies.** FR-013 refused the trail a copy nobody
  can delete, and 041 acted on that for intents. If the trail turns out to hold them, that is a
  second finding and a second feature, not a silent extension of this one.
- **The intents scrub stays as it is.** This feature adds a subject; it does not revisit 041's
  narrow scoping or its handling of an older provider.
- **No new retention policy is introduced.** The question is where FR-033 already applies, not
  how long anything should be kept.
- **Terminal state is reached only after publish.** Established from the code rather than
  assumed: the proposer handoff writes a checkpoint the RUN_CONTINUE path refuses to treat as
  terminal, and the completed run observed in #219 carries a `pr_url`. If that ordering ever
  changes, FR-010's safety argument changes with it.
- **The digest a proposal records is the digest of what it proposed.** FR-009 preserves an
  existing field rather than computing a new one.
- **The conformance row from #219 is the acceptance signal.** It is already written, already
  blocking, and already failing for this reason.
