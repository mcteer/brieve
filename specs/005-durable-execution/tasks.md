# Tasks: Durable Execution

**Input**: Design documents from `specs/005-durable-execution/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Blocking prerequisite outside this feature**: the deployment module tree (see
[ROADMAP.md](../../ROADMAP.md)) must land first. It makes `make dev-up` real and settles where
durability tests execute. `infra/dev-enclave` already proves the chain works — Nomad workload
identity → Vault → dynamic Postgres credential — but it is a proof directory, not the front door.
T000 is the gate that stops this feature starting on a promise.

**Tests**: Spec FR-013/FR-014/FR-016, each story's Independent Test, and the constitution's
Quality Gates require deterministic unit, component, and conformance tests. No live models and no
live managed-product APIs, asserted rather than assumed (T073). Unlike 001–004, the durability
lane is **not hermetic**: it runs against the real enclave, because Vault and Postgres are
components this project deploys.

**Scope bound**: FR-018 caps sealed-core changes to the durability and authority seams named in
the plan — checkpoint schema and provider protocol, grant lifetime and per-step manufacture, lease
and fencing, execution bounds, and the intent/result bracket. A core change outside that list
appearing mid-implementation is out of scope; stop and open its own spec. T077 is the review that
catches it.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing
of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Unwritable/unreadable checkpoint, unobservable step, expired grant, lost lease | Refuse or park on error; never proceed on partial state |
| **Conformance** | Durability seam | All seven rows execute under `make conformance` as in force, each with a break fixture |
| **Correlation / evidence** | Any path crossing the disruption boundary | One correlation ID joins both segments; hash chain intact |
| **Eval** | N/A | No packs, prompts, models, or policies promoted |
| **No-secret-leak** | Checkpoints, leases, intent records, database credentials | No credential material in any durable record, for any provider |
| **Determinism** | Feature test paths | No live model or managed-product API reachable; disruption simulated in-process |

## Path Conventions

- Core authority: `src/core/authority/grant.py`, `manufacture.py`, `types.py`
- Core durability: `src/core/durability/` (`types.py`, `memory.py`, `postgres.py`, `schema.sql`, `lease.py`, `resume.py`)
- Core observation: `src/core/observation/` (`types.py`, `bracket.py`)
- Core: `src/core/bounds.py`, `src/core/run.py`, `src/core/registry/memory.py`
- Harness: `tests/harness/durability_fixtures.py`
- Tests: `tests/unit/`, `tests/component/`, `tests/conformance/durability/`
- Config: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`

---

## Phase 0: Environment Gate

**Purpose**: The precondition for the entire feature, not a setup step

- [ ] T000 [GATE:determinism] Verify the deployment module tree has landed: `make dev-up` brings up Vault + Postgres with the dynamic database role configured, and **the suite can be invoked as a Nomad job with its exit status returned**. That the suite runs in an allocation is settled (plan.md); what T000 checks is that the mechanism exists. **Do not start T001 on a promise** — every durability task below assumes a reachable enclave, and a suite that silently skips when it is absent is worse than one that fails
---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency, package layout, conformance tree

- [ ] T001 Add a PostgreSQL driver to `pyproject.toml` — `psycopg[binary]` (v3) is the plan's default choice. Pin the exact version, verify it is current at implement time, and record the ADR-0017 dependency justification in the `feat/005` PR body. Regenerate and **commit `uv.lock` in the same change**: CI runs `uv sync --frozen`, which will not update the lockfile, so a stale lock fails the fast lane before any test runs. Decide and document whether the driver is a base dependency or an extra — the durability lane needs it, so an extra that CI does not install would green the wrong thing
- [ ] T002 [P] Create `tests/conformance/durability/__init__.py`
- [ ] T003 [P] Create `src/core/observation/__init__.py` (contents filled in Phase 2)
- [ ] T004 Document in `docs/development/testing.md` that the durability lane requires `make dev-up` — a prerequisite for the rows, not an alternative to them — and confirm the rows actually execute. Note that `make conformance` already runs `pytest tests/conformance` recursively, so the new directory is picked up **without** a Makefile change; the work here is the documentation and the confirmation, and this task is not done because a target looks right

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The seams every story builds on — grant, extended provider protocol, Postgres
provider, lease, bracket, bounds, parked state, and the harness fixtures

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Authority

