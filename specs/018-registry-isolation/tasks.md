# Tasks: Registry isolation — the refusal is observed, not argued

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Branch**: `spec/018-registry-isolation`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Gate Task Types

| Gate type | Applies | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** | T006, T007, T012 — an unattributable refusal fails, a permitted write fails distinctly, and nothing skips |
| **Conformance** | **Yes** | The whole feature. It *is* a conformance row the constitution names |
| **Correlation / evidence** | **No** | Participates in no run and writes no audit entry. It observes the control plane refusing, from outside |
| **Eval** | **No** | Nothing promotes |
| **No-secret-leak** | **Yes** | T008 — the rows hold a real run's authority and print refusal output, which is where a token would surface |

---

## Phase 1: Setup

**Purpose**: Confirm the rows land somewhere a lane already runs. No new directory — 010 lost
a feature's rows to one no lane enumerated, and `tests/conformance/authority/` is already on
the recipe's `host_enclave` line.

- [ ] T001 Confirm `tests/conformance/authority` is named by the `host_enclave` pytest line in the `conformance` target in `Makefile`, and record the line number in `specs/018-registry-isolation/contracts/conformance.md` — "already enumerated" is exactly the assumption 010 made and paid for
- [ ] T002 Record the per-directory `pytest --collect-only -q` counts from `main` in `specs/018-registry-isolation/contracts/conformance.md`, as the baseline T024 compares against

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Derive the bounding set and obtain a real run's authority. Every story depends on
both.

