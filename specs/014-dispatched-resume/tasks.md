# Tasks: Wire resume into the dispatched path

**Input**: Design documents from `/specs/014-dispatched-resume/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. The decisive requirement (FR-019) is that 005's properties be asserted
through a dispatch — a version of this feature without its rows would be the exact defect it
repairs, rebuilt.

**Organization**: Setup → Foundational (the grant store F1 forces, the cap, the event, the
discriminator) → US1–US5 in priority order → Polish & the FR-020 re-scoping. Gate tasks are
tagged and live in the phase that delivers the behaviour they guard.

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | Missing grant refuses; unhandled decision outcome refuses; cap exhaustion is terminal; superseded instance rejected |
| **Conformance** | The ten dispatch-level rows in `contracts/conformance-resume.md`, merge-blocking in the enclave lane |
| **Correlation / evidence** | `RUN_RESUMED` with attempt and outcome; `MATRIX_FALLBACK` on resume; the trail read back through the evidence path |
| **No-secret-leak** | The grants table holds consent metadata only; the 005 no-secret sweep extends to it |

## Path Conventions

Single project: `src/`, `tests/` at repository root. The dispatch-level rows join
`tests/conformance/durability/` — 005's lane, where clarify Q2 sited them.

---

## Phase 1: Setup

- [X] T001 Add `RESUME_ATTEMPT_CAP = 5` to `src/core/run.py` beside the other bounds, with the D3 reasoning inline: platform-set, never from workflow code, the definition, or dispatch metadata — a bound the bounded thing can raise is not a bound. The value is a tunable starting point and the comment says so
- [X] T002 [P] Add `RUN_RESUMED` to `AuditEventType` in `src/core/audit/schema.py` — one event, the outcome in the payload (`continued | stopped | suspended`, reason, 1-based attempt, completed/pending step counts), on the 013 `MODEL_GATE` pattern: one type, the distinction in the payload. The docstring records why not three events (a three-way union to ask "how many times was this run revived") and why not a `RUN_START` flag (a resumed run that stops never starts, so the event would lie in exactly the failure cases)

**Checkpoint**: `make check` green; the constant and the event exist.

---

## Phase 2: Foundational (blocking all user stories)

**Purpose**: the grant store F1 forces, the checkpoint column the cap needs, and the
discriminator. No story is demonstrable until the dispatched path can even tell it is
resuming and has consent to check.

### The grant store (research F1 — the repair)

- [X] T003 Add the `grants` table to `src/core/durability/schema.sql`: `grant_id` primary key, `subject_user_id`, `agent_definition_id`, `requested_scope` jsonb, `issued_at`, `expires_at`. Comment block records F1: ADR-0026 said "durable consent, referenced by a checkpoint via grant_id only" and the durable half was never built — plus the discipline that this table holds consent METADATA and zero credential material, extending the no-secret sweep. Also add `resume_count INTEGER NOT NULL DEFAULT 0` to the checkpoints table (D3: it must survive the disruption it counts)
- [X] T004 Add `save_grant(grant: DelegationGrant)` and `load_grant(grant_id: str) -> DelegationGrant | None` to the `DurabilityProvider` protocol in `src/core/durability/types.py`, and `resume_count: int = 0` to `CheckpointBlob` (additive, defaulted — every existing caller unchanged). Docstring: `None` on a missing grant so the CALLER decides the refusal, mirroring `load()`'s absence semantics
- [X] T005 Implement both grant methods in `src/core/durability/postgres.py` (grant is written once at issuance, never updated — a new consent is a new grant) and persist/restore `resume_count` through save/load. **Scope serialization is a decision, not an accident** (analyze M2): `AuthorityScope`'s frozensets are written as **sorted lists** and loaded back into frozensets, so the stored jsonb is deterministic and two saves of one grant are byte-identical. The schema already applies at bring-up via `infra/bin/enclave-up`'s existing statement block — **verify the new DDL rides that block and update the block's `ok` message**, because the rule about migrate-on-first-use has bitten four times
- [X] T006 [P] Keep parity in `src/core/durability/memory.py`: both grant methods, `resume_count` round-trip. Hermetic rows need a provider that behaves identically
- [X] T007 [P] Component rows in `tests/component/test_grant_store.py`: a grant round-trips with scope intact; a missing grant loads as `None`; expiry is read from the record; `resume_count` survives save/load; **and the no-secret property — serialize a stored grant and assert no credential-shaped material, because FR-012 extends to the new table by row, not by remark**

### The cap (clarify Q1, D3)

- [X] T008 Implement the cap in `src/core/durability/resume.py`: increment `resume_count` **after** the lease claim succeeds (a superseded instance must not burn attempts — the break fixture the contract names), persist it, and refuse past `RESUME_ATTEMPT_CAP` with a **terminal** `ResumeDecision(state=STOPPED, stop_reason="resume_attempts_exhausted")`. It must not suspend again: a run past its cap waiting on a dependency waits for a revival that can never come. **The only behavioural change to the 005 library in this feature** — the plan says so, and the docstring should too
- [X] T009 [P] Component rows in `tests/component/test_resume_cap.py`: attempt N of 5 continues; attempt 6 stops terminally with the reason; the count increments only after a successful claim (a failed claim leaves it untouched); the cap cannot be influenced by anything on the decision's inputs — asserted against the signature, the way 013 asserted the tier; **and a post-resume checkpoint save preserves the count** — construct a blob mid-resumed-run, save, reload, assert `resume_count` survived (the H1 wipe, from the store side)

### The discriminator (research D1)

- [X] T010 Add `resume: bool = False` to `NomadDispatcher.dispatch()` in `src/surfaces/dispatch/nomad.py` → meta `"resume": "1" if resume else ""`; add `"resume"` to `meta_optional` and `RUN_RESUME = "${NOMAD_META_resume}"` to `infra/jobs/agent-run.nomad.hcl` (the jobspec comment already warns that a key in neither list fails the dispatch loudly — rely on that); set `resume=True` in `_resume_dispatcher` in `src/surfaces/mcp/server.py`, **the only caller that may**
- [X] T010a The suspended-run record carries what the run needs to be itself again (analyze C1/C2/H2). Extend `SuspendedRunRecord` in `src/core/durability/sweeper.py` and the `suspended_runs` table in `src/core/dependencies/schema.sql` with `subject_roles`, `packs`, `steps`, and `invoke_tools`; `record_suspension` in `src/core/dependencies/store.py` persists them; `_resume_dispatcher` in `src/surfaces/mcp/server.py` passes them through `dispatcher.dispatch(...)` — which already carries `subject_roles` and `packs` parameters to the jobspec, so nothing new travels, it finally travels *populated*. **Without this, every dispatched resume refuses `no_role_for_subject` as designed**: empty roles make `resolve_user_scope` raise before resume can manufacture anything; empty packs leave `registry.observers()` without the very observers re-observation consults (a missing observer is `CANNOT_DETERMINE`, so every pack-tool intent re-suspends — naming the tool, because `dependency_products({})` is empty too); and an absent `steps` makes a resumed multi-step run complete trivially with its pending work silently dropped. The sweeper's own docstring — "dispatches *as* the run" — already argues for all four fields; they are claims-derived metadata and configuration, and none of them grants anything
- [X] T011 [P] Component row in `tests/component/test_resume_is_declared_not_inferred.py`: the dispatcher emits the flag only when asked; a dispatch carrying a used run_id and step_index WITHOUT the flag is not a resume. The docstring carries D1's reasoning: inference from checkpoint existence turns an id collision into a silent resume — the exact failure the jobspec's meta_required comment documents

**Checkpoint**: `make check` green; grants persist; the cap arithmetic holds; the flag travels.

---

## Phase 3: User Story 1 — A disrupted run finishes what it started (P1) 🎯 MVP

**Goal**: the entrypoint takes the resume path, and a killed dispatched run completes with
exactly-once effects.

**Independent test**: dispatch a multi-step run, `nomad alloc stop` it mid-flight, sweep,
and count each step's effects across both allocations: exactly one.

- [X] T012 [US1] Fix F1's latent bug in `src/surfaces/dispatch/entrypoint.py`: the fresh-dispatch path calls `issue_grant` with `duration = DEFAULT_MAX_RUN_DURATION` — **named honestly** (analyze M1): this task originally said "from the definition's ceiling", and no record anywhere carries a per-definition maximum run duration; `max_run_duration` is a defaulted parameter, not a resolved fact. The platform default is the real source today, a per-definition maximum is a future record, noted inline — then `save_grant`s it, and writes **the grant's id** — not `run.authority.credential_id` — into every `CheckpointBlob.grant_id`. Without this the store indexes garbage from day one, and US4 has nothing real to check
- [X] T013 [US1] The integration: when `RUN_RESUME == "1"`, the entrypoint loads the checkpoint by `RUN_ID`, loads the grant by the checkpoint's `grant_id` (absent → refuse `grant_missing`, exit non-zero — a missing grant is not "no consent required"), and calls `resume_run(...)` with `observers=registry.observers()` and `depends_on=dependency_products(_loaded_packs)` — consuming the three orphans. Honour **all three** outcomes: ACTIVE → run only `pending_steps` from the decision's step position; STOPPED → record and exit 0 (a bound is an ending, not a failure); SUSPENDED → write the suspended-run index entry naming `awaiting`, checkpoint, exit 0. **An unrecognized state refuses** (FR-003: unhandled must not default to proceeding). **And thread the decision's `resume_count` into every `CheckpointBlob` the resumed run saves** (analyze H1): `save()` overwrites the whole row, so a per-step blob constructed without the count resets it to zero on the first step after revival — making the cap a bound that resets whenever any work happens, and the flap row a row that can never reach it
- [X] T014 [US1] [GATE:correlation] Emit `RUN_RESUMED` from the entrypoint before any pending step executes (an investigator reading in order sees the revival before its consequences), and emit `MATRIX_FALLBACK` from `decision.matrix_fallback` when set — closing the loop 013's plan documented for the resume caller
- [X] T015 [P] [US1] Hermetic rows in `tests/component/test_entrypoint_resume_branch.py` (extract the branch into a testable function if the module shape demands it): fresh dispatch unchanged with the flag unset — byte-identical `RUN_START` payload, per SC-011; flag set + checkpoint present → the resume path; flag set + no checkpoint → STOPPED `checkpoint_missing`, never a fresh start (the library already decides this; assert the entrypoint honours it); completed steps not re-run
- [X] T016 [US1] [GATE:conformance] Dispatch row in `tests/conformance/durability/test_dispatched_resume.py` (`host_enclave` + `enclave`, both markers — the 013 lesson): multi-step run, kill the allocation mid-flight via the scheduler, re-dispatch with `resume=True`, assert completion, **exactly one execution per completed step across the whole run** (SC-001), **and that the resumed allocation actually executed the pending steps** — exit zero with pending work silently dropped is US2 scenario 2 inverted and would pass a completion-only assertion (analyze H2) — plus fresh authority in the resumed allocation (SC-002), all read through the trail, not the logs
- [ ] T017 [P] [US1] [GATE:no-secret-leak] Extend the 005 no-secret sweep to the grants table in `tests/conformance/durability/` (wherever the existing checkpoint sweep row lives — same file, new assertion): zero credential-shaped values in `grants`, asserted against the live store (SC-003)

**Checkpoint**: US1 demonstrable — the MVP. `resume_run` has a caller in `src/`.

---

## Phase 4: User Story 2 — Resolved by asking, not assuming (P1)

**Goal**: interrupted non-repeatable steps resolve by observation, against live Vault, both
directions.

**Independent test**: interrupt between bracket-open and bracket-close; resume; the landed
case skips, the not-landed case proceeds.

- [X] T018 [US2] Make the entrypoint's step loop bracket **real tool invocations** when `RUN_INVOKE_TOOLS=1`: record the intent with the actual `tool_name` before `invoke_tool`, the result after — today the loop brackets a literal `"echo"` regardless of what runs, so re-observation would consult the wrong observer for every real tool. Repeatable tools keep the current trivial bracket
- [X] T019 [P] [US2] Hermetic rows in `tests/component/test_resume_consults_observers.py`: an open intent for a tool with a registered observer is resolved through **that** observer (FR-006 — assert the observer was called, not just that a decision emerged); HAPPENED → step in `completed_steps`; DID_NOT_HAPPEN → in `pending_steps`; CANNOT_DETERMINE → SUSPENDED naming the product from `depends_on`
- [ ] T020 [US2] [GATE:conformance] Dispatch row, live, both directions, in `tests/conformance/durability/test_dispatched_reobservation.py`: a run interrupted holding an open `vault_write` intent where the write **landed** (arrange it at the probe path first) resumes without re-executing; where it **did not land**, the step proceeds — real Vault, the shipped `VaultWriteObserver`, per FR-006a/SC-004a and clarify Q3. Each direction cleans up its arranged state after itself; the rows are order-sensitive by nature and the docstring says so

**Checkpoint**: observation is the resolver, demonstrated against the product.

---

## Phase 5: User Story 3 — Suspension names what recovers it (P1)

**Goal**: the full cycle — suspend naming the product, sweeper revives, cap terminates.

**Independent test**: open `terraform_apply` intent → resume → suspended awaiting
`terraform`; `record_probe` recovery → revived; flap to the cap → terminal stop.

- [X] T020a [US3] [GATE:fail-closed] The mid-run suspension arm (analyze C3). In `src/surfaces/dispatch/entrypoint.py`'s invoke loop, distinguish a suspension from a refusal: after a denied invoke, if `run.state == SUSPENDED`, write the suspended-run index row via `record_suspension` (**which has zero callers today — in `src/` and in `tests/` — the index is a store with a reader and no writer, `resume_run`'s defect one layer earlier in the lifecycle**), save a checkpoint carrying the suspended state, and **exit 0** — a suspension is a wait, not a failure, and today's `return 1` on any refusal presents the spec's own US1 narrative (fabric blinks mid-run) as a failed allocation with no index row and nothing for the sweeper to find. While there, correct `src/core/hooks/suspension.py`'s docstring: it says "the state transition is what the sweeper reads", and the sweeper reads the **index**, verifying against the checkpoint — a docstring that misstates the contract is how the next feature repeats this one
- [X] T021 [US3] Wire the suspended-run index write into the entrypoint's **resume-time** SUSPENDED arm (the mid-run arm is T020a's; after this feature there are two writers, one per arm) — T013 stubs it: run_id, correlation, `awaiting` from the decision, step position, subject/tenant/definition for the re-dispatch — everything `SuspendedRunRecord` carries and nothing that grants
- [X] T022 [P] [US3] Hermetic row in `tests/component/test_suspension_vocabulary.py`: with `depends_on` wired, a CANNOT_DETERMINE on `terraform_apply` suspends awaiting **`terraform`** — the product, never the tool name (FR-008, SC-005); without a known product the tool-name fallback still stands, per `resume_run`'s own docstring
- [ ] T023 [US3] [GATE:conformance] Dispatch row in `tests/conformance/durability/test_dispatched_suspension_cycle.py`: the D5 harness end to end — open `terraform_apply` intent, resume, suspended awaiting `terraform`; `record_probe("terraform", reachable=True)`; the sweeper's next pass re-dispatches; the run completes. **The 009 sweeper's first end-to-end demonstration** (SC-006). **And the mid-run arm** (analyze C3): a second case in the same file suspends via the invoke path — a tool whose product the dependency store marks unreachable mid-run — and is swept and revived the same way, so both writers of the index are exercised, not only the resume-time one
- [ ] T024 [US3] [GATE:fail-closed] Dispatch row in the same file: flap the harness in a loop — each recovery revives, each revival re-suspends — and assert the run is revived **exactly `RESUME_ATTEMPT_CAP` times**, then stops terminally with `resume_attempts_exhausted` and never suspends again (SC-006a). Slow by construction; the docstring quotes the spec's assumption that waiting is what this row tests

**Checkpoint**: the cycle closes, and its bound is terminal.

---

## Phase 6: User Story 4 — Withdrawn consent ends a run (P2)

**Goal**: expired grants stop resumes, terminally — now checkable because the store exists.

**Independent test**: short-TTL grant, disrupt, wait past expiry, sweep: STOPPED
`grant_expired`, zero steps, renewal revives nothing.

- [X] T025 [P] [US4] Hermetic rows in `tests/component/test_resume_under_lapsed_consent.py`: expired grant → STOPPED `grant_expired` before any step (the library decides; assert the entrypoint records and exits without executing); a renewed/re-issued grant does not revive a STOPPED run — terminal means the sweeper's `_is_suspended` sees the terminal checkpoint and drops the candidate; any resume refusal (grant missing, authority refused) records its reason and releases the run's claim (FR-014)
- [ ] T026 [US4] [GATE:conformance] Dispatch row in `tests/conformance/durability/test_dispatched_grant_expiry.py`: dispatch under a deliberately short grant, disrupt, wait past expiry, sweep — the resumed allocation exits recording `grant_expired` with zero subsequent steps (SC-007); re-issuing consent revives nothing. **This row was impossible before this feature** — the record it checks did not exist — and the docstring says so

**Checkpoint**: consent is a bound the dispatched path actually honours.

---

## Phase 7: User Story 5 — One actor per run (P2)

**Goal**: fencing holds through a real dispatch overlap.

**Independent test**: two allocations claim one run; the superseded one achieves nothing.

- [X] T027 [P] [US5] Hermetic row in `tests/component/test_resume_claims_before_observing.py`: the lease claim precedes intent resolution in `resume_run`'s order (assert the call order, not just the outcome — the docstring's own numbered list is the contract), and a claim that fails leaves `resume_count` untouched (the T008/T009 interaction, asserted from this side)
- [ ] T028 [US5] [GATE:conformance] Dispatch row in `tests/conformance/durability/test_dispatched_fencing.py`: engineer the overlap — resume a run while the prior allocation still lives (dispatch the resume without stopping the original) — and assert the superseded instance's tool calls and checkpoint writes are rejected: zero side effects, zero state mutation (SC-008), while the successor completes

**Checkpoint**: all five stories demonstrable through dispatch.

---

## Phase 8: Polish, re-scoping, and the gate run

- [X] T029 [P] [GATE:conformance] The fresh-dispatch negative in `tests/conformance/durability/test_dispatched_resume.py`: a dispatch reusing a completed run's identifiers **without** the flag starts fresh and skips nothing (FR-002); and a dispatch **with** the flag whose run already finished terminally does not re-enter its work (the edge case; `_is_suspended`/terminal-checkpoint already decide it — assert through dispatch)
- [ ] T030 [P] [GATE:correlation] Row in `tests/conformance/durability/test_run_resumed_in_trail.py`: every revival in the cap row's flap appears as `RUN_RESUMED` with 1-based attempt and outcome, readable through the evidence path, ordered before its consequences (FR-017); chain verification passes across the resumed run's whole trail
- [ ] T031 Apply the contract's four break fixtures to the tree, watch each named row fail, revert, and record outcomes in `specs/014-dispatched-resume/contracts/conformance-resume.md`: entrypoint ignores the flag → exactly-once fails; grant load skipped → expiry row completes when it must stop; count incremented before the claim → fencing burns attempts; cap read from dispatch meta → the terminal row catches the sixth revival
- [ ] T032 [GATE:conformance] **FR-020, the re-scoping**: replace the scope note in `specs/005-durable-execution/contracts/conformance-durability.md` with a pointer to `specs/014-dispatched-resume/contracts/conformance-resume.md`, keeping the note for any property still function-only; close `ROADMAP.md` gap 0a naming this feature; update 013's cross-reference in its conformance contract. **Leaving the note after the rows land is the inverse defect — evidence outrunning the claim** — so this task is a gate, not documentation
- [ ] T033 [P] Update `docs/glossary.md`: `resume` cross-references (grant store, attempt cap, RUN_RESUMED) where the durability terms live
- [ ] T034 Run `make check`, `make conformance` (full, against a live enclave, on a clean tree — including 005's existing rows, which must still pass with the library's one behavioural change), and walk `specs/014-dispatched-resume/quickstart.md` sections 2–6. Record rows **In force** in the contract

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─→ Phase 2 Foundational ─→ Phase 3 US1 (MVP)
                                          ─→ Phase 4 US2 (needs US1's entrypoint branch)
                                          ─→ Phase 5 US3 (needs US1 + T021)
                                          ─→ Phase 6 US4 (needs T012's real grants)
                                          ─→ Phase 7 US5 (needs US1)
                                                     ─→ Phase 8 Polish & re-scoping
```