- [ ] T005 [P] Create `src/core/authority/grant.py` with `DelegationGrant` per `data-model.md` — issue, validate, expiry check. Blank subject, blank definition, or an expiry beyond the definition's maximum refuses issue. **Holds no credential material**; enforce structurally, as 004 did for checkpoints
- [ ] T006 [P] Add `GrantRef` to `src/core/authority/types.py`; `TaskCredentialRef` is unchanged
- [ ] T007 Extend `manufacture_authority` in `src/core/authority/manufacture.py` to take a grant and manufacture per-step authority under it; an expired grant refuses rather than issuing (**breaking seam** vs 003 — migrate callers in T017)
- [ ] T008 [P] [GATE:fail-closed] Unit test `tests/unit/test_grant_expiry.py` — expired grant refuses manufacture; expiry beyond the definition's maximum refuses issue; a grant is not renewable from inside a run

### Durability seam

- [ ] T009 Extend `CheckpointBlob` in `src/core/durability/types.py` with `grant_id`, `step_index`, `written_by`, `run_state`, and `stop_reason`. **`run_state` on the blob is not optional bookkeeping**: a resuming process has only the checkpoint, so without it there is no way to tell a run that finished from one interrupted mid-step, and T017a's rule would be unenforceable rather than merely untested. Also extend extend the `DurabilityProvider` protocol with `acquire_lease`, `check_lease`, `record_intent`, `record_result`, `open_intents` per `contracts/durability-seam.md`. **This is a breaking change to a seam 004 shipped one feature ago** — declare it in the `feat/005` PR under the template's breaking-change section, citing the same pre-1.0 exemption 004 recorded, rather than assuming it
- [ ] T010 Extend `InMemoryDurabilityProvider` in `src/core/durability/memory.py` to satisfy the full protocol. It remains a **test double for suites that are not about durability** — the durability rows run against Postgres
- [ ] T011 [P] Create `src/core/durability/schema.sql` with tables for checkpoints, leases, and intent/result records per `data-model.md`. Lease acquisition must be expressible as a single conditional update
- [ ] T011a [P] Create `src/core/durability/credentials.py` — the **workload performs the exchange itself**: present its Nomad workload identity to Vault, receive a dynamic Postgres credential, per `data-model.md`'s `DatabaseCredential`. **No path accepts a DSN with a password** (FR-017a), and **do not use Nomad's `vault` stanza / `template` to broker the secret into the task** — a brokered secret sits in the task's environment or filesystem for the life of the allocation, and it renews on Nomad's schedule rather than on the database's rejection, which would make FR-017b unimplementable. Its own module rather than a clause inside the provider: this is where the attestation chain is exercised, and it should be readable and testable without a database attached. `infra/dev-enclave/jobs/harness-probe.nomad.hcl` is the working reference for the exchange
- [ ] T011b Implement **reactive credential refresh** in `credentials.py` (FR-017b): attempt the operation, and on an authentication failure obtain a fresh credential from Vault and retry **once**. Reactive rather than clock-driven — a timer handles only the expiry it predicts, while the database's rejection is the authoritative signal and also covers a credential revoked early, a lease invalidated by a Vault operation, or a database restarted underneath the run. The lease is on the order of an hour and a durable run is designed to outlive it, so **this is the happy path, not the error path**. Call it *credential refresh*, never *re-authentication* — that term belongs to the run re-attesting to Vault (US2), and putting a security guarantee and a connection retry under one name is a collision that survives review by looking familiar. Keep it distinct from grant expiry too: a credential ending refreshes silently, consent ending parks the run (FR-005)
- [ ] T011c Classify the errors that trigger a refresh: **authentication failure only**, distinguished from connection-refused, permission-denied-on-object, and everything else, with the second failure surfaced rather than retried. This is the task that keeps T011b bounded — an unbounded retry would spin against a genuine misconfiguration, and the enclave has one reachable today: destroying the Postgres volume resets the database to its bootstrap password while Vault holds the rotated one, so *every* credential fails auth. That must present as a clear failure, not a hang
- [ ] T011d [P] Unit test `tests/unit/test_credential_refresh.py` — an expired credential produces one Vault round trip and the operation succeeds on retry; a non-auth error does **not** trigger a fetch; a second auth failure surfaces; and no credential material is logged, checkpointed, or placed in a span
- [ ] T012 Create `src/core/durability/postgres.py` with `PostgresDurabilityProvider`, taking its connection from `credentials.py` (T011a). A failed save propagates; a partial or corrupt blob is never returned as valid
- [ ] T013 [P] Create `src/core/durability/lease.py` with `RunLease` — acquire as a conditional update that supersedes atomically, and fence by **comparing holder identity**, not by racing
- [ ] T014 [P] Create `src/core/observation/types.py` with the `Observer` protocol and `ObservationOutcome` as a **three-way** result (`happened` / `did_not_happen` / `cannot_determine`) per `data-model.md`
- [ ] T015 [P] Create `src/core/observation/bracket.py` — write an intent record before a non-repeatable effect and a result record after, so an interruption between them is resolvable
- [ ] T016 [P] Create `src/core/bounds.py` with `ExecutionBounds` — maximum duration, step limit, stuck-wait watchdog — checked **where the run advances**, not by a background timer

