# Tasks: The MCP surface gets a server

**Input**: Design documents from `/specs/019-mcp-server/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required. The spec asks for conformance rows driven through the **served process** (FR-004, FR-016), and that is the whole point of the feature — fifty-six rows already exercise the class.

**Organization**: By user story, so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 from [spec.md](./spec.md)

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — identity and refusal paths | T009, T021, T027 |
| **Conformance** | **Yes** — a transport surface | Phases 3–6 entirely |
| **Correlation / evidence** | **Yes** — operations join a run's trail | **T028a** |
| **No-secret-leak** | **Yes** — the server handles bearer credentials | T031 |
| **Eval** | **No** | Promotes no pack, model, or policy. Principle VIII is N/A, as recorded in the plan's Constitution Check. |

---

## Phase 1: Setup

- [X] T001 Create `tests/conformance/mcp_served/__init__.py` — the directory only, no rows yet.

  **Deliberately NOT the `host_enclave` pytest line in `Makefile`**, which is where an earlier draft of this task sent it. These rows need the served process standing; 017's `tests/conformance/deployment` is likewise absent from that line and runs through `infra/bin/deployment-conformance`, which brings its surfaces up first. Rows on the pytest line would execute against nothing and fail. The lane wiring lives in T015, and it must land before T016 adds the first `test_*.py` — that is when `tests/unit/test_every_conformance_directory_is_run.py` starts checking this directory, since it only considers directories that contain rows.
- [X] T002 Record the per-directory `pytest --collect-only -q` counts from `main` in `specs/019-mcp-server/contracts/conformance.md`, as the baseline SC-007 compares against.
- [X] T003 [P] Record in `specs/019-mcp-server/research.md` which server and client APIs `mcp==1.28.1` actually provides, and confirm it resolves — the SDK is a declared dependency that nothing has ever imported, so its surface is unverified in this repository.

---

## Phase 2: Foundational — blocking prerequisites

**Everything in Phases 3–6 depends on this phase. Nothing here is optional.**

### The address problem, solved before it is discovered

Today's portal fix cost three deploy cycles to learn this. It is a task now rather than a surprise.

- [X] T004 Read the database host from the environment in `src/surfaces/mcp/served.py` and **pass it at construction** to the durability provider, the audit sink, the audit query, and the dependency store.

  **Not a core change, and the first draft of this task got that wrong.** All four already accept `host` as a keyword argument — `src/surfaces/api/service.py` passes one on line 184 — so the seam exists and is merely unused from an assembly. An earlier version of this task proposed editing the four `src/core/` modules, which would have made the plan's Principle V verdict ("the core is untouched") false, and Principle V names *audit schema* and *durability* as sealed core requiring security-maintainer review. Analysis pass 1 caught it. **The default stays `127.0.0.1`** so nothing outside an allocation changes, which is the pattern `surfaces/mcp/server.py` documents for `NOMAD_ADDR`.
- [X] T005 Verify from inside a **bridge-mode** container which address reaches the trust store, the database, and the scheduler, and record each in `research.md`. **`host.docker.internal` is not automatically the answer**: measured 2026-07-31 it resolves to Docker Desktop's macOS-facing address, which reaches services *published to macOS* (the trust store, the databases) and **not** services in host mode (the API). Getting this wrong produces a service that starts and reaches nothing.
- [X] T006 Verify the trust store's certificate covers the name chosen in T005, against the SANs declared in `infra/modules/trust-fabric/pki.tf`. Its SANs are `localhost`, `host.docker.internal`, and `127.0.0.1` — a name outside that set fails verification while working perfectly from an operator's shell, which is the confusing half.

### The server itself

- [X] T007 Create `src/surfaces/mcp/served.py` with the protocol server: handshake, operation listing, and operation dispatch into `McpTransport` (FR-001).
- [X] T008 Implement the assembly in `served.py` — construct `McpTransport` with the **real** collaborators the API constructs, no in-memory or test doubles (FR-002). Mirror `src/surfaces/api/service.py`'s `build()`; it is the only other assembly of this kind in the tree.
- [X] T009 [GATE:fail-closed] In `src/surfaces/mcp/served.py`, make the process **refuse to start** when it cannot obtain what it needs, naming the missing thing (FR-003). A surface that starts degraded and accepts connections while unable to record evidence is worse than one plainly down.
- [X] T010 Add `infra/jobs/mcp-surface.nomad.hcl` — **bridge mode with a mapped port**, copying `postgres.nomad.hcl`'s shape rather than the API's host-mode jobspec. Born reachable; see [research.md](./research.md) F1.
- [X] T011 Add `infra/bin/mcp-surface-up` **and the `mcp-surface-up` target in `Makefile` that invokes it** — [quickstart.md](./quickstart.md) documents `make mcp-surface-up` as step 1, and FR-015 requires someone connect by following those instructions without reading source, so a script with no target makes step 1 fail. Have it read Vault's coordinates through the script's own `.env` reader with `enclave-up`'s defaults as fallbacks. `enclave-up` writes `VAULT_ROOT_TOKEN` to `.env` but only *exports* the address and CA path — reading all three from `.env` works locally and fails in CI, which is a defect that shipped in `portal-up` and was caught only by running it against a deliberately minimal `.env`.
- [X] T012 Declare `mcp-surface` a deployment subject via the `meta` block in `infra/jobs/mcp-surface.nomad.hcl` — `harness_surface`, `harness_shape`, `harness_covered_by` — which is what `tests/conformance/deployment/surfaces.py` enumerates, so it is a declared surface rather than an unenrolled one (017's rule: coverage a process opts into is fail-open).

---

## Phase 3: US1 — a client attaches and the platform answers (P1)

**Goal**: an unmodified client completes the handshake and enumerates operations.

**Independent test**: attach the SDK's client to the running platform; the session establishes and the operation set comes back.

- [ ] T013 [US1] Create `tests/conformance/mcp_served/surfaces.py` — bringing up, addressing, and reaching the served process, on the model of `tests/conformance/deployment/surfaces.py`.
- [ ] T014 [US1] Create `tests/conformance/mcp_served/conftest.py` with the lifecycle fixtures and the `enclave`/`host_enclave` markers.
- [ ] T015 [US1] Add `infra/bin/mcp-surface-conformance` — bring up, mark ownership in the job's `Meta`, run, tear down — and call it from `Makefile`'s `conformance` recipe. 017's lifecycle, including the mark that distinguishes a lane-started surface from a developer's own.

  **This is the lane wiring, and it must land before T016.** The moment a `test_*.py` exists in that directory, `tests/unit/test_every_conformance_directory_is_run.py` requires a lane that both names it and selects its markers — which is what stops the 018 repeat, and which is why this cannot be left to Polish.
- [ ] T016 [P] [US1] Add `test_a_client_establishes_a_session` in `tests/conformance/mcp_served/test_a_client_reaches_the_surface.py` — the SDK's own client, against the running process (FR-001, SC-001).
- [ ] T017 [P] [US1] Add `test_the_operation_set_matches_the_other_surface` in `tests/conformance/mcp_served/test_a_client_reaches_the_surface.py`, compared **mechanically** against `specs/008-northbound-api/contracts/operations.snapshot.json` (FR-008, SC-002).
- [ ] T018 [US1] Add `test_the_served_process_is_assembled_from_real_parts` in `tests/conformance/mcp_served/test_the_assembly_is_real.py` (FR-002, FR-004) — **against the running process**, because assembly is the one path no unit test covers and the reason this feature exists.
- [ ] T018a [US1] Add `test_no_row_here_constructs_the_transport` in `tests/conformance/mcp_served/test_the_assembly_is_real.py` (FR-016) — assert by source inspection that no module in this directory instantiates `McpTransport` directly.

  **Without this, FR-016 is a sentence rather than a gate.** A row added later that constructs the transport in a fixture would pass, assert what fifty-six existing rows already assert, and be indistinguishable from one driving the served process — which is the exact defect this feature exists to close, reintroduced inside the fix. 018 needed the same shape for the same reason.

---

## Phase 4: US2 — the call is governed, and the refusal comes from the core (P1)

**Goal**: every operation passes through the governed core; a refusal is the core's.

**Independent test**: call an operation that must be refused and one that must not; confirm both outcomes and where the refusal originated.

- [X] T019 [US2] Route every operation through `McpTransport` in `src/surfaces/mcp/served.py`, with no protocol-layer path reaching a capability directly (FR-005).
- [ ] T020 [US2] Map the core's outcomes onto protocol responses in `served.py` so **refused**, **unknown operation**, **malformed request**, and **transport failure** are four distinguishable answers (FR-007). The fourth was missing: FR-007 names four and an earlier `data-model.md` table listed three, so a requirement and its edge case would have gone unimplemented behind a task that looked complete. Collapsing them tells a caller which operations exist by which error they get, and tells an honest caller nothing.
- [ ] T021 [GATE:fail-closed] [US2] Assert in `tests/conformance/mcp_served/test_the_refusal_is_the_cores.py` that the protocol layer **authors no refusals** — it may report the core's decision and never make one (FR-006).
- [ ] T022 [P] [US2] Add `test_an_operation_is_governed` in `tests/conformance/mcp_served/test_the_refusal_is_the_cores.py` (FR-005).
- [ ] T023 [US2] Add `test_a_refusal_comes_from_the_core` in `tests/conformance/mcp_served/test_the_refusal_is_the_cores.py` (FR-006, SC-005). **Design this row for the trap 018 hit**: a protocol layer refusing on its own produces an outcome identical to the core refusing, so the row must distinguish *where* the refusal came from and not merely that one occurred.
- [ ] T024 [P] [US2] Add `test_four_failures_are_distinguishable` in `tests/conformance/mcp_served/test_the_refusal_is_the_cores.py` (FR-007), including **malformed input rejected at the boundary before any governed operation is entered**, with a message naming what was wrong.

---

## Phase 5: US3 — the trail names the caller, not the server (P1)

**Goal**: every operation executes as the calling user, and the evidence proves it.

**Independent test**: two callers perform the same operation; the trail distinguishes them.

- [X] T025 [US3] Carry the caller's credential across the protocol boundary in `src/surfaces/mcp/served.py` and resolve it through the API's existing federated verification (`src/surfaces/api/verification.py`). **Reuse, never rebuild** — a second path to a subject is a second place for the subject to be wrong, and that failure is silent by construction (FR-009).
- [X] T026 [US3] Bind exactly one subject per session, fixed at the handshake, in `served.py` (FR-013a). The subject comes from the session and **never from the request** — a client-supplied subject is an impersonation surface.
- [X] T027 [GATE:fail-closed] [US3] Refuse an operation whose credential is no longer valid, **without changing or clearing the session's subject** (FR-013). See the state diagram in [data-model.md](./data-model.md): both arrows leave ESTABLISHED and the subject never moves on either. The misreading this guards — *verified at the handshake* rather than *fixed at the handshake* — produces a session that outlives its credential.
- [ ] T028 [US3] Add `test_the_trail_names_the_caller` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` (FR-009, FR-010, SC-003).
- [ ] T028a [GATE:correlation] [US3] Add `test_a_correlation_id_propagates` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` — a correlation ID supplied by the client reaches the trail, and the audit join is walkable from it.

  **The gate table claimed this was covered by T028 and T030, and it was not.** Both are identity assertions; neither touches correlation. `start_run` accepts a `correlation_id`, so the gate genuinely applies rather than being boilerplate. Found by analysis pass 3 — **a gate table that certifies itself is the exact shape this feature exists to eliminate**, and it survived two passes because nominal FR coverage cannot see it.

- [ ] T029 [US3] Add `test_two_callers_are_distinguishable` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` (FR-011, SC-004). **Not "a subject was recorded"** — that passes perfectly against a shared account, which is the defect this row exists to catch. Two callers, two records, neither the server's.
- [ ] T030 [P] [US3] Add `test_a_lapsed_credential_stops_authorizing` and `test_a_session_binds_to_one_subject` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` (FR-013, FR-013a).
- [ ] T031 [GATE:no-secret-leak] [US3] Assert in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` that no bearer credential appears in logs, audit entries, or error messages. The server now handles caller tokens, which nothing on this surface did before.
- [ ] T032 [P] [US3] Add `test_no_credential_is_refused_before_the_operation` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` (FR-012).
- [ ] T032a [P] [US3] Add `test_two_sessions_share_nothing` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` — two clients connected at once, neither seeing the other's session, subject, or results. **FR-013a binds one subject per session, which makes cross-session leakage precisely the failure that would be silent**: every operation would still succeed and the trail would still name *a* caller.
- [ ] T032b [P] [US3] Add `test_a_disconnect_leaves_the_operation_governed` in `tests/conformance/mcp_served/test_the_caller_is_the_subject.py` — an operation in flight when the client drops stays governed and recorded. A dropped connection must not be a way to leave an operation half-recorded, which would put a gap in a hash-chained trail.

