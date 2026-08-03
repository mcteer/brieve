# Feature Specification: The corpus refresh — answers that can say how old their ground is

**Feature Branch**: `spec/033-corpus-refresh`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "The corpus refresh — answers that can say how old their ground is, and a pin that actually moves." (Full measured description in the invocation; the load-bearing facts are restated inline below.)

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R7 (grounded answers), R12 (evidence quality) — the age of an answer's ground is part of what the answer proves |
| **ADRs touched** | ADR-0004 (the corpus is the supply chain's second subject — consumed, not amended); 029's answer-note precedent (window_note) consumed; no new ADR expected |
| **Evidence class** | operational — the sync record is provenance about guidance content, not attestation material |
| **Sealed core** | **None expected.** Disclosure rides on the answer object (the `window_note` shape); no audit event payload changes. A finding that wants one is surfaced, not absorbed. |

## The measured gap *(context)*

`corpus/manifest.json` holds `corpus_digest`, `document_count` (33) and `documents` — and
nothing else. No timestamp of any kind exists anywhere in the pin, so no layer above it can
compute an age even if it wanted to. The pin has not moved since 024 landed it: `corpus-sync`
re-discovers the upstream document list on every run and pins by content digest, but nothing
anywhere runs it. 024 recorded the deferral and it has been re-recorded twice since: *"an
answer cannot say its pin is forty days old... sync often, answer from the newest sync, and
the citation still provably resolves — but the scheduling half does not exist."*

Three facts bound every design here. Upstream pages carry **no version metadata**, so
staleness can only ever mean time-since-sync, never versions-behind. The corpus is a
**committed git artifact**, so a refresh is a repo change however it is triggered, and landing
one stays a reviewed act. And the merge lanes are **hermetic** — the staleness signal is
computed from the pin alone; no blocking gate fetches anything.

## Clarifications

### Session 2026-08-03

- Q: The attention threshold for an aged pin? → A: **Two tiers, 30/90 days.** Under 30 days
  the note states the age plainly; 30–90 it reads as aging; past 90 it reads as stale with a
  refresh suggestion. Never a decline.
- Q: Refresh cadence, and the no-change posture? → A: **Weekly, and a no-op run still
  proposes the timestamp refresh** — "we checked" becomes a reviewed, provable fact, and the
  disclosure resets weekly when the schedule is healthy.
- Q: Does `packs/*/skills` join? → A: **Full treatment.** The vendored skills gain the same
  synced-at provenance and join the weekly refresh proposal. Their source is a git repository
  rather than the docs site, so the mechanics differ and the plan decides them; what is
  uniform is the posture — timestamped pin, scheduled proposal, reviewed landing. Skills have
  no answer surface today, so their staleness signal is provenance-only until something
  answers from them, and that limit is stated rather than implied.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An answer discloses the age of its ground (Priority: P1)

A person asks a guidance question and gets a cited answer, as today — and the answer now
carries a note saying when its corpus was pinned, so the reader can weigh a citation from last
week differently from one pinned a quarter ago. Nobody has to know the platform's internals to
ask "how current is this?" — the answer already said.

**Why this priority**: This is the provability gap itself. An answer whose ground has no age
is an answer making a silent currency claim; every other story serves this one.

**Independent Test**: Pin a corpus with a known sync time, ask a guidance question through the
full ask path, and read the note off the answer. Age the pin (fixture time), ask again, and
the note changes accordingly.

**Acceptance Scenarios**:

1. **Given** a corpus pinned at a known time, **When** a guidance question is answered,
   **Then** the answer carries a disclosure naming when the ground was pinned, in the same
   place the estate answer's window note rides — on the answer, never on an audit event.
2. **Given** a manifest with no sync timestamp (today's shape), **When** the corpus loads,
   **Then** the platform treats the age as unknown and the answer says so rather than
   inventing a date or omitting the note — unknown is a disclosure, not an absence.
3. **Given** an aged pin past the attention threshold, **When** a guidance question is
   answered, **Then** the answer still ANSWERS — the note escalates its wording; the platform
   never declines because an operator didn't run a script. (Confirmed in clarify: 30/90-day
   tiers, decline never.)

---

### User Story 2 - The pin records when it was made (Priority: P1)

An operator runs the sync and the resulting pin says when it happened. The manifest becomes
self-describing: digest for *what*, timestamp for *when*, and the two travel together in the
same reviewed commit.

**Why this priority**: US1 is impossible without it — there is no age to disclose until the
pin carries one. It also makes the SECOND sync meaningful: today a re-run that changes nothing
is invisible; with a timestamp, "checked upstream, nothing changed" becomes a recordable fact.

**Independent Test**: Run the sync against fixture upstream content; the manifest gains a sync
timestamp; loading the corpus exposes it; re-running with unchanged content updates the
timestamp while the digest holds still.

**Acceptance Scenarios**:

1. **Given** a sync run, **When** the manifest is written, **Then** it records the sync time,
   and the corpus loader exposes it to the answering path.
2. **Given** an unchanged upstream, **When** the sync re-runs, **Then** the digest is
   unchanged, the timestamp moves, and the diff shows exactly that — "we checked" is
   distinguishable from "we changed".
3. **Given** the existing 33-document pin, **When** this feature lands, **Then** the corpus
   still loads and answers still cite — the timestamp is additive, and the absent-timestamp
   case remains loadable (scenario US1-2) so the feature can land before the first re-sync.

---

### User Story 3 - The refresh has a schedule, and landing it stays reviewed (Priority: P2)

On a cadence, the platform prepares a refresh: the sync runs, and if anything changed — or
only the timestamp moved — the change arrives as a reviewable proposal the maintainer merges
or rejects. Nothing lands unreviewed; what ends is the state where nothing happens at all.

**Why this priority**: Without it, US1's note just documents decay instead of preventing it.
It is P2 only because the disclosure must exist first for the schedule to be provably doing
its job.

**Independent Test**: Trigger the scheduled path by hand; observe a prepared, reviewable
change containing the new pin; observe that nothing merged without review; observe the run
that finds nothing upstream changed still refreshes the timestamp.

**Acceptance Scenarios**:

1. **Given** the schedule fires and upstream changed, **When** the sync completes, **Then** a
   reviewable proposal exists with the new pin (documents + manifest + timestamp) and the
   redaction posture applied, and it does not merge itself.
2. **Given** the schedule fires and upstream did not change, **When** the sync completes,
   **Then** the timestamp-only refresh is still proposed — the platform can afterwards prove
   it checked. (Confirmed in clarify: weekly cadence, and the no-op proposal is wanted.)
3. **Given** the sync fails (upstream unreachable, redaction refuses a document), **When**
   the schedule fires, **Then** the failure is visible somewhere the maintainer looks, and
   the existing pin is untouched — a failed refresh must never degrade the current ground.

---

### Edge Cases

- A clock-skewed sync writes a future timestamp: the age computation must not produce a
  negative age; the answer's note treats a future pin time as unknown-age with the fact
  stated.
- The manifest timestamp is hand-edited to something unparseable: the loader treats it as the
  absent case (unknown), never crashes, and the conformance row for US1-2 covers it.
- The upstream index disappears entirely (site restructure): the sync fails loudly with the
  existing pin intact; the staleness note keeps disclosing the last good sync's age.
- Two syncs race (scheduled and manual): both target the one standing proposal branch; the
  later force-push simply wins with the fresher pin — the git artifact property makes this a
  review-time non-event.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pin MUST record when it was made, in the manifest, written by the sync.
- **FR-002**: The corpus loader MUST expose the pin's sync time to the answering path, and
  MUST treat an absent or unparseable time as *unknown*, not as an error and not as now.
- **FR-003**: Every guidance answer MUST disclose its ground's age (or that the age is
  unknown), riding on the answer object in the same shape as the estate answer's window
  note — never on a sealed-core audit event.
