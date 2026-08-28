# Tasks: A run's write grant names only its own workspace

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md),
[contracts/conformance-run-scoped-write.md](contracts/conformance-run-scoped-write.md),
[quickstart.md](quickstart.md)

**Tests**: Included and mandatory. The defect was demonstrated live, so the fix is credible on
the same terms — contract rows E1–E10 are **enclave** rows and A1–A10 are hermetic. A row that
cannot lose has not been tested (ADR-0047).

**Organization**: By user story, with **one gate before everything** — see below. Named
contracts bind exactly: `RunWorkspace`, `ScopedWriteGrant`, `RecordedScope`, `derive_workspace`,
`manufacture_grant`, `remint_grant`. Do not substitute a near-equivalent name.

## THE GATE — T003 decides what this feature costs

`R2` is not a research note, it is the first task. **Does Nomad 2.0.4's workload identity JWT
carry a per-allocation claim that `user_claim` can point at?**

- **Yes** → Branch A. A changed `user_claim`, a templated policy, no minting. Phase 3A. ← **taken**
- ~~**No** → Branch B. 016's resource-server substrate.~~ **Not taken.**

FR-009 existed to stop the substrate being adopted before the cheap path was ruled out. It was
not ruled out — it works — which is the outcome that requirement made possible.

Phases 1, 2, 4, 5 and 6 are identical either way. The contract rows are deliberately
mechanism-independent, so only Phase 3 branches.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T033–T037 — manufacture failure, renewal failure, and the absence of any fallback. Three distinct reasons, none proceeding and none reported as another |
| **Conformance** | T025–T032 (rows E1–E10, live), T012–T014 and T019–T021 (rows A1–A10, hermetic) |
| **Correlation / evidence** | T010, T038 — the recorded scope is what FR-011 answers from, joinable on the run |
| **No-secret-leak** | T017a / T018b — a grant names paths and capabilities; no credential material reaches the record |

## Path Conventions

Single project: `src/`, `tests/`, `infra/`, `packs/`, `specs/` at repository root.

---

## Phase 1: Setup and the gate

- [ ] T001 Reproduce the defect and record the baseline in `specs/054-run-scoped-write-grant/quickstart.md` §1 — the three actions that returned 200/200/204 on 2026-08-27, so rows E1–E3 have a documented "before". Clean up every policy seeded
- [ ] T002 [P] Confirm R1 against the enclave: enumerate `identity/entity-alias/id` and record that all dispatched runs share one alias. If this has changed, [research.md](research.md) R1 is stale and the whole plan must be re-derived before proceeding
- [X] T003 **THE GATE — answered 2026-08-27: yes.** Determine whether Nomad 2.0.4's workload identity JWT carries a per-allocation claim, and whether `user_claim` in `infra/modules/trust-fabric/auth.tf` may point at it without breaking the `bound_claims` glob that exists because the identity presents the parent job id
- [X] T004 Record T003's answer in [research.md](research.md) R2 with the evidence, choose Branch A or B (**SC-006** — the rejected alternative recorded with what ruled it out), and **strike the branch not taken from this file** so a reader sees which was chosen and why rather than two live plans
- [X] T005 **Done — see [research.md](research.md) R2a.** One entity per run, permanent; Nomad GCs its allocations and Vault does not. Accepted with a follow-up owed
- [ ] T006 [P] Confirm the `b7c2a2f` guard is present and passing before anything below changes authority — FR-007 keeps it, and this feature must not be credited with a refusal that guard is producing

**Checkpoint**: the mechanism is chosen on evidence and written down.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Blocks every user story, identical under both branches.**

- [ ] T007 Create `RunWorkspace` per [data-model.md](data-model.md) in `src/core/authority/workspace.py` — `run_id`, expanded `paths`, `capabilities`
- [ ] T008 Implement `derive_workspace(run_id, declared_paths)` in `src/core/authority/workspace.py`, expanding the per-run form of the manifest declaration into concrete paths (FR-010)
- [ ] T009 Add the per-run token to the manifest's `paths` declaration in `src/core/packs/manifest.py` and `packs/vault/pack.toml`, so `vault_policy_impact` declares `scratch-agent-{run_id}-*` rather than the estate-wide wildcard ([R4](research.md))
- [ ] T010 Create `RecordedScope` in `src/core/authority/workspace.py` — `run_id`, `paths`, `derived_from` — for **FR-011 only**. It is a record an auditor reads, never a control the runtime consults ([R5](research.md))
- [ ] T011 **Assert the absence of a mechanism** (FR-017): no code path derives, stores or re-presents write scope. Vault evaluates it from the caller's identity per request, so `remint_grant` is not built — [R5](research.md) is superseded by [R2](research.md)
- [ ] T011a Build the row harness that obtains authority through the **real login path** a dispatched run uses, in `tests/conformance/authority/run_authority.py`. **Not `auth/token/create`**: a token minted from policy names has `entity_id: ""`, and under Branch A a templated policy then refuses everything including the run's own workspace — E1–E3 would pass while asserting nothing. Analysis caught this; measured 2026-08-27
- [ ] T012 [P] Row A10 in `tests/unit/test_run_workspace.py` — no derived workspace contains a wildcard. **The row to keep if any are cut**: one surviving `*` passes every other row and grants exactly what this feature removes
- [ ] T013 [P] Row A9 in `tests/unit/test_run_workspace.py` — the workspace derives from the manifest declaration, so a second place to say what a tool touches cannot appear
- [ ] T013a [P] Row A8 in `tests/unit/test_write_grant_gating.py` — the `run_id_forged` guard still refuses (FR-007). **In Foundational, not Polish**: it brackets with T006, so a break anywhere in Phases 3–5 fails immediately rather than at the end
- [ ] T014 [P] Rows A3 and A4 in `tests/unit/test_remint_stability.py` (**SC-009**) — asserted as an absence: no module derives or stores write scope, so a widened re-mint is unrepresentable rather than refused. The maintainer's hazard is closed by construction