### Run state and registry

- [ ] T017 Add `COMPLETED`, `STOPPED`, and `PARKED` to `RunState` in `src/core/run.py` and a `stop_reason: str | None` to `GovernedRun`; thread grant and lease onto `GovernedRun`; migrate every `start_governed_run` caller under `tests/` to supply a grant so `make check` stays green. **Three states, not one**: 002's `ACTIVE`/`REFUSED` pair cannot express a run that finished, a run a bound halted, or a run waiting on a human, and resume needs all three distinctions — without `COMPLETED` a resume attempt against a finished run re-enters the loop, and treating a bounded stop as `PARKED` would invite resuming past the bound
- [ ] T017a [P] Unit test `tests/unit/test_run_states.py` — a resume attempt against a `COMPLETED` or `STOPPED` run does not re-enter the run loop; `STOPPED` carries a `stop_reason`
- [ ] T018 [P] Add a repeatable flag and an optional `Observer` to `ToolRegistration` in `src/core/registry/memory.py`; repeatability is the tool author's declaration, not inferred from `product_mode`

### Harness

- [ ] T018a [P] [GATE:no-secret-leak] Unit test `tests/unit/test_database_policy_placement.py` — the database policy belongs to the **workload identity**, never to per-step authority manufactured for an agent. Assert no agent definition's ceiling and no manufactured `TaskCredentialRef` can reach the credential path. Backwards, this is serious: database access inside a definition's ceiling would let a model-chosen tool call reach the checkpoint store, which is the run's own record of what it has done
- [ ] T019 Create `tests/harness/durability_fixtures.py` — in-process disruption (tear a run down, rebuild from checkpoint), a fake `Observer` scriptable to each of the three outcomes, grant helpers, and a Postgres-backed provider fixture that obtains credentials the way the harness does
- [ ] T020 [P] [GATE:no-secret-leak] Unit test `tests/unit/test_checkpoint_purity.py` — no checkpoint written by **any** provider contains credential, token, or secret material (FR-003, SC-003). Runs without the enclave for the in-memory provider; with it for Postgres
- [ ] T021 [P] Export the new public symbols from `src/core/durability/__init__.py`, `src/core/observation/__init__.py`, and `tests/harness/__init__.py`

**Checkpoint**: Seams importable; 004 suite green after migration; Postgres provider round-trips a
checkpoint; core still free of agent-framework imports

---

## Phase 3: User Story 1 - An interrupted run resumes without re-doing its work (Priority: P1) 🎯 MVP

**Goal**: A disrupted run resumes from its checkpoint and completes, with every already-completed
step showing exactly one execution across the whole run

**Independent Test**: quickstart Scenario A — `tests/component/test_resume.py`

### Tests for User Story 1

- [ ] T022 [P] [US1] Add `tests/component/test_resume.py` — disrupt a multi-step run in-process, resume, assert it completes
- [ ] T023 [P] [US1] Assert already-completed steps show **exactly one** execution across the whole run, not one per segment (SC-001) in `tests/component/test_resume.py`
- [ ] T024 [P] [US1] [GATE:correlation] Assert `assert_correlated` / `assert_audit_chain` join both segments under one correlation ID with the hash chain intact across the disruption boundary (FR-015, SC-008)
- [ ] T024a [US1] Add `tests/component/test_resume_cross_process.py` (quickstart Scenario A2), a Postgres-backed scenario that crosses a **genuine process boundary** — write checkpoints in one process, resume in another — so durability is demonstrated rather than asserted. plan.md and research.md both commit to this; a suite that only tears down and rebuilds in-process proves the code reloads its own state, not that the state survived anything. This is the one exception to in-process simulation, and it does not violate FR-016: restarting a test process is not terminating real infrastructure
- [ ] T025 [P] [US1] [GATE:fail-closed] Add `tests/component/test_checkpoint_failure.py` — an unwritable checkpoint stops the step rather than letting it proceed unrecorded, and an unreadable or corrupt checkpoint parks or refuses rather than resuming on partial state