- **FR-004**: The disclosure MUST be computed from the pin alone. No answer-time network
  access, and no blocking lane gains a fetch.
- **FR-005**: An aged pin MUST NOT cause a decline by itself. The disclosure has three
  wordings by age: plain (under 30 days), aging (30–90), stale-with-refresh-suggestion (past
  90) — plus the unknown-age wording of FR-002. The thresholds are platform constants a
  deployment can read in one place; the answer answers in every tier.
- **FR-006**: A weekly scheduled refresh MUST prepare a reviewable change and MUST NOT land
  it unreviewed. A run that finds upstream unchanged still proposes the timestamp-only
  refresh: a reviewed "we checked at T" is the provable fact the schedule exists to produce.
- **FR-007**: A failed refresh MUST leave the existing pin untouched and MUST be visible to
  the maintainer without spelunking.
- **FR-008**: The sync's settled mechanics (document discovery, credential-shape redaction,
  content digests) are consumed unchanged. Any change they need is a finding, not a rider.
- **FR-009**: The existing pin (no timestamp) MUST remain loadable and answerable so the
  feature lands before the first re-sync, with the unknown-age disclosure covering the gap.
- **FR-010**: The vendored skills (`packs/*/skills`) gain the same synced-at provenance:
  a recorded vendoring time and source revision, refreshed by the same weekly proposal.
  Their upstream is a git repository, so "unchanged" is decidable exactly (a revision
  comparison, not a content fetch heuristic) and the mechanics are the plan's to choose.