**Checkpoint**: a run's workspace can be derived, recorded, and re-presented without drift.

---

## Phase 3A: User Story 1 — the grant is scoped *(Priority: P1, if T003 answers YES)* 🎯 MVP

**Goal**: A run's write authority names only its own workspace, via a per-allocation identity.

**Independent test**, without Phase 4: the workspace derives with no wildcard (A10), a re-mint
reproduces it (A3/A4), renewal follows the run's life (T022a), and a run with no declared write
path gets no grant (A1). The live refusal is US2's — a story whose only test lives in another
story cannot ship on its own.

- [ ] T015a [US1] Point `user_claim` at the per-allocation claim for the `agent_run` role in `infra/modules/trust-fabric/auth.tf`, keeping the `bound_claims` glob intact
- [ ] T016a [US1] Map the per-allocation claim into alias metadata via `claim_mappings` in the same role, so a templated policy can reach it
- [ ] T017a [US1] Replace the estate-wide grant in `infra/modules/trust-fabric/scratch.tf` with a templated policy naming only the calling run's workspace (**FR-001**). No credential material may reach the recorded scope
- [ ] T018a [US1] Confirm the ceiling still attaches as before — `token_policies` is role-level and must not become entity-dependent when the entity becomes per-run

## ~~Phase 3B~~ — NOT TAKEN (T003 answered yes)

*Struck rather than deleted: a reader asking "why not the substrate?" gets the answer here
instead of finding the question unaddressed. See [research.md](research.md) R3.*

**Goal**: The same, via authority manufactured per run and reached under the run's own identity.

- [x] ~~T015b~~ [US1] *(struck)*  Re-derive the resource-server substrate against **current** main from `specs/016-task-scoped-authority/research.md` — the archive tag is ~36,000 lines behind across 251 files and must not be merged
- [x] ~~T016b~~ [US1] *(struck)*  Carry the findings that cost the most: `jti` mandatory and silent in Vault's server log while the caller sees a bare 403; `use_jwks` defaulting true so static keys need it false; the entity alias carrying `external_id` and `issuer` that the typed Terraform resource cannot express
- [x] ~~T017b~~ [US1] *(struck)*  Implement `manufacture_grant` so the run reaches its grant under its **own** attested identity. A credential handed to the allocation is closed by ADR-0058 ([R3](research.md)); no credential material may reach the recorded scope
- [x] ~~T018b~~ [US1] *(struck)*  Replace the estate-wide grant in `infra/modules/trust-fabric/scratch.tf` with the manufactured per-run grant (**FR-001**)

### Both branches

- [ ] T019 [US1] Gate manufacture on the run's requested tools declaring a write path (FR-012), decided at run start rather than from what the model later calls (FR-013)
- [ ] T020 [P] [US1] Row A1 in `tests/unit/test_write_grant_gating.py` (**SC-007**) — a run declaring no write path is manufactured no write grant at all
- [ ] T021 [P] [US1] Row A2 in `tests/unit/test_write_grant_gating.py` — the decision reads requested tools, so authority never depends on model behaviour mid-run
- [ ] T022 [US1] Implement renewal while the run is alive, stopping when it is not (FR-014)
- [ ] T022a [P] [US1] Hermetic renewal row in `tests/unit/test_grant_renewal.py` — a grant renews while its run is alive and stops when it is not (FR-014). US1 must be verifiable inside its own phase; E9 confirms the same property live in Phase 4
- [ ] T023 [US1] Confirm the sweeper's grant is untouched (FR-008) — `scratch_sweep` lists the namespace by design and `scratch_policy_check` carries no `list`
- [ ] T024 [US1] Confirm no read path a run could reach before is refused after (FR-006). ADR-0057's argument is untouched and must not be narrowed by accident

**Checkpoint**: US1 is independently verifiable by its own hermetic rows. US2 then shows the estate agrees.

---

## Phase 4: User Story 2 — the bound is shown to refuse (Priority: P2)

