# Tasks: Customer-supplied context — endorsed, pinned, and citable

**Input**: Design documents from `specs/045-customer-endorsed-context/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-endorsed-context.md, quickstart.md

**Tests**: Included — the deliverable is largely its rows (E1–E24, EL1–EL3). Two rows land
**with the code they guard rather than after it**: E4 (content citable without an endorsement)
and E23 (an outbound request during answering), because both describe states that must never
exist rather than behaviours to verify later.

**Organization**: By user story, with one deliberate reorder — **US6 ("the pinned corpus is not
weakened") is Foundational, not a late phase.** Its guarantee comes from `corpus.py` never
being edited (research R1), so it is a property to establish before the endorsed reader exists
and to hold continuously, not a box to tick at the end. A diff row that first runs in Phase 7
would have nothing to say about the six phases before it.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T005 (a digest mismatch refuses, never falls back), T006 (sync-failed / empty / nothing-citable stay three distinct reports rather than one silence) |
| **Conformance** | T001, T003, T008, T009, T011, T015, T017, T020, T021, T023 — the E-rows; T026–T027 the EL legs |
| **Correlation / evidence** | T008 (endorse, sync, adopt and withdraw each recorded with who and when), T016 (one content identity per run record), T019 (per-citation provenance as data rather than presentation) |
| **Eval** | N/A per research R9 — no model, prompt, pack or policy is promoted by this feature; the relevance gate judges customer-sourced claims exactly as any other (stated per the template's rule) |
| **No-secret-leak** | T004 (the record vocabulary has no credential field to fill), T011 (E10 — no credential in a sync record or a console rendering; private-source material is referenced from the trust store, never entered) |

## The shape of the work

The pinned corpus is not edited (R1), so the endorsed reader is built **beside** it and the
"nothing weakened" guarantee is structural. Content lives in Postgres because `corpus-sync`
writes into the repository and customer content has no commit (R3). A run pins its version at
start and a resumed run re-reads at that pin rather than re-resolving (R4) — which is why
superseded versions are retained. And **sync is egress**, so ADR-0070 is in scope rather than
deferred (R6).

## Path Conventions

Single project: `src/`, `tests/`, `infra/`, `docs/` at repository root.

---

## Phase 1: Foundational (blocking all stories)

**Purpose**: the record, the store, the reader — and the guarantee that the pinned corpus is
untouched, established before anything can touch it.

- [ ] T001 [GATE:conformance] The **US6 diff row** in
      `tests/conformance/endorsed/test_pinned_corpus_untouched.py` (new dir): `src/core/answering/corpus.py`
      and the existing answering/citation conformance files are unchanged from the merge-base,
      resolved via `GITHUB_BASE_REF` → local → `origin/<base>` (043's R9 lesson, third use);
      plus the frozen-list-exists guard, because a renamed file makes the diff vacuous rather
      than red. **Lands first so it speaks about every later phase.**
- [ ] T002 [P] Trust-fabric additions: `endorsed-sources` in
      `infra/modules/trust-fabric/authority-submit.tf` (grant),
      `control-groups.tf` (`console_controlled_paths`), and `policies.tf`
      (`harness_authority_read`, **exact path, no glob** — 042's 020-lesson, third use);
      `terraform validate` clean.
- [ ] T003 [P] [GATE:conformance] Extend the four-place completeness scan in
      `tests/unit/test_console_controlled_paths.py` to cover `endorsed-sources` — grant ↔ gate
      list ↔ code's closed set. A set enforced in four places is a set that can disagree in
      four places (E1's scan half).
- [ ] T004 [P] The `EndorsedSource` record parser in `src/surfaces/api/console.py`:
      endorse / withdraw / adopt shapes, immutable `name`, location-only vocabulary
      (**no credential field to fill** — 044's FR-018b posture); `endorsed-sources` added to
      `CONSOLE_RECORDS` in `src/surfaces/api/authority_submit.py`. Unit rows for the parser and
      [GATE:no-secret-leak] for the vocabulary.
- [ ] T005 [GATE:fail-closed] The content store in `src/core/answering/endorsed_store.py`
      (new): immutable content-addressed `SyncedVersion` rows in the harness Postgres —
      `candidate` / `adopted` / `superseded`, superseded **retained** because runs may pin them
      (R3/R4). Read verifies each document against its digest and **refuses** on mismatch, the
      way `CorpusUnavailable` refuses — a refusal, never a fallback (E7).
- [ ] T006 [GATE:fail-closed] `EndorsedCorpus` + `load_endorsed` + the combined view in
      `src/core/answering/endorsed.py` (new, **beside** `corpus.py`, never inside it):
      `resolves(path, anchor)` true only for the adopted version of a non-withdrawn source for
      this tenant; paths under the reserved `/endorsed/<source>/…` namespace (R2); the combined
      view tries the pin then the endorsed set. Three distinct failure reports — sync failed,
      source empty, nothing citable (E8/FR-018). **Row E25**: tenant A's content resolves
      nothing for tenant B (FR-019 — the key does something, and the hook ADR-0046 needs).

**Checkpoint**: content can be stored, verified and resolved — and nothing can yet endorse,
sync, or cite it.

---

## Phase 2: US1 — An administrator endorses a source (P1) 🎯 the gate

**Goal**: nothing becomes citable without a recorded endorsement (FR-001–004, FR-021).

**Independent Test**: endorse from the console; the fabric decides; the record names who and
when; a non-administrator is refused; withdrawal takes effect on the next question.

- [ ] T007 [US1] Endorse / withdraw routes in `src/surfaces/api/console.py`, riding 044's
      `ConfigChange` unchanged — three outcomes, CAS, `set_by`, admin-gated. **No second write
      mechanism** (FR-001b).
- [ ] T008 [US1] [GATE:conformance] Rows **E1–E3, E5** in
      `tests/conformance/endorsed/test_endorsement.py`: the three-outcome path (E1), who/what/
      when on endorsement, withdrawal and adoption (E2), a non-administrator refused and
      recorded (E3), withdrawal in force for the next question with no restart (E5 — 044's C17
      shape, one process).
- [ ] T009 [US1] [GATE:conformance] **E4 — the row this phase exists for**, in
      `tests/conformance/endorsed/test_endorsement_required.py`: content synced but NOT
      endorsed resolves nothing; **with the endorsement check rigged out it resolves and this
      row fails** (044's C20 shape). Content becoming citable without an endorsement is the one
      thing this feature must make impossible.

**Checkpoint**: the gate exists and can lose. Nothing is synced yet.

---

## Phase 3: US2 — Endorsed content is synced and pinned (P1)

**Goal**: the platform holds its own verified copy and never fetches while answering
(FR-005–007, FR-017/018).

**Independent Test**: endorse, sync, change upstream — answers still cite the synced copy, and
drift is detectable rather than silent.

- [ ] T010 [US2] The sync in `src/surfaces/sync/endorsed_sync.py` (new): clone at a tip,
      extract citable sections, write an immutable version into the store; **records what it
      took, its identity, when, and who triggered it** (FR-017). A document with no addressable
      sections is not citable and is reported as such, never cited whole (FR-011/E20).
- [ ] T011 [US2] [GATE:conformance] Rows **E6–E10** in
      `tests/conformance/endorsed/test_sync.py`: the sync record (E6), digest mismatch refuses
      (E7), the three distinct failure states (E8), an unreachable source does not stop
      answering from what is already synced (E9), and [GATE:no-secret-leak] no credential in a
      sync record or a console rendering (E10); and E6's never-carries half — the sync record
      and every audit event carry identities and paths, **never document content** (FR-023,
      038's FORBIDDEN_PAYLOAD_KEYS shape).
- [ ] T012 [US2] **ADR-0070** in `docs/adr/0070-endorsed-content-sync-is-an-egress-class.md`
      (Proposed): endorsed-content sync as an enumerated egress class with its bounds — named
      sources only, never during answering, read-only, trust-store credentials referenced never
      entered — and the resolution of ADR-0030's tension (customer content is *consulted*
      material handled by the **pinned** mechanism, ADR-0021's labelled-snapshot shape). Index
      in `docs/adr/README.md`. **In scope, not deferred**: Principle II says adding a class
      requires an ADR, and the code lands in this phase.

---

## Phase 4: US3 — Told what changed, and decides (P1)

**Goal**: detection notifies; adoption is a person's act; nothing moves in between
(FR-017a/c/d/e).

**Independent Test**: change upstream — the console reports it, shows what changed, answers are
unaffected until adoption, and adoption is recorded.

- [ ] T013 [US3] The drift probe in `src/surfaces/mcp/health.py`: per endorsed source, compare
      the upstream tip against the adopted version's recorded tip — **a refs listing, no clone,
      no content transfer** — and write a drift flag. **Noticing changes nothing** (FR-017a).
      Rides the existing checker; no new operated component (Principle VI).
- [ ] T014 [US3] Review and adopt in `src/surfaces/api/console.py`: opening a pending change
      syncs a **candidate** version and presents added / removed / altered against the adopted
      one (FR-017c) — reviewing against a candidate synced *at review time* is what makes "the
      source moved again while awaiting review" behave correctly. Adoption flips
      `adopted_version` through the same request-and-decide path and is recorded (FR-017e).
- [ ] T015 [US3] [GATE:conformance] Rows **E11–E14** in
      `tests/conformance/endorsed/test_drift.py`: drift flagged and unadopted changes nothing,
      with the age still reflecting what is in use (E11); the review names added/removed/
      altered (E12); a source moving again is reviewed against current upstream (E13); adoption
      moves the next answer and is recorded, while declining or ignoring changes nothing, **and
      an added document becomes citable with no fresh endorsement** (E14/FR-002a).

---

## Phase 5: US4 — A run keeps the ground it started on (P1)

**Goal**: a change adopted mid-flight does not reach a run in progress, across interruption and
resume (FR-017f–h).

**Independent Test**: adopt mid-run; the run finishes on its original version; one started
after uses the new one; a run interrupted before and resumed after continues on its original.

- [ ] T016 [US4] Version pinning: the ask path resolves the adopted version **once per
      request** (free — one short request); a dispatched run writes `endorsed_version` into the
      checkpoint blob's existing `payload` dict at start, and resume **reads the pin and loads
      that version** rather than re-resolving to current (R4). The version joins
      `corpus_digest` on the ask/run record as **one bounded value** (FR-017h).
- [ ] T017 [US4] [GATE:conformance] Rows **E15–E17** in
      `tests/conformance/endorsed/test_run_isolation.py`: a run started before an adoption
      completes on its original version while one started after uses the new one, **both in one
      process** (E15); **across a resume** — interrupted before, resumed after, still on the
      original (E16); every record names exactly one content identity (E17). A record listing
      two is a run whose ground moved underneath it.
- [ ] T018 [US4] Extend the ask-record exact-key-set row in
      `tests/component/test_answering.py` to admit `endorsed_version` and bound it — the
      seventh feature in seven to extend that payload, and the exactness is what has made each
      of them a decision somebody wrote down.

---

## Phase 6: US5 — Citing and disclosing (P1)

**Goal**: customer material is citable and every answer says what it rests on
(FR-008–011, FR-017b).

**Independent Test**: ask a question only the customer's documents answer — answered, citations
resolve, provenance visible per claim, age disclosed.

- [ ] T019 [US5] The combined view wired into both surfaces —
      `src/surfaces/api/ask.py` and `src/surfaces/mcp/transport.py` (ADR-0033 parity, and 043
      shipped that asymmetry once) — with `provenance: validated-design | customer-endorsed` on
      **every citation as data**, the summary note naming validated designs / endorsed material
      / both, and the age of endorsed content disclosed by `describe_ground`'s own rule
      (FR-017b).
- [ ] T020 [US5] [GATE:conformance] Rows **E18–E21** in
      `tests/conformance/endorsed/test_citing.py`: a customer-only question is answered with
      resolving citations (E18); per-citation provenance as data, and a mixed answer naming
      both while each citation says which (E19); a document with no addressable sections is not
      citable and is reported (E20); a path in **neither** pin does not resolve (E18/FR-013);
      the age disclosed is the adopted version's (E21).
- [ ] T021 [US5] [GATE:conformance] **E23** in
      `tests/conformance/endorsed/test_no_answer_time_fetch.py`: **zero outbound requests
      during answering**, asserted by instrumentation with an endorsed source configured — not
      by the absence of code, which proves nothing about a path nobody exercised.

---

## Phase 7: US7 — Authoring sees the same material (P2)

**Goal**: one loader serves both paths, and a proposal discloses like an answer
(FR-015/016).

- [ ] T022 [US7] The authoring path consumes the **same** combined `resolves` callable
      (`src/surfaces/dispatch/policy_authoring.py`'s citation checking, 042's seam), and the
      proposal's evidence section carries the same provenance disclosure an answer does
      (FR-016); rows **E24's authoring half** in
      `tests/conformance/endorsed/test_authoring_consults.py`.
- [ ] T023 [US7] [GATE:conformance] **E24's exclusion half** in
      `tests/conformance/endorsed/test_run_cannot_endorse.py`: a dispatched run cannot endorse,
      adopt, or withdraw — no tool resolves to any of it, a planted instruction records an
      attempt and changes nothing, and **the rigged-on construction fails this row** (044's C20
      shape, FR-020/SC-007).

---

## Phase 8: Polish & Cross-Cutting

- [ ] T024 [P] The portal: `settings.html` gains the endorsed-sources section (sources, adopted
      version, age, drift flag) and a review page rendering added/removed/altered — through the
      relay only, no governance logic client-side.
- [ ] T025 [P] **EL3** — the a11y lane walks the endorsed-sources and review pages in
      `tests/a11y/test_wcag.py` and `tests/a11y/test_keyboard_and_screenreader.py`. 044's
      lesson: a page the lane does not visit is a page it has not tested, and the suite stays
      green while it goes unchecked.
- [ ] T026 Apply the trust-fabric additions to the dev enclave and run **EL1** end to end
      against a real repository: endorse → sync → ask a question only that content answers →
      citations resolve, provenance rendered, age disclosed. Record outcomes in
      `contracts/conformance-endorsed-context.md`; re-seed the model credential if the apply
      clobbers it.
- [ ] T027 Run **EL2**: change the upstream, watch the checker flag it, review the difference,
      adopt, and confirm the next answer moves **while a run started pre-adoption finishes on
      the old version**. Record the outcome.
- [ ] T028 [P] Run `specs/045-customer-endorsed-context/quickstart.md` top to bottom as
      written; fix drift in the doc, not by hand-waving the steps.
- [ ] T029 Update `ROADMAP.md` in the implementation PR: close the customer-supplied-context
      entry with the mechanism in one line, keep the original analysis beneath it, and add
      045's Shipped row (the file's own landing rule).

---

## Dependencies & Execution Order

- **Foundational**: T001 first (it must speak about every later phase); T002 ∥ T003 ∥ T004
  after T001; T005 after T002; T006 after T005.
- **US1**: T007 after T004+T006; T008 after T007; **T009 in the same phase** — the gate and the
  proof it can lose land together.
- **US2**: T010 after T005+T007; T011 after T010; T012 ∥ T010 (the ADR lands with the egress it
  describes, not after).
- **US3**: T013 after T010; T014 after T010+T013; T015 after T014.
- **US4**: T016 after T006+T014 (a version to pin, and an adoption to be isolated from);
  T017 after T016; T018 ∥ T017.
- **US5**: T019 after T016; T020 ∥ T021 after T019.
- **US7**: T022 after T019; T023 ∥ T022.
- **Polish**: T024 after T014; T025 after T024; T026 after T002+T011; T027 after T026+T017;
  T028/T029 last.

## Parallel Example

After T001: `T002 ∥ T003 ∥ T004`. After T010: `T012 (ADR) ∥ T011 ∥ T013`. After T019:
`T020 ∥ T021 ∥ T022`.

## Implementation Strategy

Foundational → **US1 (the gate)** → US2 (sync) → US3 (adopt) → US4 (isolation) → US5 (cite) →
US7 → polish.

The suggested MVP is **Foundational + US1 + US2 + US5**: endorse, sync, cite, disclose — a
customer's documents answering questions, which is the product. US3 and US4 are what make it
safe to *change* that content, and they are P1 rather than later precisely because a feature
that can adopt but cannot isolate is one where a run's ground moves underneath it.

**US6 is not a phase.** Its guarantee is that `corpus.py` was never edited, and T001 asserts
that from the first commit rather than the last.
