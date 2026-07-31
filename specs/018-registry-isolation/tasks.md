# Tasks: Registry isolation — the refusal is observed, not argued

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Branch**: `spec/018-registry-isolation`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Gate Task Types

| Gate type | Applies | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** | T003d — the named half is checked against the control plane's own enumeration, so it cannot be quietly incomplete. T003e — and it cannot quietly shrink. T003b — a bounding record that exists in ANY derived jurisdiction but was never derived fails, so coverage is not blind in the one direction a derivation cannot see. T007a — nothing in the suite may widen authority, asserted rather than trusted. T006, T007, T012 — an unattributable refusal fails, a permitted write fails distinctly, and nothing skips |
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
- [ ] T003a Implement `existing_bounding_prefixes()` in `tests/conformance/authority/bounding_records.py` — **derive the jurisdictions from the bounding paths themselves** (two mounts at planning time: the authority store and the agent registry) and enumerate what actually exists in each, using administrator authority. **Derived, not named**: a bounding record added in a third mount extends the check without anyone editing it, and hard-coding one mount would leave the registry — the record deciding whether a definition exists at all — outside the very check added to close the fail-open hole. Legal here and only here: this is a COVERAGE act, and FR-002a forbids it from ever asserting a denial
- [ ] T003b [GATE:fail-closed] Assert in `tests/conformance/authority/bounding_records.py` that every existing prefix **in every derived jurisdiction** appears in the set, or is on the exclusion list defined in that same module with a reason in source. **Every exclusion must name something that exists** — a stale entry fails rather than hides, which is the difference between an exclusion list and a subject list and the reason 017 accepted one after rejecting the other — **the direction a derivation cannot see by construction** (FR-006a). A record placed where a run cannot read still bounds that run, because the platform consults it whether or not the run can; 017 found the identical hole in its own coverage after four analysis passes
- [ ] T003c Define `NAMED_BOUNDS` in `tests/conformance/authority/bounding_records.py` — the bounds a run **cannot read** and which bind it anyway: the grant of authority itself, the rule deciding which grants a run receives, **the configuration deciding whose identities are trusted at all**, the mounts the control plane serves, and the attachment of grants to identities and groups. Seven surfaces, not the three pass 3 named — and the missing one that outranks them all is the trusted-key configuration: write it and the control plane starts believing identities somebody else mints. Each entry carries the reason it cannot be derived. **This is the more direct route to widening authority and it was missed for two analysis passes** — a run's limits are stated twice, once as a record the platform consults and once as the grant the control plane enforces, and rewriting the second moves the bound without touching the first
- [ ] T003d [GATE:fail-closed] Implement `enumerate_configuration_surfaces()` in `tests/conformance/authority/bounding_records.py` — ask the control plane, under administrator authority, for **the four kinds it genuinely enumerates**: its mounts, its auth methods, the roles those methods issue, and the grants it holds. Assert every member of those four is in `NAMED_BOUNDS` or excluded with a reason (FR-006aa). A COVERAGE act under FR-002a, never an assertion of denial.
  **Four kinds, not "everything policy-affecting".** A control plane enumerates what it HAS; it does not enumerate what BOUNDS A RUN, which is a judgement. An earlier draft asked for the latter — undecidable, since the system administration tree alone exposes dozens of write paths — and an implementer meeting that phrase would have enumerated these same four and believed the set complete, which is the hand-chosen list this check replaced wearing a mechanism's clothes