**Goal**: The refusal is a recorded answer from the live control plane, not a reading of HCL.

**Independent test**: each row makes a real attempt under a real run's authority. It fails if
the attempt succeeds, and it fails if the attempt cannot be made.

- [ ] T025 [US2] Row E1 in `tests/conformance/authority/test_run_scoped_write.py` — **read** on another run's workspace is refused, live (**FR-003**, **SC-001**)
- [ ] T026 [P] [US2] Row E2 — **write** refused, live
- [ ] T027 [P] [US2] Row E3 — **delete** refused, live. E1–E3 replay the exact actions that returned 200/200/204
- [ ] T028 [US2] Row E4 (**SC-002**) — the same authority **succeeds** on its own workspace. Not optional: a grant that reaches nothing refuses everything and would satisfy E1–E3 while breaking the product
- [ ] T029 [US2] Row E5 (**FR-004**, **SC-003**) — removing the narrowing makes E1–E3 pass again, so the refusal is attributable to this feature
- [ ] T030 [US2] Row E8 (**FR-002**) — the refusal holds **with the `run_id_forged` guard disabled**, proving the bound is Vault's answer rather than the hook. This is 042's stated reason for the ACL layer
- [ ] T031 [P] [US2] Rows E6 and E7 (**SC-005**) — a read a run could make before is still permitted; the sweeper still lists the namespace
- [ ] T032 [US2] Rows E9 and E10 — a Build outlasting one credential lifetime completes its measurement and an ended run stops renewing (SC-008); a **restarted** run gets a workspace only it can reach, and does **not** reach the previous attempt's (FR-016, reversed 2026-08-27)

**Checkpoint**: an auditor gets a recorded refusal rather than an argument.

---

## Phase 5: User Story 3 — a failure to manufacture stops the run (Priority: P3)

- [ ] T033 [US3] Stop the run with a distinct recorded reason when manufacture fails (FR-005), in `src/surfaces/dispatch/`
- [ ] T034 [US3] Handle a failed **renewal** the same way, leaving no half-written measurement (FR-015)
- [ ] T035 [P] [US3] Rows A5 and A6 in `tests/unit/test_grant_failure.py` (**SC-004**) — each failure stops the run with its own reason, and neither is reported as the other
- [ ] T036 [P] [US3] Row A7 — there is no wider authority to fall back to. The estate-wide grant must not be retained "just in case"
- [ ] T037 [US3] Confirm the record distinguishes "the measurement did not happen" from "the measurement found no change" — a reader must not read one as the other

**Checkpoint**: the honest consequence is real and recorded — a Build that cannot be granted a scoped credential stops.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T038 Confirm FR-011 end to end — an auditor can say what a finished run's authority actually granted, from the recorded scope
- [ ] T040 Update issue #226: close the structural half, or say precisely what remains. It was reopened once already because a PR closed it while the grant was unchanged
- [ ] T041 Add the 054 row to `ROADMAP.md`'s shipped table, naming ADR-0057's fired trigger and which branch T003 chose
- [ ] T042 Fill `contracts/conformance-run-scoped-write.md` §4 with the E1–E10 named-runner record
- [ ] T043 **Request security-maintainer review**, asking specifically whether the derived workspace can be induced to widen — that failure leaves every row in this feature green
- [ ] T044 Run `make check` — hermetic rows A1–A10
- [ ] T045 Run `make conformance` — the live rows E1–E10, exit 0

---

## Dependencies

```
Phase 1 (T001–T006)
  │  T003 is the GATE. T004 records the answer and strikes a branch.
  │  T001 must run BEFORE any narrowing, or E1–E3 have no documented "before".
  ▼
Phase 2 (T007–T014)   derivation, recording, re-mint stability — both branches
  ▼
Phase 3A (T015a–T018a) OR 3B (T015b–T018b) ──► converge at T019–T024
  ▼
Phase 4 (T025–T032)   needs a scoped grant to exist to refuse anything
  ▼
Phase 5 (T033–T037)   independent of Phase 4; may run alongside it
  ▼
Phase 6 (T038–T045)
```

**Parallel opportunities**: T002/T006 in Phase 1. T012–T014 are three different files. T026/T027
alongside T025. T031 is independent of the refusal rows. T035/T036 in Phase 5.

**Not parallel, and worth stating**: every Phase 4 row shares one live enclave. Running them
concurrently against the same control plane is how a row starts passing because another row
left a policy behind.

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3 (whichever branch).** That is the story that makes
Principle IV true for the one write capability a run holds.

**Phase 4 is not deferrable past the same change.** The defect was credible because it was
demonstrated; a fix shipped without the live rows asks a reader to take the narrowing on
faith, which is what ADR-0047 forbids.

**Phase 5 can lag by a change if it must** — a failure to manufacture is already a refusal
somewhere, just not yet a good one. It should not lag further, because "stops with a distinct
reason" is what turns an outage into a diagnosis.
