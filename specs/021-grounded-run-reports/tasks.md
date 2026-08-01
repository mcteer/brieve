# Tasks: A report compiles from records, or it says it could not

**Input**: Design documents from `/specs/021-grounded-run-reports/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required. The compiler is hermetic by construction — records in, report out — so the rows that matter most need no enclave, no provider, and no live product.

**Organization**: By user story. US1 and US2 are P1; US3 is P2 and is the one the Constitution Check sent back for redesign.

## Format: `[ID] [P?] [Story] Description`

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — an unreconcilable claim, an unreachable product, a failed meta-audit write | T014, T016, **T024**, T031 |
| **Conformance** | **Yes** — sealed-core seam, and a transport surface that grows the parity row | **T051** |
| **Correlation / evidence** | **Yes** — a new audit event joins the run's trail, and compiling is itself an audited read | **T009**, **T030**, **T042** |
| **No-secret-leak** | **Yes** — a report reads everything a run recorded | **T017**, T033 |
| **Eval** | **Yes** — the fifth suite is the point | Phase 6, **T036–T040** |

> **This table names task IDs, not phase ranges, and pass 2 is why.** It previously said
> "Phases 3–6" for conformance while the only `[GATE:conformance]` task was T051 in Phase 7, and
> omitted T042 from correlation. A gate table that points at a range is a table nobody can check;
> one that names IDs can be diffed against the tags. 019's conformance contract carried a stale
> table through six analysis passes.

---

## Phase 1: Setup

- [ ] T001 Create `tests/conformance/reports/__init__.py` — the directory only, no rows yet. The lane wiring is T029 and must land before the first `test_*.py`, which is when `tests/unit/test_every_conformance_directory_is_run.py` starts checking this directory at all. 010 lost a feature's rows to a directory no lane enumerated; 014 hit the subtler form.
- [ ] T002 Record the per-directory `pytest --collect-only -q` counts from `main` in `specs/021-grounded-run-reports/contracts/conformance.md` as SC-011's baseline. **Already captured at `bee9384`** — verify it still matches before relying on it.

---

## Phase 2: Foundational — blocking prerequisites

### The sealed-core change, done deliberately

- [ ] T003 Add one `EFFECT_OBSERVED` member to `AuditEventType` in `src/core/audit/schema.py`. **This is a Principle V change** — the audit schema is named sealed core and requires security-maintainer review. Document the payload vocabulary in the member's docstring the way `TOOL_CHOSEN` and `RUN_RESUMED` do: `run_id`, `step_index`, `tool`, `idempotency_key`, `outcome`, `detail`.
- [ ] T004 Assert in `tests/unit/test_audit_chain.py` that the pinned digest from 020 is unchanged — adding a member must move no existing entry's `entry_hash`. The test already exists; extend its final assertion to name the new member so the check is against the widened vocabulary rather than passing because the addition never landed.

### The typed object

- [ ] T005 [P] Create `src/core/reports/__init__.py` and `src/core/reports/report.py` — `RunReport`, `Claim`, and `ClaimStatus` per [data-model.md](./data-model.md). **Seven statuses, not two.** Each unsupported value sends a reader somewhere different: the product, the tool's registration, the run's ending, or the records themselves.
- [ ] T006 [P] Assert in `tests/unit/test_report_statuses_are_distinct.py` that no two `ClaimStatus` values are collapsible — a report with one "unknown" would be honest and useless, and collapsing them is the refactor a future reader is most likely to attempt.

### The compiler

- [ ] T007 Implement `compile_report(entries, observations, ...)` in `src/core/reports/compile.py`. **It takes already-read entries and holds no query and no credential** — that is what makes FR-008b structural rather than promised, and it is the property a reviewer should check first on any later change.
- [ ] T008 [P] Create `tests/harness/recorded_runs.py` — entry fixtures for the shapes the rows need: a clean run, a run with a denial, an open bracket, a resumed run, a model that chose nothing, a contradicted effect.

---

## Phase 3: US1 — every claim traces to a record (P1)

**Goal**: a structured account in which every statement is populated from the run's records.

**Independent test**: produce a report for a completed run, and for each claim find the record it came from.

- [ ] T009 [GATE:correlation] [US1] Populate every `Claim.evidence` with the entry it derives from, in `src/core/reports/compile.py`, so prompt → choice → hook decision → tool call → claim is walkable in both directions.
- [ ] T010 [US1] Render 020's vocabulary in `src/core/reports/compile.py` (FR-011): attribute a chosen tool to the model that chose it, and render *nothing named*, *bound exhausted*, and *provider unreachable* as the distinct endings they are.
- [ ] T011 [US1] Render `STEP_REOBSERVED` as *observed, not re-run* rather than as a gap, in `src/core/reports/compile.py`. A resumed run's earlier steps carry no outcome of their own, and a report reading that as missing would describe every resumed run as incomplete.
- [ ] T012 [US1] State the run's disposition, distinguishing in-flight from finished (FR-002), in `src/core/reports/compile.py`.
- [ ] T012a [US1] Compile a report for a run that **never started** — authority refused before anything ran — in `src/core/reports/compile.py`, and add `test_a_refused_run_still_reports` in `tests/conformance/reports/test_claims_trace_to_records.py`.

  Analysis pass 2 found this edge case stated in the spec in a full sentence and touched by no task. Its trail is `authority_refused` and nothing else: no steps, no tools, no observations, and no terminal checkpoint. **Every other task in this phase is written for a run that started**, so the natural implementation reads the absence as "still running" and reports a refused run as in flight — forever.

  It is also likely the **first** report anyone requests in anger, because a run that refused is the one people ask about. A report that cannot describe the failure people actually hit is a report for the happy path.
- [ ] T013 [US1] Include what was **refused**, not only what succeeded (FR-003), in `src/core/reports/compile.py`.
- [ ] T014 [GATE:fail-closed] [US1] Emit a claim for material the compiler cannot interpret rather than dropping it, in `src/core/reports/compile.py`. An entry type the compiler does not recognise must surface as `unreconciled` — **silence is the failure mode**, and a compiler that ignores what it does not understand gets quieter as the trail gets richer.
- [ ] T015 [P] [US1] Add `test_every_claim_traces_to_a_record` in `tests/conformance/reports/test_claims_trace_to_records.py` (FR-001, SC-001).
- [ ] T016 [GATE:fail-closed] [P] [US1] Add `test_nothing_is_composed` in `tests/conformance/reports/test_claims_trace_to_records.py` — **0** claims originate from a model. By source inspection over `src/core/reports/`, parsed rather than grepped: 020's equivalent row matched its own prose on the first attempt, and this repository has paid for that five times.
- [ ] T017 [GATE:no-secret-leak] [P] [US1] Add `test_no_secret_values_reach_a_report` in `tests/conformance/reports/test_claims_trace_to_records.py` (FR-009). A report reads everything a run recorded, so it is the widest-aperture consumer of the trail in the platform.
- [ ] T018 [P] [US1] Add `test_a_denial_always_appears` in `tests/conformance/reports/test_claims_trace_to_records.py` (FR-003, SC-002).
- [ ] T019 [P] [US1] Add `test_a_resumed_run_is_not_reported_as_incomplete` in `tests/conformance/reports/test_claims_trace_to_records.py` (FR-011, T011).

---

## Phase 4: US2 — a claim that cannot be reconciled is flagged, never softened (P1)

**Goal**: the report says what it could not verify, in the place the claim would have been.

**Independent test**: compile a report for a run with an unresolvable record and find the gap stated rather than absent.

- [ ] T020 [US2] Flag an unreconcilable claim in place (FR-005) in `src/core/reports/compile.py` — never omitted, never softened, and **never fatal to the rest of the report**.
- [ ] T020a [US2] Implement the **validation pass** in `src/core/reports/compile.py` (FR-004): every claim is checked against the record it cites **before the report is emitted**, and the check's result is what sets its status.

  Analysis pass 1 found no task for this. The spec separates three things — FR-001 *populated from* the records, FR-004 *validated against* them, FR-005 *flagged* when that fails — and the task list covered the first and third while skipping the middle. **Without an explicit validation step, "validated" degrades into "constructed from", which is a claim about where a value came from rather than a check that it is still true of the record.** Those are the same thing only while the compiler is correct, which is the assumption the check exists to remove.
- [ ] T021 [US2] Record whether the evidence verified — the chain, and reconciliation where a second copy exists (FR-010) — in `src/core/reports/compile.py`. A report compiled from records nobody checked is a weaker claim than one compiled from records that were.
- [ ] T022 [US2] State the report's own scope, per ADR-0032 (FR-012), in `src/core/reports/compile.py`.
- [ ] T023 [P] [US2] Add `test_an_open_bracket_is_stated_not_guessed` in `tests/conformance/reports/test_gaps_are_stated.py` (US2 scenario 1).
- [ ] T024 [GATE:fail-closed] [P] [US2] Add `test_one_unreconcilable_claim_does_not_suppress_the_report` in `tests/conformance/reports/test_gaps_are_stated.py` (FR-005, SC-003). **The property whose absence looks like caution**: a compiler that refused to emit anything when one claim failed would read as conservative and would hide every other finding.
- [ ] T025 [P] [US2] Add `test_the_basis_is_stated` in `tests/conformance/reports/test_gaps_are_stated.py` (FR-010).
- [ ] T025a [P] [US2] Add `test_two_reports_of_one_run_agree` in `tests/conformance/reports/test_gaps_are_stated.py` (FR-014b). Compile twice, compare every claim. **Cheap to assert only because of resolution C** — before read-back moved to run end, this property did not hold, and the first clarification said so. Now nothing is re-derived at request time, so any disagreement means the compiler is not a function of the records.
- [ ] T025b [P] [US2] Add `test_no_report_is_ever_persisted` in `tests/conformance/reports/test_gaps_are_stated.py` (FR-014a) — by source inspection over `src/core/reports/` and `src/surfaces/api/reports.py`, **parsed rather than grepped**. A negative property nothing else would catch: a report store added later would break no existing row, and FR-014's "nothing may read a report to decide anything" starts eroding the moment one exists to read.

---

## Phase 5: US3 — read-back performed by the run (P2)

**Goal**: the allocation observes each effect before a terminal state, under its own attested identity, and records what it found.

**Independent test**: arrange an effect that did not land; the report says `contradicted`, never `observed`.

**This phase is the Constitution Check's redesign.** The first plan failed Principle IV here: a read-back at report time would run under the API surface's identity and hand a reader an observation they may hold no authority to make. Everything below exists because the observation moved to where the authority already is.

- [ ] T026 [US3] Observe each effect with a registered observer before a terminal state, in `src/surfaces/dispatch/entrypoint.py`, and record `EFFECT_OBSERVED` (FR-016). **Under the allocation's own attested identity** (FR-006b) — `registry.observers()` supplies the observer, `Observer.observe` is called with the step's idempotency key, and the protocol is **not** changed.
- [ ] T027 [US3] Map the three `ObservationOutcome` values onto claim statuses in `src/core/reports/compile.py`: `happened` → `observed`, `did_not_happen` → `contradicted`, `cannot_determine` → `unverified_unreachable`. Absent observer → `unverified_no_observer`; absent observation → `unverified_not_observed`.
- [ ] T028 [US3] Ensure observing changes no run outcome (FR-016c) in `src/surfaces/dispatch/entrypoint.py`. A run that did its work and then found an effect missing completed and produced a finding — letting the observation retroactively fail the run gives a reporting mechanism power over what it reports.
- [ ] T029 [US3] Add `infra/bin/reports-conformance` and call it from `Makefile`'s `conformance` recipe — the rows that need a dispatched run that observes. **Must land before T030**, which is the first row in that file. The hermetic rows need no wiring; the first recipe line collects the tree.
- [ ] T029a [US3] Mark T030–T035 `enclave` and `host_enclave` in `tests/conformance/reports/test_the_run_observes.py`, and make T029's lane **select those markers** while the hermetic rows stay on the first recipe line.

  **`tests/conformance/reports/` will hold both kinds**, which is exactly the `tests/conformance/api` situation the `Makefile` comment already describes: ignoring the path drops the hermetic rows, collecting the enclave ones fails the lane. `tests/unit/test_every_conformance_directory_is_run.py` requires a lane that both *names* a directory **and** *selects the markers its rows carry* — and that check exists because this gap has been paid for three times: 010 lost a feature's identity rows to a directory no lane enumerated, 014 hit the subtler form where the lane named the directory and deselected the rows, and 018 came within one commit of it in the feature built to end the class.

  Analysis pass 1 found the task list silent on markers entirely.
- [ ] T030 [GATE:correlation] [P] [US3] Add `test_a_run_observes_before_it_ends` in `tests/conformance/reports/test_the_run_observes.py` (FR-006, SC-004) — against a dispatched run, evidenced from the trail.
- [ ] T031 [GATE:fail-closed] [P] [US3] Add `test_an_unreachable_product_is_not_success` in `tests/conformance/reports/test_the_run_observes.py` (FR-006a) — `cannot_determine` is recorded, and the claim reads `unverified_unreachable` rather than either outcome.
- [ ] T032 [P] [US3] Add `test_a_contradicted_effect_never_reads_as_success` in `tests/conformance/reports/test_the_run_observes.py`. **The failure ADR-0018 opens with**, and the one a reader is least able to catch by reading.
- [ ] T033 [GATE:no-secret-leak] [P] [US3] Add `test_the_report_performs_no_observation` in `tests/conformance/reports/test_the_run_observes.py` (SC-004b) — **0** read-backs at report time. Assert the compiler holds no credential and no client, because this is the Principle IV property and it must not regress silently.
- [ ] T034 [P] [US3] Add `test_a_killed_run_says_it_was_never_observed` in `tests/conformance/reports/test_the_run_observes.py` (FR-006c) — distinct from unreachable, because a killed run and a down product are different facts.
- [ ] T035 [P] [US3] Add `test_a_tool_with_no_observer_says_so` in `tests/conformance/reports/test_the_run_observes.py` (FR-016a). **FR-016b forbids adding an observer to satisfy this** — one written to make a claim verifiable rather than because the product can be asked is a stub returning success, which turns an honest `unverified` into a false `confirmed`.
- [ ] T035a [US3] Add `test_every_effect_claim_is_accounted_for` in `tests/conformance/reports/test_the_run_observes.py` (SC-004a) — the **five** statuses `observed`, `contradicted`, `unverified_unreachable`, `unverified_no_observer`, `unverified_not_observed` **partition** every effect claim, with none left asserted from the tool outcome alone.

  **This is the no-silent-assertion property, and T031/T034/T035 do not prove it.** Each asserts that one status appears in one arranged situation; none asserts the set is *closed*. A compiler that handled the three arranged cases and fell through to a bare "completed" for anything else would pass all three and fail this one — which is precisely why SC-004a is written as a partition rather than a list.

  **Assert the partition against `ClaimStatus` itself, not against a hand-written tuple.** A literal list in the row would drift from the enum exactly as this task's own first draft drifted from the criterion it cites — it said "the four statuses" and named five, because SC-004a had omitted `contradicted`. A row that enumerates its own expectations cannot catch a status being added and never handled.

---

## Phase 6: The fifth gate

**This is the point of the feature**, and ADR-0018 names its own failure mode: the corpus is "the thing most likely to be skipped under schedule pressure, which would leave the decision nominally in force and practically unenforced."

- [ ] T036 Extend the eval case vocabulary for fidelity in `src/core/evals/suites.py` (research F3). The existing `EvalCase` is `(prompt, expected, recorded)` scoring a model's answer and `EXPECTED_OUTCOMES` has no entry for fidelity — **FR-013 is not the one-line move it reads as.** A fidelity case names a recorded run and the material events a faithful report must mention.
- [ ] T037 Move `report_fidelity` from `OWED` into `SUITES` in `src/core/evals/suites.py` (FR-013, SC-006), and remove the bespoke error branch in `parse_cases` that exists to make its absence loud.
- [ ] T038 Score claim **precision and recall** against labelled material events in `src/core/evals/scoring.py` (FR-013a, SC-007). **Not a boolean** — a single pass/fail loses exactly the signal that distinguishes a report that omitted a denial from one that invented a success.
- [ ] T039 Author `packs/vault/evals/report_fidelity.toml` and `packs/terraform/evals/report_fidelity.toml` from **recorded runs with labelled material events**, and raise `[evals.cases]`'s floor in each `pack.toml` to match. **Cover the hard shapes** — a denial, an unreconcilable step, a resumption, a contradicted effect, a model that chose nothing — because a corpus of easy runs passes exactly as green as a corpus of hard ones.
- [ ] T040 [P] Add `test_an_unrunnable_fidelity_suite_raises` in `tests/component/test_eval_gates.py` (FR-013a) — never skips, never empty-passes. The discipline the other four already hold.

---

## Phase 7: The surface, and the parity row it grows

- [ ] T041 Add `report_for` in `src/surfaces/api/reports.py` — the governed read plus compilation, **transport-independent**, on the pattern `read_evidence_for` established so MCP reaches *this* rather than reimplementing it.
- [ ] T042 [GATE:correlation] Reach `read_evidence_for` rather than `EvidenceQuery.search` in `src/surfaces/api/reports.py` (FR-007, research F1) — it bounds by tenant, computes the disposition, and **fails the read if the meta-audit write fails**. A direct `search` would duplicate the disposition logic and silently skip the one write that must not be best-effort.
- [ ] T043 Handle the truncated read in `src/surfaces/api/reports.py`. `EvidenceQueryRequest.limit` defaults to **1000** and a 400-step run writes roughly seven entries per step, so a report over one would be complete in form and missing most of the run. **A correctness problem wearing a performance problem's clothes** — a truncated compilation must refuse or state the truncation, never silently report a partial run as whole.
- [ ] T044 Exclude the run's result payload in `src/surfaces/api/reports.py` (FR-008a). `get_run_result` is subject-restricted; a report is tenant-scoped, so carrying that payload routes around the restriction.
- [ ] T045 Add the route to the API router in `src/surfaces/api/app.py`.
- [ ] T046 Add the operation map entry in `src/surfaces/mcp/operations.py` and the dispatch entry in `src/surfaces/mcp/transport.py`, reaching the same `report_for` the API route does.
- [ ] T047 Regenerate `specs/008-northbound-api/contracts/operations.snapshot.json`. **The parity row grows by this operation** (FR-015b) — inherited work, and the snapshot is the part most likely to be forgotten.
- [ ] T048 [P] Add `test_a_non_subject_gets_the_report_without_the_result` in `tests/conformance/api/test_reports.py` (FR-008a, SC-005a) — both halves in one row, because they must hold together.
- [ ] T049 [P] Add `test_another_tenant_is_indistinguishable` in `tests/conformance/api/test_reports.py` (FR-008, SC-005) — same reason code, same message text.
- [ ] T050 [P] Add `test_a_report_grants_no_new_access` in `tests/conformance/api/test_reports.py` (FR-008b) — nothing visible that `read_evidence` would not return to the same caller.
- [ ] T051 [GATE:conformance] Add the report operation to `tests/conformance/mcp/test_surface_parity.py`'s coverage (FR-015b, SC-010) — same verdict, equivalent audit events, both transports.

---

## Phase 8: Polish & cross-cutting

- [ ] T052 Add `test_the_gate_scores_what_a_person_reads` in `tests/conformance/reports/test_one_object_two_consumers.py` (FR-015, FR-015a, FR-015c, SC-009). **The requirement the maintainer's answer produced**: a gate scoring a different object from the one a person reads is not gating what anyone sees — this platform's recurring failure shape, given a row instead of being left available as a shortcut.
- [ ] T053 [P] Add `test_nothing_reads_a_report` in `tests/conformance/reports/test_one_object_two_consumers.py` (FR-014, SC-008) — **0** code paths consume a report to decide anything. By source inspection, parsed.
- [ ] T054 [P] Add `test_the_contract_states_what_this_gate_does_not_assert` in `tests/conformance/reports/test_one_object_two_consumers.py`. **The limit most likely to be misread** is that a report is present-tense: observations are facts about run-end, and "verified" invites a tense the claim does not have.
- [ ] T055 Update `specs/021-grounded-run-reports/contracts/conformance.md` — replace the sketch table with the rows as shipped, and record SC-011 against T002's baseline. 019's contract carried a stale table through six analysis passes.
- [ ] T056 [P] Close the owed row in `ROADMAP.md`: report fidelity moves out of "Owed Quality Gate rows", and 021 moves from "In progress" to "Shipped". **State what remains true** — the report is faithful to the records, not present-tense about the world.
- [ ] T057 [P] Add *claim*, *material event*, and *observation* to `docs/glossary.md`.
- [ ] T058 Obtain the **security-maintainer review Principle V requires** for the audit-schema change (T003) and record it in `specs/021-grounded-run-reports/contracts/conformance.md`. The plan records it as owed rather than discharged; a feature that shipped without it would have passed a Constitution Check that said so in writing.
- [ ] T059 Run the gates: `make check`, `make evals`, `make conformance-hermetic`, and the full `make conformance`; compare per-directory counts against T002 (SC-011). **Resync the VM clock first** — dispatched rows fail on `nbf` when it drifts, and it presents as a random subset failing each run.

---

## Dependencies

```
Phase 1 (Setup)
   ↓