### Implementation for User Story 1

- [ ] T026 [US1] Create `src/core/durability/resume.py` with `resume_run` — load checkpoint, acquire lease, re-manufacture authority, resolve open intents, continue
- [ ] T026a [US1] Move a run to `COMPLETED` when its work finishes, and write that state to its checkpoint. **A state nothing writes is a state nothing can be trusted to mean** — T017 adds the value and T017a asserts on it, so without this the test passes against something no code produces
- [ ] T027 [US1] Record `step_index`, `written_by`, and the current `run_state` on every checkpoint write in the invoke path so resume has a point to resume from and fencing has an identity to compare
- [ ] T028 [US1] Ensure the resumed run invokes through the **same** `invoke_tool` path as the original — the bracket wraps that path rather than creating a second one (Principle II)
- [ ] T029 [US1] Make checkpoint-write failure propagate at the call site; no swallow-and-continue anywhere on the durability path

**Checkpoint**: Scenario A green; SC-001 and SC-008 hold; MVP demoable

---

## Phase 4: User Story 2 - Resume re-authenticates rather than replaying a credential (Priority: P1)

**Goal**: Resume manufactures fresh authority under the surviving grant, and no path accepts a
credential recovered from durable state

**Independent Test**: quickstart Scenario B — `tests/component/test_resume_authority.py`

> The substrate already makes replay unavailable: a resumed run is a new allocation with a new
> attested identity (ADR-0048). The work here is therefore **negative** — prove no path
> reintroduces a credential across the boundary. Read a failure in this phase as "someone added a
> way to carry authority across a disruption," not as "the substrate leaked."

### Tests for User Story 2

- [ ] T030 [P] [US2] Add `tests/component/test_resume_authority.py` — resume under a valid grant manufactures fresh authority (SC-002)
- [ ] T031 [P] [US2] [GATE:no-secret-leak] Assert a pre-disruption credential presented directly after resume is **rejected rather than honoured**
- [ ] T032 [P] [US2] Extend `tests/unit/test_checkpoint_purity.py` to scan every checkpoint the whole suite produces, not only fixtures — SC-003 says "anywhere in the suite" and a scan of hand-built blobs would not show that

### Implementation for User Story 2

- [ ] T033 [US2] Implement re-attestation in `resume_run`: re-exchange under the surviving grant using the **current** allocation's identity; no parameter, field, or cache accepts a prior credential
- [ ] T034 [US2] [GATE:no-secret-leak] Add a source-level check that no module under `src/core/durability/` or `src/core/authority/` reads credential material out of a checkpoint — a structural guard, since the property is the absence of a path rather than a behaviour to exercise

**Checkpoint**: Scenario B green; SC-002 and SC-003 hold

---

## Phase 5: User Story 3 - A run whose consent has expired parks instead of resuming (Priority: P1)

**Goal**: Resume under an expired grant parks with zero subsequent steps and remains resumable if
consent is renewed

**Independent Test**: quickstart Scenario C — `tests/component/test_park_on_expiry.py`

### Tests for User Story 3

- [ ] T035 [P] [US3] Add `tests/component/test_park_on_expiry.py` — disrupt, advance the frozen clock past grant expiry, attempt resume, assert `PARKED` and **zero** subsequent step executions (SC-004)
- [ ] T036 [P] [US3] Assert a parked run is durable and queryable, and that supplying fresh consent lets it resume from its checkpoint
- [ ] T037 [P] [US3] [GATE:fail-closed] Assert consent expiring **mid-run** parks at the same boundary it would on resume — the next step cannot be authorized, so there is one behaviour, not two

### Implementation for User Story 3

