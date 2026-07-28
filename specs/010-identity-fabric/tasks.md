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

- [X] T001 Create `src/core/authority/` module files `vault_fabric.py`, `ceiling.py`, and `entitlements.py` as empty modules with SPDX headers, plus `tests/conformance/identity/__init__.py`. Under `mypy` strict with `explicit_package_bases` a missing `__init__.py` is a build error rather than an inconvenience
- [X] T002 [P] Add the reason-code enumeration from [data-model.md](data-model.md) to `src/core/authority/errors.py`, as a frozen mapping rather than bare strings. A reason code invented at the call site is one nothing can assert on, and FR-012 requires three situations to stay distinguishable

---

## Phase 2: Foundational — blocks every user story

- [X] T003 [GATE:fail-closed] Widen the 005 credential seam in `src/core/durability/credentials.py`: add an authenticated **read of an arbitrary Vault path** under the same workload identity, alongside the existing `database/creds/<role>` fetch. **A sealed-core change to a seam 005 owns.** The existing class logs in and reads exactly one path; the fabric reads several unrelated ones. The alternative — a second class authenticating its own way — would be a second path to the trust fabric, which is the shape Principle II forbids elsewhere for the same reason
- [X] T004 [GATE:fail-closed] Give the read in `src/core/durability/credentials.py` a **bounded timeout that fails closed** (FR-018): one named constant, default **5 seconds**, overridable per deployment — the value is deployment-shaped, but the default must exist and must be seconds-scale, because a 60-second default holds steps open in exactly the way FR-018 exists to prevent. A resolution that hangs holds a step open, and a step held open indefinitely is a run that neither completes nor suspends — which is worse than a refusal because nothing notices it
- [X] T005 [P] Add `harness-ceilings/` and `role-bindings/` KV v2 storage to `infra/modules/trust-fabric/ceilings.tf`, written by the same apply that writes the registration. Two applies would leave a window in which a registered agent has no ceiling; per FR-005 that refuses, so the window is fail-closed — but it would look like an outage, which is why it is one apply
- [X] T006 [P] [GATE:fail-closed] Add a **narrow read policy** for the two prefixes in `infra/modules/trust-fabric/policies.tf`, and a reader role in `auth.tf`. **Not merged into `harness-database`**: that policy exists so a run can write its own record, and merging would mean anything able to reach the database could read every ceiling in the estate. The evidence path drew the same separation for the same reason
- [X] T007 Extend `agent_definitions` in `infra/modules/trust-fabric/variables.tf` and `infra/environments/*/variables.tf` with a harness-domain ceiling — `tool_names` and `product_actions`. **The registry cannot hold this** (research Finding 3): `agent_registry` is a built-in engine with a closed schema, so the variable feeds the KV record rather than the registration
- [X] T008 [GATE:conformance] Assert in `tests/unit/test_ceiling_record_shape.py` that a ceiling record with an unknown `schema_version` refuses rather than being partially parsed. A record written by a newer platform must not be half-understood by an older one — and half-understanding a ceiling means enforcing a subset of it
- [X] T009 Register an agent definition in `infra/environments/dev/variables.tf` whose ceiling **resolves to something real**, and mount whatever it names. **Blocks every enclave row.** `demo-agent`'s ceiling grants `secret/data/demo/*` and `secret/` is not mounted (research Finding 4), so every assertion against it passes whether enforcement works or not
- [X] T010 Update `infra/bin/enclave-verify` to assert **both** the `harness-ceilings/` and `role-bindings/` stores exist, are readable by the reader role, and are unreadable by everything else. T005 creates two prefixes and pass 4 caught this task verifying one — a missing role-binding store would surface not at bring-up but in a US2 row, as a resolution error naming the role rather than the store that is not there
- [X] T010a Build a **hybrid fabric** in `tests/harness/hybrid_fabric.py`: a delegating wrapper that routes named resolutions to the production fabric and the rest to the fake. **This is the mechanism behind the plan's claim that US1–US4 are independently provable, and pass 2 found that no task built it**: `manufacture_authority` resolves user scope, ceiling, and policy from one fabric object, so a per-story enclave row can only exercise its own term against the real fabric if something composes the terms — and the composition cannot live in `src/`, because production code importing the fake is FR-015's own violation. It lives here, in the harness, where importing both is legitimate. **Rows using it carry a transitional marker — `# HYBRID(<term>): migrated at T046a` — not an FR-014 marker**: an FR-014 marker claims fault injection, and a hybrid row is exercising a real term, so marking it per FR-014 would be a false statement in the file (pass 3 caught pass 2 instructing exactly that). The hybrid is scaffolding with a recorded expiry: T046a migrates its rows and deletes it

