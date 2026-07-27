# Tasks: Control Groups

**Input**: Design documents from `specs/007-control-groups/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**The premise, checked before anything else**: this feature configures the control-plane
Vault's own Control Groups. That capability is licensed on the running enclave — verified,
not assumed. T001 re-checks it, because if it is false the plan is wrong end to end rather
than merely inconvenient, and everything after T001 is wasted.

**Tests**: run against the **real** control-plane Vault. There is no faked Control Group
anywhere in this feature. A fake that always approves proves the caller can proceed; one
that never approves proves it handles denial; neither proves the gate holds, which is the
only claim that matters. Same reasoning that put the durability rows on real Postgres.

**Scope bound**: one small core module that **observes and records**. If this feature grows
an approval engine, the premise broke — stop and say so rather than building one (FR-014).

**Organization**: grouped by user story so each is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Approval mechanism unreachable; quorum unmet | Changes blocked — and **runs unaffected**, which is the half that is easy to get backwards |
| **Conformance** | Authority-change path | The gate holds against the real Vault, not a fake |
| **Correlation / evidence** | Every authority change | Request, approvals, disposition, joined by correlation ID |
| **Eval** | N/A | No packs, prompts, models, or policies |
| **No-secret-leak** | Audit records, Terraform state, outputs | No credential material, no policy content |
| **Determinism** | Feature test paths | No live model or managed-product API; the enclave is required |

## Path Conventions

- Trust fabric: `infra/modules/trust-fabric/control-groups.tf`, `policies.tf`, `variables.tf`
- Core: `src/core/authority/changes.py`, `errors.py`
- Tests: `tests/unit/`, `tests/component/` — no conformance lane; see T002

---

## Phase 0: Premise Gate

- [X] T001 [GATE:conformance] Re-verify Control Groups is licensed on the target Vault — `vault read sys/license/status` and assert `Control Groups` is in `features`. **Everything after this depends on it.** If absent, stop: the design is "configure the trust fabric's mechanism", and the alternative is an approval engine that FR-014 forbids

---

## Phase 1: Setup

- [X] T002 [P] Create `infra/modules/trust-fabric/control-groups.tf` as empty scaffolding. **No conformance lane for this feature**: it adds no row to the constitution's blocking gate list, so such a directory would be a folder nobody fills. Its tests are component tests against the real Vault, which is sufficient and pretends nothing else
- [X] T003 [P] Add quorum policy inputs to `infra/modules/trust-fabric/variables.tf` — required approvals, authorized identities, and request TTL, **per class of change and with no defaults** (FR-015). A default quorum would be a security posture chosen for every customer by whoever wrote the module

---

## Phase 2: Foundational — the gate itself

**Purpose**: express the quorum requirement in the trust fabric. Everything else observes it.

**⚠️ CRITICAL**: no story work until the gate applies cleanly against the enclave.

- [X] T004 Write the Control Group configuration in `infra/modules/trust-fabric/control-groups.tf` — the Sentinel endorsement policy and its approver sets, parameterized by T003's inputs
- [X] T005 Attach the gate to the controlled **paths** per `contracts/gated-paths.md`: ceiling policies, definitions and registry entries, workload identity role bindings, restoration, and the quorum policy itself. **Attach to paths, not callers** — a gate on callers is a gate on the callers someone thought of
- [X] T005a [GATE:fail-closed] (FR-003a, SC-013) Assert break-glass is **not** routed through this gate, and document why in `infra/README.md`: regenerating a root token requires a quorum of unseal-share holders — verified against the CLI, which states it "generates a new root token by combining a quorum of share holders". That is a stronger multi-party control and a `sys` operation Control Groups cannot intercept. **Record the consequence**: break-glass strength is set by the unseal threshold, so the development enclave's 1-of-1 makes it a single-person act regardless of anything configured here
- [X] T006 [GATE:fail-closed] Assert revocation paths are **not** controlled (FR-006). Deliberate asymmetry: a gate making revocation as slow as granting is one people route around in an incident, after which the route-around is the normal path
- [ ] T007 Sequence the policy application in provisioning so it lands **before** the bootstrap credential is revoked (FR-016). A control gating its own changes cannot create itself; without this the alternatives are a control that never exists or one with a permanent back door
- [ ] T008 [GATE:no-secret-leak] Assert no quorum policy content or credential material reaches Terraform state, module outputs, or logs

**Checkpoint**: the gate applies; a ceiling change against the enclave now requires approval.

---

## Phase 3: User Story 1 — Widening authority requires more than one person (P1) 🎯 MVP

**Goal**: a ceiling change does not take effect on one person's say-so

**Independent Test**: quickstart Scenario A

- [ ] T009 [US1] Add `tests/component/test_authority_change_quorum.py` — propose a ceiling widening against the real Vault; assert the agent's effective authority is **unchanged** below quorum (SC-001)
- [ ] T010 [US1] Assert the change takes effect when quorum is reached, with approving identities recorded
- [ ] T011 [US1] [GATE:fail-closed] Assert a request cannot be satisfied by its own requester (FR-008, SC-003). Otherwise the requirement is one person with two hats
- [ ] T012 [US1] [GATE:fail-closed] Assert no change takes effect by timeout, default, or escalation (FR-009, SC-002)
- [ ] T013 [US1] Create `src/core/authority/changes.py` — observe authority-change events and record them. **It evaluates nothing.** Vault decides; this records what was decided
- [ ] T014 [US1] Add a distinct `blocked pending approval` error to `src/core/authority/errors.py`, separate from denial. Collapsed into deny, an in-flight approval is indistinguishable from a refusal, and a caller either retries forever or reports a failure that is not one
- [ ] T015 [US1] [GATE:correlation] Record request, each approval and denial with its identity, and disposition — joined by correlation ID (FR-011, SC-008)
- [ ] T016 [US1] [GATE:no-secret-leak] Assert the audit record holds no credential material and **no mirror of Vault's approval state** (`contracts/evidence.md`). A synchronised copy is a second answer to "who approved this", and during an incident someone reads the wrong one

**Checkpoint**: Scenario A green; SC-001, SC-002, SC-003, SC-008 hold. MVP demoable.

---

## Phase 4: User Story 2 — Revoking needs no one's agreement (P1)

**Goal**: one authorized identity revokes, alone and immediately

**Independent Test**: quickstart Scenario C (first half)

- [ ] T017 [US2] Add `tests/component/test_revocation_asymmetry.py` — a single authorized identity revokes with **zero** approvals, taking effect immediately (SC-004)
- [ ] T018 [US2] Assert a revoked agent cannot obtain new authority
- [ ] T019 [US2] [GATE:correlation] Assert who revoked what, and when, is recorded

---

## Phase 5: User Story 3 — Restoring requires quorum (P1)

**Goal**: revoked access does not come back the way it left

**Independent Test**: quickstart Scenario C (second half)

- [ ] T020 [US3] Assert restoration proposed by one person does **not** take effect (SC-005), in `tests/component/test_revocation_asymmetry.py`
- [ ] T021 [US3] Assert restoration with quorum takes effect, with approvers recorded
- [ ] T022 [US3] [GATE:correlation] Assert a restoration is distinguishable in the audit trail from an original grant — otherwise an incident's aftermath reads like ordinary provisioning

---

## Phase 6: User Story 4 — Registration is a governed act (P1)

**Goal**: creating authority that did not exist requires quorum

**Independent Test**: quickstart Scenario A, registration variant

- [ ] T023 [US4] Assert a definition lacking quorum is **not created** — not merely unusable. A definition existing ungated with no workload yet is a different and weaker property, and asserting only the second would pass against an ungated creation path
- [ ] T023a [US4] Assert no workload can authenticate as an unapproved definition (the second, weaker property — worth holding as well)
- [ ] T024 [US4] Assert an approved definition exists with its ceiling and appears in the agent registry
- [ ] T025 [US4] [GATE:fail-closed] Assert changing the quorum policy is itself gated (FR-015), and that after provisioning completes and the bootstrap credential is revoked, zero authority changes are possible outside the mechanism (SC-011)

---

## Phase 7: User Story 5 — Operating within an approved definition is not gated (P2)

**Goal**: routine operations proceed without approval

**Independent Test**: quickstart Scenario E

- [ ] T026 [US5] Assert scheduling, restarting, and scaling instances of an approved definition request approval in **zero** cases (SC-006)
- [ ] T027 [US5] Assert an operation that changes the *definition* rather than an instance **is** gated. Both halves matter: gating routine work would train people to approve without reading, which destroys the gate that matters

---

## Phase 8: The negative requirements

**Purpose**: the things that must stay untrue. These are the ones that quietly stop being
true, because nobody notices the day a pause is added.

- [ ] T028 [GATE:fail-closed] Add `tests/unit/test_no_run_interrupt.py` — assert **zero** runs are paused, interrupted, or blocked by anything in this feature (FR-012, SC-009). A feature about humans authorizing is exactly where a run-time interrupt grows back
- [ ] T029 [GATE:fail-closed] Assert a narrowed ceiling applies to authority manufactured **after** the change and reaches into **zero** running steps (FR-013, SC-010)
- [ ] T030 [GATE:fail-closed] Assert that with the approval mechanism unreachable, authority changes succeed in zero cases — **and runs already holding authority continue** (FR-010, SC-007). Failing closed on the wrong thing here would halt the platform during a Vault blip
- [ ] T031 Assert a pending request that reaches its TTL results in no change (FR-017, SC-012)
- [ ] T032 Assert a request is evaluated against the policy in force when it **completes**, not when raised (FR-018). Otherwise raising one just ahead of a tightening slips it through under the looser rule, making tightening advisory

---

## Phase 9: Polish

- [ ] T033 [P] Document the quorum policy in `infra/README.md` — what is gated, what is not, who owns the policy, and the bootstrap sequence
- [ ] T034 [P] [GATE:determinism] Extend `tests/unit/test_no_live_dependencies.py` for this feature's paths; the enclave is required and permitted, live models and product APIs are not
- [ ] T036 Review the diff against the scope bound: one core module that observes, zero new dependencies, no approval engine. Growth beyond that is the signal the premise broke
- [ ] T037 Open `feat/007-control-groups` with the asymmetry, the bootstrap sequence, and the negative requirements called out

---

## Dependencies

**Story order**: US1 → US2 → US3 → US4 → US5. US2 and US3 are two halves of one asymmetry
and share a test module, so they land together in practice.

**Blocking**: T001 blocks everything — the premise. Phase 2 blocks all stories. T007's
sequencing blocks T025, since "no changes outside the mechanism" is only assertable once
the bootstrap has closed.

**Parallel**: T002/T003 in setup; the negative requirements in Phase 8 are independent of
each other; T033/T034 in polish.

### Parallel example after Phase 2

```bash
# Developer A: US1 quorum path and the observation seam
# Developer B: US2 + US3 revocation asymmetry
# Developer C: Phase 8 negative requirements
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001 — confirm the premise
2. Phase 1 Setup
3. Phase 2 the gate
4. Phase 3 US1
5. **STOP and VALIDATE**: a ceiling change against the real enclave requires approval, and the audit trail shows who approved it
6. Demoable as "one person can no longer widen an agent's authority"

### Incremental delivery

1. Premise + setup + gate
2. US1 → quorum on ceiling changes (MVP)
3. US2 + US3 → the revocation asymmetry
4. US4 → registration and the policy's own gating
5. US5 → routine operations stay ungated
6. Phase 8 → the negative requirements, asserted
7. Polish → scope review, conformance contract, PR

### Notes

- **Eval gate type omitted** (N/A) — no packs, prompts, models, or policies.
- **No fake Control Group exists anywhere in this feature.** Tests run against the real
  Vault, for the same reason the durability rows run against real Postgres.
- **These tests need the enclave, so CI cannot run them** — but they are component tests,
  not conformance rows. Constitution v1.1.0's named-runner requirement applies to blocking
  rows in the Quality Gates list, and this feature adds none. Applying it here would have
  documented rows that do not exist. If authority-change gating should be such a row, that
  is a constitution amendment argued on its merits, not implied by a task.
- **004's approval hook is deliberately untouched.** Under ADR-0049 (Proposed) a run-time
  approval interrupt is the shape being removed; settling it belongs to 0049.
- Contribution class at implement: **sealed core (authority)** — security-maintainer review
  mandatory. The gate governs what every agent may become.
