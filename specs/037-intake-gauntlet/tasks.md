# Tasks: The intake gauntlet

**Input**: Design documents from `/specs/037-intake-gauntlet/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature's output is evidence a reviewer will trust, so its rows *are* the
deliverable. Every contract row (I1–I5, A1–A5, Q1–Q5, H1–H5, D1–D10) has a task.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T017 (analysis blocks), T020 (flag short-circuits), T034 (detonation blocks), T014 (unreachable ≠ unchanged) |
| **Conformance** | Phases 3–6 — both contracts, `tests/conformance/intake/` |
| **Correlation / evidence** | T012 (a check that found nothing is recorded), T041 (machine verdict ≠ human approval) |
| **Eval** | Phase 5 entire — the analyzer's own qualification (Q1–Q5) |
| **No-secret-leak** | T037 (a canary's value never enters the trail), T024 (findings carry codes, never candidate prose) |

**Two tasks exist to prove the others can lose**: T030 (Q4 — a weakened analyzer must FAIL)
and T033 (D5 — no candidate-authored content reaches the observer). T033 is load-bearing:
every other row can pass while it fails, and that combination is the vulnerability the
gauntlet exists to inspect.

## Path Conventions

Single project: `src/`, `tests/` at repository root. New: `src/core/intake/`,
`evals/intake-seed/`, `corpus/golden-tasks/`, `infra/jobs/detonation-range.nomad.hcl`,
`infra/bin/intake-poll`, `tests/conformance/intake/`.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/intake/__init__.py` and `tests/conformance/intake/__init__.py`; add `tests/conformance/intake` to the hermetic conformance lane's collection so new rows run where they block merges (the 036 lesson: a gate asserted only locally is not a gate).
- [ ] T002 [P] Read the `[upstream]` pin in `src/core/intake/pins.py`: repository + commit from a pack manifest, with an ABSENT table meaning `authored` rather than malformed (research R2 — `packs/vault/pack.toml` has none deliberately).
- [ ] T003 [P] Define candidate identity by content digest in `src/core/intake/proposal.py` — `Candidate(skill_name, digest, commit)`. Everything downstream keys off the digest so evidence cannot drift onto different bytes (FR-005).

---

## Phase 2: Foundational (blocking all stories)

**The audit vocabulary and the ADR. Nothing in Phases 3–6 can record anything until these
exist, and T005/T006/T047 are one obligation in three files.**

- [ ] T004 [GATE:conformance] Add `ANALYSIS_VERDICT`, `DETONATION_COMPARED`, `CANARY_CONTACT`, `INTAKE_BYPASSED` to `AuditEventType` in `src/core/audit/schema.py`, additive, each with the docstring rigour `TOOL_CHOSEN` set. Record on `ANALYSIS_VERDICT` that it carries no field readable as an approval, and on `CANARY_CONTACT` that it carries an identifier and never a value.
- [ ] T005 Move `docs/adr/0053-automated-skill-intake-gauntlet.md` Proposed → **Accepted**, carrying the three clarification amendments: the range is purpose-built (not the test fake), the analyzer's floor is its own rather than ADR-0052's, and the manual path survives with a record. Include the **named trigger** Principle VI requires for the range as an operated component.
- [ ] T006 [P] Update `docs/adr/README.md` for 0053's status change, and add the range's operated-component note where the connectivity-tier ADRs are indexed.
- [ ] T007 Write the evidence-package shape in `src/core/intake/proposal.py`: delta, both provenances, verdict, comparison, canary status, and — per FR-027 — the **limits statement** naming what none of it establishes.
- [ ] T008 [P] Unit gate in `tests/unit/test_intake_is_product_blind.py`: `src/core/intake/` imports no pack, no product, and no framework. The pipeline knows pins and digests, not Terraform or Vault (Principle I).

**Checkpoint**: audit vocabulary, ADR, and the package shape exist. US1 can proceed alone.

---

## Phase 3: User Story 1 — Detection (P1) 🎯 MVP