---

## Phase 6: US4 — reachable from where a person actually works (P2)

**Goal**: a client on the developer's own machine connects.

**Independent test**: connect from macOS, outside the platform's network.

- [ ] T033 [US4] Add `test_it_is_reachable_from_outside_the_platform_network` in `tests/conformance/mcp_served/test_it_is_reachable.py` (FR-014). **Not SC-006** — an earlier draft tagged it so, and this row proves network reachability from where the lane runs, which is a different claim from *a person followed the instructions and succeeded*. Nominal coverage counted it and hid the gap; see T034a. **Record its limit in the contract**: this proves reachability *from where the lane runs*, and if the lane ever moves somewhere sharing a network namespace with the platform, the row keeps passing and stops meaning anything.
- [ ] T034 [US4] Write the client setup instructions in `docs/development/connecting-a-client.md` — address, credential, configuration — such that someone connects from nothing without reading source (FR-015). Put the honest limit here too: this is one of the two places a reader arrives from, and a limit recorded only where nobody lands is not recorded (FR-018).
- [ ] T034a [US4] **After T034**, perform SC-006 and FR-015 as a **documented act** and record it in `specs/019-mcp-server/contracts/conformance.md`: a person follows `docs/development/connecting-a-client.md` from nothing, connects a client, and records what happened — including anything they had to read source to discover, because that is the criterion failing.

  **The constitution requires this to have a name.** "A blocking row that no automated check executes MUST have a named party responsible for running it before merge." SC-006 and FR-015 are human-judgement criteria; no row can evaluate them. The plan's "no named human runner is owed" is true of the rows and false of these two, which is the same distinction the contract already draws for FR-017's demonstration and had not applied here. Analysis pass 5 found it — SC-006 was tagged onto T033, which proves reachability rather than followability, so nominal coverage read 100% while nothing evaluated it.