- [ ] T038 [US3] Implement the park transition in `src/core/run.py` and `resume.py` — parked is *waiting*, not failed, and is recorded as such
- [ ] T039 [US3] Ensure grant expiry is checked before any step executes on resume, and that a parked run holds no live authority
- [ ] T040 [US3] Record parking in the audit trail with the blocking reason, so an operator can tell "needs fresh consent" from "needs a human to resolve a step"

**Checkpoint**: Scenario C green; SC-004 holds

---

## Phase 6: User Story 4 - An interrupted step is resolved by looking, not by guessing (Priority: P1)

**Goal**: An interrupted non-repeatable step is resolved against observed external state, in both
directions, and an unobservable one parks

**Independent Test**: quickstart Scenario D — `tests/component/test_reobservation.py`

### Tests for User Story 4

- [ ] T041 [P] [US4] Add `tests/component/test_reobservation.py` — interrupt between intent and result; `happened` → step not repeated
- [ ] T042 [P] [US4] Add the opposite direction to the same module — `did_not_happen` → step proceeds. **Both directions are required**: a suite that only tests one proves the platform can skip, not that it can decide
- [ ] T043 [P] [US4] [GATE:fail-closed] Assert `cannot_determine` parks for human resolution and never resolves to a guess (FR-008)
- [ ] T044 [P] [US4] [GATE:correlation] Assert the intent record, the observation, and the resolution are all present in the audit trail and joined to the run (SC-005)
- [ ] T045 [P] [US4] Assert an unreachable external system yields `cannot_determine` rather than an assumed outcome

### Implementation for User Story 4

- [ ] T046 [US4] Wrap calls to non-repeatable tools in the intent/result bracket in the invoke path
- [ ] T047 [US4] Implement open-intent resolution in `resume_run` — ask the tool's `Observer`, act on the answer, record the resolution
- [ ] T048 [US4] Identify which currently registered tools are non-repeatable and mark them. Record in the PR that this is an **ongoing obligation** every future non-repeatable tool inherits, not a one-time pass — ADR-0026 puts the implementation difficulty here
- [ ] T049 [US4] Implement stable idempotency keys so a repeat of the same step is recognizable as the same step rather than a new one (FR-010)

**Checkpoint**: Scenario D green; SC-005 holds

---

## Phase 7: User Story 5 - A resumed run invalidates any instance still running elsewhere (Priority: P1)

**Goal**: A superseded holder's tool calls and checkpoint writes are rejected by identity
comparison — zero side effects, zero state mutation

**Independent Test**: quickstart Scenario E — `tests/component/test_fencing.py`

### Tests for User Story 5

- [ ] T050 [P] [US5] Add `tests/component/test_fencing.py` — resume while a prior instance is still active; the prior instance's tool call is rejected with **no side effect** (SC-006)
- [ ] T051 [P] [US5] Assert the prior instance's checkpoint write is rejected and does not overwrite current state
- [ ] T052 [P] [US5] Assert the rejection is **distinguishable from an ordinary denial** in the audit trail — an operator reading "denied" should be able to tell a superseded writer from a policy refusal
- [ ] T053 [P] [US5] Assert two simultaneous resume attempts end with exactly one lease holder and the other **refused, not queued**

### Implementation for User Story 5

- [ ] T054 [US5] Implement lease acquisition and fencing in `src/core/durability/lease.py` and the Postgres provider as a single conditional update
- [ ] T055 [US5] Gate every tool call and checkpoint write on `check_lease`, rejecting a superseded holder on comparison rather than racing
- [ ] T056 [US5] Add a distinct reason code for supersession so T052's assertion has something to assert on

**Checkpoint**: Scenario E green; SC-006 holds

---

## Phase 8: User Story 6 - A run cannot consume authority indefinitely (Priority: P2)

**Goal**: Each of the three bounds stops a run that exceeds it, with the reason recorded

**Independent Test**: quickstart Scenario F (first half) — `tests/unit/test_bounds.py`

### Tests for User Story 6

- [ ] T057 [P] [US6] Add `tests/unit/test_bounds.py` — maximum duration stops the run with the reason recorded
- [ ] T058 [P] [US6] Add the step-limit case to the same module
- [ ] T059 [P] [US6] Add the stuck-wait watchdog case to the same module (SC-007 requires all three)
- [ ] T060 [P] [US6] [GATE:fail-closed] Assert a bounded stop performs no further steps and releases authority

