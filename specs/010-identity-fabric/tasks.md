# Tasks: Production Identity Fabric

**Feature**: `specs/010-identity-fabric` | **Branch**: `spec/010-identity-fabric`
**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests are required.** This repository is conformance-driven and the constitution's Quality
Gates bind rows as features land (ADR-0047). Test tasks are not optional here.

## Notes carried forward from 009, because they apply directly

- **When a task says "wire A to B", verify A's interface accepts what B requires.** 009 hit
  eight instances of a mechanism specified without the thing it acts through. The plan's seam
  table checked this in advance; where a seam does not fit, the task that widens it is listed
  *before* the task that uses it.
- **A check that matches prose is not a check.** Five occurrences in 009, twice in files whose
  own docstrings warned about it. Every static check below strips docstrings via AST and
  carries a positive control proving the stripper did not swallow the body.
- **The fixture must be capable of failing.** Research Finding 4: `demo-agent`'s ceiling
  grants a path under an unmounted mount, so rows written against it pass whether enforcement
  works or not. T009 precedes every enclave row for this reason.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/authority/` module files `vault_fabric.py`, `ceiling.py`, and `entitlements.py` as empty modules with SPDX headers, plus `tests/conformance/identity/__init__.py`. Under `mypy` strict with `explicit_package_bases` a missing `__init__.py` is a build error rather than an inconvenience
- [ ] T002 [P] Add the reason-code enumeration from [data-model.md](data-model.md) to `src/core/authority/errors.py`, as a frozen mapping rather than bare strings. A reason code invented at the call site is one nothing can assert on, and FR-012 requires three situations to stay distinguishable

---

## Phase 2: Foundational — blocks every user story

- [ ] T003 [GATE:fail-closed] Widen the 005 credential seam in `src/core/durability/credentials.py`: add an authenticated **read of an arbitrary Vault path** under the same workload identity, alongside the existing `database/creds/<role>` fetch. **A sealed-core change to a seam 005 owns.** The existing class logs in and reads exactly one path; the fabric reads several unrelated ones. The alternative — a second class authenticating its own way — would be a second path to the trust fabric, which is the shape Principle II forbids elsewhere for the same reason
- [ ] T004 [GATE:fail-closed] Give the read in `src/core/durability/credentials.py` a **bounded timeout that fails closed** (FR-018): one named constant, default **5 seconds**, overridable per deployment — the value is deployment-shaped, but the default must exist and must be seconds-scale, because a 60-second default holds steps open in exactly the way FR-018 exists to prevent. A resolution that hangs holds a step open, and a step held open indefinitely is a run that neither completes nor suspends — which is worse than a refusal because nothing notices it
- [ ] T005 [P] Add `harness-ceilings/` and `role-bindings/` KV v2 storage to `infra/modules/trust-fabric/ceilings.tf`, written by the same apply that writes the registration. Two applies would leave a window in which a registered agent has no ceiling; per FR-005 that refuses, so the window is fail-closed — but it would look like an outage, which is why it is one apply
- [ ] T006 [P] [GATE:fail-closed] Add a **narrow read policy** for the two prefixes in `infra/modules/trust-fabric/policies.tf`, and a reader role in `auth.tf`. **Not merged into `harness-database`**: that policy exists so a run can write its own record, and merging would mean anything able to reach the database could read every ceiling in the estate. The evidence path drew the same separation for the same reason
- [ ] T007 Extend `agent_definitions` in `infra/modules/trust-fabric/variables.tf` and `infra/environments/*/variables.tf` with a harness-domain ceiling — `tool_names` and `product_actions`. **The registry cannot hold this** (research Finding 3): `agent_registry` is a built-in engine with a closed schema, so the variable feeds the KV record rather than the registration
- [ ] T008 [GATE:conformance] Assert in `tests/unit/test_ceiling_record_shape.py` that a ceiling record with an unknown `schema_version` refuses rather than being partially parsed. A record written by a newer platform must not be half-understood by an older one — and half-understanding a ceiling means enforcing a subset of it
- [ ] T009 Register an agent definition in `infra/environments/dev/variables.tf` whose ceiling **resolves to something real**, and mount whatever it names. **Blocks every enclave row.** `demo-agent`'s ceiling grants `secret/data/demo/*` and `secret/` is not mounted (research Finding 4), so every assertion against it passes whether enforcement works or not
- [ ] T010 Update `infra/bin/enclave-verify` to assert the ceiling records exist and are readable by the reader role and by nothing else. A missing ceiling store must fail at bring-up rather than appearing later as runs that refuse for reasons nobody can trace

---

## Phase 3: User Story 5 — the protocol stops carrying test affordances (Priority: P5, sequenced FIRST)

**Goal**: `IdentityFabric` declares only what a production implementation meaningfully implements.

**Why first despite being P5**: it is a sealed-core change every other story's code sits on.
Doing it after three implementations exist means changing three implementations.

**Independent test**: the protocol declares no test-only method and no module under `src/`
imports from `tests/`.

- [ ] T011 [US5] Remove `issue_brokered_material` and `get_brokered_material` from the protocol in `src/core/authority/fabric.py` (FR-013), and delete the "fakes implement; core never calls a live IdP" module docstring, which stops being true in this feature
- [ ] T012 [US5] [GATE:fail-closed] Make the **broker branch refuse** `broker_not_implemented` in `src/core/hooks/mirroring.py`. **This is the task research Finding 6 created and it is not a rename.** That branch is production code performing a *simulated* exchange — it writes the literal string `HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET` and returns `allow`. Principle IV names the brokered path's management token as the platform's one permitted standing credential; the mechanism it exists for does not exist. Refusing makes the gap visible when someone configures a brokered product, which is when they need to know
- [ ] T013 [US5] Keep both methods on `tests/harness/fake_identity_fabric.py` as ordinary methods. The fake needed them; it simply stops claiming they are part of the contract
- [ ] T014 [P] [US5] [GATE:conformance] Assert in `tests/unit/test_protocol_has_no_test_affordances.py` that the protocol declares no method whose name or docstring marks it test-only, **stripping docstrings via AST with a positive control** proving the stripper did not swallow the body — **and** that the production fabric structurally satisfies the protocol with no method raising "not supported" (SC-009, both halves: a clean protocol nobody implements is as vacuous as a dirty one everybody does). Without this row the next test-only convenience arrives exactly as this one did — as the shortest path at the time
- [ ] T015 [P] [US5] [GATE:conformance] Assert in `tests/unit/test_src_does_not_import_tests.py` that **zero modules under `src/` import from `tests/`** (FR-015, SC-008), resolving imports by AST rather than by string match — a check that grepped for `tests` would match this task's own docstring
- [ ] T016 [US5] Move the dispatched-run entrypoint from `tests/harness/dispatched_run.py` into `src/`, or record why it cannot (FR-015). It lives under `tests/` because a production entrypoint had no fabric to resolve through; that reason expires with this feature, and if it does not, the reason it survives is worth more than the move

---

## Phase 4: User Story 1 — the ceiling comes from the registry (Priority: P1) 🎯 MVP

**Goal**: authority for a run is bounded by the ceiling the registry holds.

**Independent test**: two definitions with different ceilings produce different manufactured
authority in a live enclave, and neither exceeds its record.

- [ ] T017 [US1] Read a registration from `agent-registry/registration/display-name/<id>` in `src/core/authority/vault_fabric.py`. `disable_read = true` in `registry.tf` is a Terraform-provider setting that keeps the resource out of state; the Vault API reads and lists fine (research Finding 1)
- [ ] T018 [US1] [GATE:fail-closed] Refuse `unknown_agent_definition` for an absent registration (FR-003). Never a default ceiling, never an empty one that widens later, never an open one
- [ ] T019 [US1] Read the harness ceiling record and build an `AuthorityScope` in `src/core/authority/ceiling.py` (FR-004)
- [ ] T020 [US1] [GATE:fail-closed] Refuse `missing_ceiling_record` when a definition is registered but has no harness ceiling, and **never infer either jurisdiction from the other** (FR-005). That substitution is how a secrets grant quietly becomes a tool grant
- [ ] T021 [US1] [GATE:fail-closed] Refuse `unknown_ceiling_entry`, **naming the entry**, when a ceiling names a tool or product action the platform does not know (FR-005a). Silently dropping it narrows a ceiling with no trace, which is a change to authority nobody can audit
- [ ] T022 [US1] Record both **declared and effective** `ceiling_policies` when reading a registration (research Finding 2). Vault appends `default` and `default-ceiling` unless `no_default_ceiling_policy` is set, which this repository has never set. A reader seeing only its own declaration is reading something that does not exist
- [ ] T022a [US1] [GATE:conformance] **Construct the production fabric in the run path**: the dispatched-run entrypoint (post-T016 location) and the surface assembly in `src/surfaces/api/app.py` build `VaultIdentityFabric` and pass it to `start_governed_run`, replacing the fake. **The task G2 named before it became a discovery.** Every task before this builds the mechanism; this is the thing it acts through, and 009 recorded eight features' worth of the difference. Without it, T023 fails as a mystery — the fabric exists, is correct, is tested, and nothing instantiates it
- [ ] T023 [P] [US1] [GATE:conformance] Enclave row in `tests/conformance/identity/test_ceiling_from_registry.py` (SC-002): two definitions, two ceilings, different manufactured authority, neither exceeding its record. Depends on T009 — against the current fixture this passes whether enforcement works or not
- [ ] T024 [P] [US1] [GATE:conformance] Enclave row in `tests/conformance/identity/test_jurisdictions_stay_disjoint.py`: a registration with a credential policy and no harness ceiling refuses. **Break fixture**: a reader that falls back to `ceiling_policies` — plausible as a "be resilient" change, and it converts a secrets grant into a tool grant
- [ ] T025 [P] [US1] [GATE:conformance] Row in `tests/conformance/identity/test_declared_vs_effective.py` asserting the appended default policies are observed and accounted for rather than discovered later

---

## Phase 5: User Story 2 — the user's scope comes from their identity (Priority: P2)

**Goal**: harness-domain scope derives from verified claims through governed mappings.

**Independent test**: two users whose claims map to different roles get different authority
for the same run request.

- [ ] T026 [US2] Resolve roles to a scope via the role-binding records in `src/core/authority/vault_fabric.py`, consuming `resolve_roles` from `core/identity/claims.py` (FR-006). 008 built claims→roles and 007 governs the mappings; only roles→scope is missing
- [ ] T027 [US2] [GATE:fail-closed] Take the **union** of multiple roles' bindings in `src/core/authority/vault_fabric.py` before intersecting downstream. Union is the only choice that makes adding a role additive — intersection would let a second role *remove* access, which nobody would predict from being granted one
- [ ] T028 [US2] [GATE:fail-closed] Keep the three "no scope" cases distinct (FR-007): `no_role_for_subject`, `unbound_role`, and a legitimately empty binding. Nobody knows who you are, nobody has said what your role means, and your role means nothing — only the third is a real empty scope, and collapsing them makes a platform failure look like a permissions decision
- [ ] T029 [P] [US2] [GATE:conformance] Enclave row in `tests/conformance/identity/test_scope_from_claims.py` (SC-004): two users, two roles, measurably different authority
- [ ] T030 [P] [US2] [GATE:conformance] Row in `tests/unit/test_no_scope_cases_stay_distinct.py` (SC-005) covering all three cases and asserting three different reason codes

---

## Phase 6: User Story 3 — policy is read live (Priority: P3)

**Goal**: a mid-run narrowing bounds the next step; an outage suspends rather than stops.

**Independent test**: narrow policy mid-run against a live fabric and observe the next step bounded.

- [ ] T031 [US3] Read policy from the trust fabric in `src/core/authority/vault_fabric.py` **on each step, with no cache** (FR-008). A cached scope used past its freshness bound is a stale permission, and a narrowing that takes an interval to bite is weaker than the guarantee 005 asserts
- [ ] T032 [US3] [GATE:fail-closed] Ensure a mid-run **widening** does not enlarge the grant issued at run start, in `src/core/authority/manufacture.py` (FR-009). Narrowing binds immediately; widening waits for a new run
- [ ] T033 [US3] [GATE:fail-closed] Suspend naming `trust-fabric` when the fabric cannot be reached mid-run (FR-008a), through 009's `suspend_run(run, *, awaiting=...)` in `src/core/durability/resume.py`. `awaiting` is a free string, so the seam already accepts this — verified in the plan's seam table rather than discovered here
- [ ] T034 [US3] [GATE:fail-closed] Refuse rather than suspend in `src/core/run.py` when the fabric is unreachable **at run start**. There is no grant, no checkpoint, and nothing to resume — the asymmetry falls out of a run existing or not existing yet, and is not a special case
- [ ] T035 [US3] Assert the **recovery ordering** in `src/surfaces/mcp/server.py`'s supervisory pass and in `tests/conformance/identity/test_recovery_order.py` (FR-008b): fabric returns → checker login succeeds → credentials obtained → health recorded → sweep resumes. **The trust fabric is a dependency of the mechanism that monitors dependencies**, so this is the only order that terminates. Nothing else in this platform has this property and no existing row asserts an ordering constraint of this kind
- [ ] T036 [US3] [GATE:fail-closed] Ensure nothing that failed to reach the fabric can mark it healthy, in `src/core/dependencies/store.py` (FR-008c). A monitor that cannot run leaves the state unknown, and unknown already refuses
- [ ] T037 [P] [US3] [GATE:conformance] Enclave row in `tests/conformance/identity/test_policy_read_per_step.py` (SC-006): a mid-run narrowing bounds the next step, with **zero steps served from cache**. **Break fixture**: a resolver caching policy for a few seconds — an obvious optimisation, and the row that catches it is the zero-cached-steps assertion, not the one asserting the narrowing eventually applies
- [ ] T038 [P] [US3] [GATE:conformance] Enclave row in `tests/conformance/identity/test_fabric_outage_suspends.py` (SC-006a): the run suspends naming the fabric, holds no container, and resumes with **zero operator actions**

---

## Phase 7: User Story 4 — entitlement mirroring asks something real (Priority: P4)

**Goal**: the user's own product entitlements are resolved through a real seam and enforced.

**Independent test**: a user narrower than the credential cannot exceed themselves.

- [ ] T039 [US4] Define the entitlement-resolution seam in `src/core/authority/entitlements.py` — ours, real — and implement it on `tests/harness/fake_product_api.py`. The product's authorization system is outside our boundary and correctly stays faked; the interface that asks it is not (spec C2)
- [ ] T040 [US4] [GATE:fail-closed] Refuse `entitlement_unavailable` when a product cannot be asked (FR-011). Unknown entitlement is not empty and is certainly not full
- [ ] T041 [US4] [GATE:fail-closed] Keep both authorization domains independent in `src/core/hooks/mirroring.py` — either refusing refuses the call (FR-010, ADR-0044). Two checks that must agree are not one check consulted twice
- [ ] T042 [P] [US4] [GATE:conformance] Row in `tests/conformance/identity/test_mirroring_bites.py` (SC-007): a user narrower than the credential cannot exceed themselves, with **zero side effects** on the attempt
- [ ] T043 [P] [US4] [GATE:conformance] Row in `tests/conformance/identity/test_broker_refuses.py` asserting the broker branch refuses `broker_not_implemented` rather than allowing on a placeholder (research Finding 6)

---

## Phase 8: Polish & cross-cutting

- [ ] T044 [GATE:fail-closed] Assert in `tests/conformance/identity/test_fabric_unreachable_from_a_tool.py` that with an **agent's own credential** the ceiling paths are denied **by Vault** (FR-016). A refusal produced by our code would satisfy the behaviour and miss the point — ADR-0015 puts the fabric structurally outside every agent ceiling, and "structurally" means the denial is not ours to make
- [ ] T045 [GATE:fail-closed] Extend `tests/unit/test_no_static_credentials.py` to cover the fabric's configuration and environment (FR-002, SC-010), reusing the assertion the durability and evidence paths already carry
- [ ] T046 [GATE:conformance] Break fixture in `tests/conformance/identity/test_break_empty_scope_on_error.py`: **a fabric returning an empty scope on error**. Every "denied" row still passes, because denial is what an empty scope produces — only the reason code fails. This is the most likely regression in the feature, since returning `AuthorityScope()` in an exception handler is the shortest path and reads as fail-closed
- [ ] T046a [GATE:conformance] **Sweep every existing row that resolves authority through the fake** (FR-014, SC-001) — the task without which this feature's headline criterion is false on its own merge commit. For each conformance and component row importing `fake_identity_fabric`: migrate it to the production fabric where its subject allows, or mark it fault-injection with the explicit statement FR-014 requires. Record the resulting mapping — which rows moved, which stayed and why — in `contracts/conformance-identity.md`, which is FR-019's deliverable and falls out of this sweep rather than being written separately
- [ ] T046b [P] [GATE:conformance] Gate check in `tests/unit/test_fake_fabric_is_fault_injection_only.py`: no conformance or component row imports the fake without the fault-injection marker (SC-001, mechanically). **Imports resolved by AST, not by string match**, with a positive control — this repository has had five checks match prose instead of code, and a grep for the fake's name would match the marker comments this check requires
- [ ] T047 Write `docs/adr/00NN-harness-ceilings-live-in-the-trust-fabric.md` (FR-020): what the trust fabric now holds, why the ceiling is a separate record rather than a registration field, and why that is a truer expression of ADR-0044's disjoint jurisdictions than sharing a struct would have been
- [ ] T048 [P] Record the **RFC 8693 + RAR divergence** (research Finding 5) in `ROADMAP.md` under known gaps: the constitution describes manufacture as "RFC 8693 + RAR against ceiling policies" and the implementation is a JWT role login. Not closed here — it is a second large feature — but this is the last honest moment to notice, since this is the feature that reads ceilings
- [ ] T049 [P] Record the **brokered-path gap** (research Finding 6) in `ROADMAP.md`: Principle IV names the broker's management token as the platform's one permitted standing credential, and the mechanism it exists for is a stub that returns allow
- [ ] T050 [P] Record `no_default_ceiling_policy` as a follow-up decision (research Finding 2). Setting it changes the security posture of every registration and belongs in a decision of its own, not a module edit
- [ ] T051 [P] Update `ROADMAP.md`: the production `IdentityFabric` gap moves from **claimed by 010** to shipped; 010 joins the shipped table
- [ ] T052 [P] Record the rows in `contracts/conformance-identity.md` as **In force**, over the fake-to-real mapping T046a produced there
- [ ] T053 [GATE:conformance] Run `make check` and `make conformance` against a **live enclave**, and confirm every break fixture passes on a clean tree. A row whose failure nobody has observed is a row nobody knows works

---

## Dependencies

```
Phase 1 Setup (T001–T002)
  └─> Phase 2 Foundational (T003–T010)          [T009 blocks every enclave row]
        └─> Phase 3 US5 protocol (T011–T016)     [sealed core; everything sits on it]
              ├─> Phase 4 US1 ceilings (T017–T025)   🎯 MVP
              ├─> Phase 5 US2 user scope (T026–T030)
              ├─> Phase 6 US3 policy (T031–T038)
              └─> Phase 7 US4 entitlements (T039–T043)
                    └─> Phase 8 Polish (T044–T053)
                          [T046a needs all four stories real — a row can only
                           migrate off the fake once its resolution has somewhere
                           real to go; T046b needs T046a's markers to exist]
```

**Two orderings are not free**, and both are recorded in the plan:

1. **US5 before US1–US4** despite being P5. A sealed-core protocol change made after three
   implementations exist means changing three implementations.
2. **T009 before every enclave row.** The current fixture's ceiling grants a path under an
   unmounted mount, so rows written against it are green regardless of enforcement.

**US1, US2, US3, US4 are independent of each other** once US5 lands. The intersection narrows
whichever term is real, so a story can be proven while the others still resolve through the
fake — which is what makes each independently testable.

## Parallel opportunities

- **Phase 2**: T005 and T006 are separate Terraform files; T008 is a test
- **Phase 3**: T014 and T015 are separate test files over separate concerns
- **Phase 4**: T023, T024, T025 are three separate row files
- **Phase 5**: T029 and T030
- **Phase 6**: T037 and T038
- **Phase 7**: T042 and T043
- **Phase 8**: T046b runs beside T046a's tail; T048–T052 are documentation in different files

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3 + Phase 4** — through T025. That delivers the property
the feature exists for: an agent's ceiling comes from what an operator configured, proven end
to end against a live trust fabric. The remaining stories each replace one more fake, and the
intersection means each is independently demonstrable.

**Stop-and-check point after T012.** Making the broker branch refuse is a behaviour change to
a path that currently returns `allow`. If anything depends on that `allow` — including a test
— it will surface there, and it is better to find it in a two-task phase than in a fifty-task
one.

## Task count

**56 tasks** — 2 setup, 8 foundational, 6 US5, 10 US1, 5 US2, 8 US3, 5 US4, 12 polish.

Three were added by the analyze pass rather than the original generation, and each has a
finding behind it: T022a (G2 — the wiring task, the ninth instance of the seam pattern
caught before implementation instead of during), and T046a/T046b (G1 — the sweep and its
enforcement, without which SC-001 is false on the feature's own merge commit).
