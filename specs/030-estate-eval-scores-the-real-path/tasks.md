# Tasks: The estate eval scores the path a person's question takes

**Input**: Design documents from `/specs/030-estate-eval-scores-the-real-path/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the feature is itself a correction to what a gate proves, so every
behavioural task lands with the row that could catch its own removal.

**Organization**: by user story. One ordering is load-bearing: **the parse validation and the role
tags land together** (T002+T003) — the validation refuses untagged estate cases, so a commit
carrying one without the other turns the blocking gate red in between.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

*(none — no dependency, no scaffolding. The eval harness and both packs already exist.)*

## Phase 2: Foundational — the case knows who could ask it

- [X] T002 `EvalCase` in `src/core/evals/suites.py` gains `asker_role: str = ""`, and
      `parse_cases` validates it for estate cases only: absent → `UnrunnableSuite` naming the
      case; outside the platform's role vocabulary → likewise. The vocabulary is
      `ROLE_VISIBILITY`'s keys **imported from `core.answering.scope`**, never copied — a second
      role list is the fragmentation seam. Never defaulted, and the docstring says why: a
      defaulted role is the implicit assumption this feature removes, reappearing one field over.
      Non-estate suites ignore the field.
- [X] T003 Tag every estate case in `packs/vault/evals/estate_state.toml` and
      `packs/terraform/evals/estate_state.toml` with `asker_role`, following **the expected set,
      not the prompt** (research F3): vault 001/002/003/005 → `compliance-analyst` (002 expects
      `rec-vault-002`, an `authority_denied` record, among its three — the finding inside the
      finding), vault 004 → `operator`; terraform 001/004/005 → `compliance-analyst`, 002/003 →
      `operator`. **The terraform assignment was corrected by the analysis pass** (C1): the plan
      said two denied-cases, and measuring the expected sets found three — terraform-004, *"What
      happened during the staging plan run?"*, expects an `authority_denied` record among its
      three, which is vault-002's finding-inside-the-finding recurring one pack over. Tagged the
      plan's way, the visibility check would have refused it at load and turned the gate red —
      the tag follows the expected set, and the expected set has to be *measured*, not skimmed.
      **Same commit as T002.** Each file's header gains the statement of
      what this suite still does not exercise (research F5): the governed read and its access
      record, temporal windows, the per-type bound.

**Checkpoint**: every estate case declares its asker, the gate still passes, and an untagged case
cannot load.

## Phase 3: User Story 2 — the eval exercises what stands between a question and its records (P1)

**Goal**: the scorer narrows to the case's declared role before the answering function sees a
record, and a case expecting the invisible refuses to load.

**Independent test**: a recording provider under an operator case receives no authority records;
an operator case expecting one is `UnrunnableSuite`.

- [X] T004 [US2] The visibility check in `src/core/evals/scoring.py`, in
      `EstateAnsweringScorer._answer` — **the place case and fixture actually meet** (analysis
      C2: the plan sited this at `__init__`, which never sees a case; cases arrive per call).
      Before narrowing, every id in the case's `events` must resolve to a record whose type the
      case's `asker_role` may see; a violation is `UnrunnableSuite` naming the case, the
      reference and the invisible type. Per-case and loud — a refusal mid-suite is still a
      refusal, never an exclusion-by-silence (FR-003).
- [X] T005 [US2] The narrowing in `EstateAnsweringScorer._answer`: records handed to
      `answer_estate_question` become the fixture's ∩ `visible_event_types({case.asker_role})`.
      The scorer's class docstring gains the honest-scope statement: what this drives (role
      visibility — this feature's finding) and what it deliberately does not (the governed read,
      windows, the per-type bound; driving those would put an evidence store and an access record
      per case inside the eval — research F1). This closes 024's "scores a path the product does
      not take", one layer in, for the piece the finding is about.
- [X] T006 [P] [US2] [GATE:fail-closed] The rows in
      `tests/component/test_estate_eval_scores_visibility.py`: an estate case with no
      `asker_role` refuses at parse; an unknown role refuses at parse; an operator case expecting
      an authority reference refuses at scorer construction (the row that would have caught the
      original defect); a recording provider under an operator-declared case **never receives** a
      record outside operator visibility (the row that fails when somebody deletes the narrowing
      — research F4 direction 1); a compliance-analyst case still receives all five; and the
      role vocabulary is asserted to be `ROLE_VISIBILITY`'s own keys, not a copy.
- [X] T007 [US2] [GATE:conformance] The blocking gate over the tagged suites:
      `tests/component/test_eval_gates.py` passes with identical verdicts — narrowing changes
      what the provider *could* see, and correctly tagged cases rest only on what their role
      sees, so no verdict moves. The contract's vacuous-mutation note is referenced from the row
      that would tempt it (research F4: re-running tagged cases without narrowing passes, so that
      is NOT the check).

**Checkpoint**: the suite scores what each declared role would receive, and both failure
directions have rows.

## Phase 4: User Story 1 — a qualified cell means what it says (P1)

**Goal**: what a cell's estate evidence asserts is decided in the open and written down.

**Independent test**: ADR-0059 exists, Accepted, and the suites' declared roles match what it
says a cell's evidence spans.

- [X] T008 [US1] Write `docs/adr/0059-estate-eval-evidence-spans-asker-roles.md`: the matrix
      schema is untouched (`role` stays the agent role); a cell's estate evidence **spans the
      asker roles its cases declare**; qualification requires **every declared role's subset to
      pass**. Context carries the finding (three-fifths of the estate evidence behind the first
      two live cells was gathered for a role production does not grant) and 024's lineage.
      Rejected with reasons: per-visibility cells (combinatorial, and an ask serves whichever
      role asks) and visibility smuggled into `judge`. Status Accepted, relates to
      ADR-0022/0039/0035. **Review: Dan McTeer, merges with this feature.**
- [X] T009 [P] [US1] [GATE:conformance] The agreement row in
      `tests/component/test_estate_eval_scores_visibility.py`: the set of roles declared across
      each pack's estate cases is exactly what ADR-0059 says the evidence spans
      (`{operator, compliance-analyst}` today) — so a case file quietly dropping a role, or
      adding one the ADR does not name, fails a row rather than silently changing what a cell
      asserts.

**Checkpoint**: the claim a cell makes is written, reviewed, and pinned by a row.

## Phase 5: User Story 3 — the two live cells are re-examined (P2)

**Goal**: the cells earned 2026-08-02 are confirmed, re-earned, or withdrawn on corrected
evidence — not grandfathered.

**Independent test**: the matrix variables record the outcome with a date.

- [ ] T010 [US3] `make evals-smoke` then `make evals-live` under the corrected suite — **named
      runner: Dan McTeer** (~25 min, vendor cost). The narrowing is already in the path both
      lanes share, so this is the same lane that earned the cells, now scoring what each role
      would receive.
- [ ] T011 [US3] Record the outcome in `infra/environments/dev/variables.tf`: **pass** → the two
      cells' comments gain "re-examined 2026-08-0X under role-scoped evidence (030), confirmed";
      **fail for any role subset** → the affected cells gain `withdrawn = true` and the apply is
      run, with quickstart §3's consequence pre-stated (the deployed ask refuses
      `unqualified_cell` until an operator rebinds — the mechanism working, not an outage).
      Either way the matrix says what happened rather than leaving the cells standing on
      superseded evidence unexamined.

**Checkpoint**: no live cell stands on evidence this feature discredited.

## Phase 6: Polish & cross-cutting

- [X] T012 [P] Update this feature's `contracts/conformance.md` status rows as they land, and the
      ROADMAP entry for 030: the finding (024's, one layer in), the four-of-five correction, the
      vacuous-mutation note, ADR-0059's shape, and the standing deferrals restated (operator
      visibility of authority records — still owed from 029; the un-scored path pieces, now
      stated at the suites).
- [X] T013 `make check`, `make evals`, and the hermetic conformance sweep green. (No enclave lane
      needed — nothing in this feature touches a deployed surface or the store.)

---

## Dependencies

```text
Phase 2 (T002 ∥→ T003, SAME COMMIT — the validation refuses untagged cases)
  → Phase 3 / US2 (T004 → T005 → T006 ∥ T007)
  → Phase 4 / US1 (T008 ∥ T009)        [independent of US2 after Phase 2]
    → Phase 5 / US3 (T010 → T011)      [needs the corrected suite from US2]
      → Phase 6 (T012 ∥ T013)
```

## Parallel opportunities

- T006 ∥ T007 (different files); T008 ∥ T009; T012 ∥ T013.
- US1's ADR can be drafted while US2's rows run — they meet only at T009.

## Implementation strategy

**MVP = Phases 2–3**: the suite stops scoring records no grantable role could receive, with both
failure directions pinned. US1 writes down what that means for the matrix; US3 applies it to the
two cells already standing. The named run (T010) and the ADR review (T008) are the merge gate's
human halves.

## Notes

- **Task numbering starts at T002** — a deliberate gap where a setup phase would be, so the
  foundational pair keeps the numbers the dependency graph refers to.
- **Gate types**: fail-closed (T006), conformance (T007, T009); the live re-run is a named human
  activity, not a lane.
- **No sealed core, no Principle V review** — fourth feature running. One human review instead:
  ADR-0059's (T008).
- **What would make this feature fail honestly**: a role tag chosen by the prompt's vibe rather
  than the expected set. T004's check catches the visible half; T009 catches the drift half.