### Implementation for User Story 6

- [ ] T061 [US6] Check bounds where the run advances in `src/core/tools/invoke.py` and `src/core/run.py` — not in a background timer, whose failure would silently unbound the run
- [ ] T062 [US6] Move the run to `STOPPED` and set `stop_reason` on the transition, so SC-007's "with the reason recorded" is satisfied by data rather than by a log line

**Checkpoint**: Scenario F first half green; SC-007 holds

---

## Phase 9: User Story 7 - The durability guarantees hold for any provider (Priority: P2)

**Goal**: All seven conformance rows execute as **in force**, each with a break fixture, written
against the seam rather than an implementation

**Independent Test**: quickstart Scenarios F (second half) and G — `make conformance`

### Conformance rows

- [ ] T063 [P] [US7] [GATE:conformance] Add `tests/conformance/durability/test_kill_resume.py` and `test_kill_resume_break.py`
- [ ] T064 [P] [US7] [GATE:conformance] Add `test_reauthenticate_never_replay.py` and its break fixture
- [ ] T065 [P] [US7] [GATE:conformance] Add `test_reobserve_never_reexecute.py` and its break fixture
- [ ] T066 [P] [US7] [GATE:conformance] Add `test_fencing_double_resume.py` and its break fixture
- [ ] T067 [P] [US7] [GATE:conformance] Add `test_park_on_grant_expiry.py` and its break fixture
- [ ] T068 [P] [US7] [GATE:conformance] Add `test_duplicate_side_effect_rejection.py` and its break fixture
- [ ] T069 [P] [US7] [GATE:conformance] Add `test_drain_across_upgrade.py` and its break fixture — a controlled in-process handover, honestly labelled as simulated rather than a real rolling upgrade

Break fixtures follow 004's pattern: **self-verifying**, constructing the weakened arrangement and
asserting the check raises, so they pass on a clean tree. A row whose failure nobody has observed
is a row nobody knows works (FR-014).

### Provider independence and the gate

- [ ] T070 [US7] Parameterize the durability conformance lane by provider — a `--provider` pytest option in `tests/conformance/durability/conftest.py` supplying the provider fixture, as `quickstart.md` Scenario G shows — so the same rows run against both the in-memory double and Postgres **without rewriting** — that is the executable form of ADR-0024's central claim (SC-009)
- [ ] T071 [US7] Update `contracts/conformance-adapter.md` in `specs/004-primary-adapter/` to move the durability rows from deferred to in force, in this same change — ADR-0047 requires the deferral list stay accurate, and a stale one reads as a gap nobody noticed
- [ ] T072 [US7] Make the durability conformance lane merge-blocking in `.github/workflows/ci.yml` for changes touching the durability seam, as 004 did for the adapter lane. If the enclave cannot run in CI, say so explicitly in the PR and record what that means for the claim — **do not** let the rows silently skip

**Checkpoint**: `make conformance` runs all seven rows in force and passes on a clean tree

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T073 [P] [GATE:determinism] Extend `tests/unit/test_no_live_dependencies.py` so the prohibition covers this feature's paths: no live model provider, no live managed-product API, and no test that simulates disruption by terminating real infrastructure (FR-016, SC-010). Note that the check's shape changes here — Vault and Postgres are now **permitted and required**, so a blanket "no network" assertion would be wrong
- [ ] T074 [P] Document the durability lane in `docs/development/testing.md` — what `make dev-up` must be running, what fails loudly when it is not, and why this lane is not hermetic when every earlier one was
- [ ] T075 [P] Update `ROADMAP.md` to move durable execution from Next to Shipped and record the seven gate rows as attached
- [ ] T076 [GATE:fail-closed] Review every new failure path for catch-and-continue: unwritable checkpoint, unreadable checkpoint, unobservable step, expired grant, lost lease. Each must refuse or park; none may proceed on partial state
- [ ] T077 Review the sealed-core diff against FR-018's list before opening the PR. A core change outside checkpoint schema, provider protocol, grant lifetime, per-step manufacture, lease and fencing, bounds, and the bracket is out of scope and needs its own spec. Confirm FR-017 as well: no dedicated workflow-engine provider has appeared, which attaches later and only under ADR-0028's named-trigger rule
- [ ] T078 Open `feat/005-durable-execution` with the breaking-seam declaration (T009), the dependency justification (T001), the single-node caveat, and security-maintainer review — contribution class is **sealed core**