Phase 2 (Foundational) ── the audit member, the typed object, the compiler
   ↓
Phase 3 (US1) ── every claim traces to a record. The feature's floor
   ↓
Phase 4 (US2) ── gaps stated. US1 is worth little without it
   ↓
Phase 5 (US3) ── the run observes. The Principle IV redesign
   ↓
Phase 6 (the fifth gate) ── needs claims to score, so it follows US1–US3
   ↓
Phase 7 (surface) ── independent of Phase 6; both need US1
   ↓
Phase 8 (Polish)
```

**Story independence, honestly.** US1 and US2 are one deliverable in practice: a report that traces every claim but silently drops what it cannot verify is the artifact ADR-0018 warns about, wearing this feature's name. US3 is genuinely separable — a report compiled with every effect claim reading `unverified_not_observed` is honest and useful, and it is the sane fallback if the observation work proves larger than expected.

**Phase 6 is the one that closes the constitution's row.** Phases 3–5 could all land and leave the owed gate row exactly where it has been since 013.

---

## Parallel opportunities

- **Within Phase 2**: T003/T004 (audit) and T005–T008 (the object) are independent.
- **Within US1**: T015–T019 once the compiler exists.
- **Within US2**: T023–T025, T025a and T025b are five assertions in one module.
- **Within US3**: T030–T035 once T029 and T029a land. T035a is **not** parallel — it asserts the partition the others populate.
- **Phase 7**: T048–T050 are three assertions in one module.
- **Phase 8**: T053, T054, T056, T057 are independent of the rest.

---

## Implementation strategy

**MVP is Phase 1 + 2 + US1 + US2.** A report that traces every claim and states every gap is the whole of ADR-0018's central decision, and it needs no enclave to prove.

**Do not stop there.** Without US3 every effect claim reads `unverified_not_observed`, which is honest but leaves the failure the ADR opens with — "applied successfully to three workspaces" — exactly as reachable as it is today. Without Phase 6 the owed Quality Gate row stays owed and this feature closes nothing the constitution is counting.

**T003 is the first task with a cost outside this feature.** It touches sealed core; T058 closes that obligation, and the two should be planned as a pair rather than discovered at merge.

## Notes

- **No named human runner is owed for any row.** There is no model in this path and no live provider — the point of ADR-0018. The only person-shaped obligation is T058's Principle V review.
- **The `Observer` protocol is not touched.** That was resolution B, and it was not chosen. `core.observation` is unchanged, and `tests/unit/test_observers_match_the_protocol.py` should still pass untouched — if it does not, the redesign drifted.
- **No new ADR.** ADR-0018 is implemented; ADR-0035, ADR-0032, ADR-0055, ADR-0033 and ADR-0034 are consumed.
