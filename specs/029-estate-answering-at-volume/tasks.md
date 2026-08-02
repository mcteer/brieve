# Tasks: Estate answering at real volume

**Input**: Design documents from `/specs/029-estate-answering-at-volume/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — all three findings were invisible to the existing rows, and each task that
adds behaviour adds the row that would have caught its finding.

**Organization**: by user story. US1 (routing) and US2 (relevance) are both P1 and independent;
US3 (the newest window) arrives as the branch's first commit and its remaining work is the
both-implementations discipline. The foundational phase is the query-layer bound both P1 stories
sit on.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Cherry-pick `fix/evidence-read-returns-the-newest-window` (commit `21e71a3`) onto the
      implementation branch as its first commit — the US3 fix, its seven rows (verified to fail
      against the old behaviour), and the corrected causal story in
      `src/core/audit/postgres_query.py` / `tests/harness/memory_evidence.py` /
      `tests/component/test_evidence_read_window.py`. Then `make check` to confirm a clean graft
      before anything is built on it.

## Phase 2: Foundational — the per-type bound, in both implementations, with teeth

- [ ] T002 `EvidenceQueryRequest` in `src/core/audit/query.py` gains
      `limit_per_type: int | None = None` — additive and defaulted, the same seam-versioning shape
      025 used for `event_types`. Docstring carries the measured reason: one bound over
      undifferentiated types is a competition, and at any row count the common types crowd out the
      rare ones (60 `run_start` in a window of 1,000 at 63,947 readable). `None` is byte-for-byte
      today's read.
- [ ] T003 The in-memory twin in `tests/harness/memory_evidence.py`: when `limit_per_type` is set
      with `event_types`, fill per-type buckets from the newest end over the existing sort, return
      oldest-first overall; carry **window accounting** — per requested type, returned vs matched —
      on the result (the `SearchResult` shape from data-model.md, chosen so no existing `search()`
      caller breaks). `limit_per_type=None` follows today's path untouched.
- [ ] T004 The Postgres implementation in `src/core/audit/postgres_query.py`: one windowed query —
      `ROW_NUMBER() OVER (PARTITION BY event_type ORDER BY timestamp DESC, correlation_id DESC,
      seq DESC)` filtered to `<= limit_per_type`, plus `COUNT(*) OVER (PARTITION BY event_type)`
      for the accounting, outer query restoring ascending order. **One query, never one per type.**
      Comment names the finding and the volume that exposed it.
- [ ] T005 [GATE:fail-closed] Property rows in `tests/component/test_evidence_read_window.py`,
      **written once and parametrized over implementations** (the in-memory one runs hermetically;
      the Postgres parameter is enclave-marked and runs in T018): rare types not crowded out at the
      measured skew; newest-per-type selection; oldest-first return; `limit_per_type=None`
      reproduces today; zero returns nothing (the `[-0:]` trap, again); accounting counts returned
      vs matched correctly; **scope untouched** — results always a subset of `event_types`, tenant
      bound intact.
- [ ] T006 [P] [GATE:conformance] The SQL-shape row beside the Postgres implementation: the
      generated SQL carries `PARTITION BY` exactly when `limit_per_type` is set and never
      otherwise — the hermetic half of a differential that cannot honestly be hermetic
      (plan, Complexity Tracking).
- [ ] T007 [GATE:conformance] The mutation check, performed and **recorded in
      `specs/029-estate-answering-at-volume/contracts/conformance.md`**: flip the window selection
      in one implementation only (oldest-first fill), observe T005's parametrized rows fail, revert.
      The discipline that would have caught finding three, applied before the rows are trusted.

**Checkpoint**: the read can bound per type, both implementations agree, and the rows could have
seen them disagree.

## Phase 3: User Story 1 — a question about my estate reaches my estate (P1)

**Goal**: the trail's nouns join the router's vocabulary; the five failed questions route.

**Independent test**: SC-007's questions route to estate; the guidance regression set stays
guidance.

- [ ] T008 [US1] Grow `ESTATE_TERMS` in `src/core/answering/routing.py` with the trail's nouns:
      `tool`, `tools`, `agent`, `agents`, `secret`, `secrets`, `used`, `active` (research F1 —
      drawn from `AuditEventType`'s own members, the discipline the module docstring already
      prescribes; `did` deliberately excluded as too common). The mechanism — term overlap, ties
      to estate — is untouched.
- [ ] T009 [US1] [GATE:conformance] The routing rows in `tests/component/test_ask_routing.py`:
      SC-007's five questions (*"Which tools were used?"*, *"What did the planner agent do?"*,
      *"Were any secrets read?"*, *"Which agents are active?"*, *"What ran today?"*) route to
      `ESTATE`; a **guidance regression set** — including *"How do I read a secret?"* and
      *"How should I configure the vault agent?"*, the eager-routing shapes research F1 names —
      keeps routing to `GUIDANCE`; and genuinely unroutable questions still return `NEITHER`.
      A term that cannot survive both sets is a wrong term, not a reason to bend the tie-break —
      the row's docstring says so, because that is the argument the next term-adder needs.

**Checkpoint**: the five questions reach the evidence plane; no guidance question was captured.

## Phase 4: User Story 2 — the answer rests on the records the question is about (P1)

**Goal**: a question's types get the window; the answer says when it was a window.

**Independent test**: at the measured skew, a runs question is answered from predominantly run
records, and the answer carries the window note.

- [ ] T010 [US2] Create `src/core/answering/focus.py`: `focus_types(question) ->
      frozenset[AuditEventType] | None` — the deterministic term→types table from data-model.md
      (runs → `RUN_START/RUN_STOPPED/RUN_RESUMED`; tools/used → `TOOL_CHOSEN/TOOL_OUTCOME`;
      denied/refused → `AUTHORITY_DENIED/AUTHORITY_REFUSED`; secrets → `EFFECT_OBSERVED`;
      agents/active → `RUN_START`; failed/error → `ENFORCEMENT_ERROR/RUN_STOPPED`). `None` for no
      recognised focus. Module docstring: same vocabulary discipline as `routing.py`, no roles, no
      clock, no store — and why this lives in `answering`, not `audit` (the query layer stays
      ignorant of questions).
- [ ] T011 [P] [US2] [GATE:fail-closed] The focus rows in `tests/component/test_estate_focus.py`:
      each SC-007 question maps to the types its answer needs; an unfocused question returns
      `None`; and the **composition properties** — `focus ∩ visible` is always a subset of
      visible (never widens, FR-005), an empty intersection falls back to `visible` (a role that
      cannot see the asked-about type must not masquerade as an empty estate while FR-009 is
      open), and an empty *visible* still refuses before any read (025's rule, re-asserted where
      the new code could have eroded it).
- [ ] T012 [US2] Wire the ask path in `src/surfaces/api/ask.py`: `estate_answer_for` computes
      `focus_types(question)`, passes `focus ∩ visible` (falling back to `visible` when the
      intersection is empty or focus is `None`) and `limit_per_type` (a named constant with the
      measured rationale) to `read_evidence_for`; threads the read's window accounting through to
      the answer. `read_evidence_for` in `src/surfaces/api/evidence.py` gains the pass-through —
      additive, defaulted, no existing caller changes.
- [ ] T013 [US2] The answer's `window_note` in `src/core/answering/estate.py`: present exactly
      when a requested type was truncated, carrying what the answer rests on and what was left out
      (*"the 200 most recent run records of 1,847 today"*); absent otherwise, so a small estate
      renders as before. **On the answer, never the `ASK_ANSWERED` record** — the comment carries
      the reason (the trail's access record already serves the investigator; the asker is about to
      act), because that line is what keeps this feature out of sealed core.
- [ ] T014 [US2] [GATE:conformance] **The volume row** in
      `tests/conformance/answering/test_estate_at_volume.py`: rebuild the live composition —
      hundreds of `effect_observed`/`pre_decision` against tens of `run_start`, thousands of
      entries total — and assert a runs question through the full ask path is answered from
      predominantly run records (SC-002 in the exact shape that failed), that the answer carries
      the window note with true counts, and that an un-truncated small estate carries none.
- [ ] T015 [US2] [GATE:conformance] The window note on both surfaces: the API response and the MCP
      payload carry it identically (they share the answer functions, so this is one row per
      surface over the same fixture); `tests/component/test_portal_asks.py` gains the rendering
      row — the note appears with the answer, as plain content.
- [ ] T016 [US2] The portal rendering in `src/surfaces/portal/templates/ask.html`: the window note
      under the claims, plain page content in the same visual register as the source line — no new
      JS, no live region (028's discipline holds).

**Checkpoint**: a runs question at 63,947-entry skew answers about runs, and says what it rests on.

## Phase 5: User Story 3 — the newest window, in both implementations (P2)

**Goal**: the cherry-picked fix holds under the parametrized rows, including against real Postgres.

**Independent test**: T005's rows pass with the Postgres parameter against seeded volume.

- [ ] T017 [US3] [GATE:conformance] The enclave half: the T005 property rows' Postgres parameter in
      the enclave lane (beside `tests/conformance/api`'s evidence rows, enclave-marked), seeded
      with thousands of entries at the measured skew — newest window, per-type bound, accounting,
      scope, all against the real store. This is the half of FR-008 a hermetic lane cannot
      honestly claim, stated as such in the contract.

**Checkpoint**: both implementations proven on the behaviour, not only the shape.

## Phase 6: Polish & cross-cutting

- [ ] T018 [P] The a11y answered-state row covers the window note (the ask page's answered state
      gains visible content): extend the estate-answer fixture in `tests/a11y/conftest.py` so the
      note renders, and confirm `tests/a11y/test_wcag.py`'s estate row still passes.
- [ ] T019 [P] Update `specs/029-estate-answering-at-volume/contracts/conformance.md` status rows
      as they land (including T007's mutation-check record), and the ROADMAP entry for 029 — the
      three findings, the fix shape, and the **two recorded decisions still owed**: `operator`
      visibility of authority records (FR-009), and 025's `estate_state` suite scoring a question
      no operator can ask (re-aim it, or score it as `compliance-analyst`).
- [ ] T020 `make check`, the hermetic conformance sweep, and `make a11y` all green; then
      `make conformance` on the live enclave (includes T017). **Runner: Dan McTeer** for the
      enclave half.
- [ ] T021 SC-007 against the live tenant — **named runner: Dan McTeer**, per quickstart §5: the
      five questions through the deployed portal at 236k entries; answers about runs cite run
      records; truncated answers say what they rest on; *"Which runs were denied?"* still declines
      for an operator, correct under FR-009 until decided otherwise.

---

## Dependencies

```text
Phase 1 (T001, the cherry-pick)
  → Phase 2 (T002 → T003 ∥ T004 → T005 → T006 ∥ T007)
    → Phase 3 / US1 (T008 → T009)          [independent of Phase 4]
    → Phase 4 / US2 (T010 → T011 ∥ T012 → T013 → T014 → T015 → T016)
      → Phase 5 / US3 (T017)               [needs T005's parametrization]
        → Phase 6 (T018 ∥ T019 → T020 → T021 last)
```

US1 and US2 are independent after Phase 2; either alone is shippable, both are needed for SC-007.

## Parallel opportunities

- T003 ∥ T004 (different files, one behaviour — T005 is what forces the agreement).
- T006 ∥ T007; T008/T009 ∥ T010/T011; T018 ∥ T019.

## Implementation strategy

**MVP = Phase 2 + Phase 4** — the read stops starving, which is the finding that makes the
capability unusable. Phase 3 is small and independent; land it in the same PR. The two named runs
(T020's enclave half, T021) and the mutation-check record (T007) close the feature.

## Notes

- **Gate types**: fail-closed (T005, T011), conformance (T006, T007, T009, T014, T015, T017,
  T020), plus a11y coverage (T018).
- **No sealed core, no Principle V review** — held by T013's design line (the note on the answer,
  never the record). If implementation finds that line untenable, that is a finding to surface,
  not a payload to grow quietly.
- **The one constant**: `limit_per_type`'s value at the ask path — named, with the measured
  rationale, in one place (T012).
- **What would make this feature fail honestly**: a term or focus mapping that captures guidance
  questions. The regression sets are the guard, and a term that cannot survive both is a wrong
  term.