---

## Dependencies

**Story completion order**: US1 → US2 → US3 → US4 → US5 → US6 → US7. US2–US6 each depend on US1's
resume path existing; US7 depends on all of them, since the rows assert their guarantees.

**Blocking**: T000 (deployment tree) blocks everything. Phase 2 blocks all story phases. T009's
protocol change blocks T010 and T012. T011a's credential module blocks T012 — the provider takes
its connection from it rather than building one. T017's `RunState` change blocks US1's completion
assertions, US3's parking, and US6's bounded stop.

**Parallel opportunities**:

- T005/T006, T011, T011a, T011d, T013–T016, T017a, T018, T018a in Foundational (different files)
- Within each story, test modules marked [P] can be drafted before implementation
- All seven conformance rows (T063–T069) are independent of each other
- After US1: US2's authority work and US6's bounds work touch different modules

### Parallel Example: After Foundational + US1 MVP

```bash
# Developer A: US2 re-attestation + US3 parking
# Developer B: US4 re-observation + the bracket
# Developer C: US5 fencing + US6 bounds
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T000 — confirm the enclave is real, not promised
2. Phase 1 Setup
3. Phase 2 Foundational (the grant and protocol migrations are mandatory)
4. Phase 3 US1
5. **STOP and VALIDATE**: Scenario A, exactly-once on completed steps, correlation across the boundary, `make check`
6. Demoable as kill-and-resume before the harder guarantees land

### Incremental Delivery

1. Setup + Foundational → seams, Postgres provider, harness fixtures
2. US1 → kill-and-resume (MVP)
3. US2 → re-authenticate, never replay
4. US3 → park on expired consent
5. US4 → re-observe, never re-execute — the hardest, per ADR-0026
6. US5 → fencing against double resume
7. US6 → execution bounds
8. US7 → all seven rows in force, then merge-blocking
9. Polish → scope review, security-maintainer review on the feat PR

### Notes

- **Eval gate type omitted** (N/A) — no packs, prompts, models, or policies promoted.
- **The determinism bar changed shape** for this feature. Earlier features asserted "no operated
  service"; here Vault and Postgres are required. What survives is narrower: no live models, no
  live managed-product APIs, and disruption simulated in-process. T073 must encode the narrower
  rule, not the old one.
- **The suite runs as a Nomad job.** Settled, not open — a host process has no workload identity
  and therefore no route to a database credential, and the alternatives are a DSN (FR-017a
  forbids it) or a second Vault auth method (a standing credential on a workstation). What the
  deployment tree still owes is the mechanism, not the decision.
- **`RunState` gains three terminal states, not one.** 002's `ACTIVE`/`REFUSED` pair cannot
  express a run that finished, one a bound halted, or one waiting on a human — and resume needs
  all three distinctions. Without `COMPLETED` a resume attempt against a finished run re-enters
  the loop; treating a bounded stop as `PARKED` invites resuming past the bound.
- **"Credential refresh" and "re-authentication" are different things.** The run re-authenticates
  to Vault on resume — that is US2 and Principle IV. The provider refreshes a database credential
  after a rejection — that is plumbing. They must not share a word, or a reviewer skims one
  thinking they read the other.
- **Two guarantees are the substrate's, not this code's.** Resume-re-authenticates and fencing are
  properties of Nomad workload identity (ADR-0048). The tasks that touch them are written to prove
  no path *undoes* them — a different and easier job than enforcement, and worth stating so nobody
  builds a credential blacklist that duplicates what the substrate already provides.
- **Single-node caveat.** Fencing and parking are proven against single-node behaviour; multi-node
  partition is not exercised. Recorded in `contracts/conformance-durability.md` so the claim is not
  read as broader than it is.
- **Parking has no human surface.** Control Groups (ADR-0016) and northbound (ADR-0033) are out of
  scope; parked runs are observable and resumable programmatically, which meets the conformance bar
  and is honestly less than a product.
- **Drain-across-upgrade is simulated** as a controlled handover, not a real rolling upgrade.
- A dedicated workflow-engine provider remains deferred under ADR-0028's named-trigger rule
  (FR-017).
- Contribution class at implement: **sealed core** — security-maintainer review mandatory.