- [ ] T035 [P] [US4] Add `test_neither_process_takes_the_other_down` in `tests/conformance/mcp_served/test_it_is_reachable.py` (FR-015a, SC-008) — stop each, the other keeps serving.

---

## Phase 7: Polish & cross-cutting

- [ ] T036 **Do not rename the `mcp` job.** Record in `infra/jobs/mcp.nomad.hcl` that it runs the supervisory loop rather than the surface it is named for, and enumerate what a future rename must update.

  **An earlier draft of this task renamed it**, describing the cost as stopping a running job and updating the deployment lane's subject list. Analysis pass 3 found the actual blast radius: `infra/modules/trust-fabric/variables.tf` defaults the bound job name to `mcp` and `auth.tf` defines `vault_jwt_auth_backend_role "mcp"`, so **the allocation's workload identity binds on that name** — renaming without re-binding leaves the supervisory loop unable to authenticate, which is the defect shape the API already paid for once. `tests/conformance/durability/test_dispatched_suspension_cycle.py` also hardcodes `nomad job status mcp`.

  A task whose stated cost is "stop the old job" and whose real cost includes re-binding a Vault auth role is worse than one that is missing, because it reads as safe. If the name is worth changing it deserves its own change with these bindings enumerated — not a line in a Polish phase.