**Goal**: upstream moves, the platform notices, and nothing is adopted.
**Independent test**: quickstart Scenario A. No model is invoked anywhere in this phase.

- [ ] T009 [US1] Implement change detection in `src/core/intake/pins.py`: compare the recorded pin against upstream's current commit and return moved/unmoved/unreachable as three distinct outcomes, never two.
- [ ] T010 [US1] Compute the delta against the pinned commit in `src/core/intake/proposal.py`, so analysis cost tracks upstream MOTION rather than upstream size (ADR-0053 stage 3).
- [ ] T011 [US1] Write the poller `infra/bin/intake-poll` using `urllib` (research R3/R4 — no HTTP client enters the tree; the poller is a scheduled workflow, not a periodic Nomad job, because none exists here).
- [ ] T012 [P] [US1] [GATE:correlation] Row I1 in `tests/conformance/intake/test_detection.py`: an unmoved pin proposes nothing AND records that it was checked. "We looked and nothing had moved" is what distinguishes a maintained pin from an old one.
- [ ] T013 [P] [US1] Row I2 in the same file: a moved pin produces a proposal carrying the delta and both provenances, and the skill on disk is **byte-identical afterwards** — detection adopts nothing.
- [ ] T014 [P] [US1] [GATE:fail-closed] Row I3: an unreachable upstream reports failure and proposes nothing. Reporting silence as stability is how a pin rots while looking maintained.
- [ ] T015 [P] [US1] Row I4: move upstream twice with a proposal open; earlier evidence is not presented as describing the new bytes (FR-005, keyed on digest).
- [ ] T016 [US1] Row I5: the same pipeline against an imported snapshot produces the same proposal shape as against a reachable upstream (ADR-0021 — one pipeline, one trigger difference).
- [ ] T017 [US1] Add the GitHub Actions schedule in `.github/workflows/intake-poll.yml`, inheriting 033's accepted limitation: a token-created PR triggers no checks, a PAT is the standing credential Principle IV refuses, so the proposal **explains its own missing checks** rather than acquiring one.

**Checkpoint**: US1 is shippable on its own and improves intake with zero new risk — no model has read anything.

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
- [ ] T024 [P] [US2] [GATE:no-secret-leak] Row A4 + the findings shape: an incomplete analysis blocks, and `ANALYSIS_VERDICT.findings` carries **codes, never quoted candidate prose** — the trail must not become a copy of hostile content.
- [ ] T025 [US2] [GATE:fail-closed] Row A5: any flag short-circuits to the human and **detonation is not attempted**. This is what makes A1's verdict meaningful rather than decorative.

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
- [ ] T029 [P] [US4] [GATE:eval] Row Q1 in `tests/conformance/intake/test_qualification.py`: a corpus below the floor **fails** rather than warns — ADR-0052's own posture, since a floor nothing enforces is a suggestion.
- [ ] T030 [P] [US4] [GATE:eval] Row Q2: a corpus satisfying "all four suites" while covering one attack class must FAIL. The category error that would otherwise pass at the right threshold.
- [ ] T031 [US4] [GATE:eval] Row Q3: must-flag rate and false-positive budget enforced as stated numbers, measured values printed on failure. A revision moves in `contracts/conformance-intake.md`, carrying its measurement.
- [ ] T032 [US4] [GATE:eval] **Row Q4 — the row that proves the others can lose**: deliberately weaken the analyzer and require qualification to FAIL. If Q4 passes trivially, Q1–Q3 have stopped meaning anything.
- [ ] T033 [P] [US4] Row Q5: changing the analyzer and attempting promotion without re-scoring is refused (FR-016).

**Checkpoint**: the analyzer's verdicts now carry weight, because something can take it away.

---

## Phase 6: User Story 3 — Detonation (P1)

**Goal**: the candidate is executed where it can do nothing, and watched from outside.
**Independent test**: quickstart Scenarios D and E.