---

## Phase 3: User Story 5 — the protocol stops carrying test affordances (Priority: P5, sequenced FIRST)

**Goal**: `IdentityFabric` declares only what a production implementation meaningfully implements.

**Why first despite being P5**: it is a sealed-core change every other story's code sits on.
Doing it after three implementations exist means changing three implementations.

**Independent test**: the protocol declares no test-only method and no module under `src/`
imports from `tests/`.

- [X] T011 [US5] Remove `issue_brokered_material` and `get_brokered_material` from the protocol in `src/core/authority/fabric.py` (FR-013), and delete the "fakes implement; core never calls a live IdP" module docstring, which stops being true in this feature
- [X] T012 [US5] [GATE:fail-closed] Make the **broker branch refuse** `broker_not_implemented` in `src/core/hooks/mirroring.py`. **This is the task research Finding 6 created and it is not a rename.** That branch is production code performing a *simulated* exchange — it writes the literal string `HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET` and returns `allow`. Principle IV names the brokered path's management token as the platform's one permitted standing credential; the mechanism it exists for does not exist. Refusing makes the gap visible when someone configures a brokered product, which is when they need to know
- [X] T013 [US5] Keep both methods on `tests/harness/fake_identity_fabric.py` as ordinary methods. The fake needed them; it simply stops claiming they are part of the contract
- [X] T014 [P] [US5] [GATE:conformance] Assert in `tests/unit/test_protocol_has_no_test_affordances.py` that the protocol declares no method whose name or docstring marks it test-only, **stripping docstrings via AST with a positive control** proving the stripper did not swallow the body (SC-009, first half). Without this row the next test-only convenience arrives exactly as this one did — as the shortest path at the time. *(The second half of SC-009 — the production fabric satisfies what remains — is T045a, in Polish: pass 2 caught this row asserting a class that does not exist until Phase 4, a defect pass 1's own remediation introduced.)*
- [X] T015 [P] [US5] [GATE:conformance] Assert in `tests/unit/test_src_does_not_import_tests.py` that **zero modules under `src/` import from `tests/`** (FR-015, SC-008), resolving imports by AST rather than by string match — a check that grepped for `tests` would match this task's own docstring
- [X] T016 [US5] Record in `tests/harness/dispatched_run.py`'s docstring that it moves to `src/` at T038a and why not now: the production fabric it will construct does not exist until US1–US3 land, and moving it earlier would force it to import the fake from `src/` — FR-015's violation, committed by the task meant to satisfy FR-015. *(Pass 2 caught the move scheduled here, in a phase where it is impossible; the move itself is T038a.)*

---

## Phase 4: User Story 1 — the ceiling comes from the registry (Priority: P1) 🎯 MVP

**Goal**: authority for a run is bounded by the ceiling the registry holds.

**Independent test**: two definitions with different ceilings produce different manufactured
authority in a live enclave, and neither exceeds its record.

- [X] T017 [US1] Read a registration from `agent-registry/registration/display-name/<id>` in `src/core/authority/vault_fabric.py`. `disable_read = true` in `registry.tf` is a Terraform-provider setting that keeps the resource out of state; the Vault API reads and lists fine (research Finding 1)
- [X] T018 [US1] [GATE:fail-closed] Refuse `unknown_agent_definition` for an absent registration (FR-003). Never a default ceiling, never an empty one that widens later, never an open one
- [X] T019 [US1] Read the harness ceiling record and build an `AuthorityScope` in `src/core/authority/ceiling.py` (FR-004)
- [X] T020 [US1] [GATE:fail-closed] Refuse `missing_ceiling_record` when a definition is registered but has no harness ceiling, and **never infer either jurisdiction from the other** (FR-005). That substitution is how a secrets grant quietly becomes a tool grant
- [X] T021 [US1] [GATE:fail-closed] Refuse `unknown_ceiling_entry`, **naming the entry**, when a ceiling names a tool or product action the platform does not know (FR-005a). Silently dropping it narrows a ceiling with no trace, which is a change to authority nobody can audit
- [X] T022 [US1] Record both **declared and effective** `ceiling_policies` — in the resolution's audit payload, where an investigator will look — when reading a registration (research Finding 2). Vault appends `default` and `default-ceiling` unless `no_default_ceiling_policy` is set, which this repository has never set. A reader seeing only its own declaration is reading something that does not exist
- [X] T023 [P] [US1] [GATE:conformance] Enclave row in `tests/conformance/identity/test_ceiling_from_registry.py`: two definitions, two ceilings, different manufactured authority, neither exceeding its record — **via the hybrid fabric (T010a)**: ceiling resolves through the production fabric, the other terms through the fake, carrying the `HYBRID` transitional marker (T010a). Depends on T009 — against the current fixture this passes whether enforcement works or not. *(SC-002's dispatched end-to-end claim lands at T038c, once the run path is wired; this row proves the term, not the plumbing.)*
- [X] T024 [P] [US1] [GATE:conformance] Enclave row in `tests/conformance/identity/test_jurisdictions_stay_disjoint.py`: a registration with a credential policy and no harness ceiling refuses. **Break fixture**: a reader that falls back to `ceiling_policies` — plausible as a "be resilient" change, and it converts a secrets grant into a tool grant
- [X] T025 [P] [US1] [GATE:conformance] Row in `tests/conformance/identity/test_declared_vs_effective.py` asserting the appended default policies are observed and accounted for rather than discovered later

---

## Phase 5: User Story 2 — the user's scope comes from their identity (Priority: P2)

**Goal**: harness-domain scope derives from verified claims through governed mappings.

**Independent test**: two users whose claims map to different roles get different authority
for the same run request.

- [X] T026 [US2] Resolve roles to a scope via the role-binding records in `src/core/authority/vault_fabric.py`, consuming `resolve_roles` from `core/identity/claims.py` (FR-006). 008 built claims→roles and 007 governs the mappings; only roles→scope is missing
- [X] T027 [US2] [GATE:fail-closed] Take the **union** of multiple roles' bindings in `src/core/authority/vault_fabric.py` before intersecting downstream. Union is the only choice that makes adding a role additive — intersection would let a second role *remove* access, which nobody would predict from being granted one
- [X] T028 [US2] [GATE:fail-closed] Keep the three "no scope" cases distinct (FR-007): `no_role_for_subject`, `unbound_role`, and a legitimately empty binding. Nobody knows who you are, nobody has said what your role means, and your role means nothing — only the third is a real empty scope, and collapsing them makes a platform failure look like a permissions decision
- [X] T029 [P] [US2] [GATE:conformance] Enclave row in `tests/conformance/identity/test_scope_from_claims.py` (SC-004): two users, two roles, measurably different authority — via the hybrid fabric (T010a), user scope real, carrying the `HYBRID` transitional marker
- [X] T030 [P] [US2] [GATE:conformance] Row covering all three "no scope" cases and asserting three different reason codes (SC-005). **Landed in `tests/component/test_vault_fabric_resolution.py` rather than the unit file the task named**: the cases are behaviour of the real fabric over a controlled transport, which is what a component row is, and a unit file would have had to re-stub the same transport to say the same thing. The fourth case is there too — a role bound to nothing, which must NOT raise, because it is the only one of the four that is an answer about permissions rather than about the platform

---

## Phase 6: User Story 3 — policy is read live (Priority: P3)

**Goal**: a mid-run narrowing bounds the next step; an outage suspends rather than stops.

**Independent test**: narrow policy mid-run against a live fabric and observe the next step bounded.

- [X] T031 [US3] Read policy from the trust fabric in `src/core/authority/vault_fabric.py` **on each step, with no cache** (FR-008). A cached scope used past its freshness bound is a stale permission, and a narrowing that takes an interval to bite is weaker than the guarantee 005 asserts
- [X] T032 [US3] [GATE:fail-closed] Ensure a mid-run **widening** does not enlarge the grant issued at run start, in `src/core/authority/manufacture.py` (FR-009). Narrowing binds immediately; widening waits for a new run
- [X] T033 [US3] [GATE:fail-closed] Suspend naming `trust-fabric` when the fabric cannot be reached mid-run (FR-008a), through 009's `suspend_run(run, *, awaiting=...)` in `src/core/durability/resume.py`. `awaiting` is a free string, so the seam already accepts this — verified in the plan's seam table rather than discovered here
- [X] T034 [US3] [GATE:fail-closed] Refuse rather than suspend in `src/core/run.py` when the fabric is unreachable **at run start**. There is no grant, no checkpoint, and nothing to resume — the asymmetry falls out of a run existing or not existing yet, and is not a special case
- [X] T035 [US3] Assert the **recovery ordering** in `src/surfaces/mcp/server.py`'s supervisory pass and in `tests/conformance/identity/test_recovery_order.py` (FR-008b), consuming T036a's probe — the ordering row is vacuous until something can actually record the fabric healthy: fabric returns → checker login succeeds → credentials obtained → health recorded → sweep resumes. **The trust fabric is a dependency of the mechanism that monitors dependencies**, so this is the only order that terminates. Nothing else in this platform has this property and no existing row asserts an ordering constraint of this kind
- [X] T036 [US3] [GATE:fail-closed] Ensure nothing that failed to reach the fabric can mark it healthy, in `src/core/dependencies/store.py` (FR-008c). A monitor that cannot run leaves the state unknown, and unknown already refuses
- [X] T036a [US3] [GATE:fail-closed] Implement the **trust-fabric probe** in the MCP service's health pass (`src/surfaces/mcp/server.py`): a successful credential acquisition records `trust-fabric` healthy in the dependency store; a failed one records unreachable. **Pass 2 found SC-006a had no mechanism**: the only probe in the platform is `unconfigured_probe`, which reports unreachable, and "trust-fabric" is not a registered product — so its state stays UNKNOWN forever, `permits_calls()` never becomes true, and the sweeper never resumes a fabric-suspended run. The probe is deliberately not a new check: **the checker's own login is the probe**, which is FR-008b's ordering made executable — the pass cannot record healthy without having first obtained credentials, so the order asserts itself
- [X] T037 [P] [US3] [GATE:conformance] Enclave row in `tests/conformance/identity/test_policy_read_per_step.py` (SC-006), via the hybrid fabric (T010a), policy real: a mid-run narrowing bounds the next step, with **zero steps served from cache**. **Break fixture**: a resolver caching policy for a few seconds — an obvious optimisation, and the row that catches it is the zero-cached-steps assertion, not the one asserting the narrowing eventually applies
- [X] T038 [P] [US3] [GATE:conformance] Enclave row in `tests/conformance/identity/test_fabric_outage_suspends.py` (SC-006a): the run suspends naming the fabric, holds no container, and resumes with **zero operator actions**

---

## Phase 6a: Integration — the run path uses the production fabric

**Goal**: the mechanism built in US1–US3 is the thing dispatched runs actually resolve through.

**Why a phase of its own, after US3 and before US4**: `manufacture_authority` resolves user
scope, ceiling, and policy from one fabric object, so the wiring needs all three real —
which is exactly why pass 1's wiring task (placed inside US1) could not work, and why pass 2
moved it here. Entitlements are not needed first: the production fabric's
`resolve_product_entitlements` refusing `entitlement_unavailable` until US4 configures the
seam is fail-closed behaviour, not absence.

- [X] T038a Move the dispatched-run entrypoint from `tests/harness/dispatched_run.py` to `src/surfaces/dispatch/entrypoint.py` — beside the dispatcher whose jobs invoke it — completing what T016 recorded (FR-015). The reason it lived under `tests/` — no fabric to resolve through — expires at this task and not before. Update `infra/jobs/agent-run.nomad.hcl`'s command to the new module path, or the job dispatches an entrypoint that no longer exists
- [X] T038b [GATE:conformance] **Construct the production fabric in the run path**: the moved entrypoint and the surface assembly in `src/surfaces/api/app.py` build `VaultIdentityFabric` and pass it to `start_governed_run`, replacing the fake. The task pass 1 named G2 and placed where it could not work; every task before this builds the mechanism, and this is the thing it acts through
- [X] T038c [GATE:conformance] Dispatched end-to-end row in `tests/conformance/identity/test_dispatched_end_to_end.py` (SC-002): a run dispatched through the real entrypoint, resolving every term from the live trust fabric under an attested identity, bounded by the registered ceiling. **This is the row that proves the plumbing** — T023 proved the term through the hybrid; a feature that stopped there would have a correct fabric nothing instantiates
- [X] T038d [GATE:conformance] **Wire the identity rows into a lane that can run them** — pass 4 found they had none. Add `tests/conformance/identity` to the in-allocation pytest command in `infra/jobs/conformance.nomad.hcl`, and exclude the directory **by path** from the host lanes in `Makefile` (`conformance` line 1 and `conformance-hermetic`). The durability pattern, not the api one: these rows construct `NomadWorkloadIdentity`, which raises outside an allocation, so the host `-m enclave` lane fails them on identity and the hermetic lane fails them on the missing enclave — there is no host lane that works, and without this task `make conformance` at T053 either skips the feature's rows silently or fails all of them in a way that reads as a Vault regression. Include the negative control: assert the host lanes collect **zero** identity rows. *(Eleventh instance of the seam pattern — rows specified without the runner that executes them — and the first found by asking "who runs this file" instead of "what does this file assert")*

---

## Phase 7: User Story 4 — entitlement mirroring asks something real (Priority: P4)

**Goal**: the user's own product entitlements are resolved through a real seam and enforced.

**Independent test**: a user narrower than the credential cannot exceed themselves.

- [X] T039 [US4] Define the entitlement-resolution seam in `src/core/authority/entitlements.py` — ours, real — and implement it on `tests/harness/fake_product_api.py`. The product's authorization system is outside our boundary and correctly stays faked; the interface that asks it is not (spec C2)
- [X] T040 [US4] [GATE:fail-closed] Refuse `entitlement_unavailable` when a product cannot be asked (FR-011). Unknown entitlement is not empty and is certainly not full
- [X] T041 [US4] [GATE:fail-closed] Keep both authorization domains independent in `src/core/hooks/mirroring.py` — either refusing refuses the call (FR-010, ADR-0044). Two checks that must agree are not one check consulted twice
- [X] T042 [P] [US4] [GATE:conformance] Row in `tests/conformance/identity/test_mirroring_bites.py` (SC-007): a user narrower than the credential cannot exceed themselves, with **zero side effects** on the attempt
- [X] T043 [P] [US4] [GATE:conformance] Row in `tests/conformance/identity/test_broker_refuses.py` asserting the broker branch refuses `broker_not_implemented` rather than allowing on a placeholder (research Finding 6)

---

## Phase 8: Polish & cross-cutting

- [ ] T044 [GATE:fail-closed] Assert in `tests/conformance/identity/test_fabric_unreachable_from_a_tool.py` that with an **agent's own credential** the ceiling paths are denied **by Vault** (FR-016). A refusal produced by our code would satisfy the behaviour and miss the point — ADR-0015 puts the fabric structurally outside every agent ceiling, and "structurally" means the denial is not ours to make
- [ ] T045 [GATE:fail-closed] Extend `tests/unit/test_no_static_credentials.py` to cover the fabric's configuration and environment (FR-002, SC-010), reusing the assertion the durability and evidence paths already carry
- [ ] T045a [P] [GATE:conformance] Assert in `tests/unit/test_production_fabric_satisfies_protocol.py` that `VaultIdentityFabric` structurally satisfies `IdentityFabric` with **no method raising "not supported"** (SC-009, second half — a clean protocol nobody implements is as vacuous as a dirty one everybody does). Here rather than in US5, where pass 1 put it and pass 2 found it asserting a class that did not exist yet
- [ ] T046 [GATE:conformance] Break fixture in `tests/conformance/identity/test_break_empty_scope_on_error.py`: **a fabric returning an empty scope on error**. Every "denied" row still passes, because denial is what an empty scope produces — only the reason code fails. This is the most likely regression in the feature, since returning `AuthorityScope()` in an exception handler is the shortest path and reads as fail-closed
- [ ] T046a [GATE:conformance] **Sweep every existing row that resolves authority through the fake** (FR-014, SC-001) — the task without which this feature's headline criterion is false on its own merge commit. For each conformance and component row importing `fake_identity_fabric`: migrate it to the production fabric where its subject allows, or mark it fault-injection with the explicit statement FR-014 requires. **Migrate every `HYBRID`-marked row to the full production fabric and delete `tests/harness/hybrid_fabric.py`** — the hybrid is scaffolding, FR-014's "fault injection only" cannot describe it, and scaffolding that survives its purpose becomes the next feature's precedent. Record the resulting mapping — which rows moved, which stayed and why — in `contracts/conformance-identity.md`, which is FR-019's deliverable and falls out of this sweep rather than being written separately
- [ ] T046b [P] [GATE:conformance] Gate check in `tests/unit/test_fake_fabric_is_fault_injection_only.py`: no conformance or component row imports the fake without the fault-injection marker, **and zero rows import `hybrid_fabric` at all** (SC-001, mechanically). The second assertion closes the loophole pass 3 found in pass 2's mechanism: a row reaching the fake *through the hybrid* passes a direct-import check unmarked, so the check the hybrid's own author wrote was bypassable by the hybrid — one level of indirection is all it took. Checking for zero hybrid importers after T046a's deletion is cheaper and stricter than resolving transitive imports. **Imports resolved by AST, not by string match**, with a positive control — this repository has had five checks match prose instead of code, and a grep for the fake's name would match the marker comments this check requires
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
  └─> Phase 2 Foundational (T003–T010a)         [T009 blocks every enclave row;
        │                                        T010a is what makes the stories
        │                                        independently provable at all]
        └─> Phase 3 US5 protocol (T011–T016)     [sealed core; everything sits on it]
              ├─> Phase 4 US1 ceilings (T017–T025)   🎯 MVP (term proven via hybrid)
              ├─> Phase 5 US2 user scope (T026–T030)
              ├─> Phase 6 US3 policy + fabric health (T031–T038)
              │     └─> Phase 6a Integration (T038a–T038c)
              │           [needs US1+US2+US3: manufacture resolves scope, ceiling,
              │            AND policy from one fabric object — entitlements refuse
              │            fail-closed until US4, which is behaviour, not absence]
              └─> Phase 7 US4 entitlements (T039–T043)
                    └─> Phase 8 Polish (T044–T053)
                          [T046a needs all four stories real AND the integration
                           landed — a row can only migrate off the fake once its
                           resolution has somewhere real to go; T046b needs
                           T046a's markers to exist]
```

**Three orderings are not free**:

1. **US5 before US1–US4** despite being P5. A sealed-core protocol change made after three
   implementations exist means changing three implementations.
2. **T009 before every enclave row.** The current fixture's ceiling grants a path under an
   unmounted mount, so rows written against it are green regardless of enforcement.
3. **Integration after US3, not inside US1.** The run path resolves three terms from one
   object, so wiring the production fabric in before all three exist breaks every dispatched
   run — pass 1 placed the wiring task inside US1 and pass 2 caught it.

**US1, US2, US3, US4 are independent of each other** once US5 lands — *through the hybrid
fabric (T010a)*, which is what makes the claim true rather than aspirational: each story's
rows exercise their own term against the production fabric while the others resolve through
the fake, carrying the `HYBRID` transitional marker, fully migrated and the hybrid deleted
at T046a. The **dispatched run path** is not
independent; it is Phase 6a, and it needs three stories done.

## Parallel opportunities

- **Phase 2**: T005 and T006 are separate Terraform files; T008 is a test
- **Phase 3**: T014 and T015 are separate test files over separate concerns
- **Phase 4**: T023, T024, T025 are three separate row files
- **Phase 5**: T029 and T030
- **Phase 6**: T037 and T038 (T036a precedes T035's row)
- **Phase 6a**: T038a→b→c are deliberately sequential — move, wire, prove, in that order; T038d (lane wiring) is independent of the chain
- **Phase 7**: T042 and T043
- **Phase 8**: T046b runs beside T046a's tail; T048–T052 are documentation in different files

## Implementation strategy

**MVP is Phase 1 + Phase 2 + Phase 3 + Phase 4** — through T025. That proves the property
the feature exists for — an agent's ceiling comes from what an operator configured, enforced
against a live trust fabric — via the hybrid harness, with the other terms still faked and
marked. **The dispatched end-to-end claim is deliberately not in the MVP**: it lands at
Phase 6a, because the run path needs scope and policy real too, and claiming end-to-end
before then would be claiming the plumbing while only the term is proven.

**Stop-and-check point after T012.** Making the broker branch refuse is a behaviour change to
a path that currently returns `allow`. If anything depends on that `allow` — including a test
— it will surface there, and it is better to find it in a two-task phase than in a fifty-task
one.

## Task count

**62 tasks** — 2 setup, 9 foundational, 6 US5, 9 US1, 5 US2, 9 US3, 4 integration, 5 US4,
13 polish.

Nine exist because analyze looked, across four passes. Pass 1 added the SC-001 sweep and its
enforcement (T046a/T046b) and a wiring task; pass 2 found that wiring task could not work
where it sat — the run path resolves three terms from one fabric object — and replaced it
with the hybrid harness (T010a), the Integration phase (T038a–c), and the trust-fabric probe
(T036a), without which no fabric-suspended run would ever have resumed. Three of pass 2's
four findings were introduced by pass 1's remediation, which is the same fix-introduces-defect
streak every 008 and 009 pass showed — recorded here because the next feature's passes should
expect it rather than be surprised by it.
