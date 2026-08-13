# Tasks: An answer is useful — primary response, supporting citations

**Input**: Design documents from `specs/046-answer-usefulness/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-answer-usefulness.md, quickstart.md

**Tests**: Included — the feature's deliverable is largely its conformance rows (S1–S5, N1–N3,
U1–U4) plus named-runner live legs (L1–L3). Prefer **new test files** over editing existing
answering cases; if a citation_accuracy / must_decline case must change because of the wire
shape, record the cause in the task note and never silently weaken the gate (spec US4 / SC-005).

**Organization**: By user story. US1 (primary answer shape) is MVP. US2 (illustrative code)
extends the provider contract. US3 (sufficiency suite) is the usefulness gate. US4 is the
non-regression checkpoint — the feature ships at the US4 checkpoint or not at all.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T004 (uncited / empty support declines); T011 (no uncited code); T018 (sufficiency cases that omit the fact) |
| **Conformance** | T005–T006, T009–T010, T022–T024, T027 — S/N/L rows |
| **Correlation / evidence** | T025 — `ask_answered` content-free + cell/digest/disposition/relevance_gate present (FR-008) |
| **Eval** | T014–T020 (`answer_sufficiency`); T023 existing answering suites green |
| **No-secret-leak** | N/A for new paths — ask still brokers credentials as 027; no new secret-bearing surface (stated) |

## The shape of the work

Governance order does not move: cite-resolve → relevance (043, untouched) → compose wire.
`primary_answer` is presentation of a kept claim statement, not a bypass around the gate.
Estate stays on today's `claims[]` / `references` shape (Q2-B).

## Path Conventions

Single project: `src/`, `tests/`, `packs/`, `docs/` at repository root.

---

## Phase 1: Setup

*(No scaffolding or new dependency. ROADMAP closure note lands in Polish after behaviour
exists.)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: provider candidate → single `Claim` mapping, and `ask_for` composition of
`primary_answer` + top-level `citations` for guidance — the seam every story stands on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T001 Change guidance `_INSTRUCTION` and parse path in
      `src/adapters/anthropic_answering.py` so the model returns a JSON **object**
      `{ "answer": "...", "citations": [{"path","anchor"}] }` (research R3); permit fenced
      illustrative code in `answer` when the question asks for an example/template and sections
      support it; forbid inventing uncited config and forbid claiming to have acted; map that
      object to a single `Claim(statement=answer, citations=…)` before `answer_question`; retain
      fail-closed parse (`ProviderUnavailable` on unusable shape); empty answer or empty
      citations → no keep → decline via existing gate.
- [x] T002 Compose guidance answered wire fields in `src/surfaces/api/ask.py`: set
      `primary_answer` from the kept claim's statement and top-level `citations` as deduped
      `{url, provenance}` from resolved citations (research R1/R2); **estate branch unchanged**
      (`claims` + `references`); omit legacy `claims` on **new** guidance answers once
      consumers are updated (research R4 preference).
- [x] T003 [P] Unit coverage for the new provider parse/mapping in
      `tests/unit/test_live_answer_provider_primary_shape.py` (new file): object → one Claim;
      array-shaped legacy model output refused or mapped only if explicitly supported — prefer
      refuse; malformed JSON → `ProviderUnavailable`.
- [x] T004 [GATE:fail-closed] Component/conformance row in
      `tests/conformance/answering/test_primary_answer_grounding.py` (new file): candidate with
      unresolvable citations does not ship answered with those citations; answered guidance
      without citations is impossible when the gate held (contract S2/S3).

**Checkpoint**: Product path can emit `primary_answer` + `citations` for guidance; estate
untouched; nothing portal-visible required yet.

---

## Phase 3: User Story 1 — The answer is primary; citations support it (P1) 🎯 MVP

**Goal**: Readers get a coherent primary answer first; citations are support (SC-001, S1, S4,
S5).

**Independent Test**: Ask a covered guidance question through API (and portal once T007 lands);
response has non-empty `primary_answer` and supporting `citations`; reader can restate substance
without opening a link.

### Tests for User Story 1

- [x] T005 [P] [US1] [GATE:conformance] Assert answered guidance JSON shape (S1) in
      `tests/conformance/answering/test_primary_answer_shape.py` (new file).
- [x] T006 [P] [US1] [GATE:conformance] Extend API/MCP ask parity in
      `tests/conformance/mcp/test_ask_parity.py` (or sibling new file if edits would tangle) so
      guidance parity covers `disposition`, `primary_answer`, and `citations` (S5 / SC-006).

### Implementation for User Story 1

- [x] T007 [US1] Update `src/surfaces/portal/templates/_outcome.html` to render
      `primary_answer` first, then supporting citations; **dual-shape replay** for legacy
      outcomes that only have `claims[]` (research R4; contract S4).
- [x] T008 [US1] Update any portal/API helpers that assume guidance answers are only
      `claims[]` (search `src/surfaces/portal/` and conversation context renderers) so new
      outcomes display correctly without breaking reopen of old threads.
- [x] T009 [US1] [GATE:conformance] Portal/component assertion for primary-first render +
      legacy `claims[]` replay in `tests/component/test_portal_ask_outcome_shape.py` (new file)
      (S4).

**Checkpoint**: Guidance Ask is answer-first on API/MCP/portal; MVP demoable.

---

## Phase 4: User Story 2 — Illustrative code when asked (P1)

**Goal**: When the asker wants an example/template and the corpus supports it, `primary_answer`
may include fenced code; Ask still never acts (FR-004/FR-005, N1/N2, SC-004).

**Independent Test**: Hermetic recorded candidate with fenced HCL in `answer` ships as answered
`primary_answer` containing that fence and resolvable citations; ask path still has no tools.

### Tests for User Story 2

- [x] T010 [P] [US2] [GATE:conformance] Row in
      `tests/conformance/answering/test_illustrative_code_in_answer.py` (new file): recorded
      primary with fenced code + resolving citations → answered; `primary_answer` contains the
      fence; no authoring side effects (N2).
- [x] T011 [P] [US2] [GATE:fail-closed] Row in the same file (or sibling): code-only / template
      request whose citations do not resolve → declined or stripped — never uncited
      configuration (FR-005).

### Implementation for User Story 2

- [x] T012 [US2] Verify T001's `_INSTRUCTION` in `src/adapters/anthropic_answering.py` already
      covers illustrative-code permission and the no-invention / never-acted rules (no second
      rewrite); adjust only if T010/T011 expose a gap.
- [x] T013 [US2] Confirm never-acts conformance still passes
      `tests/conformance/answering/test_asking_never_acts.py` (N1) — fix only if the new
      instruction accidentally implies tools; do not weaken the row.

**Checkpoint**: Shape supports useful templates in-answer; authorship boundary intact.

---

## Phase 5: User Story 3 — Sufficiency suite (P1)

**Goal**: True / cited / on-subject / fact-omitting answers can fail a gate (FR-006, SC-003,
U1–U3) without retuning 043 (U4 / FR-009).

**Independent Test**: Load suite refuses empty `must_contain`; omitting recorded answer fails;
including facts passes; `anthropic_relevance.py` instruction unchanged.

### Tests for User Story 3

- [x] T014 [P] [US3] [GATE:eval] Loader rows in
      `tests/unit/test_answer_sufficiency_suite.py` (new file): empty `must_contain` refused at
      load (U1); suite membership wiring covered.
- [x] T015 [P] [US3] [GATE:eval] Scorer rows in
      `tests/component/test_answer_sufficiency_scorer.py` (new file): fact-omitting recorded
      answer **fails** (U2); fact-including passes (U3).

### Implementation for User Story 3

- [x] T016 [US3] Add `answer_sufficiency` suite + `must_contain` field to
      `src/core/evals/suites.py` (research R5); refuse empty `must_contain` at load; do **not**
      force into `expected: str` / `ANSWERING_SUITES` verb judge.
- [x] T017 [US3] Wire scoring in `src/core/evals/scoring.py`: product path → require every
      `must_contain` substring in `primary_answer` (case-insensitive, whitespace-normalised);
      update `AnsweringScorer` / related helpers so citation_accuracy still sees `https://` after
      the shape change (research R5).