**Orderings that are not obvious from the phases:**

- **T020a → T023's mid-run case.** The invoke loop must file suspensions before a row can
  sweep them; without T020a the mid-run case fails as a failed allocation, which is analyze C3.
- **T010a → T013, T023.** The record extension lands before the entrypoint reads the new env
  and before the sweep-revival row runs — without it that row fails on `no_role_for_subject` by
  design, which is analyze C1.
- **T003 → T005 → T012.** The table must exist and apply at bring-up before the entrypoint
  writes grants, or the first dispatched run on a fresh enclave dies on a missing relation —
  the defect that has bitten four times, in its newest costume.
- **T012 → T013.** The resume path loads grants the fresh path saved; wiring resume before
  grants exist makes US4's refusal path the common case.
- **T008 ⇄ T027.** The cap increments after the claim; the fencing row asserts the same
  boundary from the other side. Land T008 first, but review them together.
- **T018 → T020.** The bracket must carry the real tool name before the live re-observation
  row can consult the right observer — today it says `"echo"` unconditionally.
- **T031 → T034.** Break fixtures before the final gate run, so the run certifies rows
  someone has seen fail.
- **T032 is last-but-one on purpose**: re-scoping 005's contract before the rows are in
  force would be the inverse of the defect this feature fixes.

**US2, US4, US5 are mutually independent** once US1 lands. US3 additionally needs T021.

