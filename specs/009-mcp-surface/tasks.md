# Tasks: MCP Surface

**Input**: Design documents from `specs/009-mcp-surface/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**The order is unusual and deliberate: the CI lane comes before everything it protects.**
Sixteen merge-blocking rows currently depend on an instruction in `AGENTS.md`. This feature
then makes a sealed-core change, amends the constitution, and adds a persistent service —
each exactly the kind of change those rows exist to catch. Building the control first is the
only sequence where the control is ever tested by something that had not already passed it.

**Tests**: the **products agents operate** are faked; they are outside our boundary and
making one unreachable is how an outage is simulated. Everything else is real — Vault,
Postgres, the scheduler, allocations, and the MCP protocol itself.

**Scope bound**: the surface adds no decision of its own, and the dependency gate is a hook
rather than a pre-check. If either drifts, the thing that drifted is the finding — say so
rather than adjusting the test.

**Organization**: grouped by user story so each is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Unknown or stale dependency health; unreachable trust fabric | Refused, and refused **before execution** — not refused after an intent record exists |
| **Conformance** | Every row in `contracts/conformance-mcp.md` | Fifteen rows, including the **parity row owed since ADR-0033** |
| **Correlation / evidence** | Parity's audit comparison; continuous verification | Equivalence is types, order, subject, decision fields — not "both produced some audit" |
| **Eval** | N/A | No packs, prompts, models, or policies promoted |
| **No-secret-leak** | CI workflow, health detail fields, alert output | No licence, no token, no product credential in any emitted artifact |
| **Determinism** | Every test path | Only the operated products are faked. No live model, no live managed-product API |

## Path Conventions

- Surface: `src/surfaces/mcp/`
- Core mechanism: `src/core/dependencies/`, `src/core/durability/`
- Infrastructure: `infra/jobs/mcp.nomad.hcl`, `.github/workflows/enclave.yml`
- Governance: `.specify/memory/constitution.md`, `docs/adr/0049-*.md`
- Tests: `tests/unit/`, `tests/component/`, `tests/conformance/mcp/`, `tests/harness/`

---

## Phase 0: Premise Gates

Both are cheap, and each can invalidate a large part of this plan. Run them before anything
is built on top.

- [X] T001 [GATE:conformance] Add `mcp` to a scratch environment and run `bash scripts/check-licenses.sh`. **Already verified during Phase 0 research** — `mcp` 1.28.1 is MIT and its tree (`sse-starlette`, `python-multipart`, `jsonschema`, `referencing`, `rpds-py`, `python-dotenv`, `httpx-sse`, `pydantic-settings`) clears the allowlist with no changes. Re-run as the gate rather than trusting a note, since 008's premise gate caught a wrong licence claim in exactly this position
- [X] T002 [GATE:conformance] **ANSWERED: no, not unmodified.** Three substrate assumptions surfaced, each fixed in the substrate module or the lane — see the commits. **Prove the enclave can come up on a Linux GitHub runner at all**, on a throwaway branch, before building the lane on the assumption. `infra/bin/enclave-up` requires `docker nomad vault terraform python3` on PATH and starts `nomad agent -dev` reachable on `127.0.0.1`; the runner has Docker but none of the others, and the docker-driver-plus-agent arrangement is only ever exercised on Docker Desktop. If it cannot come up, the lane's design is wrong and everything after T012 changes shape

---

## Phase 1: Setup

- [X] T003 Pin `mcp==1.28.1` in the `surfaces` extra in `pyproject.toml`, with a comment recording that the protocol is adopted rather than implemented (Principle I; ADR-0033's "migrate onto official servers as they mature")
- [X] T004 [P] Create `src/surfaces/mcp/__init__.py` and `src/core/dependencies/__init__.py`, and `tests/conformance/mcp/__init__.py`. Under `mypy` strict with `explicit_package_bases`, a missing `__init__.py` is a build error rather than an inconvenience
- [X] T005 [P] Fix the fast lane's sync step in `.github/workflows/ci.yml`: it runs `uv sync --frozen --extra adapters` while `make check` uses `--extra adapters --extra surfaces`. It works because `uv run` resolves the missing extra, at the cost of the cache the sync step exists to warm

---

## Phase 2: User Story 6 — CI runs the rows a human currently has to remember (P1) 🎯 FIRST

**Goal**: an enclave lane that stands the stack up and runs the enclave rows, so sixteen
merge-blocking rows stop depending on an instruction being obeyed.

**Independent test**: open a pull request that breaks an enclave row; the lane fails and the
merge is blocked without a human having run anything.

**This phase lands before the rest of the feature on purpose** — see the note at the top.

- [X] T006 [US6] [GATE:no-secret-leak] Create `.github/workflows/enclave.yml` triggered on `pull_request`, with the enclave job conditioned on `github.event.pull_request.head.repo.full_name == github.repository`. **Not `pull_request_target`**: that runs base-branch workflows with secrets available while the fork controls the code under test, which would hand a licence and a live enclave to arbitrary pull requests — a credential-disclosure problem traded for a coverage gap
- [X] T007 [US6] Install `nomad`, `vault`, and `terraform` in the lane, pinned by version and checksum. Docker is already present on the runner; the other three are not
- [X] T008 [US6] [GATE:no-secret-leak] Write the Vault Enterprise licence from `secrets.VAULT_ENT_LICENSE` into the environment `enclave-up` expects, and assert it never reaches a log. **Quote handling is the trap 006 paid for**: `.env` values are quoted, and passing the quotes through made Vault reject the licence with "error decoding version: expected integer"
- [X] T009 [US6] (FR-018) Run **`make dev-up` then `make conformance`** — the same commands a human runs, not a bespoke sequence (Principle VII). Two ways to run the gate is two gates, and the one nobody runs locally is the one that rots
- [X] T010 [US6] [GATE:fail-closed] **Observed three times before the lane first went green**, which is stronger evidence than a contrived run: every bring-up failure reported failure and skipped conformance. Assert in `.github/workflows/enclave.yml` that a failure to stand up the enclave reads as a **failure**, never a pass or a skip (FR-020). Verify by running the lane with the licence secret deliberately absent
- [X] T011 [US6] Assert the job conditions in `.github/workflows/ci.yml` and `.github/workflows/enclave.yml` keep the fast lane running for fork pull requests while the enclave lane does not (FR-019), and that a fork contributor's experience is unchanged
- [X] T012 [US6] [GATE:conformance] (SC-011, SC-012) **Prove `.github/workflows/enclave.yml` fails on a broken row.** Push a branch with a deliberately broken enclave row and confirm the lane goes red. A lane that has only ever seen green is a lane nobody knows works — the same reason every conformance row here ships a break fixture

**Checkpoint**: from here, every subsequent change in this feature is covered by an automated gate.

---

## Phase 3: Foundational — the sealed-core change, the amendment, and the health store

**Blocking for US1–US5.** Contains the two changes that are not this feature's own: a state
removed from 005's durability path, and a constitutional gate row that changes what it asserts.

### Governance (security-maintainer review required)

- [X] T013 Remove `RunState.PARKED` and add `SUSPENDED` in `src/core/run.py`, splitting what it conflated: grant expiry becomes `STOPPED` with the reason recorded, and an unreachable dependency becomes `SUSPENDED` naming that dependency. **Not a rename** — keeping the name would carry the human-in-the-loop connotation into the state that most needs it gone. **`is_terminal()` is where the split becomes behaviour**: `SUSPENDED` must be non-terminal, and the method's own docstring says why it is load-bearing — a resume attempt against a finished run re-enters the loop. Wrong in one direction the sweeper can resume nothing; wrong in the other a stopped run resumes past its bound
- [X] T014 Update `src/core/durability/checkpoint.py` and `resume.py` for the split, and the five test modules that reference parking, including `tests/conformance/durability/rows.py`
- [X] T015 [GATE:conformance] Amend `.specify/memory/constitution.md` in **three** places, with one Sync Impact Report citing ADR-0049 and ADR-0033 and naming each (FR-004a, SC-014):
  1. Quality Gates durability rows: **"grant-expiry parking"** → grant-expiry **stop**.
  2. Quality Gates: **"surface parity across all four transports"** → parity across **every pair of implemented transports**. Claiming the row as worded would assert something untrue with two transports — the stub ADR-0047 forbids.
     **Frame this as a correction, because that is what it is.** ADR-0033 says *"the same operation attempted through **any** transport"* — it never said all four. The constitution's wording was a mis-statement of the ADR it exists to gate, so Principle X applies directly: where a document conflicts with an Accepted ADR, the ADR wins and the document is amended. "This corrects a mis-statement of ADR-0033" is a materially easier governance argument than "we are changing the gate because two is not four", and it is the true one.
  3. **Principle VIII**: "or the run **parks**" → the run **stops**, reason recorded. Found by an analyze pass; the first draft amended only the gate row, which would have left a *principle* describing a state that cannot exist.
     **Stops, not suspends — and the wrong choice looks right.** This "parks" has a different trigger from the durability one: no eval-qualified model cell is available, not a product outage. Suspending is tempting, because a cell *might* be qualified later. It is wrong: qualifying a cell is eval-gated human work, so a run suspended waiting for one is a run waiting on a person — precisely what ADR-0049 removes. Reaching for `SUSPENDED` here would restore human-waiting through the model-fallback path while every other part of the feature forbids it.
  **MINOR** — rows are redefined and a principle's wording follows an Accepted ADR; no principle is removed, so no ADR-0016 quorum
- [X] T015a [GATE:conformance] Assert in `tests/unit/test_parked_is_gone.py` that zero occurrences of `PARKED` remain anywhere in `src/` or `tests/` (FR-015, SC-009), **and that `.specify/memory/constitution.md` describes neither parking nor four-transport-only parity** (SC-014), **and that `RunState.SUSPENDED.is_terminal()` is `False`** — the one-line assertion that keeps the sweeper able to resume anything at all. The governing document was getting less scrutiny than the code it governs, and a partial amendment is the failure mode a checker catches trivially. Without it, a single missed reference leaves a state in the sealed core that nothing can enter and everything still compiles
- [X] T016 [P] Update `specs/005-durable-execution/contracts/conformance-durability.md` so its parking row matches what it now asserts

### The dependency mechanism

- [X] T017a Add `dependency_health: DependencyHealthReader | None = None` to `GovernedRun` in `src/core/run.py`, and a matching optional parameter on `start_governed_run`. **A 002-era sealed-core change, and the one that makes the gate buildable at all**: `builtin_governance_hooks()` takes no arguments and a hook handler receives only a `HookContext`, so without a field on the run there is no path from the gate to the health it must consult. Optional and defaulting to `None` so every existing caller keeps compiling — the mistake T042a1 nearly repeated. **In Foundational, not in a story phase**: anything that constructs a run depends on it, so a story working in parallel would otherwise find `GovernedRun` changing underneath it
- [X] T017b [GATE:fail-closed] Make the gate **inert when no reader is configured**, and fail closed only when a reader is present and reports unknown. The distinction matters and is easy to collapse: "unknown health for a monitored product is unhealthy" (FR-006) is not "a run with no dependency mechanism denies everything". Collapsing them would make every 002-era run and test refuse every tool call, which looks like the gate working
- [X] T017 Create `DependencyHealth` and `HealthState` in `src/core/dependencies/types.py` per data-model.md, with **`UNKNOWN` treated as `UNHEALTHY`**. Guessing reachable is how a dead dependency gets called anyway
- [X] T018 Create the health store in `src/core/dependencies/store.py`, persisting to Postgres via the schema in T019. **Not in memory**: a restart must not silently mean "everything is reachable again", and a stale record must read as unknown rather than as either extreme
- [X] T019 Add `dependency_health` and `suspended_runs` to a new `src/core/dependencies/schema.sql`, with an index on `suspended_runs(awaiting)` — the sweeper's query is "what is waiting on this product", not a scan of every run
- [X] T020 [GATE:no-secret-leak] Grant the evidence role **no access** to either new table in `infra/modules/trust-fabric/database.tf`. Neither is evidence; both are operational state, and widening a SELECT-only credential to cover "things in the same database" is how it quietly becomes a general reader

### The service

- [ ] T021 Create `infra/jobs/mcp.nomad.hcl` as a Nomad **`service`** job — the first persistent component here. Use `cores`, not default MHz resources: the enclave node fingerprints its CPU total as a couple of dozen MHz, and 008's dispatch job queued forever with "Resources exhausted" before that was found
- [ ] T022 [GATE:fail-closed] Give the service an `identity` block with a TTL and `change_mode = "restart"`, and **no product credential of any kind**. A persistent service is a persistent identity — the least ephemeral thing in this platform — so what limits it is what it is not given
- [ ] T022a [GATE:fail-closed] Add a `mcp` JWT auth role in `infra/modules/trust-fabric/auth.tf`, bound to the MCP job id and carrying `harness_database` so `verify_stream_integrity` (T054) can read under the run role. **The auth backend defines `harness`, `conformance`, `agent-run`, and the per-agent roles — no `mcp`** — so T024 would obtain credentials against a role that does not exist. That failure surfaces as "claim nomad_job_id does not match any associated bound claim values", which 008 hit at T030 and which names the claim rather than the missing role
- [ ] T023 Register the service from `infra/bin/enclave-up` and assert it in `infra/bin/enclave-verify`, so a missing MCP service fails at bring-up rather than appearing later as suspended runs that never resume
- [ ] T024 Create the service entrypoint in `src/surfaces/mcp/server.py`, obtaining credentials by presenting its own workload identity

**Checkpoint**: the sealed-core change is done and gated; stories can proceed.

---

## Phase 4: User Story 1 — The same operation, through a second surface, gets the same answer (P1)

**Goal**: the parity row ADR-0033 has been owed since 008.

**Independent test**: drive every operation in 008's recorded set through both transports as
the same subject; assert identical verdicts and equivalent audit events.

- [ ] T025 [US1] Implement the MCP tool surface in `src/surfaces/mcp/operations.py`, reaching the authorization core through the interface 008 exposes rather than a parallel path (FR-001)
- [ ] T026 [US1] [GATE:fail-closed] Authenticate **as the calling user, never as the service** (FR-002a) in `src/surfaces/mcp/server.py`. A service account would collapse every caller into one subject and destroy the non-repudiation the delegation chain exists for — invisibly, because everything would still work
- [ ] T027 [US1] Build the parity driver in `tests/harness/parity.py`: run an operation through both transports as one subject and return both verdicts and both audit projections
- [ ] T028 [US1] [GATE:correlation] Implement the audit projection in `tests/harness/parity.py` — event types, order, subject, decision fields; **transport excluded** (FR-003a). Naming the projection is what makes the assertion falsifiable; "both produced some audit" is satisfied by two surfaces that agree about nothing
- [ ] T029 [US1] [GATE:conformance] **Satisfy the amended parity row** (FR-003, FR-004, SC-001) — the API/MCP pair, per T015's incremental wording. Not the four-transport row as originally worded in `tests/conformance/mcp/test_surface_parity.py`, driven from `specs/008-northbound-api/contracts/operations.snapshot.json`. Deferring a second time with two transports would stop being rigour
- [ ] T030 [P] [US1] [GATE:conformance] Coverage row in `tests/conformance/mcp/test_surface_parity.py` (FR-005, SC-003): an operation on one transport and not the other is detected **in either direction**, including MCP exposing something the API does not — the direction a transport-specific convenience would grow
- [ ] T031 [P] [US1] Break fixture in `tests/conformance/mcp/test_surface_parity.py`: make one transport emit an extra audit event and assert the comparison catches it. A fixture that broke a verdict would be caught by the verdict row and prove nothing about the audit comparison
- [ ] T032 [P] [US1] [GATE:conformance] Assert in `tests/conformance/mcp/test_mcp_acts_as_caller.py` that every MCP-originated operation names the calling user as subject; zero name the service (SC-002a)

---

## Phase 5: User Story 3 — A tool call against a known-dead dependency is refused before it runs (P1)

**Goal**: refusal before execution, inside the pipeline, with the two denial classes distinct.

**Independent test**: mark a dependency unhealthy, attempt a call, assert the denial precedes
execution, no intent record is written, and the denial is audited.

**Before US2** because suspension is what happens when a run meets a dependency it cannot
reach — the knowing has to exist first.

- [X] T033 [US3] Implement the dependency gate as a **pre-execution hook** in `src/core/dependencies/gate.py`, registered in `builtin_governance_hooks()` in `src/core/hooks/governance.py` alongside authority and mirroring (FR-009), reading health through `run.dependency_health` (T017a)
- [ ] T034 [US3] [GATE:fail-closed] Deny before execution and write **no intent record** in `src/core/dependencies/gate.py` (FR-007, SC-004). Attempting a call against a dead dependency writes an intent that must later be resolved by re-observation — against the same dead dependency, so the bracket that makes interrupted steps resolvable becomes the thing that cannot be resolved
- [ ] T035 [US3] Implement `DenialClass` in `src/core/dependencies/types.py`: `POLICY` and `AVAILABILITY`, both audited, **only availability model-visible** (FR-008). Getting this backwards would teach agents that scope refusals are obstacles to route around, which inverts Principles II and III — and nothing would break visibly
- [ ] T036 [US3] [GATE:conformance] Row in `tests/conformance/mcp/test_dependency_refusal.py`: refusal precedes execution and no intent record exists
- [ ] T037 [US3] [GATE:conformance] **Placement row** in `tests/conformance/mcp/test_refusal_placement.py` (FR-009): assert the gate runs inside the hook pipeline, in hook order, not as a pre-flight. Break fixture **moves it to a working pre-flight** and asserts detection — a fixture that merely removed the gate would test refusal, which T036 already covers. The failure being guarded is a working optimisation
- [ ] T038 [P] [US3] [GATE:conformance] Assert in `tests/conformance/mcp/test_denial_classes.py` (FR-008, SC-005) that the two denial classes are distinguishable in the trail, and that only availability reaches the model
- [ ] T039 [P] [US3] [GATE:fail-closed] Assert in `tests/component/test_unknown_health_refuses.py` that an unknown or stale health record refuses rather than being assumed reachable (FR-006)

---

## Phase 6: User Story 2 — A run waiting on a broken dependency resumes without anyone noticing (P1)

**Goal**: ADR-0049's central claim, end to end.

**Independent test**: make a dependency unreachable mid-run; assert the run suspends naming
it and its container exits. Restore it; assert the sweeper resumes the run in a **new**
allocation and it completes.

- [ ] T040 [US2] Implement suspension in `src/core/durability/resume.py`: record the run as `SUSPENDED` naming the dependency, at its step index (FR-010). **The checkpoint write and the `suspended_runs` insert happen in one transaction** — the checkpoint is authoritative and the table is the sweeper's index over it, and a suspension that recorded one without the other fails silently in whichever direction it split: invisible to the sweeper forever, or resumable after completion
- [ ] T041 [US2] [GATE:conformance] **End the container on suspension** in `src/core/durability/resume.py` (FR-011). A suspended run is a record, not a process holding a slot — an idling container costs nothing until it costs one slot per suspended run
- [ ] T042 [US2] Implement the health checker in `src/surfaces/mcp/health.py` as the **single owner** of reachability (FR-006a), with asymmetric transitions: one failure marks unhealthy, several consecutive successes mark healthy. **Its subject set is the distinct `product` values in the MCP service's own registry**, which T042c declares the registry of record — not a separate configuration list, or a newly registered product goes unmonitored while the mechanism reports healthy
- [ ] T042c [US2] Declare the MCP service's `ToolRegistry` the **estate's registry of record**, in `src/surfaces/mcp/server.py`, with the boundary stated in the module docstring: `ToolRegistry` is per-process and in-memory (002 built it for one caller in one process), so before this **no instance existed that the persistent service could read** — the health checker's subject set had no source, the sixth instance of a prior feature's seam not reaching far enough. **The ADR-0008 line**: this is the platform's own tool registry gaining a persistent home, not a registry *product* — it registers nothing for anyone else, serves no other system, and ships no API for third parties. If it ever grows one, that is the ADR-0008 violation, not this
- [ ] T042a [US2] Extend `infra/jobs/agent-run.nomad.hcl` to carry `run_id` and `step_index` in `meta_required`, and `tests/harness/dispatched_run.py` to resume from them. 008's job declares neither, so **as it stands the sweeper can decide to resume and has nothing to resume with** — found by an analyze pass, and the same shape as 008 shipping `NomadDispatcher` with no job to dispatch to
- [ ] T042a1 [US2] Extend the **`RunDispatcher` protocol** in `src/surfaces/dispatch/types.py` to carry resume state — `run_id` and `step_index`, **both optional and resume-only** — and implement it in both `nomad.py` and `inprocess.py`. Optional is not a style choice: 008's `POST /runs` calls `dispatch()` with exactly five keyword arguments (`src/surfaces/api/runs.py:60`), so required parameters stop the API route compiling. **This is a change to a seam 008 owns**, and it is the layer the first fix for this stopped short of: T042a extends the jobspec to *require* those fields and T042b wires the sweeper to the dispatcher, but `dispatch()` accepts neither, so the sweeper cannot pass what the job demands. Third instance of "a mechanism specified without the thing it acts through" — and the first where fixing one produced the next
- [ ] T042b [US2] Wire the sweeper to `NomadDispatcher` (008) in `src/core/durability/sweeper.py` so resumption goes through the existing dispatch seam rather than a second path to the scheduler. A resume-specific dispatcher would be a second way to start a run, which is how two lifecycles diverge. Depends on T042a1 — the protocol has to accept resume state before anything can pass it
- [ ] T043 [US2] Implement the sweeper in `src/core/durability/sweeper.py`, hosted by the MCP service. **One sweep resumes every run waiting on that dependency** — recovery is a platform-level event, so the response is platform-level. No run polls. **`suspended_runs` is a candidate list, not the truth**: the sweeper re-reads each candidate's checkpoint and resumes only if `run_state` is still `SUSPENDED`, so a stale row cannot resume a finished run
- [ ] T043a [P] [US2] [GATE:conformance] Assert in `tests/conformance/mcp/test_suspend_and_sweep.py` that a `suspended_runs` row whose checkpoint has since reached a terminal state is **skipped and cleaned up**, not resumed. The break fixture writes the two stores in separate transactions and kills between them, then asserts the divergence is detected — the split write is precisely how the silent disagreement happens
- [ ] T044 [US2] [GATE:fail-closed] In `src/core/durability/sweeper.py` (FR-012), the sweeper runs under the service's own identity and **never holds or forwards a run's credentials**; each resumed run gets a new allocation that manufactures its own. A sweeper carrying a credential forward would reintroduce replay after 005 spent a feature making it structurally unavailable
- [ ] T045 [US2] [GATE:conformance] Enclave row in `tests/conformance/mcp/test_suspend_and_sweep.py` (SC-006, SC-007): suspension names the dependency, no container remains, and recovery resumes the run
- [ ] T046 [US2] [GATE:conformance] Assert in `tests/conformance/mcp/test_suspend_and_sweep.py` that the resumed run runs in a **new allocation with a new identity** and re-authenticates. Break fixture resumes into the *same* allocation and asserts detection — resuming and completing looks identical from outside, and only the new-identity assertion distinguishes re-authentication from replay
- [ ] T047 [P] [US2] [GATE:conformance] Assert in `tests/conformance/mcp/test_suspension_bounds.py` that suspension expires against the run's **existing** maximum duration (FR-013), stopping with the reason recorded. No new ceiling, no timeout that grants by default
- [ ] T048 [P] [US2] Assert in `tests/component/test_sweep_respects_revocation.py` that a revoked grant cannot be resumed: the resumed run manufactures fresh authority and fails to obtain it
- [ ] T049 [P] [US2] Assert in `tests/conformance/mcp/test_sweep_fencing.py` that two concurrent sweeps do not double-resume — 005's single-writer fencing governs, and the loser's writes are rejected
- [ ] T050 [P] [US2] Assert in `tests/component/test_health_hysteresis.py` that flapping does not produce a resume storm: recovery hysteresis holds runs suspended until the dependency is consistently healthy

---

## Phase 7: User Story 4 — The agent does the part it still can (P2)

**Goal**: a dependency being down produces partial work rather than nothing.

**Independent test**: with a dependency down, run a task whose plan-producing half needs
nothing from it; assert the output is returned and names what was not attempted.

- [ ] T051 [US4] Surface the availability refusal to the agent as an invitation to adapt in `src/core/dependencies/gate.py`, carrying which dependency and that the refusal is availability rather than policy
- [ ] T052 [US4] [GATE:conformance] Row in `tests/conformance/mcp/test_degraded_completion.py`: the reachable half completes and is returned, naming the unavailable dependency
- [ ] T053a [P] [US4] [GATE:conformance] Assert in `tests/unit/test_nothing_waits_on_a_human.py` that no path in `src/surfaces/mcp/` or `src/core/dependencies/` notifies, prompts, or blocks on a person (FR-014, SC-008). **Strip comments and docstrings before matching** — these modules discuss waiting on humans at length precisely because they must not do it, and this repository has had four checks match prose instead of code
- [ ] T053 [P] [US4] Assert in `tests/conformance/mcp/test_degraded_completion.py` that the result is **not presented as a completed action** (FR-016). Returning plan output that reads as applied is worse than returning nothing

---

## Phase 8: User Story 5 — The evidence trail is checked while the system is running (P2)

**Goal**: continuous verification, not bring-up verification.

**Independent test**: tamper with a stream while the service runs; assert it is reported
without operator action.

- [ ] T053b [US5] Build a **run-role connection factory** in `src/surfaces/mcp/server.py`, drawing credentials through the `mcp` Vault role (T022a). `verify_stream_integrity(conn_factory, ...)` takes one, and without it T054 has nothing to pass — the fifth instance of this feature's recurring shape, and one the seam table did not list
- [ ] T054 [US5] Run `verify_stream_integrity` (008) periodically from the MCP service in `src/surfaces/mcp/server.py` using T053b's factory, scoped so one pass does not walk an estate's whole history
- [ ] T055 [US5] [GATE:correlation] Surface findings from `src/surfaces/mcp/server.py` (FR-017) where an operator will see them, not only recorded. A finding written to a table nobody reads is the same as no finding
- [ ] T056 [US5] [GATE:conformance] Enclave row in `tests/conformance/mcp/test_continuous_verification.py` (SC-010): tampering is reported with no operator action, **and a clean store reports clean**. The false-positive half matters as much — a check that always fires gets disabled
- [ ] T057 [P] [US5] Update `ROADMAP.md`: continuous evidence-stream verification moves from deferred to shipped

---

## Phase 9: Polish and the record

- [ ] T058 [GATE:conformance] Resolve **ADR-0049** in `docs/adr/0049-*.md` — Accepted, amended, or withdrawn on the evidence of having built it (FR-021, SC-013). It was left Proposed deliberately, until something built it. Leaving it Proposed is a failure of this requirement, not a deferral
- [ ] T058a Record the supersession in `docs/adr/0026-*.md`: its re-consent and human-resolution rules are superseded by ADR-0049, the rest stands. Principle X requires superseding be **recorded, never edited in place**, and an ADR silently outlived by another is exactly the failure that principle names
- [ ] T059 Update `specs/008-northbound-api/contracts/conformance-api.md` and `specs/005-durable-execution/contracts/conformance-durability.md` to say which rows CI now covers and which remain named to a human — fork pull requests only (FR-022). A contract still claiming no automated runner exists is wrong in the direction that makes people trust the gate less than they should
- [ ] T060 [P] Update `AGENTS.md`: the harness gate now applies to fork pull requests and to anything the lane cannot cover, rather than to everything
- [ ] T061 [P] Update `ROADMAP.md`: 009 shipped; the **four-transport parity row moves from Deferred to In force**
- [ ] T062 [P] Record the fifteen rows in `contracts/conformance-mcp.md` as **In force**
- [ ] T063 [GATE:conformance] Run `make check` and `make conformance` against a live enclave, and confirm every break fixture passes on a clean tree. A row whose failure nobody has observed is a row nobody knows works

---

## Dependencies

```text
T001, T002 (premise gates)
  └─> Phase 1 (T003–T005)
        └─> Phase 2 / US6 — the CI lane (T006–T012)   ← protects everything after
              └─> Phase 3 Foundational (T013–T024)
                    ├─> US1 parity (T025–T032)
                    ├─> US3 refusal (T033–T039)
                    │     └─> US2 suspend + sweep (T040–T050, incl. T042a/T042b)
                    ├─> US4 degraded completion (T051–T053a)   [needs US3's classes]
                    └─> US5 continuous verification (T054–T057)
                          └─> Phase 9 (T058–T063)
```

**T002 gates the lane's design.** If the enclave cannot come up on a Linux runner, T006–T012
change shape — possibly to a self-hosted runner, which is a different decision with different
costs.

**T013 → T014 → T015 → T015a → T016 is one landing.** Removing `PARKED` breaks the durability path
until T014, and leaves the constitution describing behaviour that cannot happen until T015.
The tree is red in between; land them together.

**US3 before US2** is a real ordering, not a preference: suspension is what happens when a
run meets a dependency it cannot reach, so the knowing has to exist first.

### Parallel example after Phase 3

```text
# Developer A: US1 parity — the row owed since ADR-0033
# Developer B: US3 refusal, then US2 suspension and sweep
# Developer C: US5 continuous verification
```

---

## Implementation Strategy

### First increment: the CI lane alone (Phases 0–2)

Merge-worthy by itself, and worth merging by itself. It changes nothing about how the
platform behaves and everything about whether a regression can reach `main` unnoticed.

### Then the rest

1. **Foundational** — the sealed-core change and the amendment. Small in code, largest in
   review: it touches 005's durability path and the governing document.
2. **US1** — parity. The headline, and the row this feature exists to claim.
3. **US3 → US2** — refusal, then suspension and sweep. ADR-0049's substance.
4. **US4, US5** — degraded completion and continuous verification.
5. **Phase 9** — resolve ADR-0049 and correct every contract that describes the old gate
   coverage.

### Notes

- **The parity row is claimed here.** 008 refused it because parity is a property between
  transports and there was one. There are two now, and a third refusal would be avoidance.
- **Two changes belong to other features.** `RunState` is 005's and the Quality Gates row is
  the constitution's. Both need security-maintainer review, and neither is this feature's to
  change quietly.
- **When a task says "wire A to B", check that A's interface accepts what B requires.**
  Three findings across 008 and 009 have been the same shape — a dispatcher with no job, a
  sweeper with no resume metadata, a protocol with no resume parameters — and the third
  appeared while fixing the second. The check is mechanical and would have caught all three.
- **The riskiest thing here is not any of the four pieces.** It is the denial-class
  asymmetry: only availability is model-visible. Backwards, it trains agents to route around
  governance boundaries, and every test still passes.