- [ ] T037 [P] Add `test_the_contract_states_what_this_gate_does_not_assert` in `tests/conformance/mcp_served/test_it_is_reachable.py` (FR-018) — checked rather than trusted, because a later edit could remove the statement and let a green row imply more than it asserts.
- [ ] T038 Update `specs/019-mcp-server/contracts/conformance.md` — replace the provisional row table with the rows as shipped, and record the SC-007 counts against T002's baseline.
- [ ] T039 [P] Close ROADMAP gap 0f in `ROADMAP.md`, and update the surface-parity row: parity now binds between two **served** surfaces rather than between one service and one class.
- [ ] T040 Perform the FR-017 demonstration by hand against a local enclave and record it in `contracts/conformance.md` with its output: the credential used, the client's own refusal, and evidence the refusal originated in the core. **Never in a lane** — an act whose point is that a person watched it happen is not improved by automating the watching.
- [ ] T041 Run the gates defined in `Makefile` — `make check`, `make conformance-hermetic`, and the full `make conformance`; compare per-directory collection counts against T002's baseline (SC-007). The total rises because this feature adds rows, so only the pre-existing directories are the comparison.

---

## Dependencies

```
Phase 1 (Setup)
   ↓
Phase 2 (Foundational) ── blocks everything below
   ↓
Phase 3 (US1) ──┐
   ↓            │  US2 and US3 both need a served process to talk to,
Phase 4 (US2)   │  so US1 is genuinely first rather than merely P1.
Phase 5 (US3)   │
Phase 6 (US4) ──┘  Independent of US2/US3 once Phase 2 lands.
   ↓
Phase 7 (Polish)
```