## Parallel opportunities

- **Setup**: T001 ∥ T002.
- **Foundational**: T006 ∥ T007 after T004/T005; T009 ∥ T011 after their implementations.
- **After US1**: Phases 4, 6, 7 in parallel; Phase 5 after T021.
- **Polish**: T029 ∥ T030 ∥ T033.

**Not parallel, despite looking it**: T012 and T013 (same function, same file, and the
resume path reads what the fresh path writes); T023 and T024 (the flap row reuses the
cycle row's harness state).

## Implementation strategy

**MVP = Phase 3 (US1)**: a killed dispatched run completes exactly once, and `resume_run`
has a caller in `src/`. That alone closes the headline of ROADMAP gap 0a — everything after
it makes the remaining 005 properties dispatch-proven.

The dispatch rows are deliberately one-per-file and join 005's existing lane rather than a
new directory.

**The lane wiring was not free, and an earlier draft of this file said it was.** The claim
here was that `tests/conformance/durability` is already collected by `make conformance`, so
no lane-wiring task could be forgotten — the 010 lesson inverted into a free ride. It is
half true and therefore worse than false: the directory *is* named by a lane, the
in-allocation one, which runs it with `-m "not host_enclave"`. Every row this feature adds
is `host_enclave` by nature — it drives the scheduler, which nothing the scheduler placed
can do — so all ten would have been deselected there and collected nowhere else
(`make conformance`'s first line ignores the path; `pytest -m enclave` reads `testpaths`,
which is `tests/unit` and `tests/component`). They would have passed when run by hand and
been invisible to the gate: this feature's own defect, rebuilt inside the gate meant to
prove it fixed.

The fix — adding the directory to the host_enclave line in the `Makefile` — landed in a
preparatory commit **before** this feature's first row, so no task here carries it and
T034's run certifies rows a lane actually collects. The general form, for the next feature
that reasons about a lane: "already named by a lane" and "named by a lane that will run
*this* row" are different questions, and only the second one is the gate.
