# Tasks: The intake gauntlet

**Input**: Design documents from `/specs/037-intake-gauntlet/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature's output is evidence a reviewer will trust, so its rows *are* the
deliverable. Every contract row — A0, I1–I5, A1–A5, Q1–Q6, H1–H5, D1–D10 — has a task.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T008a (the tier's posture), T014 (unreachable ≠ unchanged), T024 (analysis blocks), T025 (flag short-circuits), T039 (detonation blocks) |
| **Conformance** | Phases 2–7 — both contracts, `tests/conformance/intake/` |
| **Correlation / evidence** | T012 (a check that found nothing is recorded), T047 (machine verdict ≠ human approval) |
| **Eval** | Phase 5 entire — the analyzer's own qualification (Q1–Q6) |
| **No-secret-leak** | T042 (a canary's value never enters the trail), T024 (findings carry codes, never candidate prose) |

**Two tasks exist to prove the others can lose**: **T032** (Q4 — a weakened analyzer must
FAIL qualification) and **T041** (D5 — no candidate-authored content reaches the observer).
T041 is load-bearing: every other row can pass while it fails, and that combination is the
vulnerability the gauntlet exists to inspect.

**And one exists to catch what no single run can**: T032a (Q6 — leniency drift across
qualifications). Q1–Q5 are point-in-time and would all pass while the analyzer degrades one
requalification at a time.

## Path Conventions

Single project: `src/`, `tests/` at repository root. New: `src/core/intake/`,
`evals/intake-seed/`, `corpus/golden-tasks/`, `infra/jobs/analysis-tier.nomad.hcl`,
`infra/jobs/detonation-range.nomad.hcl`, `infra/bin/intake-poll`,
`tests/conformance/intake/`.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/intake/__init__.py` and `tests/conformance/intake/__init__.py`; add `tests/conformance/intake` to the hermetic conformance lane's collection so new rows run where they block merges (the 036 lesson: a gate asserted only locally is not a gate).
- [ ] T002 [P] Read the `[upstream]` pin in `src/core/intake/pins.py`: repository + commit from a pack manifest, with an ABSENT table meaning `authored` rather than malformed (research R2 — `packs/vault/pack.toml` has none deliberately).
- [ ] T003 [P] Define candidate identity by content digest in `src/core/intake/proposal.py` — `Candidate(skill_name, digest, commit)`. Everything downstream keys off the digest so evidence cannot drift onto different bytes (FR-005).

---

## Phase 2: Foundational (blocking all stories)

**The audit vocabulary, the ADR, and THE ISOLATION TIER. Nothing in Phases 3–7 can record anything until these
exist, and T004/T005/T054 are one obligation in three files.**