- [ ] T003e [GATE:fail-closed] Split `NAMED_BOUNDS` in `tests/conformance/authority/bounding_records.py` into the entries **T003d can confirm** (members of the four enumerated kinds) and the entries **only a judgement put there** — then assert the second group by name. T003d already covers the first, so naming those adds nothing; the second group is what nothing else would notice shrinking, and stating which is which is the difference between two checks and one check plus a duplicate
- [ ] T003f Record the residual in `specs/018-registry-isolation/contracts/conformance.md` (FR-006ab) — a surface that bounds a run and is not a member of the four enumerated kinds is outside this check, and sits in the named half only because somebody judged it belonged. **A named limit is worth more than a predicate that reads as total and is not**, which is what the previous four analysis passes were each about
- [ ] T004 Assert in `tests/conformance/authority/bounding_records.py` that the derived set is non-empty and raise if it is not — an empty set would make every row in this feature pass vacuously, which is the most dangerous way this gate can fail
- [ ] T005 Implement `run_authority()` in `tests/conformance/authority/bounding_records.py` — obtain a token carrying **all** the policies a run holds, as deployed. Not a synthesized single-grant token: the claim is that a run cannot write its bounds, and stripping its authority proves something narrower (research R2, correcting the spec's original FR-003)
- [ ] T006 [GATE:fail-closed] Implement `attempt_write()` in `tests/conformance/authority/bounding_records.py` returning one of four outcomes — REFUSED, UNATTRIBUTABLE, PERMITTED, UNREACHABLE. **A write is REFUSED only when the same authority can read the path**: verified 2026-07-31 that a nonexistent mount is denied in identical words to a real bounding record, so 403 alone would pass a row with one letter wrong in its path (FR-012)
- [ ] T007 [GATE:fail-closed] Implement the PERMITTED path in `tests/conformance/authority/bounding_records.py` — report it as its own outcome and **remove what was written**, reporting whether the removal succeeded. A red test is something someone reruns; a widened ceiling is a live condition the gate itself created (FR-004a, FR-004b)
- [ ] T007a [GATE:fail-closed] Add `test_nothing_here_widens_authority` to `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — assert by source inspection that no module **writes a policy or grants a capability** (FR-008b). **Scoped to the act, not the authority**: reading with an administrator's token is neither, and is required by T003a. A check keyed on which authority appears would forbid the enumeration another task mandates — the same shape as 017's rule that forbade retry loops in words that caught its own readiness wait. The sharpest safety property in the feature rested entirely on nobody adding such a fixture later; a property enforced by everyone remembering is the shape this repository has paid for more than once
- [ ] T008 [GATE:no-secret-leak] Add a redaction pass over refusal output in `tests/conformance/authority/bounding_records.py`, and a row asserting a token-shaped value is masked. **Build the fixture value from parts** — a literal matching the provider's published pattern gets the push blocked, correctly, and 017 paid for that on its first push

**Checkpoint**: the set is derived AND cross-checked against what exists, a run's real authority is available, the four outcomes are distinguishable, and nothing in the package can widen authority.

---

## Phase 3: User Story 1 — A run cannot widen its own bounds, and that is observed (P1) 🎯 MVP

**Goal**: Every bounding path refuses a write under a real run's authority, observed rather than argued.

**Independent test**: Run the rows against the live control plane; every path refuses. Then, by hand, grant one write and confirm the row goes red.

- [ ] T009 [US1] Implement `test_a_run_cannot_write_any_bounding_record` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — attempt a real write to every **derived** path under a real run's authority and assert every outcome is REFUSED
- [ ] T009a [US1] Implement `test_a_run_cannot_write_the_grant_itself` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — attempt a real write to every entry in `NAMED_BOUNDS` and assert every outcome is REFUSED. **The row the feature is named after**: writing the grant of authority widens a run's bounds directly, bypassing every record the derived rows check. Probed 2026-07-31 — all three refuse today, so this asserts a property that holds rather than finding one that does not
- [ ] T010 [US1] Assert the **cross-definition** case in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a run may not widen *anyone's* bounds, not merely its own (US1 scenario 2)
- [ ] T011 [US1] Report the control plane's own account on failure from `tests/conformance/authority/bounding_records.py`, redacted, so a red row names what the control plane said rather than only that an assertion did not hold (FR-004)

**Checkpoint**: US1 is independently valuable — the constitution's row is in force for the first time.

---

## Phase 4: User Story 2 — The refusal comes from the control plane (P1)

**Goal**: The refusal is the control plane's, and it is attributable.

**Independent test**: Point a row at a path with a typo; it must fail, not pass.

- [ ] T012 [GATE:fail-closed] [US2] Implement `test_the_refusal_is_attributable` in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — assert every **derived** path is readable by the same authority, so each refusal is about the capability rather than a wrong path
- [ ] T012a [US2] Attribute the `NAMED_BOUNDS` refusals differently in the same file, and say why: **a run cannot read them either**, so the read discriminator does not apply. Confirm each path exists using administrator authority instead — a COVERAGE act under FR-002a, never an assertion of denial. Without this the named rows have the exact defect T013 exists to catch, one set over
- [ ] T013 [US2] Add `test_a_typo_in_a_path_does_not_pass` to `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` — a deliberately misspelled path must produce UNATTRIBUTABLE and fail. **This is the row that would have caught the naive implementation**, and without it the guard is untested
- [ ] T014 [US2] Assert in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` that **no refusal assertion uses administrator authority** — a denial to an administrator proves nothing, because an administrator is not what the claim is about. Scoped to refusal assertions rather than to the whole package: the coverage enumeration in T003a legitimately needs admin, and an earlier draft of this task forbade the thing another task requires (FR-002a)

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
- [ ] T022 Assert in `tests/conformance/authority/test_a_run_cannot_move_its_own_bounds.py` that `specs/018-registry-isolation/contracts/conformance.md` states the gate does not assert the records' contents are correct (FR-011) — checked rather than trusted, because a later edit could remove the statement and let a green row imply more than it asserts. Then record in that same contract what a failure means when the run's read grant is removed — every row fails, correctly, reporting "could not attribute" rather than "isolation broke". Two opposite meanings, one colour
- [ ] T023 [P] Close the third open item in `ROADMAP.md` — the registry-isolation gate row now has an owning feature, and ADR-0047 distinguishes the two states 004 asked for
- [ ] T024 Run `make check` and `make conformance-hermetic`, and compare per-directory collection counts against the T002 baseline — the total rises because this feature adds rows, so only the pre-existing directories are the comparison (SC-007)

---

## Dependencies & Execution Order

```
Phase 1 (Setup)        T001 → T002
                           ↓
Phase 2 (Foundational) T003 → T003a → T003b → T003c → T003d → T003e
                       → T004 → T005
                       → T006 → T007 → T007a → T008
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
Phase 3 (US1, P1)   Phase 4 (US2, P1)   Phase 6 (US4, P2)
   T009–T011, T009a           T012–T014, T012a           T018–T020
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

**T003b guards the second most dangerous, and it is subtler.** A non-empty set can still be
incomplete: the derivation reads a run's read grants, so a bounding record placed outside them
is invisible to it — and a record the run cannot read still bounds that run, because the
platform consults it regardless. Analysis found this, as it found the identical hole in 017's
coverage after four passes. The cross-check is the only direction the derivation cannot see by
construction.

**T003d exists because T003c was the wrong shape, and the reasoning was already written
down.** A hand-written list of bounds is a *subject* list. This feature's own checklist
records why 017 accepted an exclusion list after rejecting one: a stale exclusion names
something absent and fails, a stale subject list omits in silence. The named half was
introduced as a subject list anyway and was incomplete the day it was written — missing the
trusted-key configuration, which outranks every record in either half, because writing it
makes the control plane believe identities somebody else mints.

So both halves now have a completeness check, and neither rests on someone maintaining a
list. Four analysis passes, four coverage mechanisms, and this is the second distinct
anti-pattern the feature documented and then committed.

**T003c is the third-order version, and the sharpest.** A run's limits are stated twice —
once as a record the platform consults, and once as the grant the control plane enforces.
Every design before analysis pass 3 checked the first and missed the second, which is the
more direct route: rewriting the grant moves the bound without touching any record. It sits
outside both halves by construction, because a run holds no read access to it and nothing
derived from a run's grants can see it. Named, therefore, and the naming is not a shortcut —
it is the only thing that works.

**T003a's jurisdictions are derived, and that is the second-order version of the same
mistake.** Pass 1 added the cross-check to close a fail-open hole; pass 2 found the
cross-check itself covered the mount you would think of first and not the second. The
bounding paths span two — the authority store and the agent registry — so the jurisdictions
come from the paths rather than from a name, and a third extends the check for free.

**T003a and T014 are the pair to read together.** Enumerating what exists needs administrator
authority; asserting a refusal must never use it, because a denial to an administrator proves
nothing. An earlier draft of T014 forbade the whole package from touching admin authority,
which would have made T003a impossible — the resolution is a distinction between two kinds of
act, not a compromise between them.

**T013 is the row that tests the guard.** T006 implements the read discriminator; T013 proves
it works by feeding it a path that does not exist. Without T013 the discriminator is
untested, and an implementation that quietly dropped it would look identical.

**T016 asserts a floor, not an equality, on purpose.** Six bounding paths exist today and one
of them arrived the day the spec was written. An equality assertion would go red the next
time someone legitimately adds a bounding record — training whoever hits it to edit the test
rather than ask why the set changed.

**T021 is the only task that touches real authority, and it is manual.** Everything else
observes refusals that already occur.
