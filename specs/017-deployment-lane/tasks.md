# Tasks: A deployment lane — every deployed process is proven to run

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Branch**: `spec/017-deployment-lane`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Gate Task Types

| Gate type | Applies | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** | T015a — the runner leaves no reservation behind, so it cannot starve the merge-blocking rows on the next run (FR-007). T008a — a definition nobody enrolled fails, so coverage is not opt-in (FR-005a). T012 — absent, unschedulable or restarting fails, never skips (FR-006). T013 — no retry may absorb a failure (FR-014). T036a — the gate is demonstrably deterministic, which is what makes refusing retries defensible (SC-008), checked by the runner rather than by a row inside the set it runs |
| **Conformance** | **Yes** | The whole feature. Transport surfaces are the subject |
| **Correlation / evidence** | **No** | This feature participates in no run and writes no audit entry. It observes surfaces from outside; nothing joins a correlation ID because nothing here is part of a run |
| **Eval** | **No** | No pack, prompt, model or policy promotes here |
| **No-secret-leak** | **Yes** | T014 — the gate prints allocation output on failure (FR-004), and allocation output is exactly where a credential would surface |

---

## Phase 1: Setup

**Purpose**: Create the directory and **wire it to a lane in the same change**. This
ordering is not stylistic: `make conformance`'s own comments record that 010 lost a whole
feature's rows to a directory no lane enumerated, and that 014 nearly repeated it with a
directory a lane named but deselected. Creating the package before it is collected would
rebuild, inside this feature, the exact failure the feature exists to close.

- [ ] T001 Create `tests/conformance/deployment/__init__.py` with a module docstring stating what this package asserts (reach, not correctness) and what it does not
- [ ] T002 Create `infra/bin/deployment-conformance` as a minimal runner — stand the surfaces up via `infra/bin/portal-up`, then run pytest over `tests/conformance/deployment` — and invoke it as the **final line** of the `conformance` target in `Makefile`, with a comment citing the 010 and 014 directory-enumeration failures the recipe already records.
  **The directory must NOT be added to any pytest line in `make conformance`.** Those lines run before the surfaces are stood up, so rows there would assert against an API and a portal that do not exist yet and fail on every invocation (FR-006 makes an absent process a failure, never a skip). Ordering is guaranteed by recipe position rather than by a separate CI step: by the last line the conformance batch job has completed and released its reservation, which is exactly what R4 requires
- [ ] T003 Prove the directory is collected **before committing anything that depends on it**: add a temporary always-failing row at `tests/conformance/deployment/test_the_lane_collects_this_directory.py`, run `bash infra/bin/deployment-conformance` — the runner, not the whole recipe, since `make conformance` would cost a full enclave pass plus a bring-up and teardown to prove the same thing — observe it fail, then **delete it in the same working session**. It is never committed — a deliberately red row on a branch whose lane is merge-blocking would block every push until someone removed it, which is a self-inflicted version of the problem this feature exists to fix

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The declaration mechanism and the reach helper. Every story depends on these.

