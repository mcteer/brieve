# Tasks: Northbound API Operations

**Feature**: `specs/011-api-operations` | **Branch**: `spec/011-api-operations`
**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests are required.** Conformance-driven repository; gate rows bind as features land
(ADR-0047).

## Lessons carried forward, because each cost a prior feature something

- **Snapshot-first per operation** (research F6): grow the snapshot, watch the parity row
  fail, add both surfaces, watch it pass. The row is the development loop, not the audit.
- **The fixture must be capable of failing** (010's T009): the stop rows need a run that is
  *still running* when the stop lands, and every existing fixture completes immediately.
  T008 precedes every stop row for this reason.
- **No new conformance directory** (010's double lane gap): rows land in
  `tests/conformance/api/` and `tests/conformance/identity/`, which both runners already
  enumerate. A marker does not run a row that no lane collects.
- **When a task says "wire A to B", verify A accepts what B requires**: the plan's seam
  table found three "no"s in advance (no subject on checkpoints, no stored accessor, no
  `list` capability). Each remedy is a Foundational task below, before anything consumes it.

---

## Phase 1: Setup

- [X] T001 Create `src/core/runs/` — `__init__.py`, `index.py`, `changes.py`, `refusals.py` as SPDX-headed stubs, plus `schema.sql`. The package docstring carries the recorded open question: `suspended_runs` (009) and `run_index` are both "find runs by something other than their id" tables, and whether they converge is deliberately unresolved until something forces it
- [X] T002 [P] Define the operation refusal codes in `src/core/runs/refusals.py` as a frozen mapping on the 010 pattern: `no_such_record`, `outside_tenant`, `not_permitted` (FR-020). The trail records all three distinctly; the caller sees the first two identically — the collapse is the tenant boundary, the trail's distinction is what lets an investigator see probing

---

## Phase 2: Foundational — blocks every user story

- [X] T003 Write `src/core/runs/schema.sql`: `run_index` and `authority_change_requests` per [data-model.md](data-model.md), with a keyset index on `run_index (tenant_id, subject_user_id, created_at, run_id)` — the list operation's exact query shape, so the boundary filter is the access path rather than a post-filter
- [X] T004 [GATE:fail-closed] Apply the runs schema at bring-up in `infra/bin/enclave-up` (the `SET ROLE brieve` pattern, in the same psql pass as the others), **and add REVOKE statements for both tables to the evidence role** in `infra/modules/trust-fabric/database.tf` — the `dependency_health` treatment: operational state in the same database is not evidence, and a SELECT-only credential that can read who started every run has stopped being narrow
- [X] T005 [P] Add `list` capability on the registration path to `harness-authority-read` in `infra/modules/trust-fabric/policies.tf` (research F5 — 010 granted exactly what resolution needed, and enumeration is the second caller). `terraform validate` after
- [X] T006 [GATE:conformance] Write the run index in `src/core/runs/index.py` **as a seam** — a protocol with an in-memory implementation and a Postgres one — and wire it into `dispatch()` in both `src/surfaces/dispatch/nomad.py` and `src/surfaces/dispatch/inprocess.py` as a collaborator defaulting in-memory, in the same motion as the dispatch, from arguments dispatch already receives. **The seam shape is load-bearing, not style** (pass 4): `InProcessDispatcher` is pure in-memory and is what `surface_under_test` builds for every hermetic row, so an unconditional Postgres write would put a database inside the fast lane. The in-memory index then serves the hermetic halves of the list and stop rows for free. Insert-only; nothing updates it; state stays on the checkpoint. This is the closure of the recurring seam finding — the signature already carries subject, tenant, and definition
- [X] T007 Write the change-request record in `src/core/runs/changes.py` — store on 202 (accessor, requester, tenant, mapping, submitted-at) plus the Vault status poll against `sys/control-group/request` through the existing authenticated-read shape. **The record is the authorization, not a cache**: Vault answers anyone presenting an accessor, so the record is what makes collect tenant-scoped instead of a bearer capability
- [ ] T008 [GATE:conformance] Give the dispatched entrypoint a **multi-step mode** in `src/surfaces/dispatch/entrypoint.py` (step count and per-step delay via optional dispatch metadata, declared `meta_optional` in `infra/jobs/agent-run.nomad.hcl` — Nomad rejects undeclared keys, found the hard way in 010). **Each step runs the full 005 bracket** — record the intent, execute, record the result, checkpoint — because a fixture that merely sleeps has no step boundaries for the stop to be observed at and no intents for the zero-open-intents row to count. Pass 1 caught the task that exists to prevent vacuous stop rows specifying a fixture that would produce one. **Blocks every stop row**: the existing fixtures complete immediately, so a stop row against them passes whether the stop works or not
- [X] T009 Extend `infra/bin/enclave-verify`: both new tables exist, the harness role reads them, the evidence role cannot. Both prefixes this time — 010's pass 4 caught the one-of-two omission and the failure mode is a US2 row error naming the wrong thing
- [X] T009a [GATE:conformance] **Extend the app assembly** in `src/surfaces/api/app.py` (and the MCP transport constructor in `src/surfaces/mcp/transport.py`, which mirrors it): the builder accepts a run-index reader, a durability provider, and a change-request store, constructed once from the credentials the environment supplies — the 009/010 assembly pattern. **Pass 2 found every new operation reading through a handle the assembly never constructs**: `app.state` holds five components and none of them can reach the run index, the checkpoints, or the change-request records. Without this task, five stories improvise five wirings of one concern — the mechanism-without-the-thing-it-acts-through pattern, fifth appearance, one layer up: not a missing seam this time but a missing assembly

---

## Phase 3: User Story 1 — collect an authority change's disposition (Priority: P1) 🎯 MVP

**Goal**: the requester learns what happened without being told out of band — the 008
defect closed.

**Independent test**: submit a gated change, approve out of band, observe pending →
approved through the operation alone.

- [X] T010 [US1] Add `GET /claim-mappings/{accessor}` and `collect_mapping_change` to `specs/008-northbound-api/contracts/operations.snapshot.json` **first**, and confirm the parity row fails — red before the surfaces exist, green when both do
- [X] T011 [US1] Write the change-request record from the 202 path in `src/surfaces/api/mappings.py` — the moment `BlockedPendingApprovalError` carries an accessor, it is recorded before it is returned. An accessor returned but unrecorded is 008's defect kept warm
- [X] T012 [US1] [GATE:fail-closed] Implement collect in `src/surfaces/api/mappings.py`: resolve the record by accessor **through the T009a change-request store**, refuse unless the caller is its requester in its tenant (caller sees not-found, trail records `outside_tenant`), then poll Vault. **Pending is an answer, indefinitely** — never presented as failure
- [X] T013 [US1] Add the `collect_mapping_change` tool to `src/surfaces/mcp/operations.py` and `src/surfaces/mcp/transport.py`, calling the same function the route calls — 009's pattern, one core and two front doors
- [ ] T014 [P] [US1] [GATE:conformance] Enclave rows in `tests/conformance/api/test_collect_mapping_change.py` (SC-001), **marked `host_enclave`** — the approve-out-of-band step needs the admin token the allocation deliberately lacks, the same reason `test_claim_mapping_gated.py` carries the marker. Rows: pending → approved with zero out-of-band signals to the requester; another tenant's accessor answers not-found with `outside_tenant` in the trail; pending stays pending across repeated polls with no approver action, never reading as failure
- [ ] T015 [P] [US1] [GATE:conformance] **Break fixture — a collect that authorizes** in `tests/conformance/api/test_collect_mapping_change.py`: call collect as the sole would-be approver N times and assert the change stays pending. The plausible defect is implementing against the wrong member of Vault's request-endpoint family, and this is the only row that would catch it

---

## Phase 4: User Story 2 — list my runs (Priority: P2)

**Goal**: a returning subject enumerates their work with nothing retained from a previous
session.

**Independent test**: three runs by A, one by B; A lists exactly three.

- [X] T016 [US2] Snapshot += `GET /runs` / `list_runs`; parity red, then surfaces
- [X] T017 [US2] [GATE:fail-closed] Implement the list query in `src/core/runs/index.py`: tenant first, subject second, keyset cursor `(created_at, run_id)`, bounded page, **stateless between calls** (FR-005). The cursor is opaque and carries no total — a count is the withholding disclosure FR-004 forbids
- [X] T018 [US2] Add `GET /runs` to `src/surfaces/api/runs.py` (run summaries per [data-model.md](data-model.md) — state joined from the checkpoint **via the T009a provider**, everything else from the **T009a index reader**) and `list_runs` to the MCP surface
- [X] T019 [P] [US2] [GATE:conformance] Enclave rows in `tests/conformance/identity/test_list_runs.py`: mine-and-only-mine across two subjects and two tenants (SC-002, SC-003); bounded pages; empty list for a subject with no runs is an answer, not an error
- [X] T020 [P] [US2] [GATE:conformance] **Break fixture — a cursor that carries the total**: inspect the cursor across pages for anything monotonic with the withheld count. `OFFSET/COUNT` pagination reads identically in the happy path, and this is the row that distinguishes it
- [ ] T021 [P] [US2] [GATE:conformance] **The divergence row** in `tests/conformance/identity/test_index_trail_agree.py` (plan, post-design IX): a dispatched run appears in both the run index and the audit trail. **The two writes are minutes apart on a cold dispatch** — the index at `dispatch()`, `run_start` inside the allocation — so the row waits for the allocation to reach a terminal state before comparing (the 010 end-to-end wait and budget), and says so, because a divergence row that flakes on the window teaches people to re-run the one row whose job is to be believed. Two accounts of what ran; this row is what makes silent disagreement impossible — an investigator who finds them differing must be finding a loud failure, not a quiet drift

---

## Phase 5: User Story 3 — a run's result (Priority: P3)

**Goal**: what a run produced, without the caller reading a single audit entry.

**Independent test**: complete a run with a known result and retrieve it.

- [X] T022 [US3] Snapshot += `GET /runs/{run_id}/result` / `get_run_result`; parity red, then surfaces
- [ ] T023 [US3] **Give the entrypoint terminal checkpointing, then put the result in it**, in `src/surfaces/dispatch/entrypoint.py`: today the entrypoint never calls `checkpoint_run` at all — it starts a run, prints, and exits — so without this task every API-started run reads *not finished* forever and only one arm of FR-007's three-way disposition is reachable. The terminal checkpoint carries a `RunOutcome` and the run's output under the reserved `"__run_result__"` key (research F4). The one place a run's ending is recorded; a second place would eventually disagree with it
- [X] T024 [US3] [GATE:fail-closed] Implement retrieval in `src/surfaces/api/runs.py` + MCP: resolve through the **T009a index reader** (the tenant check), read the terminal checkpoint **via the T009a provider**, compute the **three-way disposition** (FR-007) — no terminal state → not finished; result key → the result; terminal without it → ended without one, with `stop_reason` as the why. Never the raw payload. **Results are returned whole up to a bound; past it the operation refuses with an explicit too-large disposition** — never a silent truncation, which the spec names as worse than a refusal because a partial result presented as complete is acted on
- [X] T025 [P] [US3] [GATE:conformance] Enclave rows in `tests/conformance/identity/test_run_result.py`: all three dispositions distinguishable (SC-005); a stopped run returns disposition and reason, not empty (a run that failed is not a run that returned nothing); another tenant answers not-found; **an over-bound result refuses as too-large with zero bytes of the result attached** — the truncation-as-completion defect has no other row
- [X] T026 [P] [US3] [GATE:conformance] **Break fixture — the checkpoint payload wholesale** in `tests/conformance/identity/test_run_result.py`: assert resume-internal keys are absent from the response. Returning the payload passes every disposition row — the result *is* in there — and makes resume state a compatibility surface, which is the US3 argument one layer down

---

## Phase 6: User Story 4 — stop a run (Priority: P4)

**Goal**: withdrawal, not the pause ADR-0049 removed. Terminal, unilateral, attributable,
and leaving zero open intents.

**Independent test**: stop a multi-step run mid-step; the in-flight step brackets, no next
step begins, the run is terminal, nothing waits on anyone.

- [X] T027 [US4] Snapshot += `POST /runs/{run_id}/stop` / `stop_run`; parity red, then surfaces
- [X] T028 [US4] [GATE:fail-closed] Implement the stop operation in `src/surfaces/api/runs.py` + MCP: verify the caller **started** this run via the **T009a index reader** (FR-010 — its only role here; the index is insert-only per its own contract and the stop does not touch it), then write `run_state = STOPPED`, `stop_reason = stopped_by:<subject>` to the **checkpoint** through the **T009a provider's** `save` — state lives on the checkpoint, which is the whole reason the index could stay insert-only. Stopping a terminal run reports the existing state (FR-011) — asking twice is not an error. The caller returns immediately; nothing waits
- [ ] T029 [US4] [GATE:fail-closed] **Sealed core**: teach the step boundary to observe a durable STOPPED state in `src/core/durability/checkpoint.py` — read the row's state before the next intent is written; if stopped, end after the in-flight step's bracket with no new intent (C3's semantics falling out of placement, not a timeout). **Additive; resume untouched**
- [X] T029a [US4] [GATE:fail-closed] **Sealed core**: make `save` terminal-once in `src/core/durability/postgres.py` — guard `run_state` and `stop_reason` in the upsert with `COALESCE(checkpoints.run_state, EXCLUDED.run_state)`. **Pass 1 found the shipped upsert is last-write-wins**, so a routine checkpoint (which carries `NULL` state) erased a stop and silently resurrected the run, and the stop-versus-finish race went to whoever wrote last. With the guard, a terminal state can never be cleared and the first terminal write wins — the property research originally asserted, now true by construction. Nothing legitimate overwrites a terminal state today (resume refuses terminal runs; suspension rows carry `NULL`), so the guard forbids only the write that was always a defect. **One assumption the guard now depends on, stated so it stays visible**: blob ids are never reused across runs — a fresh run under a previously-stopped blob id could never record its own completion. Dispatch guarantees this by minting fresh ids, and the resurrection fixture uses a fresh id so it tests the guard rather than the assumption
- [X] T030 [P] [US4] [GATE:conformance] Enclave rows in `tests/conformance/identity/test_stop_run.py` against the T008 multi-step fixture: terminal and attributable, distinguishable from a bound (FR-012); **zero intents open after a stop** (FR-008a — a terminal run never resumes, so an open intent would be permanent); only the starter may stop; a second stop is idempotent. **Plus the resurrection fixture**: stop a run mid-flight, let it write a routine checkpoint, and assert the run is still stopped — the row that catches T029a's defect if the COALESCE guard ever simplifies away
- [X] T031 [P] [US4] [GATE:conformance] **The sweeper rows** in `tests/conformance/identity/test_stop_run.py` (FR-009, SC-006): a stopped run is never resumed — asserted against 009's `_is_suspended`, which already refuses terminal checkpoints. Zero new code; the row exists because the property is load-bearing and currently held by two lines nobody may simplify. **Plus the interleaving where stop, suspension, and the sweeper all meet** (pass 4 — a spec sentence with no assertion): stop a **suspended** run, mark its dependency healthy, sweep — nothing resumes, and the `suspended_runs` entry is **forgotten rather than retried**, because a candidate the sweeper keeps re-examining forever is a slow leak wearing a clean pass

---

## Phase 7: User Story 5 — enumerate agent definitions (Priority: P5)

**Goal**: what exists and whether this subject may start it — display fields and a flag,
never the other jurisdiction.

**Independent test**: two subjects, same tenant — same definitions, different `may_start`.

- [ ] T032 [US5] Snapshot += `GET /agent-definitions` and `GET /agent-definitions/{id}` / `list_agent_definitions`, `get_agent_definition`; parity red, then surfaces
- [ ] T033 [US5] Add a `list_path` alongside `read_path` in `src/core/durability/credentials.py` (Vault LIST is a GET with `?list=true`) — the 005 seam widened a second time, same argument as 010's T003: a second class authenticating its own way would be a second path to the trust fabric
- [ ] T034 [US5] [GATE:fail-closed] Implement enumeration in `src/surfaces/api/definitions.py` + MCP: list registrations, read each harness-authority ceiling record, compute `may_start = subject scope ∩ ceiling ≠ ∅` (research F5 — **intersection, not subset**: 002 refuses only requests exceeding scope, and subset would mark startable agents unavailable, inverting C2). The public view is built from the harness-authority record and display fields only — `ceiling_policies` and paths never appear (FR-014)
- [ ] T035 [P] [US5] [GATE:conformance] Enclave rows in `tests/conformance/identity/test_list_definitions.py`: same definitions, different marking for two subjects (SC-008); zero credential-issuance detail in any response, asserted by key inspection (SC-009); a definition removed between enumeration and use refuses `unknown_agent_definition` at start — the 010 behaviour, re-asserted from this path. **And FR-018's arm**: when the subject's scope cannot be resolved, the enumeration **refuses** — never an unmarked or empty list, both of which read as fail-closed and are wrong answers about a person's authority
- [ ] T036 [US5] Record in `specs/011-api-operations/contracts/conformance-operations.md` how FR-013a is satisfied **today**: the registry is one-per-deployment and carries no tenant, so cross-tenant absence is structural rather than filtered. A multi-tenant deployment sharing one registry would disclose definitions across tenants — recorded as a named limit beside the others, because it is the kind of gap that looks closed until someone deploys the topology that opens it

---

## Phase 8: Polish & cross-cutting

- [ ] T037 [GATE:conformance] Extend the verdict half of parity in `tests/conformance/mcp/test_surface_parity.py` (or a driver over `tests/harness/parity.py`): every 011 operation yields the same verdict on both transports, not only the same catalogue entry. The coverage half grows by construction; the verdict half grows only if someone writes it
- [ ] T038 [GATE:conformance] The audited-everywhere row in `tests/conformance/identity/test_operations_audited.py` (FR-017, SC-011): each new operation appears in the trail attributed to the authenticated human, and the refusal shapes record `no_such_record` / `outside_tenant` / `not_permitted` distinctly while the caller-facing collapse holds (FR-020). **And the unauthenticated half of FR-016**: a call to each new operation with no credential refuses, on both transports — 008's structural argument (a route without a subject can do nothing) is strong, and it is an argument rather than a row
- [ ] T039 [P] Update `ROADMAP.md`: 011 shipped — the API/MCP catalogue at ten operations; the portal's remaining precondition is the portal itself
- [ ] T040 [P] Record the rows in `specs/011-api-operations/contracts/conformance-operations.md` as **In force**, and note in `specs/008-northbound-api/contracts/conformance-api.md` that the snapshot grew from four to ten under the same parity row
- [ ] T041 [GATE:conformance] Run `make check` and `make conformance` against a live enclave; confirm every break fixture passes on a clean tree. A row whose failure nobody has observed is a row nobody knows works

---

## Dependencies

```
Phase 1 Setup (T001–T002)
  └─> Phase 2 Foundational (T003–T009a)
        │   [T006 run index blocks US2/US3/US4; T007 blocks US1;
        │    T008 multi-step fixture blocks every stop row;
        │    T005 list capability blocks US5]
        ├─> Phase 3 US1 collect (T010–T015)   🎯 MVP
        ├─> Phase 4 US2 list (T016–T021)
        ├─> Phase 5 US3 result (T022–T026)
        ├─> Phase 6 US4 stop (T027–T031)
        └─> Phase 7 US5 definitions (T032–T036)
              └─> Phase 8 Polish (T037–T041)
```

**The stories are genuinely independent of each other** — no story reads another's tables
or operations, and each is provable alone once Foundational lands. The only cross-story
ordering is inside Phase 8: T037's verdict parity needs all six operations to exist.

**Snapshot-first discipline within each story**: the first task of every story grows the
snapshot and confirms the parity row goes red. A story whose snapshot task is done and
whose surfaces are not is a red build *by design* — do not interleave stories mid-way, or
two red causes become indistinguishable.

## Parallel opportunities

- **Phase 2**: T005 (Terraform) beside T003/T004 (schema); T007 beside T006
- **Each story**: the row tasks ([P]) parallel each other once the surfaces exist
- **Across stories**: US1–US5 may proceed in parallel after Foundational, subject to the
  snapshot-first note above — parallel stories mean parallel red parity states, which is
  workable for one developer only if committed story-by-story
- **Phase 8**: T039/T040 are documentation in different files

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3** — the collect operation, which closes the only gap
that is a defect rather than an absence. It exercises both new records' pattern (the
change-request record directly, the index write incidentally via T006) and lands the
snapshot-first loop before the bulkier stories repeat it.

**Then in priority order.** US4 (stop) carries the sealed-core change and the most
delicate semantics; it benefits from the multi-step fixture having been exercised by
US2/US3 rows first, but does not require it.

## Task count

**43 tasks** — 2 setup, 8 foundational, 6 US1, 6 US2, 5 US3, 6 US4, 5 US5, 5 polish.

Two were added by analyze passes, each with a code-verified finding behind it. Pass 1 read
`save()`'s SQL and found the research asserting the opposite — last-write-wins, so a
routine checkpoint would have erased a stop and resurrected the run (T029a). Pass 2 read
`app.py`'s assembly and found every new operation consuming handles it never constructs
(T009a) — the recurring pattern at a layer no pass had inspected before.