- **FR-011**: The skills' staleness signal is provenance-only — recorded where an operator
  reads provenance, not disclosed on answers, because nothing answers from skills today.
  The spec states this limit so its future removal is a deliberate feature, not drift.
- **FR-012**: A skills refresh failure obeys FR-007 identically: existing vendored content
  untouched, failure visible.

### Key Entities

- **The pin**: the manifest (digest, count, documents) plus, now, the sync time — one
  reviewed git artifact whose *what* and *when* travel together.
- **The age disclosure**: a note on the guidance answer derived from pin time vs. answer
  time; three states (fresh wording, escalated wording, unknown).
- **The prepared refresh**: a reviewable change produced by the scheduled sync — new pin,
  new documents, redaction applied — that only a review lands.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every guidance answer produced after this feature states its ground's age or
  that the age is unknown — 100% of answers, asserted at the full ask path, both packs.
- **SC-002**: The second sync in the platform's history happens and lands as a reviewed
  change; the manifest's timestamp moves; answers' notes change accordingly the next time
  the serving process reads the pin.
- **SC-003**: A scheduled run against unchanged upstream produces a provable "checked at T"
  record without human intervention beyond review.
- **SC-004**: No blocking lane's row count, hermeticity, or runtime materially changes:
  the staleness signal costs no fetch and no vendor call anywhere a gate runs.
- **SC-005**: A refresh failure (simulated unreachable upstream) leaves every existing
  answer identical and is visible as a failure — degraded currency is disclosed, never
  silently served.
- **SC-006**: The vendored skills carry a provable vendoring time and source revision, and
  the weekly proposal covers them: a skills-only upstream change produces a reviewable
  proposal without any corpus change riding along.

## Assumptions

- The disclosure's consumer is a person reading an answer (portal, API, MCP alike — the note
  is on the shared answer object, so all three surfaces carry it without per-surface work).
- Age is wall-clock days since sync; nothing finer is meaningful at a documentation cadence.
- The scheduled trigger runs where CI already runs; a deployment without that scheduler still
  has the manual sync and the same disclosure — the schedule is convenience, the disclosure
  is the guarantee.
- The Opus/Sonnet answering models are unaffected: the note is platform-composed, not
  model-composed, exactly like the window note.