- [ ] T004 [P] Add a `meta` block to `infra/jobs/api.nomad.hcl` declaring `harness_surface`, `harness_shape = "served"`, and `harness_covered_by` naming this feature's rows
- [ ] T005 [P] Add the same `meta` block to `infra/jobs/portal.nomad.hcl` with `harness_shape = "served"`
- [ ] T006 [P] Add a `meta` block to `infra/jobs/mcp.nomad.hcl` with `harness_shape = "served"` and `harness_covered_by` naming `tests/conformance/evidence/test_the_service_ships.py` — covered elsewhere, and the declaration is what makes that checkable rather than assumed
- [ ] T007 [P] Add a `meta` block to `infra/jobs/agent-run.nomad.hcl` with `harness_shape = "dispatched"` and `harness_covered_by` naming `tests/conformance/durability/`
- [ ] T007a Decide and record a verdict for `infra/jobs/harness-probe.nomad.hcl` — ours and batch-shaped, and unaddressed until analysis pass 1 raised it. Either declare it a subject or exclude it with a reason; **not deciding is what FR-005a forbids**
- [ ] T008 Implement `tests/conformance/deployment/surfaces.py` — parse **every** `infra/jobs/*.nomad.hcl`, return declared subjects and excluded definitions separately, **resolve every `harness_covered_by` target and fail if it does not exist** — the contract claims coverage-elsewhere is "checkable rather than assumed", and only the dispatched process was being checked, so `mcp`'s could have named a deleted file and nothing would notice — define the exclusion list in the same module with each entry carrying its reason in source (`postgres` and `collector-postgres`: vendor images, no assembly of ours; `conformance`: the gate's own runner, asserting against it is circular), and **raise on an unrecognised `harness_shape`** rather than defaulting, so a typo cannot silently drop a process from coverage (data-model.md)
- [ ] T008a [GATE:fail-closed] Implement the discovery check in `tests/conformance/deployment/surfaces.py` — a definition on disk that is neither declared nor excluded **fails**, and a stale exclusion naming a file that no longer exists also fails (FR-005a). This is the row that makes coverage fail closed rather than opt-in; without it a process nobody enrolled is invisible, which is this feature's own subject matter one level up
- [ ] T009 Implement the allocation lookup in `tests/conformance/deployment/conftest.py` — resolve a job's **running** allocation, filtering by status rather than taking the last row of `nomad job status` (the stopped allocation sorts last, which cost a wrong reading on 2026-07-31)
- [ ] T010 Implement `exec_request()` in `tests/conformance/deployment/conftest.py` — issue an HTTP request from **inside** the allocation via `nomad alloc exec`, returning status, body and headers (research R5: a shell reaches host-networked surfaces on Linux CI and not on Docker Desktop)
- [ ] T011 Implement per-process waits in `tests/conformance/deployment/conftest.py` behind a **single named helper** (`wait_for_working_state`), read from the declaration or a named constant per process, with a docstring recording that these are **measured on the runner, not guessed** (research, residual unknowns). One helper, so T013 can tell a readiness poll from an assertion retry structurally rather than by reading loop syntax
- [ ] T012 [GATE:fail-closed] Implement `require_running()` in `tests/conformance/deployment/conftest.py` — a process that is absent, unschedulable, or has restarted more than once fails; `pytest.skip` MUST NOT appear anywhere in this package (FR-006)
- [ ] T013 [GATE:fail-closed] Add `tests/conformance/deployment/test_no_retry_and_no_skip.py` asserting that no module **other than the single wait helper in `conftest.py`** loops over an assertion, and that `pytest.skip` appears nowhere in the package — FR-014. Scoped to "every module except the one allowed to wait" rather than to loop syntax, because a readiness poll and an assertion retry look identical textually and a row that could not tell them apart would either false-positive on T011 or be weakened until it asserted nothing
- [ ] T014 [GATE:no-secret-leak] Implement failure reporting in `tests/conformance/deployment/conftest.py` that prints the allocation's own error output (FR-004) **with a redaction pass**, and add a row asserting a token-shaped value in captured output is redacted — allocation output is exactly where a credential surfaces
- [ ] T015 Harden `infra/bin/deployment-conformance` (created in T002) — **record which surfaces it started and stop exactly those, on success only**, leaving any a developer had already brought up alone. **On failure, leave them running and say so** ("left `api` running for inspection; the next run replaces it"): tearing down on failure destroys the allocation a developer needs to diagnose, and the captured stderr tail is often not enough — the Vault-role refusal that motivated this whole feature appeared in the middle of a start-up log, not at its end. FR-007a's guarantee matters on the recurring path, which is the passing one; a failing gate blocks the merge anyway. **A teardown that fails, fails the gate** — swallowing it returns the surfaces to persisting and the next run to starving the conformance job, reported green by the gate built to prevent exactly that. The failure this prevents is documented in `infra/bin/portal-up`'s own header, is forbidden by FR-007, and is invisible in CI — every automated run is a fresh runner with one invocation, so it surfaces only on a developer's second local run. Also force a **new allocation** rather than trusting `nomad job run` against an unchanged jobspec (research R7, observed 2026-07-31), capture and print the scheduler's placement output on failure, then invoke the rows
- [ ] T015a [GATE:fail-closed] Add `test_the_runner_leaves_no_footprint` to `tests/conformance/deployment/test_every_declared_process_is_asserted.py` — assert that on a passing run the runner stops every surface it started, so a second consecutive `make conformance` finds the same free capacity as the first, **and that a teardown which fails fails the gate rather than being swallowed**. Both directions, because the happy path alone would leave FR-007a unenforced in exactly the case that reintroduces the defect. Asserted rather than trusted: the symptom is a placement failure two runs in that reads as an infrastructure problem rather than as a gate defect
- [ ] T016 Confirm no temporary or placeholder row survives in `tests/conformance/deployment/` before the first push — T003's probe is deleted in its own session, and this is the check that it actually was