- [ ] T034 [US3] Write `infra/jobs/detonation-range.nomad.hcl`: **no authority source at all**, no route to any real estate, canaries seeded, full audit. Purpose-built — NOT the test-only fake, whose merge-blocking guard must not be weakened (FR-015a, research R5).
- [ ] T035 [US3] Author `corpus/golden-tasks/` — fixed tasks both skill versions run against. Fixed is the point: a corpus that changed between runs would produce a diff describing the corpus rather than the candidate.
- [ ] T036 [US3] Implement the comparison in `src/core/intake/detonation.py`: attempts, denials, canary contact, with `written_by` carrying the **observer's** identity and never the specimen's.
- [ ] T037 [US3] Run specimen and observer as separate allocations with separate workload identities; the observer's input is a **governed evidence read** of the run's records — a channel that structurally cannot carry candidate prose (research R7).
- [ ] T038 [P] [US3] Rows D1–D2 in `tests/conformance/intake/test_detonation.py`: both versions run, `tasks_run > 0`, and a constructed behavioural difference appears in the comparison.
- [ ] T039 [P] [US3] [GATE:fail-closed] Row D3: a broken range blocks the candidate rather than passing it to the reviewer as clean.
- [ ] T040 [P] [US3] Row D4: specimen and observer hold distinct identities in distinct allocations — read the identities, do not infer them from behaviour.
- [ ] T041 [US3] [GATE:conformance] **Row D5 — the load-bearing row**: seed candidate output with a marker and assert it appears NOWHERE in the observer's context or report. Every other row can pass while this fails, and that combination is the vulnerability the gauntlet exists to inspect (FR-013, SC-005).
- [ ] T042 [P] [US3] [GATE:no-secret-leak] Rows D8–D9: a seeded canary is caught mechanically with nobody reading anything, and `CANARY_CONTACT` carries the identifier and **never the value** — a trail that quoted canaries would become the exfiltration channel it detects.
- [ ] T043 [P] [US3] Row D10: realistic skill content discussing credentials in documentation does not register canary contact. Paired with Q3's budget — a check firing on the word "secret" trains reviewers to ignore it.
- [ ] T044 [US3] Rows D6–D7 in `tests/conformance/intake/test_range_posture.py`, marked `enclave`: the range reaches no real authority and no real estate, and is not the test fake. Named in the contract so they are not mistaken for absent.

---

## Phase 7: User Story 5 — The human gate (P1)

**Goal**: nothing the pipeline produced decided anything.
**Independent test**: quickstart Scenarios F and G.

- [ ] T045 [US5] Implement the recorded manual path in `src/core/intake/manual.py`: adoption succeeds with the pipeline unavailable, writing `INTAKE_BYPASSED` with who, when, which skill, and why (FR-025a).
- [ ] T046 [US5] [GATE:conformance] Row H1 in `tests/conformance/intake/test_human_gate.py`: drive every stage to its most favourable outcome and assert **no promotion** without a recorded human acceptance. Asserted over the whole sequence, because the failure is emergent — each stage declining to promote is not the same as no path promoting.
- [ ] T047 [P] [US5] [GATE:correlation] Row H2: the human acceptance is identifiable as a person's act and no machine verdict can be mistaken for one (FR-022, ADR-0043).
- [ ] T048 [P] [US5] Row H3: accepted candidates still land warn-mode before enforce-mode.
- [ ] T049 [US5] Row H4: the manual path works and its record is **no quieter** than a gauntlet promotion — the failure is a bypass that becomes routine because nothing makes its use visible (FR-025b).
- [ ] T050 [P] [US5] Row H5: the evidence package carries its limits statement (FR-027, SC-008).

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
   └─> Foundational (T004–T008)     [audit vocab + ADR + package shape]
          ├─> US1 (T009–T017)       ── detection; SHIPPABLE ALONE, no model involved
          └─> US2 (T018–T025)       ── containment
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
- Foundational: T006 ∥ T008; T005 independent of both.
- US1: T012–T015 are `[P]` once T009–T011 land — four rows, four concerns.
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