- [x] T018 [US3] [GATE:fail-closed] Author
      `packs/vault/evals/answer_sufficiency.toml` with ≥1 case whose `recorded` is
      true/cited/on-subject and omits the fact (must fail) and ≥1 case that includes the fact
      (must pass); include a retention-shaped fact case aligned with the ROADMAP example when
      fixture material allows.
- [x] T019 [P] [US3] Author `packs/terraform/evals/answer_sufficiency.toml` with the same
      load/score rules as vault — **required** (Principle VII; both packs ship the suite).
- [x] T020 [US3] [GATE:eval] Assert `src/adapters/anthropic_relevance.py` subject-vs-sufficiency
      instruction is **unchanged** (U4) via a focused unit/diff row in
      `tests/unit/test_relevance_prompt_untouched_by_046.py` (new file) — pin the critical
      sentence about not judging sufficiency.

**Checkpoint**: Usefulness is fail-able without reopening 043.

---

## Phase 6: User Story 4 — Existing safety and grounding do not regress (P1)

**Goal**: must-deny / must-decline / citation-accuracy / relevance / never-acts remain blocking
and green (SC-005, N3); estate shape unchanged.

**Independent Test**: `make evals` (and relevance hermetic rows) green; estate ask JSON still
uses `claims`/`references` without requiring `primary_answer`.