**Checkpoint**: the directory is collected, **every** job definition has a verdict, and a row can reach a surface from inside its allocation. A definition nobody enrolled now fails rather than being invisible.

---

## Phase 3: User Story 1 — A deployed process that cannot start fails the merge (P1) 🎯 MVP

**Goal**: A surface whose assembly cannot obtain its credentials fails the gate, naming that surface and reporting its own error.

**Independent test**: Point the API at a Vault role that does not exist; the gate fails, names the API, and reports the login refusal rather than a bare timeout.

- [ ] T017 [US1] Implement `test_the_api_reaches_a_working_state` in `tests/conformance/deployment/test_the_api_answers_as_itself.py` — assert the API's allocation reaches a running state within its wait and has not restarted
- [ ] T018 [P] [US1] Implement `test_the_portal_reaches_a_working_state` in `tests/conformance/deployment/test_the_portal_read_its_configuration.py` — same for the portal
- [ ] T019 [US1] Add failure attribution in `tests/conformance/deployment/conftest.py`: on timeout, report the allocation's stderr tail so the verdict names the surface's own error rather than the wait elapsing (FR-004, SC-001)
- [ ] T020 [GATE:conformance] [US1] Add the break fixture in `tests/conformance/deployment/test_break_a_surface_assembly.py` — submit the API with a credential role that does not exist, assert the gate fails, then restore. **The break must be in the assembly, not in a route** (contracts/conformance.md), because a broken route proves the row can fail without proving it detects this failure class
- [ ] T021 [US1] Record in `specs/017-deployment-lane/contracts/conformance.md` the observed cold-start time per process and the wait actually set, replacing the "measured, not guessed" placeholder

**Checkpoint**: US1 is independently valuable — a surface that cannot start now blocks the merge.

---

## Phase 4: User Story 2 — A process that starts without its dependencies is not counted as working (P1)

**Goal**: Assert something only a completed assembly can produce. This is the criterion a naive implementation misses.

**Independent test**: A process running and accepting connections but holding no credential fails the gate.

- [ ] T022 [US2] Implement `test_the_api_answers_with_its_own_refusal` in `tests/conformance/deployment/test_the_api_answers_as_itself.py` — an unauthenticated request returns `401` carrying the verifier's own reason code, which exists only if a verifier was constructed and passed in (data-model.md; verified against the running service 2026-07-31)
- [ ] T023 [P] [US2] Implement `test_the_portal_redirects_to_the_configured_issuer` in `tests/conformance/deployment/test_the_portal_read_its_configuration.py` — the redirect's `Location` carries the **configured** issuer and a PKCE challenge, which a process holding defaults would not emit
- [ ] T024 [GATE:fail-closed] [US2] Add `test_a_generic_answer_does_not_satisfy_the_gate` to `tests/conformance/deployment/test_the_api_answers_as_itself.py`, asserting that a bare `200`, an empty body, or a refusal without a reason code fails — SC-002, and the row that keeps this gate from degrading into a liveness check
- [ ] T025 [US2] Add a comment in `tests/conformance/deployment/test_the_api_answers_as_itself.py` recording why a health endpoint was rejected: it would have passed throughout the entire period the API could not start

**Checkpoint**: the gate now distinguishes *running* from *assembled*.

---

## Phase 5: User Story 5 — The dispatched process is proven to run, not just to have run (P1)

**Goal**: The dispatched entrypoint is covered, and the coverage is asserted rather than incidental.

**Independent test**: Remove the dispatch from the durability rows and confirm this gate fails.

**Note**: research R1 found this is **already covered** — 014's durability rows dispatch real allocations and assert completion. The work here is to make that coverage checkable, not to rebuild it.

