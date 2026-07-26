# Tasks: Deployment Module Tree

**Input**: Design documents from `specs/006-deployment-module-tree/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: FR-016 says the tree's correctness is demonstrated by **applying** it, not by reading it.
So the verification here is not a Python test tier — it is a configuration-digest comparison across
two substrates, an executable bring-up contract, and the durability rows running inside an
allocation. Where a shell or Terraform check is the right instrument, that is what the task builds.

**Scope bound**: `src/` is untouched. The only repository code change is **deleting**
`DevVaultCredentials` from `tests/conformance/durability/conftest.py` (FR-006). A task that adds
production code to `src/` is out of scope for this feature; stop and say so.

**Migration, not greenfield**: `infra/dev-enclave/` works today and is what `make dev-up` drives.
Every task below has to keep that true or knowingly break it for one commit — so the tree is built
beside it (Phase 2–3), cut over once (Phase 8), and only then is the old directory deleted. There
is no window where a contributor has no working enclave.

**Organization**: grouped by user story so each is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Provisioning and bring-up paths | Sealed store refuses configuration; missing prerequisite fails by name; absent identity yields no credential |
| **Conformance** | The durability rows, now relocated | All seven still pass, now under an attested identity rather than a token |
| **Correlation / evidence** | N/A | No run-participating code paths change |
| **Eval** | N/A | No packs, prompts, models, or policies |
| **No-secret-leak** | Credential paths, module outputs, digests | No token, key, or password in state, outputs, digests, or logs |
| **Determinism** | Conformance relocation | Still no live model or managed-product API; the enclave remains permitted and required |

## Path Conventions

- Modules: `infra/modules/{trust-fabric,substrate-docker,substrate-vm}/`
- Roots: `infra/environments/{dev,production}/`
- Jobs: `infra/jobs/`
- Entry points: `infra/bin/`, `Makefile`
- Retired: `infra/dev-enclave/` (deleted in Phase 8)

---

## Phase 1: Setup

- [X] T001 (FR-001) Create the module and environment skeleton — `infra/modules/{trust-fabric,substrate-docker,substrate-vm}/`, `infra/environments/{dev,production}/`, `infra/jobs/`, `infra/bin/` — with `versions.tf` in each root pinning Terraform ≥ 1.9 and the vault/docker providers
- [X] T002 [P] Move `infra/dev-enclave/jobs/*.nomad.hcl` to `infra/jobs/`, unchanged. Moving before rewriting keeps the diff for the rewrite honest
- [X] T003 [P] Move `infra/dev-enclave/nomad/client.hcl` to `infra/nomad/client.hcl`. It enables the container driver's volume mounts, which the scheduler refuses by default — a constraint the production tree inherits, not a dev wrinkle
- [X] T004 Add `infra/.gitignore` covering `.terraform/`, `*.tfstate*`, and `*.tfvars`. State is currently committed-adjacent under `dev-enclave/`; the new roots must never repeat that
- [X] T004a Create `infra/README.md` with its section headings and nothing else — layout, the two axes, bring-up contract, posture dispositions, failure catalogue, substrate requirements. **Created first because four later tasks write into it** (T015, T040, T042, T047); a file authored at the end would overwrite them, and the two things lost would be the HA deferral and the failure catalogue — the writing in this feature most worth keeping

---

## Phase 2: Foundational — the substrate-independent module

**Purpose**: `trust-fabric` is the product. Everything else composes it.

**⚠️ CRITICAL**: no story work until this module applies cleanly.

- [X] T005 (FR-001, FR-002) Create `infra/modules/trust-fabric/variables.tf` with exactly the inputs in `data-model.md` — `agent_definitions`, `nomad_jwks_url`, `database_endpoint`, `profile`, `seal_config`. **A fourth substrate-derived input is the signal the boundary moved**: it may be right, but it is a deliberate change to `contracts/module-interface.md`, not a variable someone adds
- [X] T006 [P] Create `infra/modules/trust-fabric/auth.tf` — JWT auth backend from `nomad_jwks_url`, per-definition agent roles, and the harness role with `bound_claims` on the job id. Without the bound claim any workload could assume the harness role and the attestation is decorative
- [X] T007 [P] Create `infra/modules/trust-fabric/policies.tf` — per-definition ceiling policies and the harness database policy. The database policy attaches to the **workload** identity, never to an agent ceiling: database access inside a definition's ceiling would let a model-chosen tool call reach the checkpoint store, which is the run's own record of what it did
- [X] T008 [P] Create `infra/modules/trust-fabric/registry.tf` — identity entities and agent-registry registrations with their ceiling policies (ADR-0015's first-class registry, not a convention over kv)
- [X] T009 Create `infra/modules/trust-fabric/database.tf` — database secrets engine, connection, dynamic role granting the parent role, and `rotate-root`. Keep `ignore_changes` on the connection password: without it every apply undoes the rotation and quietly restores the standing credential the rotation exists to remove
- [X] T010 Create `infra/modules/trust-fabric/pki.tf` — PKI mount, control-plane CA, and a role issuing the trust store's own certificate
- [X] T011 [GATE:no-secret-leak] Create `infra/modules/trust-fabric/outputs.tf` — auth path, credential path, CA certificate, and `configuration_digest`. Assert no output carries a token, key, or password; a module output is the easiest place for one to escape into a root's state
- [X] T012 Implement `configuration_digest` per `data-model.md` — a stable hash over auth methods, roles, policies, secrets engines, registry entries, and database roles. **Exclude everything substrate-derived**; including an address makes the digests differ by construction and the comparison worthless. **Compute it from resolved inputs and literal configuration, never from resource attributes** — a digest hashing a mount accessor or an entity id resolves to "known after apply", and SC-001's plan-level comparison then compares two unknowns and passes while proving nothing
- [ ] T012a [GATE:fail-closed] Assert the digest is a known value at plan time — inspect `terraform show -json <plan>` and fail if the digest output appears under `after_unknown`. Name the mechanism, because otherwise the likely implementation is a human reading a plan, which is what this task exists to replace. Without it the failure in T012 is silent: the comparison succeeds, the criterion reports green, and nobody learns the two trees diverged
- [X] T013 (FR-012) [GATE:fail-closed] Add a precondition refusing apply when the trust store is sealed. A configuration tool that cannot read concludes the resources are absent and discards its record of them; the next apply then fails trying to create what exists

**Checkpoint**: `trust-fabric` applies against the existing dev Vault and produces a digest.

---

## Phase 3: Foundational — substrates

- [X] T014 Create `infra/modules/substrate-docker/` from the current `substrate.tf` — trust-store container, named volumes, and the ownership fix. Carry the two traps forward as **code with comments**, not prose: `CAP_IPC_LOCK` in long form, or every apply replaces the container and reseals the store; and a `terraform_data` provisioner for the volume chown rather than a one-shot container, which either self-removes and leaves an unresolvable id or lingers as cruft
- [X] T015 [P] Create `infra/modules/substrate-vm/` — the production shape, producing the same three outputs. **Not** a stub: an unimplemented substrate makes SC-001 unverifiable, and SC-001 is the feature. **It must also plan without cloud credentials**, or SC-001 becomes unverifiable in development, which is exactly what the clarification set out to avoid. Target a provider that plans offline — locally-managed VMs, or resources shaped like the real thing with no authenticating provider — and record which was chosen and why in `infra/README.md`
- [X] T016 [GATE:fail-closed] Add node-identity validation to `substrate-docker` — raft data is bound to `node_id`, and moving a store to a differently-named node leaves it outside its own peer set: it unseals, reports standby forever, and answers every call "sealed". Nothing in that chain names the cause

---

## Phase 4: User Story 1 — One tree, two substrates (P1) 🎯 MVP

**Goal**: the same configuration produces a workstation enclave and a customer one, differing only in substrate

**Independent Test**: quickstart Scenario D

- [X] T017 [US1] (FR-001) Create `infra/environments/dev/main.tf` composing `substrate-docker` + `trust-fabric` with `profile = "development"`
- [X] T018 [US1] (FR-001) Create `infra/environments/production/main.tf` composing `substrate-vm` + `trust-fabric` with `profile = "production"`
- [X] T019 [US1] Add `infra/bin/enclave-digest-diff` — plan both roots, extract both digests, compare, and print the differing elements on mismatch. **Printing the difference is the point**: "digests differ" sends the reader back to do the diff the tool already did
- [X] T020 [US1] [GATE:conformance] Wire `make enclave-digest-diff` and assert identical digests across the two roots (SC-001)
- [X] T021 [US1] Add a check that `infra/modules/trust-fabric/` references no substrate resource and no substrate-only provider — invariant 1 of `contracts/module-interface.md`, which is a property of the source and so is checkable by reading it
- [X] T022 [US1] Add the mirror check: no `substrate-*` module creates a policy, role, registry entry, or secrets engine (invariant 2). One direction alone would let the delta escape the other way
- [X] T022a [US1] [GATE:fail-closed] Assert **no substrate module submits the trust store as a scheduler workload** (FR-004) — no jobspec, no scheduler API call, no scheduler-managed allocation for it. **The constraint is scheduling, not packaging** (ADR-0048, verbatim: "A container Nomad does not manage is a peer of the substrate, not a resource inside it"). `substrate-docker` creating the trust-store container directly is *correct* and must keep passing this check; a check that forbids it has read the rule as "must not be containerized", which ADR-0048 calls out as a misreading with real cost — it would rule out the most convenient way to run a pinned version in development. The rule matters for two independent reasons: containment (the identity record must not live in the substrate whose access it constrains) and circularity (the scheduler is itself a client of the store, so that arrangement has no cold start that terminates)

**Checkpoint**: Scenario D green; SC-001 holds. The feature is demonstrable.

---

## Phase 5: User Story 3 — Bring-up publishes a contract (P1)

**Goal**: when bring-up succeeds you know what is true; when it cannot, it names what is missing

**Independent Test**: quickstart Scenarios A, B, C

> Sequenced before US2 deliberately: the conformance relocation depends on an environment that
> can state it is ready, and "the suite failed" versus "the environment was not up" is exactly the
> confusion this story removes.

- [X] T023 [US3] Create `infra/bin/enclave-verify` asserting each of the six guarantees in `contracts/bring-up-contract.md` against a running environment
- [X] T024 [US3] Port `dev-up.sh` to `infra/bin/enclave-up`, driving the environment root instead of a flat directory, and **running `enclave-verify` before reporting success** — otherwise the contract describes intent rather than state
- [X] T025 [P] [US3] Port `dev-down.sh` to `infra/bin/enclave-down`. Destroys nothing: the volumes hold the trust store and the run state
- [X] T025a [US3] [GATE:fail-closed] Assert the bootstrap order — trust store before scheduler, scheduler before any agent workload (FR-003). Today it holds because `enclave-up` was ported from a script that happens to be ordered correctly; "no supported path may invert this order" is currently untested. It is the only ordering that terminates, and an inverted one fails at cold start, which is the worst time to find out
- [X] T026 [US3] [GATE:fail-closed] Make every prerequisite failure name the missing prerequisite (FR-008). "Bring-up failed" withholds the diagnosis the tool already performed
- [X] T027 [US3] [GATE:fail-closed] Assert re-running against a configured environment unseals and **never re-initialises** (FR-009). Re-initialising discards the trust store and invalidates every credential derived from it — the most expensive mistake available here
- [X] T028 [US3] Point `make dev-up` / `dev-down` / `dev-status` at `infra/bin/*` so the tree's entry points are the documented ones, not tooling beside them

**Checkpoint**: Scenarios A–C green; SC-005 and SC-006 hold.

---

## Phase 6: User Story 2 — Conformance under a real attested identity (P1)

**Goal**: the durability rows run in an allocation under their own workload identity, and the last static token leaves the repository

**Independent Test**: quickstart Scenario E

- [X] T029 [US2] (FR-005) Create `infra/jobs/conformance.nomad.hcl` — a batch job with an `identity` block (`aud` matching the Vault role, job id matching its `bound_claims`), mounting the working tree and running the durability rows
- [X] T030 [US2] Add the Vault role binding for the conformance job in `infra/modules/trust-fabric/auth.tf`, scoped to the database policy only
- [X] T031 [US2] Teach `tests/conformance/durability/conftest.py` to obtain credentials through `core.durability.credentials` — the workload's own exchange — with no token branch
- [X] T032 [US2] [GATE:no-secret-leak] **Delete `DevVaultCredentials`** from `tests/conformance/durability/conftest.py` (FR-006, SC-003). Deleted, not bypassed: while it exists, someone can reach for it under time pressure
- [X] T033 [US2] Point `make conformance` at the job — submit, stream, surface the exit status. The honest cost is worse failure output through allocation logs; surface it well rather than pretend it is free
- [X] T034 [US2] [GATE:fail-closed] Assert a run outside an allocation fails naming the absent workload identity, with no fallback (SC-004, FR-007)
- [X] T035 [US2] [GATE:conformance] Assert all seven durability rows still pass in their new home, against both providers
- [X] T036 [US2] [GATE:determinism] Update `tests/unit/test_no_live_dependencies.py` — `ENCLAVE_PATHS` shrinks as the conftest stops reaching Vault directly. The list is an explicit allowlist, so it must shrink when the reason for an entry does

**Checkpoint**: Scenario E green; SC-002, SC-003, SC-004 hold. The last static token is gone.

---

## Phase 7: User Story 4 — Production posture answered (P2)

**Goal**: each of the four items implemented or deferred with a reason; none silently absent

**Independent Test**: quickstart Scenario G

- [ ] T037 [US4] Implement TLS in `infra/modules/trust-fabric/pki.tf` and the substrate listener config — self-signed bootstrap certificate, replaced by a PKI-issued one **as part of apply**, not as a follow-up someone forgets. The first certificate cannot come from a PKI that is not yet serving; that circularity is the same shape as ADR-0048's, with the same resolution
- [ ] T038 [US4] (FR-011) Implement bootstrap-credential revocation for `profile = "production"` only. Development keeps the root token deliberately — revoking it there breaks the re-apply loop, and an enclave nobody re-applies costs more safety than the retained token does on a workstation
- [ ] T038a [US4] Update every client of the trust store for TLS — `Makefile`'s hardcoded `http://127.0.0.1:8200`, `.env`, `infra/bin/*`, the conformance job, and the CA trust each needs. **T037 is not done until this is**: enabling TLS makes the environment correct and every tool talking to it broken, which presents as "the enclave is down" and is not
- [ ] T039 [P] [US4] Implement the `seal_config` seam: a production root can express auto-unseal without editing `trust-fabric`; the development default remains 1-of-1 shamir
- [ ] T040 [P] [US4] Record the HA deferral in `infra/README.md` with its named trigger, **and** its consequence: 005's conformance caveat persists, so landing this feature does not close it
- [ ] T041 [US4] [GATE:fail-closed] Assert all four items carry a non-empty disposition (SC-007). Silence is the failure FR-010 exists to prevent; deferral is not

**Checkpoint**: Scenario G green; SC-007 and SC-008 hold.

---

## Phase 8: User Story 5 — Cut over and carry the traps forward (P2)

**Goal**: one supported way to stand up an environment; the expensive knowledge survives the deletion

**Independent Test**: quickstart Scenarios F and H

- [X] T042 [US5] Move the six-entry failure catalogue from `infra/dev-enclave/README.md` into `infra/README.md`, keeping for each the condition, the symptom, **and where the symptom points instead of its cause** — that last column is why they cost time
- [X] T043 [US5] [GATE:fail-closed] For each catalogue entry, add prevention or detection that names the **cause**, not the symptom (FR-013, SC-009)
- [X] T043a [US5] **Migrate Terraform state out of `infra/dev-enclave/` before anything is deleted.** That state tracks 15 live resources — the running trust-store container, both named volumes, and every mount, role, policy and registry entry. Deleting the directory orphans them, and the new dev root then tries to create a container whose name is taken and mounts that already exist. Either `terraform state mv` each resource into `infra/environments/dev/`, or destroy and rebuild — and if rebuilding, say plainly that the volumes go with it, which means re-initialising the trust store and writing new credentials to `.env`. **This failure has already happened twice in this repository**; it is not hypothetical
- [X] T043b [US5] [GATE:fail-closed] After migration, assert the new root plans clean against the running environment — no creates for resources that already exist. That is the check that would have caught both prior occurrences
- [X] T044 [US5] **Delete `infra/dev-enclave/`** (FR-015, SC-010). Only after Phases 4–7 are green **and T043a/T043b have run**: deleting the working environment before its replacement is verified would leave contributors with none, and deleting it before its state is migrated would leave the resources unmanaged
- [X] T045 [US5] Update `CONTRIBUTING.md`, `docs/development/testing.md`, and `ROADMAP.md` for the new paths and entry points
- [X] T046 [US5] Assert exactly one applicable tree exists — no second directory that can be applied (SC-010)

**Checkpoint**: Scenarios F and H green; SC-009 and SC-010 hold.

---

## Phase 9: Polish

- [X] T047 [P] Complete and review `infra/README.md` — fill the sections T015, T040, and T042 did not, and check the whole reads as one document rather than four appends. **Do not rewrite it**: the substrate rationale, the HA deferral, and the failure catalogue are already there and are the parts worth keeping
- [ ] T048 [P] Document in `contracts/substrate-requirements.md` terms what Kubernetes would have to demonstrate — the same conformance assertions, not an analogous story (FR-014)
- [ ] T049 [GATE:no-secret-leak] Sweep state, outputs, digests, and entry-point logs for credential material. `.env` values are quoted, and passing the quotes through once made the trust store reject its licence with an error that named neither quoting nor the licence
- [ ] T050 Review the diff against the scope bound: `src/` untouched, one deletion in `tests/`. Anything else is out of scope for this feature
- [ ] T051 Open `feat/006-deployment-module-tree` with the FR-010 dispositions, the HA deferral and its consequence, and the `infra/dev-enclave` deletion called out

---

## Dependencies

**Story order**: US1 → US3 → US2 → US4 → US5. US3 precedes US2 because the conformance relocation
needs an environment that can state it is ready. US5 is last by necessity — it deletes the working
environment, so everything must be green first.

**Blocking**: Phase 2 (`trust-fabric`) blocks everything. T012's digest blocks US1's comparison, and
T012a blocks trusting it. T015's substrate blocks it too — SC-001 cannot be verified against a
substrate that does not exist, or one that cannot plan offline. T023's verify blocks T024. T037's
TLS blocks T038a, and neither is done without the other. **T043a and T043b block T044**: deleting
the proof directory before its state is migrated orphans 15 live resources.

**Parallel**: T002/T003 in setup; T006–T008 in Phase 2 (different files); T014/T015 across
substrates; T039/T040 in US4; T047/T048 in polish.

**`infra/README.md` accretes**: T004a creates the skeleton, T015/T040/T042 write into it, T047
completes and reviews. Anything that *rewrites* it drops the earlier three.

### Parallel example after Phase 3

```bash
# Developer A: US1 roots and the digest comparison
# Developer B: US3 bring-up contract and verification
# Developer C: US4 TLS and the seal seam
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 Setup
2. Phase 2 `trust-fabric`
3. Phase 3 substrates
4. Phase 4 US1
5. **STOP and VALIDATE**: two roots, identical digests, Scenario D green
6. Demoable as "one tree, two substrates" — the feature's central claim, before anything is deleted

### Incremental delivery

1. Setup + foundations → the module that is the product
2. US1 → one tree, two substrates (MVP)
3. US3 → bring-up states what it guarantees
4. US2 → conformance under a real identity; the last static token goes
5. US4 → production posture answered
6. US5 → cut over, delete the proof, keep its catalogue
7. Polish → scope review, PR

### Notes

- **Eval and correlation gate types omitted** (N/A) — no packs and no run-participating code paths.
- **`src/` is untouched.** The only repository code change is a deletion. That makes this the first
  feature since 002 with no Principle V exposure, and T050 is the review that keeps it true.
- **The HA deferral keeps 005's caveat alive.** Fencing and parking remain proven against
  single-node behaviour. T040 records it; the roadmap and conformance contract must keep saying it.
- **CI still does not run the enclave.** Unchanged by this feature and recorded in 005's conformance
  contract; the durability rows remain merge-blocking for a human running them locally.
- Contribution class at implement: **infrastructure**. No sealed-core change, so no
  security-maintainer gate on that basis — but the trust fabric is what every authority claim rests
  on, and the PR should be read that way.
