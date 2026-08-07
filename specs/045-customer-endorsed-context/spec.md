# Feature Specification: Customer-supplied context — endorsed, pinned, and citable

**Feature Branch**: `spec/045-customer-endorsed-context`

**Created**: 2026-08-07

**Status**: Draft

**Input**: Measured against merged main (`d6be271`). A customer's own material — internal
compliance policies, architecture standards, reference designs — considered when the platform
answers, without weakening the citation gate that makes an answer trustworthy.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4, R13 (evidence)** — an answer resting on customer material says so, and the endorsement behind it names a person and a time. **R7 (fail-closed)** — content that cannot be verified against its pin is not answered from. **R2, R3 (authority per task)** — endorsing is an administrator's act through the governed path, not a deployment step. **R5, R11 (total interception)** — syncing customer content is a platform act with a record, never an answer-time fetch |
| **ADRs touched** | **ADR-0030** (pinned vs consulted — the record says consulted material is *fetched fresh*, and the corpus does the opposite; this feature must state which shape customer content takes rather than inherit a description of a mechanism the tree does not have), **ADR-0004** (the corpus as the supply chain's second subject — customer material is emphatically **not** that, and saying so is half the design), **ADR-0021** (the labelled-snapshot exception, which is closer to what the corpus actually does), **ADR-0069** (the console path this rides rather than reinventing), **ADR-0046** (multi-tenancy owns the dimension the corpus lacks; consumed as a constraint, not built here), ADR-0047 |
| **Evidence class** | **attestation-relevant.** An answer citing customer material is an answer resting on content the platform did not vendor. What makes that defensible is a recorded endorsement — who trusted it, when — and a disclosure on the answer itself |

## What is true today, measured

**The citation gate is the constraint, not storage.** `answer.py` declines when no claim
survives; `corpus.py` calls citation resolution *"the single most important check in this
feature"* and refuses an unresolvable citation because *"it reads as evidence, and a reader who
follows it and finds nothing has been told something false about what this platform knows."*
Customer documents that are merely *read* would make every grounded answer decline.

**The corpus has no tenant dimension at all.** `load_corpus()` takes a manifest path and is
called with no arguments from exactly two places — the API ask route and the MCP transport.
`Corpus` is `{digest, documents, synced_at}`; `resolves(path, anchor)` is a dictionary lookup
and an anchor check.

**"Nothing is fetched here" is load-bearing.** A sync populates the cache; the reader refuses
what does not match the pin, *"because a corpus that fetched at answer time would make every
answer depend on a third party being reachable, and would make 'pinned' untrue."*

**The governed write path exists and has a principal.** 044 gave an administrator a console
that requests and a trust fabric that decides, and gave the platform its first `authority_submit`
grant. `CONSOLE_RECORDS` is a closed set of three, enforced in four places that must agree —
the route, the submitter, the Vault grant, and the Control Group's path list.

**044 also drew a line this feature must not cross.** Ceilings, the model matrix and the
protected-policy set are estate governance and are deliberately not console-writable.

## Clarifications

### Session 2026-08-07

- Q: What does an administrator endorse — a source, or individual documents? → A: **The source,
  as a whole.** One endorsement covers everything synced from it, including documents added to
  it later. This matches how a person actually decides to trust a body of work, and keeps the
  endorsement a **governance decision rather than a filing task**: an administrator facing two
  hundred files would approve in bulk without reading, and the record would then say more than
  it means. One decision, one record, one withdrawal.
  **The cost is stated rather than absorbed**: a document added upstream becomes citable at the
  next sync without a fresh human act. What bounds that is the sync record — FR-017 already
  requires each sync to say what it took — so *when* a document became citable is answerable
  even though nobody endorsed it individually.

- Q: How does an answer disclose that it rests on customer material, especially when mixed? →
  A: **Per-citation provenance, plus a summary note.** Every citation carries where it came
  from, and the answer's note says whether it rests on validated designs, on the customer's own
  endorsed material, or on both.
  **A summary alone would answer the wrong question.** A reader weighing an answer is not asking
  "did any of this come from our own documents" — they are asking *"does THIS claim rest on
  HashiCorp's guidance or on ours"*, and those carry different weight for different decisions.
  A note cannot answer that, and a purely visual distinction cannot be filtered or recorded.
  **Provenance is data, not presentation**, so the trail and any consumer see the same fact the
  reader does.

- Q: Where does an endorsement live, given 044's closed set of three console records? → A: **A
  fourth record, `endorsed-sources`**, added to all four places that must agree — the route's
  closed set, the submitter, the Vault grant, and the Control Group's path list.
  **Separate because the acts are separate.** Endorsing whose documents the platform may cite
  and naming where Terraform Enterprise lives are different governance decisions, plausibly
  reviewed by different people; folding the first into `product-connections` would make one
  grant cover both and one revocation remove both. **042's lesson applies directly**: its
  enumerated grant exists so that scoping cannot widen by accident, and reusing a record because
  it is already writable is exactly how it would.
  **The four-place update is the cost and it is not avoidable by hiding.** A second write
  mechanism outside the console would avoid it and reintroduce what 044's design argues against
  — two lifecycles for one act, one of which stops getting attention.

- Q: When is an endorsed source synced? → A: **The platform DETECTS change; an administrator
  ADOPTS it.** Those are two acts and separating them is the whole answer.
  The platform may notice that an endorsed source has moved and **notify** the administrator.
  Noticing changes nothing: what the platform answers from is unchanged until a person reviews
  the difference and accepts it. So content still never changes without somebody deciding it
  should — which was the reasoning behind rejecting a scheduler — while nobody has to remember
  to go and look.
  **033's rule carries over**: the age of the ground is disclosed rather than inferred, and an
  answer resting on customer material says how old that material is by the same reasoning the
  pinned corpus already does.

- Q: What happens to a run that is already in flight when an administrator accepts a change? →
  A: **It finishes on the content it started with.** A run resolves its ground once, at the
  start, and keeps it; only runs starting afterwards see the new content.
  **Otherwise a run's ground could move underneath it mid-flight** — the first half of an answer
  resting on one version of a standard and the second half on another, with one `corpus_digest`
  recorded for both and no way to tell afterwards which claim rested on what. That is the same
  class of failure 005 addressed for authority and effects: a resumed run **re-authenticates but
  never replays**, and by the same reasoning it must **re-read its ground but never re-resolve
  it**. A resumed run continues on the version it began with, not on whatever is current.
  **This is nearly free on the ask path and is the real requirement on the dispatched path**: an
  ask is one short request, while a dispatched authoring run spans steps and can be checkpointed
  and resumed hours later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An administrator endorses a source (Priority: P1)

An administrator names a repository of the customer's own documents and endorses it. The
platform records who endorsed it and when, and the endorsement is a governed change the trust
fabric decides — not a deployment step.

**Why this priority**: Nothing downstream exists without a trust statement about content the
platform did not vendor. The endorsement *is* the answer to "why may we cite this".

**Independent Test**: Endorse a source from the console; confirm the change is decided by the
fabric, the record names the endorsing administrator and the time, and a non-administrator
cannot endorse anything.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they endorse a source, **Then** the change is submitted
   as a request and the fabric's decision — applied, awaiting approval, or refused — is
   reported honestly.
2. **Given** any endorsement, **When** it is recorded, **Then** the record names the
   administrator, the source, and the time.
3. **Given** a non-administrator, **When** they attempt to endorse, **Then** they are refused
   and the refusal is recorded.
4. **Given** an endorsement is withdrawn, **When** the next question is asked, **Then** nothing
   from that source is citable, and no restart is required.

---

### User Story 2 — Endorsed content is synced and pinned (Priority: P1)

The platform takes a copy of the endorsed documents, records their content identity, and
answers only from that copy. It never reaches the customer's repository while answering a
question.

**Why this priority**: The pin is what makes a citation checkable. Without it the platform is
quoting something that may have changed, which is the failure the whole answering path exists
to prevent.

**Independent Test**: Endorse a source, sync it, then change the upstream content. Confirm
answers still cite the synced copy, and that the drift is detectable rather than silent.

**Acceptance Scenarios**:

1. **Given** an endorsed source, **When** it is synced, **Then** the platform records the
   content identity of what it took and when it took it.
2. **Given** a question is asked, **When** it is answered, **Then** no request is made to the
   customer's repository as part of answering it.
3. **Given** synced content that no longer matches its recorded identity, **When** an answer is
   attempted, **Then** the platform refuses to answer from it rather than answering from
   unverified content.
4. **Given** a source that cannot be synced, **When** the failure occurs, **Then** it is
   reported as a sync failure, and previously synced content keeps working.

---

### User Story 3 — The administrator is told what changed, and decides (Priority: P1)

An endorsed source moves upstream. The administrator is notified, sees **what changed**, and
chooses whether to adopt it. Until they do, the platform answers from what it already holds.

**Why this priority**: Without notification an administrator has to remember to look, and
nobody does. Without review, "accept" is a button somebody presses without knowing what they
are accepting — which makes the endorsement record say a person decided when what they did was
click. The review is what keeps the second endorsement as real as the first.

**Independent Test**: Endorse a source, change it upstream, and confirm the console reports a
change, describes what changed, and that answers are unaffected until an administrator accepts.

**Acceptance Scenarios**:

1. **Given** an endorsed source that has changed upstream, **When** the administrator opens the
   console, **Then** it reports that the source has changed.
2. **Given** a reported change, **When** the administrator reviews it, **Then** they can see
   which documents were added, removed, or altered before deciding.
3. **Given** an unadopted change, **When** a question is asked, **Then** it is answered from the
   content the platform already holds, and the answer's age reflects that content.
4. **Given** the administrator adopts the change, **When** the next question is asked, **Then**
   it is answered from the new content, and the adoption is recorded with who and when.
5. **Given** the administrator declines or ignores the change, **When** time passes, **Then**
   nothing about what the platform answers from changes.

---

### User Story 4 — A run in flight keeps the ground it started on (Priority: P1)

A change adopted while a run is in progress does not reach that run. It finishes on the content
it began with; runs starting afterwards use the new content.

**Why this priority**: A run whose ground moves mid-flight produces an answer resting on two
versions of the truth with one identity recorded for both — and nobody can tell afterwards which
claim rested on what. It is the same class of failure durable execution already addresses for
authority and effects, arriving through content instead.

**Independent Test**: Start a run, adopt a change mid-flight, and confirm the run completes on
the original content while a run started afterwards uses the new content. Interrupt and resume a
run across an adoption; confirm the resumed run continues on its original content.

**Acceptance Scenarios**:

1. **Given** a run in progress, **When** a change is adopted, **Then** that run continues on the
   content it started with.
2. **Given** a run that started after an adoption, **When** it runs, **Then** it uses the new
   content.
3. **Given** a run interrupted before an adoption and resumed after it, **When** it resumes,
   **Then** it continues on the content it originally resolved — not on what is now current.
4. **Given** any run, **When** its record is read, **Then** the identity of the content it used
   is in the record, and one run's record names exactly one such identity.

---

### User Story 5 — An answer may cite customer material, and says that it did (Priority: P1)

A question the customer's own documents answer is answered from them, with citations that
resolve — and the answer discloses that it rests on the customer's own material rather than on
validated designs.

**Why this priority**: This is the feature. It is also where it is most likely to mislead: a
citation into a customer document looks identical to a citation into a validated design, and a
reader who cannot tell the difference cannot weigh the answer.

**Independent Test**: Ask a question only the customer's documents answer. Confirm it is
answered, that every citation resolves, and that the answer says which material it rests on.

**Acceptance Scenarios**:

1. **Given** endorsed, synced content that answers a question, **When** it is asked, **Then**
   the answer cites it and the citations resolve.
2. **Given** an answer resting on customer material, **When** it is returned, **Then** it
   discloses that, distinguishably from an answer resting on validated designs.
3. **Given** an answer mixing both, **When** it is returned, **Then** the disclosure says so
   rather than naming only one, **and each citation carries its own provenance** so a reader can
   tell which claim rests on which.
4. **Given** a citation into customer material, **When** a reader follows it, **Then** it
   resolves to the content the platform actually holds.

---

### User Story 6 — The pinned corpus is not weakened (Priority: P1)

Everything true of the platform's own corpus before this feature is still true after it: the
same pin, the same refusal on mismatch, the same decline when nothing resolves.

**Why this priority**: Extending resolution to content the platform does not control is exactly
where the gate gets loosened by accident. A feature that made customer content citable by making
*everything* easier to cite would have traded the platform's most important check for a
capability.

**Independent Test**: Run the existing answering and citation suites unedited. Confirm an
invented citation still declines, and that no path admits a document that is not in some pin.

**Acceptance Scenarios**:

1. **Given** an invented citation, **When** an answer is composed, **Then** it is dropped
   exactly as before.
2. **Given** the platform's own corpus, **When** it is loaded, **Then** it is verified against
   its pin exactly as before.
3. **Given** any citation from any source, **When** it is resolved, **Then** it resolves against
   a recorded pin or it does not resolve.

---

### User Story 7 — Authoring sees the same material (Priority: P2)

A run authoring a change against the customer's architecture standards consults the same
endorsed content the answering path does, and its proposal cites it the same way.

**Why this priority**: *"Write the Vault integration for this repo"* against a customer's
standards is the same requirement arriving through the authoring path. Two sources of endorsed
content would disagree eventually.

**Independent Test**: Author a proposal for a subject the customer's standards cover; confirm
the citations in the proposal resolve against the same pin the answering path uses.

**Acceptance Scenarios**:

1. **Given** endorsed content, **When** an authoring run consults it, **Then** it reads the same
   synced copy the answering path reads.
2. **Given** a proposal citing customer material, **When** it is composed, **Then** the
   disclosure that it rests on customer material is carried into the proposal.

---

### Edge Cases

- **Endorsed content contradicts a validated design**: both are cited, and the disclosure makes
  the provenance of each visible. The platform does not adjudicate between them.
- **A document is removed from the source between syncs**: it stops being citable once the
  change is adopted; answers already given are unaffected, and the record of what was cited
  stands.
- **A source changes again while a change is awaiting review**: the administrator reviews
  against what is currently upstream, not against a stale snapshot of the difference.
- **A run outlives several adoptions**: it finishes on the content it started with, however many
  landed meanwhile.
- **A change is adopted while a run is suspended awaiting approval**: the run resumes on its
  original content, and the record says which — a suspension is not a new run.
- **The endorsed source is empty or contains nothing citable**: reported as such, distinct from
  a sync failure.
- **Content arrives in a form with no addressable sections**: it is not citable, and the
  platform says so rather than citing the document as a whole and calling it evidence.
- **An administrator endorses a source containing secrets**: out of scope for the platform to
  detect, and stated plainly — an endorsement is a trust statement, and this one would be a
  mistaken one. What the platform guarantees is that the endorsement is attributable.
- **Two administrators endorse conflicting versions of the same source**: the record shows who
  endorsed what and when; the later endorsement is in force.
- **A relevance judge is asked about a claim from customer material**: unchanged — 043's gate
  asks whether a claim answers the question, not where it came from.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An administrator MUST be able to endorse a source of customer documents through
  the platform's existing governed configuration path.
- **FR-001a**: Endorsements MUST live in their **own** governed record, separately grantable and
  separately revocable from the records that already exist. Every place that enumerates the
  writable set MUST be updated together, and a check MUST assert they agree — a set enforced in
  four places is a set that can disagree in four places.
- **FR-001b**: The feature MUST NOT introduce a second write mechanism for governance records.
  One act, one path.
- **FR-002**: An endorsement MUST record who endorsed it, what was endorsed, and when.
- **FR-002a**: An endorsement applies to a **source**, and covers every citable document synced
  from it — including documents that appear in it after the endorsement. The sync record is what
  makes *when* a given document became citable answerable, since no person endorsed it
  individually.
- **FR-003**: Endorsing MUST NOT be possible for a non-administrator, and an attempt MUST be
  recorded.
- **FR-004**: An endorsement MUST be withdrawable, and withdrawal MUST take effect without a
  restart.
- **FR-005**: The platform MUST take and retain its own copy of endorsed content, and MUST
  record the content identity of that copy.
- **FR-006**: Answering a question MUST NOT require reaching the customer's source. A source
  being unreachable MUST NOT prevent answering from content already synced.
- **FR-007**: Content that does not match its recorded identity MUST NOT be answered from.
- **FR-008**: A citation into endorsed content MUST resolve against the platform's own copy, by
  the same check the pinned corpus uses.
- **FR-009**: An answer resting wholly or partly on customer material MUST disclose that,
  distinguishably from an answer resting on validated designs.
- **FR-009a**: Every citation MUST carry the provenance of the document it points at —
  validated design, or the customer's own endorsed material — as **data rather than
  presentation**, so the record and any consumer see what the reader sees.
- **FR-010**: The disclosure MUST name which material an answer rests on when it rests on both.
- **FR-010a**: A reader MUST be able to tell, for **an individual claim**, which material it
  rests on. A summary that answers only "did any of this come from customer material" answers a
  question nobody is asking.
- **FR-011**: Content with no addressable sections MUST NOT be citable, and the platform MUST
  report that rather than citing a document as a whole.
- **FR-012**: The platform's own corpus MUST continue to be verified against its pin exactly as
  before, and every existing citation-resolution behaviour MUST be unchanged.
- **FR-013**: A citation MUST resolve against a recorded pin or not resolve; no path may admit a
  document that is in no pin.
- **FR-014**: The existing answering and citation conformance rows MUST pass unedited.
- **FR-015**: An authoring run MUST consult the same synced copy the answering path consults.
- **FR-016**: A proposal citing customer material MUST carry the same disclosure an answer does.
- **FR-017**: A sync MUST be recorded — what was synced, its identity, when, and whether it
  succeeded.
- **FR-017a**: A source MUST be synced when it is endorsed. The platform MAY **detect** that an
  endorsed source has changed upstream, and MUST NOT **adopt** any change without an
  administrator accepting it. Detecting is not adopting: content the platform answers from never
  changes without a person deciding it should.
- **FR-017c**: An administrator MUST be notified when an endorsed source has changed, and MUST
  be able to see **what changed** — which documents were added, removed, or altered — before
  deciding. An accept button in front of an unreviewed change makes the record claim a person
  decided when what they did was click.
- **FR-017d**: An unadopted change MUST have no effect on what any answer rests on, and the age
  disclosed for that content MUST remain the age of what is actually in use.
- **FR-017e**: An adoption MUST be recorded with who adopted it and when, exactly as the
  original endorsement is.
- **FR-017f**: A run MUST resolve the identity of the content it uses **once**, at its start, and
  MUST use that content for its whole life. A change adopted mid-flight MUST NOT reach a run
  already in progress.
- **FR-017g**: A **resumed** run MUST continue on the content it originally resolved, not on
  whatever is current at resume. A resumed run re-authenticates and never replays; by the same
  reasoning it re-reads its ground and never re-resolves it.
- **FR-017h**: A run's record MUST name the identity of the content it used, and MUST name
  exactly one — a record listing two is a run whose ground moved underneath it.
- **FR-017b**: The age of endorsed content MUST be visible to an administrator, and an answer
  resting on it MUST disclose that age by the same rule the pinned corpus already follows —
  a disclosure that appears only past a threshold trains readers that silence means fresh.
- **FR-018**: A sync failure MUST be distinguishable from an empty source and from content that
  is present but not citable.
- **FR-019**: Endorsed content MUST be scoped so that one customer's material cannot be cited in
  an answer given to another. Where the platform serves a single customer this is trivially
  satisfied and MUST still be stated rather than assumed.
- **FR-020**: A dispatched run MUST NOT be able to endorse a source or alter what is endorsed.
- **FR-021**: A row MUST exist that **fails** if customer content becomes citable without an
  endorsement.
- **FR-022**: The feature MUST state whether customer content is a tenant dimension on the
  existing corpus or a second, parallel corpus, and MUST NOT leave that to be inferred from the
  implementation.
- **FR-023**: No secret value from endorsed content MAY enter a record or a trail beyond what the
  answer itself cites.

### Key Entities

- **Endorsed source**: a named location of customer documents, the administrator who endorsed
  it, and when.
- **Synced copy**: the platform's own copy of that content, with its recorded identity and sync
  time.
- **Citable document**: a document within a synced copy that has addressable sections a citation
  can point at.
- **Provenance disclosure**: what an answer says about which material it rests on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A question that only the customer's own documents answer is answered, with
  citations that resolve.
- **SC-002**: 100% of answers resting on customer material disclose it; zero rest on it silently.
- **SC-002a**: For any answer, a reader can determine the provenance of **each** claim without
  consulting anything outside the answer.
- **SC-003**: Zero requests reach a customer source while a question is being answered.
- **SC-004**: Content that fails its identity check is answered from zero times.
- **SC-005**: Every endorsement and withdrawal appears in the trail with its administrator and
  time.
- **SC-006**: 100% of endorsement attempts by a non-administrator are refused.
- **SC-007**: A dispatched run alters what is endorsed zero times, across wordings and including
  an instruction planted in a subject.
- **SC-008**: The existing answering and citation rows pass unedited, measured as an empty diff.
- **SC-009**: An invented citation declines exactly as it did before this feature.
- **SC-010**: Customer content becomes citable without an endorsement zero times, and a row
  fails if that changes.
- **SC-011**: A withdrawal is in force for the next question, with no restart.
- **SC-013**: An administrator can state how old any endorsed source's content is, from the
  console alone.
- **SC-014**: Zero changes reach what the platform answers from without an administrator
  accepting them.
- **SC-015**: An administrator can say which documents a pending change adds, removes, or alters
  before accepting it.
- **SC-016**: Zero runs observe a content change mid-flight, including runs interrupted before an
  adoption and resumed after it.
- **SC-017**: Every run record names exactly one content identity.
- **SC-012**: A proposal citing customer material carries the same disclosure an answer does.

## Assumptions

- **Endorsement is the trust statement, and it is the answer to the citation problem.** The gate
  needs a reason to treat unvendored content as citable; "a named administrator endorsed this at
  this time" is that reason, and it is a governance fact the trail already knows how to carry.
- **Sync-then-answer, never fetch-at-answer.** The platform's existing reasoning holds for
  customer content: an answer that depended on the customer's repository being reachable would
  make "pinned" untrue and would fail at the worst moment.
- **This feature is the document half only.** The ROADMAP describes one panel over Git
  repositories *and* MCP server configurations and warns they are "two features of very
  different size". MCP servers are excluded: their resources cannot be pinned the way a cloned
  repository can, and their tools are a capability source that collides with eval-gated
  promotion and with the ceiling vocabulary being assembled before a run starts. That is a
  separate feature with its own record about what bounds an un-eval-gated capability.
- **The console is consumed, not rebuilt.** 044 built the administrative surface, the role, and
  the request-and-decide path. Adding a fourth console-writable record means updating the four
  places that must agree, which is work this feature does rather than a mechanism it invents.
- **Multi-tenancy is a constraint, not a deliverable.** ADR-0046 owns the tenant dimension and is
  unbuilt. A single-customer deployment satisfies FR-019 trivially; what this feature must not do
  is build a boundary that a later multi-tenancy feature has to build again differently.
- **Endorsing is not vetting.** The platform does not inspect endorsed content for secrets,
  accuracy, or currency. It guarantees that the endorsement is attributable and that what is
  cited is what was synced.