- [ ] T026 [US5] Implement `test_the_dispatched_process_is_covered` in `tests/conformance/deployment/test_the_dispatched_process_is_covered.py` — assert the module named by `agent-run`'s `harness_covered_by` exists and contains a row that **dispatches**, rather than one that reads prior records (FR-013)
- [ ] T027 [US5] In `tests/conformance/deployment/test_the_dispatched_process_is_covered.py`, assert the durability rows are collected by a lane that will run them — parsed from the `conformance` target in `Makefile` — not merely that the directory is named, which 014 already found is a different question (`make conformance`'s own comment records a lane that named the directory and deselected the rows)
- [ ] T028 [US5] Record in `specs/017-deployment-lane/contracts/conformance.md` that this row asserts coverage exists, and would **not** catch a change that gutted a durability row while leaving its name in place

**Checkpoint**: the dispatched shape cannot lose its coverage silently.

---

## Phase 6: User Story 3 — The rule covers every deployed process (P2)

**Goal**: Set equality, in both directions.

**Independent test**: Add a declaration with no assertion — the gate fails. Remove a declaration and leave its assertion — the gate fails.

- [ ] T029 [US3] Implement `test_every_declared_process_is_asserted` in `tests/conformance/deployment/test_every_declared_process_is_asserted.py` — declared processes and asserted processes are the same set, and **every `harness_covered_by` names a path that exists** (P1)
- [ ] T030 [US3] Assert the **reverse** direction in the same row: an assertion against an undeclared process fails, because such a row passes forever while testing nothing (data-model.md)
- [ ] T031 [US3] Add the exclusion check to `tests/conformance/deployment/test_every_declared_process_is_asserted.py` — an excluded definition must not appear as uncovered, and every exclusion must still exist on disk
- [ ] T031a [US3] Add `test_an_unenrolled_definition_fails` to `tests/conformance/deployment/test_every_declared_process_is_asserted.py` — write a job definition carrying neither a declaration nor an exclusion, assert the gate fails, then remove it. **Demonstrated, not argued**: this is the direction the first design could not detect at all (FR-005a, SC-003)
- [ ] T032 [US3] Record in `specs/017-deployment-lane/contracts/conformance.md` the known limit: a job definition in the tree but never deployed reads as uncovered rather than absent, which is the correct failure but will read as a false positive the first time

**Checkpoint**: a process added later is covered without anyone remembering.

---

## Phase 7: User Story 4 — A contributor can run the gate before pushing (P3)

**Goal**: Same verdict locally and in the automated run.

**Independent test**: Run on macOS and on Linux against the same tree; verdicts match.

- [ ] T033 [US4] Verify `infra/bin/deployment-conformance` runs on macOS against a local enclave and reaches **the same verdict as the automated run for the same commit** — the comparison is the whole point of SC-006, so the referent is named rather than left to be inferred. Exercises the `nomad alloc exec` path that exists for this reason (research R5)
- [ ] T034 [US4] Add a clear failure message in `infra/bin/deployment-conformance` when the surfaces are not up, instructing the contributor to run bring-up rather than erroring obscurely (US4 scenario 2)
- [ ] T035 [US4] Add `test_the_runner_enumerates_this_directory` to `tests/conformance/deployment/test_every_declared_process_is_asserted.py` — assert `infra/bin/deployment-conformance` names `tests/conformance/deployment`, that the `conformance` target invokes that script, and that the runner stands surfaces up **via `infra/bin/portal-up`** rather than submitting job definitions itself (FR-001: the same definitions a deployment uses, not a test-specific variant — true by construction today, and this is what would catch a future shortcut). **No separate step is added to `.github/workflows/enclave.yml`**: the lane already runs `make conformance`, and putting the invocation in the recipe rather than the workflow keeps one way to run the gate (Principle VII) and makes the ordering a property of the recipe rather than of a workflow file nobody runs locally

**Checkpoint**: one way to run the gate, on both substrates.

---

## Phase 8: Polish & cross-cutting

- [ ] T036 [GATE:conformance] Compare **per-directory `pytest --collect-only -q` counts** between `main` and this branch, and confirm no pre-existing directory's count fell. Collection needs no enclave and runs in seconds, so the two sides are cleanly comparable — a full `make conformance` on `main` would take twelve minutes against enclave state that differs between runs, and comparing totals proves nothing because this feature adds rows. A lane that silently stopped collecting a directory looks exactly like a pass (FR-007, SC-005)
- [ ] T036a [GATE:fail-closed] Add a `--repeat N` mode to `infra/bin/deployment-conformance` that stands the surfaces up **once** and then runs the row set N times, failing on differing verdicts, then run it and record the result in `specs/017-deployment-lane/contracts/conformance.md` (SC-008).
  Repeats the **assertions**, not bring-up: SC-008 is about the gate's determinism, and re-deploying each pass would measure the scheduler instead while costing minutes per iteration. Record that boundary in the contract — bring-up determinism is not what SC-008 covers.
  **Not a row in `tests/conformance/deployment/`.** A row there would be inside the set the script invokes, so running the gate from within the gate recurses without bound. The check belongs one level out, in the thing that runs the rows. Refusing retries (FR-014) without evidence the gate is stable is a decision taken on hope; this is that evidence
- [ ] T036b Record in `specs/017-deployment-lane/contracts/conformance.md` that **SC-006 and SC-008 are verified once at implementation, not by a recurring gate** — a Linux runner cannot check the macOS half of SC-006, and running the gate twice on every invocation would double the lane. Name what would re-verify them and when. The plan's "no named human runner is owed" is true of the ROWS and broader than what is true of these two criteria
- [ ] T037 Complete the SC-007 assessment in `specs/017-deployment-lane/contracts/conformance.md`: for each of the five known instances, state whether this gate would have caught it — **including the ones it would not**. On current research the expected answer is that three were in the dispatched path and were caught by 014, which makes this feature's own contribution narrower than gap 0d implies
- [ ] T038 Update `ROADMAP.md` — close gap 0d, add the 017 row, and record what the gate does **not** cover. In the same change, per the file's own maintenance rule
- [ ] T039 [P] Add `docs/development/deployment-lane.md` describing how to run the gate, how to add a process to it, and the two traps (host networking, and an unchanged jobspec placing no new allocation)
- [ ] T040 Run `make check` and `make conformance-hermetic` — both are separate targets and the fast lane runs the second

---

## Dependencies & Execution Order

```
Phase 1 (Setup)          T001 → T002 → T003
                             ↓
Phase 2 (Foundational)   T004–T007 [P] → T007a → T008 → T008a
                         T009 → T010 → T011 → T012, T013, T014 → T015 → T015a → T016
                             ↓
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
Phase 3 (US1, P1)   Phase 4 (US2, P1)   Phase 5 (US5, P1)
   T017–T021           T022–T025           T026–T028
        └────────────────────┼────────────────────┘
                             ↓
Phase 6 (US3, P2)        T029–T032 (incl. T031a)
                             ↓
Phase 7 (US4, P3)        T033–T035
                             ↓
Phase 8 (Polish)         T036, T036a, T036b, T037–T040
```

**Story dependencies**: US1, US2 and US5 are independent of each other once Phase 2 lands —
they assert different things about different processes. US3 depends on US1/US2/US5 existing,
because set equality needs a set of assertions to compare against. US4 is last because it
verifies the others behave identically on a second substrate.

**Parallel opportunities**:

- T004–T007: four job definitions, four files, no ordering between them
- T018 with T017; T023 with T022 — API and portal rows live in different files
- T039 with T036–T038 — documentation is independent of the verification tasks

**MVP scope**: **Phases 1–3.** US1 alone closes the gap that motivated the feature: a
surface that cannot start blocks the merge. US2 makes the gate honest rather than a liveness
check and should follow immediately, but US1 has standalone value on the day it lands.

---

## Notes

**T003 exists because of a real failure, not caution.** A placeholder row that must be seen
to fail before anything depends on the directory being collected. The `make conformance`
recipe records two features that lost rows to enumeration problems — one to a directory no
lane named, one to a directory a lane named and deselected. Building this feature without
proving collection first would rebuild that failure inside the gate meant to close it.

**T020's break fixture must break the assembly.** Breaking a route proves the row can go
red; it does not prove the row detects *this* failure class. The defect that motivated the
feature was a credential role bound to the wrong job, and that is what the fixture should
reproduce.

**T037 is expected to be unflattering and must be written that way.** A success criterion
satisfiable only by good news is not a criterion.

**T008a and T031a exist because analysis pass 1 found the coverage mechanism fail-open.**
The first design had a process become a subject by opting in, so a job definition added
without a declaration was invisible — the gate could not fail for a process it never knew
about, and the process nobody remembered to enrol is exactly the one nobody remembered to
cover. Building a coverage mechanism that cannot see a gap would have reproduced this
feature's own subject matter one level up, inside the feature meant to close it. T008a
inverts the default; T031a demonstrates the inversion works rather than asserting it.

**T013's scope is "every module except the wait helper", not "no loops".** A readiness poll
and an assertion retry are textually identical, so a row keyed on loop syntax would either
false-positive on T011 or be relaxed until it asserted nothing. T011 exists as a single
named helper so the distinction is structural.