**Story independence, honestly stated.** US2, US3, and US4 are independently *testable* but not independently *deliverable* — each needs the server from US1 to exist. US4 is the one that could genuinely ship alone if the server existed, which is why it is P2 rather than P1: valuable, and not what makes the surface correct.

---

## Parallel opportunities

- **T003** runs alongside T001–T002.
- **Within Phase 2**: T004 and T005/T006 are independent (code versus measurement).
- **Within US1**: T016 and T017 are different assertions in one module, written in parallel once T013–T015 land. T018a is independent of both.
- **Within US2**: T022 and T024 alongside T023.
- **Within US3**: T028a, T030, T032, T032a and T032b alongside T028–T029.
- **Within US4**: T033 and T035 are independent; **T034a is not** — it follows T034, because a person cannot follow instructions that have not been written. An earlier draft placed it first.
- **Phase 7**: T037 and T039 are independent of everything else remaining.

---

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3 (US1).** That is a served surface an unmodified client can reach and enumerate — the thing that has never existed. It is not yet *proven* governed, which is why US2 and US3 are also P1 and are not optional.

**Do not stop at the MVP.** A served surface without US2 and US3 is the dangerous intermediate state: it looks like the platform working while nothing has confirmed that reaching the platform through this door is not a way around it, and every pre-existing row would still pass.

**T015 must land before T016, for a mechanical reason** rather than a stylistic one. The
lane-membership check fails on a conformance directory that contains rows and that no lane both
names and selects the markers of — so the first `test_*.py` written before the lane exists turns
the suite red. That is the check working: 018 shipped twelve rows nothing collected, and this is
what stops the next one.

**An earlier draft put that obligation on T001 and pointed it at the wrong lane** — the
`host_enclave` pytest line, where the rows would have run with no served process standing.
017's deployment rows are absent from that line for exactly this reason. Analysis pass 1 caught
it; the ordering constraint is real, it simply belongs one task later and to a different lane.

## Notes

- **Eval gates are N/A**: this promotes no pack, model, or policy.
- **No ADR is needed.** ADR-0033 and ADR-0048 already decided this; the feature builds what they decided.
- **The honest limit appears in two places** (T034, T037) and is asserted by a row rather than trusted: a served, governed, recorded surface does **not** mean a model is choosing anything. The tool selection behind a dispatched run is still a scripted round-robin (ROADMAP gap 0e), and the demonstration will feel like more than it is.