- [x] T021 [US4] Reauthor or adapt any answering eval `recorded` strings that break solely
      because of the provider JSON object shape — **record each change's cause in the commit
      message / task note**; never weaken `expected` outcomes (SC-005).
- [x] T022 [US4] [GATE:conformance] Estate guidance isolation row in
      `tests/conformance/answering/test_estate_shape_unchanged_046.py` (new file): estate
      answered payloads are not required to carry `primary_answer` (Q2-B).
- [x] T023 [US4] [GATE:eval] Run and green the existing answering + relevance hermetic suites
      (`make evals` / project targets); fix regressions without retuning the relevance judge.
- [x] T024 [US4] [GATE:conformance] Confirm never-acts + ask parity suites green after
      T021–T023.

**Checkpoint**: Feature complete for merge-bar hermetic properties; live legs remain named-runner.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T025 [P] [GATE:correlation] Assert `ask_answered` audit payloads still omit question and
      answer text and still carry authorising cell, corpus digest, disposition, and
      relevance-gate metadata (FR-008 as remediated) in
      `tests/conformance/answering/test_ask_record_content_free.py` (new or extend existing)
      (research R7).
- [ ] T026 [P] Close the ROADMAP entry *"An answer can be true, cited, on-subject and useless"*
      in `ROADMAP.md` (move to Shipped / remove from Next) with a one-paragraph note pointing at
      046 — only after US4 checkpoint **and** after T027's FR-010 measurement does not force a
      retrieval follow-on.
- [ ] T027 [GATE:conformance] Named-runner live legs L1–L3 per
      `specs/046-answer-usefulness/contracts/conformance-answer-usefulness.md` and
      `quickstart.md` §5: SC-002 sampling, SC-004 illustrative code, FR-010 retrieval offer
      measurement — **Dan McTeer**; if FR-010 shows the fact section never offered, do not claim
      the ROADMAP case closed; record the measurement in quickstart notes.
- [ ] T028 [P] Named-runner SC-001 walkthrough: three covered guidance questions; for each,
      a reader who does not open citations can restate the substance (3/3); record pass/fail in
      `specs/046-answer-usefulness/quickstart.md` notes — **Dan McTeer**.
- [ ] T029 Request sealed-core / security review for
      `src/adapters/anthropic_answering.py` changes (plan Constitution Check Principle V).
- [x] T030 Run `specs/046-answer-usefulness/quickstart.md` hermetic sections (§1–§4) and fix
      gaps; `make check` green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: none
- **Foundational (Phase 2)**: blocks all user stories
- **US1 → US2 → US3 → US4**: sequential recommended (same files: provider, ask.py, scorers);
  US2/US3 can parallelize tests after T002 if staffed carefully
- **Polish**: after US4 checkpoint

### User Story Dependencies

- **US1**: after Foundational — MVP
- **US2**: after T001 instruction exists; independently testable with recorded fixtures
- **US3**: after wire exposes `primary_answer` (T002); suite does not depend on portal
- **US4**: after US1–US3 behaviour landed

### Parallel Opportunities

```text
After T002:
  T005 || T006
  T010 || T011
  T014 || T015
After US4:
  T025 || T026
```

---

## Parallel Example: User Story 1

```bash
# After Foundational:
Task: "S1 shape row in tests/conformance/answering/test_primary_answer_shape.py"
Task: "Parity extension in tests/conformance/mcp/test_ask_parity.py"
# Then portal:
Task: "Primary-first + dual-shape in src/surfaces/portal/templates/_outcome.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 2 Foundational (T001–T004)
2. Phase 3 US1 (T005–T009)
3. **STOP** — demo answer-first Ask in the portal
4. Continue US2 → US3 → US4 before claiming usefulness/ROADMAP closure

### Incremental Delivery

1. Foundational → wire works
2. US1 → answer-first UX (MVP)
3. US2 → templates/snippets in-answer
4. US3 → sufficiency can fail
5. US4 → gates green
6. Polish → ROADMAP + live legs + review

---

## Notes

- Do **not** edit `src/adapters/anthropic_relevance.py` prompt text except to prove it unchanged (T020).
- Do **not** reshape estate answers.
- Security review owed on sealed adapter touch (T028).
- Commit after each task or logical group; Conventional Commits + sign-off when committing.