- [ ] T003 Implement `bounding_paths()` in `tests/conformance/authority/bounding_records.py` — parse the **deployed** policy a run carries and return every path it may read in the authority jurisdiction. Each readable bounding path is one the run must not write, and that equivalence is what keeps the set from going stale. **Not** from Terraform source: reading configuration is the argument this feature replaces with evidence
- [ ] T004 Assert in `tests/conformance/authority/bounding_records.py` that the derived set is non-empty and raise if it is not — an empty set would make every row in this feature pass vacuously, which is the most dangerous way this gate can fail
- [ ] T005 Implement `run_authority()` in `tests/conformance/authority/bounding_records.py` — obtain a token carrying **all** the policies a run holds, as deployed. Not a synthesized single-grant token: the claim is that a run cannot write its bounds, and stripping its authority proves something narrower (research R2, correcting the spec's original FR-003)
- [ ] T006 [GATE:fail-closed] Implement `attempt_write()` in `tests/conformance/authority/bounding_records.py` returning one of four outcomes — REFUSED, UNATTRIBUTABLE, PERMITTED, UNREACHABLE. **A write is REFUSED only when the same authority can read the path**: verified 2026-07-31 that a nonexistent mount is denied in identical words to a real bounding record, so 403 alone would pass a row with one letter wrong in its path (FR-004aa)
- [ ] T007 [GATE:fail-closed] Implement the PERMITTED path in `tests/conformance/authority/bounding_records.py` — report it as its own outcome and **remove what was written**, reporting whether the removal succeeded. A red test is something someone reruns; a widened ceiling is a live condition the gate itself created (FR-004a, FR-004b)
- [ ] T008 [GATE:no-secret-leak] Add a redaction pass over refusal output in `tests/conformance/authority/bounding_records.py`, and a row asserting a token-shaped value is masked. **Build the fixture value from parts** — a literal matching the provider's published pattern gets the push blocked, correctly, and 017 paid for that on its first push

**Checkpoint**: the set is derived, a run's real authority is available, and the four outcomes are distinguishable.

---

## Phase 3: User Story 1 — A run cannot widen its own bounds, and that is observed (P1) 🎯 MVP

**Goal**: Every bounding path refuses a write under a real run's authority, observed rather than argued.

**Independent test**: Run the rows against the live control plane; every path refuses. Then, by hand, grant one write and confirm the row goes red.

- [ ] T009 [US1] Implement `test_a_run_cannot_write_any_bounding_record` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — attempt a real write to every derived path under a real run's authority and assert every outcome is REFUSED
- [ ] T010 [US1] Assert the **cross-definition** case in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a run may not widen *anyone's* bounds, not merely its own (US1 scenario 2)
- [ ] T011 [US1] Report the control plane's own account on failure from `tests/conformance/authority/bounding_records.py`, redacted, so a red row names what the control plane said rather than only that an assertion did not hold (FR-004)

**Checkpoint**: US1 is independently valuable — the constitution's row is in force for the first time.

---

## Phase 4: User Story 2 — The refusal comes from the control plane (P1)

**Goal**: The refusal is the control plane's, and it is attributable.

**Independent test**: Point a row at a path with a typo; it must fail, not pass.

- [ ] T012 [GATE:fail-closed] [US2] Implement `test_the_refusal_is_attributable` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — assert every derived path is **readable** by the same authority, so each refusal is about the capability rather than a wrong path
- [ ] T013 [US2] Add `test_a_typo_in_a_path_does_not_pass` to `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a deliberately misspelled path must produce UNATTRIBUTABLE and fail. **This is the row that would have caught the naive implementation**, and without it the guard is untested
- [ ] T014 [US2] Assert no row uses an administrator's authority, in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a refusal that never could have succeeded proves nothing, and an admin token would not be refused at all

---

## Phase 5: User Story 3 — Every place a run could widen a bound is covered (P2)

**Goal**: The set is derived, so a path added later is covered without anyone remembering.

**Independent test**: Add a read grant to the policy and confirm the new path appears in the set without a row being written.

- [ ] T015 [US3] Implement `test_the_bounding_set_is_derived_not_listed` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — assert the set comes from the deployed policy and contains no hard-coded members
- [ ] T016 [US3] Assert in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` that the set contains the six paths known at planning time, **as a floor rather than an equality** — an equality assertion would fail every time someone legitimately adds a bounding path, which trains people to edit the test rather than think
- [ ] T017 [US3] Add `test_ordinary_writes_are_not_in_scope` to `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a run's own secret space is untouched by this gate. **A check that drifted across that line would forbid the platform's purpose while looking stricter**, which is a worse failure than the one this feature fixes (FR-004c)

---

## Phase 6: User Story 4 — A gate row with no deferring record has a defined state (P2)

**Goal**: ADR-0047 names three states, and this row moves to in-force.

**Independent test**: A reviewer can determine, for any row not in force, which state it is in and where the reason is recorded.

- [ ] T018 [US4] Amend `docs/adr/0047-conformance-gate-rows-attach-as-features-land.md` at PATCH level — name **deferred by decision** (an ADR chose to postpone it; cite it) and **not yet applicable** (no feature carries it; nothing deferred it; the reason belongs in the feature's contract). Quote 004's contract, which predicted this fix and declined to invent a citation to satisfy the clause
- [ ] T019 [US4] Update `specs/004-primary-adapter/contracts/conformance-adapter.md` — the registry-isolation row moves from not-yet-attached to **in force**, citing this feature. FR-010: an amendment that described states without placing the row that prompted it would leave the situation it exists to end
- [ ] T020 [P] [US4] Update the Quality Gates row table in `ROADMAP.md` — registry isolation is in force and no longer unassigned

---

## Phase 7: Polish & cross-cutting

- [ ] T021 Perform the one-time demonstration by hand against a local enclave, and record it in `specs/018-registry-isolation/contracts/conformance.md`: the grant made, the row's failure output, the revocation, and **verification that the revocation took**. Never in a lane (FR-008) — a fixture killed between grant and revoke leaves a real control plane permissive with nobody watching
- [ ] T022 Record in `specs/018-registry-isolation/contracts/conformance.md` what a failure means when the run's read grant is removed — every row fails, correctly, reporting "could not attribute" rather than "isolation broke". Two opposite meanings, one colour
- [ ] T023 [P] Close the third open item in `ROADMAP.md` — the registry-isolation gate row now has an owning feature, and ADR-0047 distinguishes the two states 004 asked for
- [ ] T024 Run `make check` and `make conformance-hermetic`, and compare per-directory collection counts against the T002 baseline — the total rises because this feature adds rows, so only the pre-existing directories are the comparison (SC-007)

---

## Dependencies & Execution Order

```
Phase 1 (Setup)        T001 → T002
                           ↓
Phase 2 (Foundational) T003 → T004 → T005 → T006 → T007 → T008
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
Phase 3 (US1, P1)   Phase 4 (US2, P1)   Phase 6 (US4, P2)
   T009–T011           T012–T014           T018–T020
        └──────────────────┤                  │
                           ↓                  │
Phase 5 (US3, P2)      T015–T017              │
                           └──────────────────┘
                                    ↓
Phase 7 (Polish)             T021–T024
```

**Story dependencies**: US1 and US2 are independent once Phase 2 lands — one asserts the
refusal, the other asserts it is attributable. US3 depends on US1 existing, because it checks
the set those rows iterate. **US4 is entirely independent of all of them** — it amends a
record and touches no code, and could be done first if the gate stalled.

**Parallel opportunities**:

- T018–T020 with any of Phases 3–5: the ADR amendment shares no file with the rows
- T020 with T019; T023 with T021–T022

**MVP scope**: **Phases 1–3.** US1 alone puts the constitution's row in force for the first
time since it was written. US2 should follow immediately — without it a typo passes — but US1
has standalone value on the day it lands.

---

## Notes

**T004 guards the most dangerous failure in this feature.** If `bounding_paths()` returned an
empty set, every row would iterate nothing and pass. A gate that asserts isolation while
asserting nothing at all is worse than no gate, because it is believed.

**T013 is the row that tests the guard.** T006 implements the read discriminator; T013 proves
it works by feeding it a path that does not exist. Without T013 the discriminator is
untested, and an implementation that quietly dropped it would look identical.

**T016 asserts a floor, not an equality, on purpose.** Six bounding paths exist today and one
of them arrived the day the spec was written. An equality assertion would go red the next
time someone legitimately adds a bounding record — training whoever hits it to edit the test
rather than ask why the set changed.

**T021 is the only task that touches real authority, and it is manual.** Everything else
observes refusals that already occur.
