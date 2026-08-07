# Tasks: Grounded means relevant, not merely resolvable

**Input**: Design documents from `specs/043-grounded-means-relevant/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-relevance.md, quickstart.md

**Tests**: Included — the deliverable is largely its rows (R1–R15, L1–L3). **New assertions
land in new files**: FR-004/SC-003 forbid editing any existing answering eval case, and R9
asserts that as a diff rather than a promise.

**Organization**: By user story. US1 (the gate) and US2 (nothing regresses) are P1; US3 (the
record) is P2. The seed machinery is Foundational because both the hermetic rows and the live
qualification stand on it.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T008 (R4's three causes), T009 (R5 cost bound), T012 (R6 unbound-first, at the surface where the binding is resolved) |
| **Conformance** | T007–T012, T014–T016 — the R-rows; T021–T022 the L-legs |
| **Correlation / evidence** | T015 — MODEL_GATE's first production writer, ordered before the outcome record |
| **Eval** | T005/T006 (seed floor + seeds), T020 (qualification, majority-of-three, two numbers) |
| **No-secret-leak** | N/A — no credential or tool-result path is touched; the judge call brokers exactly as the answer call does (stated per the template's rule) |

## The shape of the work

The gate must be able to lose (R7), the production caller must be the thing asserted (R8 —
`verify-the-production-caller` is a named lesson here), and the fixture judge affirms by
default *as scaffolding*, with the refusing branches driven by their own rows. **The feature
ships at the US2 checkpoint or not at all**: a gate that declines the motivating case by
declining more of everything is the fix becoming the defect.

## Path Conventions

Single project: `src/`, `tests/`, `evals/`, `infra/` at repository root.

---

## Phase 1: Setup

*(No setup tasks — no new dependency, no scaffolding. The record this feature owes is the 0g
closure note, which lands in Polish because it must describe what shipped.)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the protocol, the parser, the binding, and the seed machinery — everything both
the hermetic rows and the live legs stand on.

- [X] T001 Create `src/core/answering/relevance.py`: `RelevanceJudge` protocol,
      `RelevanceVerdict` (relevant indices, model, raw leading token), and the strict
      leading-token parser — `RELEVANT: 1,3` / `RELEVANT: none`; anything else is malformed
      and surfaces as a typed refusal, never a provider fault (research R3; 032's
      harness-owns-vocabulary rule).
- [X] T002 [P] Add `relevance_cell: str = ""` to `AskBinding` in
      `src/core/authority/ask_binding.py` — **and teach the parser a per-field expected role,
      because today it refuses this feature's own record**: `parse_ask_binding_record` iterates
      the two sources and refuses at parse any cell whose role is not `ask` ("a cell qualified
      for another role licenses that role, not this one"). The relevance field expects `judge`,
      with the SAME parse-time refusal in both directions — a relevance cell naming an
      `ask`-role cell refuses identically, because one qualification must not license another
      either way. Absent stays empty (the unbound refusal lands with the surface wiring,
      T011). **Unit rows for both parser refusal directions** land beside it in
      `tests/unit/test_ask_binding_relevance.py` (new file) — the contract's companion
      assertion, tasked here so it is nobody's afterthought.
- [X] T003 [P] Create `src/core/evals/relevance_seed.py`: seed loader with the floor enforced
      at load — ≥10 cases, ≥3 supported-but-irrelevant, ≥3 fully-relevant, ≥1 mixed;
      `author` required non-empty; per-claim verdicts from the closed `relevant`/`irrelevant`
      vocabulary; **deliberately separate from `judge.py`'s `SeedCase`** so the existing judge
      chain's loader and floor are untouched (research R4).
- [X] T004 [P] Create the fixture relevance judge in `tests/harness/fixture_relevance.py`:
      affirms all claims by default (scaffolding — the contract header says why), with
      constructor knobs to affirm a subset, affirm none, be unreachable, or return a malformed
      token; counts its invocations for R5.
- [X] T005 [GATE:eval] Unit rows for the loader in
      `tests/unit/test_relevance_seed_loader.py`: each floor violation refuses at load (R13);
      a seed whose citation does not resolve against the real pin is refused (R14) — the judge
      must be qualified on the world the path produces.
- [ ] T006 [GATE:eval] Author `evals/relevance-seed/seed.toml`: ≥10 human-labelled cases,
      every one carrying `author = "Dan McTeer"`, with the motivating retention case as the
      first supported-but-irrelevant seed (claims citing the real Terraform/Boundary retention
      anchors, labelled irrelevant against the "this platform" question), ≥2 more
      supported-but-irrelevant, ≥3 fully-relevant, ≥1 mixed. **Maintainer reviews the labels
      like code** — generated labels measure the generator (FR-014/FR-015).

**Checkpoint**: protocol, binding field, loader and seeds exist; nothing user-visible changed.

---

## Phase 3: User Story 1 — A question the corpus cannot answer is declined (P1) 🎯 MVP

**Goal**: the gate runs after citation resolution, drops the irrelevant with the ground
recorded, declines "not covered" when nothing survives, and fails closed on every judge
failure (SC-001's hermetic half, SC-005, SC-006).

**Independent Test**: drive `answer_question` with a fixture judge affirming none — declined,
third reason; affirming one of three — answered with two disclosed irrelevant.

- [X] T007 [US1] Widen `src/core/answering/answer.py`: optional `relevance` parameter; gate
      invoked only when `kept` is non-empty; third `declined_reason` (*"the corpus does not
      cover what was asked"*); `Answer.irrelevant` distinct from `dropped`;
      `Answer.relevance_note` naming the verdict as a model judgement (FR-001/002/006/007/018).
- [X] T008 [P] [US1] [GATE:fail-closed] Rows R1–R4 in
      `tests/conformance/answering/test_relevance_gate.py` (new file): all-irrelevant declines
      with the third reason (R1); the two decline grounds distinguishable end to end (R2);
      partial keep with disclosure (R3); unreachable / unqualified / malformed each decline
      naming their distinct cause and never answer (R4).
- [X] T009 [P] [US1] [GATE:fail-closed] Row R5 in the same file: an ask declining by
      resolution never invokes the judge, asserted by the counting fixture. **R6 is
      deliberately NOT here**: unbound is decided where the surface resolves the binding, and
      `answer_question` knows nothing about bindings — a row for it in this file would have
      nothing to assert against. It lands in T012, after the wiring exists.
- [X] T010 [US1] [GATE:conformance] Row R7 in the same file: with `relevance=None`, R1's
      assertion FAILS — the gate can lose, asserted by running the rigged construction.
- [ ] T011 [US1] Wire the surface in `src/surfaces/api/ask.py` and
      `src/surfaces/api/service.py`: resolve `relevance_cell` beside the ask binding,
      construct the judge (fixture cell → fixture judge in dev; live cell → adapter), pass it
      to `answer_question`; unbound/unqualified/unavailable each decline naming the cause
      (FR-017).
- [ ] T012 [US1] [GATE:conformance] Rows R6 + R8 in
      `tests/conformance/answering/test_relevance_caller.py` (new file), both driven against
      the surface because both are facts about it: an empty `relevance_cell` refuses
      `relevance_unbound` before any availability question (R6 — 026's "nobody decided" rule,
      asserted where the binding is resolved); and the surface constructs and passes a judge,
      so stopping fails this row while R1–R7 stay green (R8,
      `verify-the-production-caller`).

**Checkpoint**: the gate works, refuses correctly, can lose, and the production caller is the
thing proven.

---

## Phase 4: User Story 2 — Cross-product answers survive (P1)

**Goal**: no case that answers today begins declining; a genuinely cross-product answer is
kept (SC-003, SC-004).

**Independent Test**: run the answering suites unedited with the fixture judge wired; ask a
two-product question through the gate with all claims affirmed.

- [ ] T013 [US2] Wire the fixture judge into the recorded-suite path so the existing answering
      suites run with the gate PRESENT (never bypassed) and unedited — the fixture affirms for
      cases expecting `answered`, and the wiring lives in the scorer construction, not in any
      case file (`src/core/evals/scoring.py` or its conftest seam; zero case edits).
- [ ] T014 [P] [US2] [GATE:conformance] Row R9 in
      `tests/conformance/answering/test_relevance_regression.py` (new file): `git diff` over
      the answering eval case files against the merge-base is empty, and the recorded suites
      pass with the gate wired.
- [ ] T015 [P] [US2] [GATE:conformance] Row R10 in the same file: a question whose claims span
      two products' documents, all affirmed → answered with both citations kept. **This row
      fails if the fix is product-scoping**, which is its reason to exist.

**Checkpoint**: the ship line. Declining more of everything is now a red suite, not a quiet
cost.

---

## Phase 5: User Story 3 — The relevance decision is inspectable (P2)

**Goal**: every judgement is in the trail as a model gate; a declined answer's record says
what was considered (SC-007, SC-010).

**Independent Test**: produce a decline and an answer; read only the records.

- [X] T016 [US3] [GATE:correlation] Write `MODEL_GATE` from `src/surfaces/api/ask.py` on every
      relevance judgement — payload `{gate: "relevance", verdict, kept_count,
      irrelevant_count, model, cell}`, **before** the ask outcome record (031's
      fallback-before-issued ordering); statements never enter the payload. **Verify at
      implement whether `record_ask` carries the decline REASON** (the visible call passes
      `disposition=` only): if the record drops it, widen `record_ask` additively so R2/R12's
      "distinguishable from the records alone" is a fact about the records rather than about
      the in-memory `Answer` — a reason that exists only in the response is invisible to an
      auditor.
- [ ] T017 [P] [US3] [GATE:conformance] Rows R11–R12 in
      `tests/conformance/answering/test_relevance_record.py` (new file): the gate event is
      present, ordered before the outcome, carries the cell identity and counts and no
      statements (R11); from a declined ask's records alone a reader can state what was
      considered, what dropped on which ground, and which model judged (R12).

---

## Phase 6: The live legs (US1's live half; named runner: Dan)

**Goal**: the motivating case declines against a live judge; smoke is green; the judge
qualifies at majority-of-three with two numbers (SC-001, SC-002, SC-008, SC-009).

- [ ] T018 [US1] Create `src/adapters/anthropic_relevance.py`: the live judge, through
      `client_and_model` (the adapter seam owns credential/import/model-id — and the
      no-live-dependencies guard forbids a vendor import anywhere else); leading-token protocol
      from T001; **sealed-core additive class, named for Principle V review**.
- [ ] T019 [US1] Add the relevance leg to `tests/evals_live/smoke.py`: the unedited
      `vault-must-decline-001` through the real path with the live judge, response printed —
      one call before anything bigger (L1); smoke exit reflects it (L2).
- [ ] T020 [US1] [GATE:eval] Create `tests/evals_live/relevance_qualify.py` and the
      `evals-relevance-qualify` Makefile target: every seed case at majority-of-three, two
      numbers printed separately — overall vs the ≥90% floor, and supported-but-irrelevant
      which must be ALL correct; a rigged always-affirm candidate demonstrably clears the
      first and fails the second (R15). **The lane binds nothing** — promotion is a separate
      human act.
- [ ] T021 [US1] [GATE:conformance] Hermetic row R15 in
      `tests/unit/test_relevance_qualification.py`: the qualification scoring itself, driven
      with a rigged always-affirm candidate against the loaded seed set — passes the majority
      floor, fails the supported-but-irrelevant number, and is refused.
- [ ] T022 [US1] Add the fixture judge cell and `relevance_cell` binding to
      `infra/modules/trust-fabric/` (dev estate defaults), **following the estate's
      fixture-cell precedent for provenance fields** (`qualified_by = "fixture"`, `judge =
      "seed"` — a judge-role cell with empty provenance is the shape promotion refuses), so
      `make dev-up` yields a surface with the gate present and bound; run the live legs
      (L1–L3) and record the results — re-seed the model credential if an apply intervenes
      (the apply clobbers it).

---

## Phase 7: Polish & Cross-Cutting

- [ ] T023 [P] Run `specs/043-grounded-means-relevant/quickstart.md` top to bottom as written;
      fix drift in the doc, not by hand-waving the steps.
- [ ] T024 Update `ROADMAP.md` in the implementation PR: mark gap 0g **CLOSED by 043** with
      the mechanism in one line, and add 043's Shipped row (the file's own landing rule).

---

## Dependencies & Execution Order

- **Foundational**: T001 → T004 (the fixture implements the protocol); T002, T003 ∥ T001;
  T005 after T003; T006 after T003 (the loader validates the seeds as written).
- **US1**: T007 after T001; rows T008–T010 after T007+T004; T011 after T002+T007;
  T012 after T011 — **R6 lives in T012 because the unbound refusal does not exist until
  T011 wires it**; placing it earlier was pass 1's M1 finding.
- **US2**: T013 after T007+T004; T014/T015 [P] after T013.
- **US3**: T016 after T011; T017 after T016.
- **Live**: T018 after T001; T019 after T011+T018; T020 after T003+T006+T018; T021 after
  T003+T006; T022 last, after everything.
- **Polish**: T023/T024 after all.

### Parallel opportunities

- T002, T003 ∥ T001; T005 ∥ T006 once T003 lands.
- T008, T009 together; T014, T015 together; T017 ∥ T014/T015.
- T018 ∥ the whole of US2/US3 (different files).

## Implementation Strategy

**MVP is Phases 2–3** — the gate, refusing correctly, able to lose, with the production caller
proven. **Not shippable alone**: without US2's regression rows, a gate that buys its decline by
declining everything ships green, which is the fix becoming the defect. **Ship at the US2
checkpoint or not at all.** US3 and the live legs complete the evidence story and SC-001's
live half; T022's run is the named-runner obligation being discharged.

## Notes

- **24 tasks; 18 contract rows (R1–R15, L1–L3)**, and every asserting task names its rows.
- Zero edits to existing answering eval cases; R9 asserts it as a diff from the merge-base
  (`git stash` is not a baseline, and neither is a moving `main`).
- The corpus and the failing case are untouched throughout — the two "fixes" this estate has
  names for.
- T006 is the human dependency: the maintainer authors and reviews the seed labels.