- [ ] T004 [GATE:conformance] Add `ANALYSIS_VERDICT`, `DETONATION_COMPARED`, `CANARY_CONTACT`, `INTAKE_BYPASSED` to `AuditEventType` in `src/core/audit/schema.py`, additive, each with the docstring rigour `TOOL_CHOSEN` set. Record on `ANALYSIS_VERDICT` that it carries no field readable as an approval, and on `CANARY_CONTACT` that it carries an identifier and never a value.
- [ ] T005 Move `docs/adr/0053-automated-skill-intake-gauntlet.md` Proposed → **Accepted**, carrying the three clarification amendments: the range is purpose-built (not the test fake), the analyzer's floor is its own rather than ADR-0052's, and the manual path survives with a record. Include the **named trigger** Principle VI requires for the range as an operated component.
- [ ] T006 [P] Update `docs/adr/README.md` for 0053's status change, and add the range's operated-component note where the connectivity-tier ADRs are indexed.
- [ ] T007 Write the evidence-package shape in `src/core/intake/package.py` (split from `proposal.py`, which already carries candidate identity and delta): delta, both provenances, verdict, comparison, canary status, and — per FR-027 — a **stage-aware limits statement** naming what has not run as well as what ran and found nothing. The package is what a detection proposal GROWS INTO as stages complete, not a thing assembled once at the end.
- [ ] T008a [GATE:fail-closed] **Build the hardened untrusted-content isolation tier** in `infra/jobs/analysis-tier.nomad.hcl` — the thing ADR-0038 named in 2026 and nothing has implemented since. Concretely, and each clause is the tier rather than the ceiling: **bridge networking, never `network_mode = "host"`** (the fix `portal.nomad.hcl` records making, for the same reason — host mode puts the workload on the machine's network); **egress allowlisted to the pinned source only**; **no repository mount** — the delta is delivered as input, not reachable on disk; and its own workload identity distinct from any other task. (FR-006)
- [ ] T008b [GATE:conformance] Declare tier membership in `src/core/intake/tier.py` so a definition can REQUIRE the hardened tier, and dispatch refuses a definition that asks for it into an allocation that does not provide it. A tier nothing checks is a comment in a jobspec. (FR-006)
- [ ] T008c [P] Row A0 in `tests/conformance/intake/test_isolation_tier.py`: assert the tier's posture STRUCTURALLY — bridge mode not host, no repo mount, allowlist present — and assert a definition requiring the tier is refused when dispatched outside it. **A ceiling is not a tier**: a ceiling bounds what a definition may call, a tier bounds what the process can reach, and this row exists because the two are easy to conflate. (FR-006, FR-009)
- [ ] T008 [P] Unit gate in `tests/unit/test_intake_is_product_blind.py`: `src/core/intake/` imports no pack, no product, and no framework. The pipeline knows pins and digests, not Terraform or Vault (Principle I).

**Checkpoint**: audit vocabulary, ADR, package shape and the hardened tier exist. US1 can
proceed alone and needs none of the tier; US2 cannot start without it.

---

## Phase 3: User Story 1 — Detection (P1) 🎯 MVP

**Goal**: upstream moves, the platform notices, and nothing is adopted.
**Independent test**: quickstart Scenario A. No model is invoked anywhere in this phase.

- [ ] T009 [US1] Implement change detection in `src/core/intake/pins.py` (FR-001, FR-003): compare the recorded pin against upstream's current commit and return moved/unmoved/unreachable as three distinct outcomes, never two.
- [ ] T010 [US1] Compute the delta against the pinned commit in `src/core/intake/proposal.py`, so analysis cost tracks upstream MOTION rather than upstream size (ADR-0053 stage 3).
- [ ] T011 [US1] Write the poller `infra/bin/intake-poll` (FR-001) using `urllib` (research R3/R4 — no HTTP client enters the tree; the poller is a scheduled workflow, not a periodic Nomad job, because none exists here).
- [ ] T012 [P] [US1] [GATE:correlation] Row I1 (FR-002) in `tests/conformance/intake/test_detection.py`: an unmoved pin proposes nothing AND records that it was checked. "We looked and nothing had moved" is what distinguishes a maintained pin from an old one.
- [ ] T013 [P] [US1] Row I2 (FR-004) in the same file: a moved pin produces a proposal carrying the delta and both provenances, and the skill on disk is **byte-identical afterwards** — detection adopts nothing.
- [ ] T014 [P] [US1] [GATE:fail-closed] Row I3 (FR-003): an unreachable upstream reports failure and proposes nothing. Reporting silence as stability is how a pin rots while looking maintained.
- [ ] T015 [P] [US1] Row I4 (FR-005, FR-004b): move upstream twice with a proposal open; the proposal is marked stale and **refuses acceptance**, so earlier evidence cannot be accepted as describing the new bytes.
- [ ] T016 [US1] Row I5 (FR-001): the same pipeline against an imported snapshot produces the same proposal shape as against a reachable upstream (ADR-0021 — one pipeline, one trigger difference).
- [ ] T016a [US1] **Emit the proposal** in `src/core/intake/emit.py` and open the version-bump PR — the artifact US1 exists to produce, which the first task list asserted (T013) without anything writing it. Carries 033's accepted limitation in the proposal body: a token-created PR triggers no checks, a PAT is the standing credential Principle IV refuses, so the proposal **explains its own missing checks** rather than acquiring one. (FR-004)
- [ ] T016b [US1] Emit it as a **detection proposal**: stages-run stated, and the analyzer/detonation sections present-but-empty with the reason, never omitted. "No analysis has run" must appear where a verdict would (FR-004a, FR-027a) — an omitted section reads as a clean one.
- [ ] T016c [US1] Implement **snapshot input** in `src/core/intake/pins.py` as an alternate trigger into the same pipeline, so an air-gapped estate runs the identical stages from an imported bundle. ADR-0053's claim is one pipeline with one trigger difference, and the difference is the part with no implementation until now. (FR-001)
- [ ] T016d [US1] Detect **supersession**: an open proposal whose candidate digest no longer matches upstream is marked stale and refuses acceptance. The digest makes drift visible (T003); this makes it refuse. (FR-004b, FR-005)
- [ ] T017 [US1] Add the GitHub Actions schedule in `.github/workflows/intake-poll.yml`, inheriting 033's accepted limitation: a token-created PR triggers no checks, a PAT is the standing credential Principle IV refuses, so the proposal **explains its own missing checks** rather than acquiring one.

**Checkpoint**: US1 is shippable on its own and improves intake with zero new risk — no model
has read anything. What it emits is a **detection proposal**: the evidence package's early
form, honest about which stages have not run.

---

## Phase 4: User Story 2 — Containment (P1)

**Goal**: the candidate is read adversarially by something that cannot act.
**Independent test**: quickstart Scenario B.

- [ ] T018 [US2] Register the analysis agent definition with **the narrowest ceiling in the fleet**: read the delta, write one report artifact, nothing else. No product tool, no egress beyond the pinned source (FR-007).
- [ ] T019 [US2] Implement the structured verdict in `src/core/intake/verdict.py`: `clean` / `flagged` / `inconclusive`. Three-valued because an analysis that could not complete is not a clean one (FR-024).
- [ ] T020 [US2] Deliver candidate text to the analyzer as delimited DATA, never as instruction, and accept only the verdict schema back (FR-008).
- [ ] T021 [P] [US2] Row A1 in `tests/conformance/intake/test_containment.py`: a candidate carrying text addressed to the analyzer leaves the verdict unchanged, and the attempt is recorded.
- [ ] T022 [P] [US2] [GATE:conformance] Row A2: assert what the analysis ceiling **contains** — read-delta plus one artifact, nothing more. Structural, so it holds for redirections nobody thought to write; a ceiling that grows a product tool fails here (FR-009).
- [ ] T023 [P] [US2] Row A3: an analyzer stepping outside its ceiling is refused and recorded, through the interception that already exists.
- [ ] T024 [P] [US2] [GATE:no-secret-leak] Row A4 (FR-024) + the findings shape: an incomplete analysis blocks, and `ANALYSIS_VERDICT.findings` carries **codes, never quoted candidate prose** — the trail must not become a copy of hostile content.
- [ ] T025 [US2] [GATE:fail-closed] Row A5 (FR-010): any flag short-circuits to the human and **detonation is not attempted**. This is what makes A1's verdict meaningful rather than decorative.

**Checkpoint**: the analyzer runs contained. It is not yet trusted — Phase 5 is what makes its verdicts mean anything.

---

## Phase 5: User Story 4 — The gate has a gate (P1)

**Goal**: the analyzer is qualified before it is trusted, and re-qualified as it changes.
**Independent test**: quickstart Scenario C.

**Sequenced BEFORE detonation deliberately** (research R9): shipping the pipeline ahead of the
gate that qualifies its analyzer creates the ungated input ADR-0053 warns about, and would
put a row in `OWED` for the first time since 021.

- [ ] T026 [US4] Author `evals/intake-seed/` — human-labelled hostile cases covering redirection, exfiltration, encoded payloads, and content aimed at the reviewer (FR-019). Authored here, authoritative when reviewed and merged (ADR-0052's mechanism).
- [ ] T027 [US4] Implement `src/core/evals/intake_seed.py`: load the corpus and enforce a floor expressed in **attack classes**, not the judge's four answering suites (FR-020b).
- [ ] T028 [US4] Add `intake_analysis` to `SUITES` in `src/core/evals/suites.py` **in this same change**, so `OWED` stays empty (research R9).
- [ ] T029 [P] [US4] [GATE:eval] Row Q1 (FR-020, FR-020a) in `tests/conformance/intake/test_qualification.py`: a corpus below the floor **fails** rather than warns — ADR-0052's own posture, since a floor nothing enforces is a suggestion.
- [ ] T030 [P] [US4] [GATE:eval] Row Q2 (FR-020b): a corpus satisfying "all four suites" while covering one attack class must FAIL. The category error that would otherwise pass at the right threshold.
- [ ] T031 [US4] [GATE:eval] Row Q3 (FR-017): must-flag rate and false-positive budget enforced as stated numbers, measured values printed on failure. A revision moves in `contracts/conformance-intake.md`, carrying its measurement.
- [ ] T032 [US4] [GATE:eval] **Row Q4 (SC-002) — the row that proves the others can lose**: deliberately weaken the analyzer and require qualification to FAIL. If Q4 passes trivially, Q1–Q3 have stopped meaning anything.
- [ ] T032a [US4] [GATE:eval] Row Q6 in `tests/conformance/intake/test_qualification.py`: retain each qualification's scores and assert a **downward trend in must-flag rate is surfaced** rather than absorbed. Q1–Q5 are all point-in-time; without this the analyzer degrades one requalification at a time, each of them passing, which is precisely the silent failure US4 exists to prevent. (FR-018)
- [ ] T033 [P] [US4] Row Q5: changing the analyzer and attempting promotion without re-scoring is refused (FR-016).

**Checkpoint**: the analyzer's verdicts now carry weight, because something can take it away.

---

## Phase 6: User Story 3 — Detonation (P1)

**Goal**: the candidate is executed where it can do nothing, and watched from outside.
**Independent test**: quickstart Scenarios D and E.

- [ ] T034 [US3] Write `infra/jobs/detonation-range.nomad.hcl`: **no authority source at all**, no route to any real estate, canaries seeded, full audit. Purpose-built — NOT the test-only fake, whose merge-blocking guard must not be weakened (FR-015a, research R5).
- [ ] T035 [US3] Author `corpus/golden-tasks/` (FR-011) — fixed tasks both skill versions run against. Fixed is the point: a corpus that changed between runs would produce a diff describing the corpus rather than the candidate.
- [ ] T036 [US3] Implement the comparison in `src/core/intake/detonation.py`: attempts, denials, canary contact, with `written_by` carrying the **observer's** identity and never the specimen's.
- [ ] T037 [US3] Run specimen and observer as separate allocations with separate workload identities; in `src/core/intake/separation.py`; the observer's input is a **governed evidence read** of the run's records — a channel that structurally cannot carry candidate prose (research R7).
- [ ] T038 [P] [US3] Rows D1–D2 (FR-011, FR-014) in `tests/conformance/intake/test_detonation.py`: both versions run, `tasks_run > 0`, and a constructed behavioural difference appears in the comparison.
- [ ] T039 [P] [US3] [GATE:fail-closed] Row D3 (FR-014): a broken range blocks the candidate rather than passing it to the reviewer as clean.
- [ ] T040 [P] [US3] Row D4 (FR-013): specimen and observer hold distinct identities in distinct allocations — read the identities, do not infer them from behaviour.
- [ ] T041 [US3] [GATE:conformance] **Row D5 (FR-013, SC-005) — the load-bearing row**: seed candidate output with a marker and assert it appears NOWHERE in the observer's context or report. Every other row can pass while this fails, and that combination is the vulnerability the gauntlet exists to inspect (FR-013, SC-005).
- [ ] T042 [P] [US3] [GATE:no-secret-leak] Rows D8–D9 (FR-012): a seeded canary is caught mechanically with nobody reading anything, and `CANARY_CONTACT` carries the identifier and **never the value** — a trail that quoted canaries would become the exfiltration channel it detects.
- [ ] T043 [P] [US3] Row D10 (FR-017, SC-003): realistic skill content discussing credentials in documentation does not register canary contact. Paired with Q3's budget — a check firing on the word "secret" trains reviewers to ignore it.
- [ ] T044 [US3] Rows D6–D7 (FR-012, FR-015, FR-015b) in `tests/conformance/intake/test_range_posture.py`, marked `enclave`: the range reaches no real authority and no real estate, and is not the test fake. Named in the contract so they are not mistaken for absent.

---

## Phase 7: User Story 5 — The human gate (P1)

**Goal**: nothing the pipeline produced decided anything.
**Independent test**: quickstart Scenarios F and G.

- [ ] T045 [US5] Implement the recorded manual path in `src/core/intake/manual.py` (FR-025): adoption succeeds with the pipeline unavailable, writing `INTAKE_BYPASSED` with who, when, which skill, and why (FR-025a).
- [ ] T046 [US5] [GATE:conformance] Row H1 (FR-021, SC-006) in `tests/conformance/intake/test_human_gate.py`: drive every stage to its most favourable outcome and assert **no promotion** without a recorded human acceptance. Asserted over the whole sequence, because the failure is emergent — each stage declining to promote is not the same as no path promoting.
- [ ] T047 [P] [US5] [GATE:correlation] Row H2: the human acceptance is identifiable as a person's act and no machine verdict can be mistaken for one (FR-022, ADR-0043).
- [ ] T048 [P] [US5] Row H3 (FR-023): accepted candidates still land warn-mode before enforce-mode.
- [ ] T049 [US5] Row H4: the manual path works and its record is **no quieter** than a gauntlet promotion — the failure is a bypass that becomes routine because nothing makes its use visible (FR-025b).
- [ ] T049a [P] [US5] Unit gate in `tests/unit/test_promotion_gate_unchanged.py`: assert `promote_skill`'s signature and its refusal reason codes (`promotion_incomplete`, `digest_mismatch`, `injection_suspected`) are untouched. This feature FEEDS that gate; a boundary that is only remembered erodes the first time a stage "just needs one more field". (FR-026)
- [ ] T050 [P] [US5] Row H5 (FR-027, FR-027a, SC-008): the evidence package carries its **stage-aware** limits statement, and a proposal with no verdict says so **where a verdict would appear**. Assert both — an omitted section and a section saying "not run" are the same to a grep and opposite to a reader.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T051 [P] Update `ROADMAP.md`: move the entry to Shipped with what it found, and **remove the `Next` entry** — landing means removing it, not only adding a row.
- [ ] T052 [P] Update `docs/glossary.md`: intake gauntlet, detonation range, canary, analysis verdict, intake seed set.
- [ ] T053 Run `make check`, `make conformance-hermetic`, and the enclave rows; confirm `OWED` is still empty.

---

## Phase 9: Sealed-core review (blocks merge, not a code task)

- [ ] T054 [GATE:conformance] **Principle V security-maintainer review** (Dan). Four additive `AuditEventType` members on `TOOL_CHOSEN`'s precedent. Recorded on the implementation PR; the feature does not merge without it.

---

## Dependencies

```text
Setup (T001–T003)
   └─> Foundational (T004–T008c)    [audit vocab + ADR + package shape + THE TIER]
          ├─> US1 (T009–T017)       ── detection; SHIPPABLE ALONE, no model involved
          │                            emits a DETECTION PROPOSAL (T016a–d)
          └─> US2 (T018–T025)       ── containment; needs the tier (T008a–c)
                 └─> US4 (T026–T033) ── qualification; BEFORE detonation, per R9
                        └─> US3 (T034–T044) ── detonation
                               └─> US5 (T045–T050) ── the human gate
Polish (T051–T053) after the stories it documents
Review (T054) gates merge
```

- **US1 depends on Foundational only.** It ships without an analyzer, a range, or a corpus.
- **US4 precedes US3 deliberately.** An unqualified analyzer feeding a detonation pipeline is
  the ungated input ADR-0053 names; sequencing it first is why `OWED` stays empty.
- **T004/T005/T054 are one obligation in three files** — the enum members, the ADR that
  accepts them, and the review that approves them. None merges alone.

## Parallel Opportunities

- Setup: T002 ∥ T003 after T001.
- Foundational: T006 ∥ T008 ∥ T008c; T005 independent; T008a → T008b → T008c.
- US1: T012–T015 are `[P]` once T009–T011 land — four rows, four concerns. T016a–d serialize
  (emit → detection-proposal shape → snapshot input → supersession) and gate T017.
- US2: T021–T024 `[P]` after T018–T020.
- US4: T029, T030, T033 `[P]`; T031/T032 serialize on the scorer.
- US3: T038–T040, T042, T043 `[P]` after T034–T037.

## Implementation Strategy

**MVP is US1 alone.** Detection ships without a model reading anything, removes the latency
cost ADR-0004 named, and carries no new risk. If everything after it were abandoned, intake
would still be better than it is today.

**Order**: Setup → Foundational → US1 (ship-ready) → US2 → **US4** → US3 → US5 → Polish,
with T054 gating merge throughout.

**Two rows are written before the things they guard are trusted**: T032 (Q4) before the
analyzer's verdicts are relied on, and T041 (D5) before the detonation report is read as
evidence. A suite that cannot lose has proven nothing — and here, a suite that cannot lose
would produce a reviewer who has been reassured rather than informed, which is the one
outcome this feature must not cause.
