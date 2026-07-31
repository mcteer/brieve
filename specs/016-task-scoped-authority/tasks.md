# Tasks: Task-scoped authority manufacture

**Input**: Design documents from `/specs/016-task-scoped-authority/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included, and decisive. SC-002 is the whole feature — a refusal issued by the trust
store rather than by our own code — and it cannot be asserted hermetically, because a double
refuses exactly what the test tells it to. The rows against a live Vault are what distinguish
this work from the per-action enforcement that already passes.

**Organization**: Setup (activate and configure the substrate) → **T004, which is a research
task and blocks everything** → Foundational (scope derivation, grant, token) → US1–US5 in
priority order → Polish.

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | A tool with no declared paths refuses the launch (T012); an undetermined scope refuses rather than granting broadly |
| **Conformance** | The twelve rows in `contracts/conformance-task-authority.md`, host_enclave, against a live Vault with the flag activated |
| **No-secret-leak** | The grant record is not a credential (T031); no key material outside Vault (T016) |
| **Correlation / evidence** | The launch decision, refusals, and arrangement in force all recorded and walkable (T024, T027) |

## Path Conventions

Single project: `src/`, `tests/`, `infra/`, `packs/` at repository root. Conformance rows join
a **new** `tests/conformance/authority/` directory, wired into the Makefile host lane **in the
same change that creates it** (T005).

---

## Phase 1: Setup — the substrate is configured and reversible

- [ ] T001 Create `infra/modules/trust-fabric/task-authority.tf`: a transit mount and an `ecdsa-p256` key named for the grant issuer. Comment records F3 — `marshaling_algorithm=jws` is valid for ECDSA P-256 only, so ES256 is forced rather than chosen, and the private key never leaves Vault, which is what makes ADR-0056's "no second standing credential" true rather than mitigated.
- [ ] T002 Extend `infra/bin/enclave-up` to activate `oauth-resource-server` via `sys/activation-flags/oauth-resource-server/activate`. Record F1 inline: the flag is **reversible** — both directions were exercised — so this is an ordinary bring-up step rather than a staged migration, and `make dev-up` stays the single description of what an enclave is.
- [ ] T003 Add the resource-server profile to `task-authority.tf`: `issuer_id`, `audiences`, `jwt_type=access_token`, `use_jwks=false`, and `public_keys` carrying the transit key's exported PEM with a `key_id`. **Two traps recorded inline, both cost an hour to find** (F2): `public_keys` entries must be JSON objects — the CLI's `key=value` form fails with `public_key at index 0 must be an object` — and `use_jwks` defaults to **true**, so omitting it fails with `jwks_uri is required` even when keys are supplied. Terraform's `vault_generic_endpoint` sends JSON, so the first trap does not bite there; the second does.

**Checkpoint**: `make dev-up` brings up an enclave with the flag on, a transit key, and a profile trusting it. Nothing validates yet — T004 is why.

---

## Phase 2: Foundational (blocking every user story)

### The question that gates the feature

- [ ] T004 **[BLOCKS ALL]** Establish how a grant's subject binds to a Vault Identity entity, and record the answer in `specs/016-task-scoped-authority/research.md` as F5's resolution. With a valid signature, valid schema, and RAR details present, Vault refuses with `no alias found` / `error looking up entity`, and none of `sub`=entity UUID, `sub`=display name, matching `client_id`, or an alias against the profile's `config_id` binds. Work the three routes quickstart section 0 names, in order: HashiCorp's `hashicorp-education/learn-vault-agentic-iam`; `vault path-help identity/entity-alias` for what accessors it accepts; a temporary audit device for a structured view of the resolution attempt. **Do not proceed past this task on an assumption** — every row below sits behind a grant validating, and a design built on a guessed binding looks complete and fails at the first live row.

### The lane, wired at birth

- [ ] T005 Create `tests/conformance/authority/` with `__init__.py` and `conftest.py`, and add the directory to the `host_enclave` line in `Makefile` **in this same task**. The conftest documents the marker discipline every row file carries — `pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]`, both — and provides the operator-token Vault client the rows need. 010 lost a feature's rows to a directory no lane enumerated; 014 lost ten more to a directory a lane named but deselected. Wire it at birth; correct nothing later.

### Scope derivation

- [ ] T006 Add a `paths` field to the tool manifest model in `src/core/packs/manifest.py`: a list of `{path, capabilities}` objects. Comment records F7 — no tool declares what it touches today, so this is the one additive declaration the derivation needs.
- [ ] T007 [GATE:fail-closed] Enforce in `src/core/packs/registration.py` that a tool whose `risk_class` is `secret_touching` **must** declare `paths`; the loader refuses otherwise. Same shape as 013's rule that a non-repeatable tool must declare an observer, and for the same reason: the declaration is what makes the governance decidable. A tool that has not said what it touches cannot be granted it.
- [ ] T008 [P] Declare `paths` for every tool in `packs/vault/pack.toml` and `packs/terraform/pack.toml`. `vault_read` and `vault_write` are `secret_touching` and T007 now requires it.
- [ ] T009 Create `src/core/authority/scope.py` with `EntailedScope`: derive `path → capabilities` from a run's requested tools via their manifests, tracking tools whose declaration is missing. Templates like `{agent}` expand to concrete paths here — **Vault RAR matches exactly**, so a wildcard surviving into `authorization_details` is a path that matches nothing (data-model).
- [ ] T010 [P] Hermetic rows in `tests/unit/test_entailed_scope.py`: a subset of tools yields a subset of paths; templates expand; an undeclared tool lands in `undetermined`; an empty tool set yields an empty scope, which is **valid** rather than an error (spec Edge Cases).

### The grant and its token

- [ ] T011 Extend `DelegationGrant` in `src/core/authority/grant.py` with `entailed_paths` and `arrangement`. **`DelegationGrant`, `issue_grant`, and the provider's `save_grant`/`load_grant` already exist** (005/014) — this adds fields to the consent record that is already durable, and does not introduce a second grant object. Two grant records for one consent would be the fragmentation Principle VII forbids.
- [ ] T012 [GATE:fail-closed] Extend `issue_grant` to refuse when the entailed scope is undetermined (FR-004), and to assert `entailed_paths ⊆ the definition's ceiling paths` (FR-003). Over-granting to be safe is how a ceiling becomes decorative; refusing is the direction Principle III requires.
- [ ] T013 Extend `src/core/authority/vault_fabric.py` to read the ceiling **policy's** paths, which is what T012 bounds against. F6: this is the secrets half of the ceiling, disjoint from the harness half in `harness-ceilings/` — reading it here adds no rule to an engine that does not own it.
- [ ] T014 Create `src/core/authority/grant_token.py`: assemble the RAR JWT — `iss`, `aud`, `sub`, `jti`, `iat`, `nbf`, `exp`, and `authorization_details` of type `vault:path_access`. **`jti` is mandatory** (F4): its absence is a hard schema failure, and the reason appears only in Vault's server log while the caller sees a bare 403.
- [ ] T015 Sign in `grant_token.py` via `transit/sign/<key>` with `hash_algorithm=sha2-256` and `marshaling_algorithm=jws`, assembling `header.payload.signature` from Vault's response. No key material in this module or any other.
- [ ] T016 [GATE:no-secret-leak] Hermetic rows in `tests/unit/test_grant_token.py`: the assembled token carries every mandatory claim; `authorization_details` matches the entailed scope exactly; **no signing key material appears anywhere in the module, its inputs, or its outputs** — the only credential in play is the Vault token the issuer holds from its own attested identity.

**Checkpoint**: a grant can be computed, bounded, minted, and signed. T004 has established that Vault will resolve it. User stories can begin.

---

## Phase 3: User Story 1 — A run holds only what its task needs (P1) 🎯 MVP

**Goal**: A run's credential reaches what its task entails and is refused the rest of the definition's ceiling — with the refusal issued by Vault.

**Independent Test**: Launch a run whose tools entail path A, attempt path B which the ceiling permits and the task does not, and confirm B is refused by the trust store.

- [ ] T017 [US1] Mint the grant at launch in `src/surfaces/api/runs.py`: derive the entailed scope from `requested_tools`, issue the grant, sign the token. This lives on the path that already holds an attested workload identity and already talks to Vault — **no new long-lived component** (plan, F2).
- [ ] T018 [US1] Carry the task-scoped token to the run's allocation so tool handlers use it instead of the role-bound token, in `src/surfaces/dispatch/entrypoint.py` and the pack tool bindings.
- [ ] T019 [P] [US1] Component rows in `tests/component/test_task_grant_launch.py`: a launch produces a grant whose paths match the requested tools; a launch with an undeclared tool refuses; the grant never exceeds the ceiling.
- [ ] T020 [US1] [GATE:conformance] Row in `tests/conformance/authority/test_grant_reaches_its_task.py`: a run whose tools entail P reads P (SC-003 — zero false refusals), and is refused Q which the definition's ceiling permits (SC-001). Read the refusal's **reason from Vault's server log**, not from the status code — every RAR rejection presents as an indistinguishable 403 (F4), so a row asserting "403 therefore RAR worked" would pass for the wrong reason on a malformed token.
- [ ] T021 [US1] [GATE:conformance] Row in `tests/conformance/authority/test_the_refusal_is_vaults.py`: present the grant **directly to Vault**, with the in-process hook pipeline entirely out of the picture, and confirm Q is still refused (SC-002). **This is the row the feature exists for** — every other refusal in this system is one our own code produced, and this is the one that holds when our code is wrong.
- [ ] T022 [US1] [GATE:conformance] Row in the same file: a grant naming a path **outside** the ceiling is refused even though the grant names it (FR-003) — the intersection is restrictive in both directions, not just ours.

**Checkpoint**: US1 complete. The feature's central claim is demonstrated against a live trust store.

---

## Phase 4: User Story 2 — The person is asked once, at the start (P1)

**Goal**: Exactly one authorization decision per launch, attributed to the authenticated person, with no mid-run re-asking.

**Independent Test**: Launch a multi-step run; count authorization decisions; confirm one, at launch, naming the person.

- [ ] T023 [US2] Enforce and record the single decision in `src/surfaces/api/runs.py`: the entitlement intersection (`user ∩ ceiling ∩ task`) is evaluated once and the outcome recorded on the grant. Steps consume it; nothing re-evaluates (FR-005).
- [ ] T024 [US2] [GATE:correlation] Emit the launch decision to the audit trail with the person, the task, and the resulting scope — counts and paths, never secret values. Refusals recorded too (FR-009/010).
- [ ] T025 [P] [US2] Component rows in `tests/component/test_one_decision_per_launch.py`: a multi-step run triggers exactly one decision; a person beyond their entitlements is refused at launch.
- [ ] T026 [US2] [GATE:conformance] Row in `tests/conformance/authority/test_one_decision_per_launch.py`: count exchanges across a multi-step run (SC-004); a person whose entitlements do not cover the task is refused at launch and the refusal is recorded naming person and task (SC-005), read through the evidence path.

**Checkpoint**: US1 and US2 both independently demonstrated.

---

## Phase 5: User Story 3 — A disrupted run resumes without a person present (P2)

**Goal**: A resumed run operates under the launch grant's scope, with nobody there to consent.

**Independent Test**: Kill a run mid-task, let it resume, compare the resumed grant's scope to the launch grant's.

- [ ] T027 [US3] Re-derive the grant token on resume in `src/surfaces/dispatch/entrypoint.py`, from the **recorded grant** under the platform's own attested identity, bounded by the recorded expiry (FR-015/015b). The record is a **ceiling on the resume**, never a seed for a fresh decision — a resume that re-derived from the request would let scope drift.
- [ ] T028 [US3] Confirm the existing grant-expiry path stops the run rather than resuming it when the recorded expiry has passed (FR-014, ADR-0049). This is assertion against machinery that already exists, not new behaviour.
- [ ] T029 [P] [US3] Component rows in `tests/component/test_resume_keeps_its_scope.py`: the re-derived scope equals the recorded scope; an expired grant stops; nothing durable is written that could widen it.
- [ ] T030 [US3] [GATE:conformance] Row in `tests/conformance/authority/test_resume_keeps_its_scope.py`: disrupt a run mid-task, resume it, assert the scope is identical — neither wider nor narrower — with no person present (SC-006).
- [ ] T031 [US3] [GATE:no-secret-leak] [GATE:conformance] Row in the same file: present the **recorded grant's bytes directly to the trust store** and assert it obtains nothing (SC-006a). This is what makes "the record is data, not a credential" falsifiable rather than asserted.

**Checkpoint**: long-running work survives disruption without widening or standing credentials.

---

## Phase 6: User Story 4 — An operator can see which protection is in force (P2)

**Goal**: The arrangement in force is reported plainly, including when it is the weaker one or absent.

**Independent Test**: Configure each arrangement in turn and read the posture; each reports as itself with a reason.

- [ ] T032 [US4] Detect and report the arrangement in `src/surfaces/mcp/server.py`'s supervisory reporting: `federated`, `platform_issued`, or `absent`, each with a reason (FR-016/017). Detection reads the resource-server profile and whether a customer IdP is configured for exchange.
- [ ] T033 [P] [US4] Component rows in `tests/component/test_authority_posture.py`: three arrangements, three distinct reports, three distinct reasons; the unconfigured case reports `absent` **plainly** rather than defaulting to a value that reads as protected (FR-018).
- [ ] T034 [US4] [GATE:conformance] Row in `tests/conformance/authority/test_posture_names_the_arrangement.py`: configure each arrangement against the live enclave and assert the report matches what is actually operating (SC-008), including the unconfigured case.

**Checkpoint**: an operator can no longer hold a false assurance about which protection they have.

---

## Phase 7: User Story 5 — A task cannot quietly widen its own authority (P3)

**Goal**: Work outside the granted scope is refused and recorded, distinguishably from a ceiling refusal.

**Independent Test**: Launch a run, attempt work outside the grant, confirm refusal and its recorded cause.

- [ ] T035 [US5] Distinguish the two refusal causes in the audit payload — "outside the granted task" versus "outside the agent's ceiling" (FR-010). Different causes with different remedies: one is re-consent, the other is a ceiling change.
- [ ] T036 [P] [US5] Component rows in `tests/component/test_grant_refusals_name_their_cause.py`: both causes recorded distinctly; neither carries a secret value.
- [ ] T037 [US5] [GATE:conformance] Row in `tests/conformance/authority/test_a_task_cannot_widen_itself.py`: a run attempting work outside its grant is refused, the refusal recorded, and the cause named (US5 scenarios).

---

## Phase 8: Polish & Cross-Cutting

- [ ] T038 [P] Update `docs/glossary.md`: `task grant`, `entailed scope`, `rich authorization request`, `resource server`, `arrangement (federated / platform-issued / absent)` — cross-referenced to the ceiling terms already there.
- [ ] T039 [GATE:conformance] Row asserting **tool authority is unchanged** by this feature: the same run's tool decisions are identical before and after (SC-009a). A row proving the *absence* of an effect, which is what FR-011a promises.
- [ ] T040 Confirm the standing-credential count is unchanged (SC-009): the issuer holds a Vault token from its own attested identity and no key, and nothing new was added to the one named exception in Principle IV.
- [ ] T041 Apply the contract's four break fixtures (grant minted with ceiling paths; `jti` dropped; resume re-derives from the request; a tool's `paths` widened to a wildcard), watch each named row fail, revert, and record outcomes **In force** in `specs/016-task-scoped-authority/contracts/conformance-task-authority.md`. The `jti` fixture earns its place by making that failure mode — every row red with the reason only in Vault's log — familiar before it is met under time pressure.
- [ ] T042 Close the ROADMAP's RFC 8693 + RAR row naming this feature, and confirm the three "what these rows do not prove" limits (narrowing only as tight as tool declarations; no containment claim for a compromised allocation; nothing established about customers' IdPs) are stated in the contract and overclaimed nowhere in spec, plan, or ADR-0056.
- [ ] T043 Run `make check`, `make conformance` (full, live enclave, clean tree), and walk `specs/016-task-scoped-authority/quickstart.md` sections 1–6. Record rows **In force** in the contract.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001–T003)**: no dependencies.
- **T004**: depends on Setup, and **blocks everything else in the feature**. It is a research task with an unknown answer, and it is scheduled first because nothing downstream can be demonstrated until a grant validates.
- **Foundational (T005–T016)**: T005 can run beside T004; T006–T016 depend on T004 only insofar as they should not be *finished* against an unvalidated assumption — they can be written, but not proven.
- **US1 (T017–T022)**: depends on Foundational.
- **US2 (T023–T026)**: depends on Foundational; independent of US1.
- **US3 (T027–T031)**: depends on Foundational and on US1's minting path.
- **US4 (T032–T034)**: depends on Foundational only.
- **US5 (T035–T037)**: depends on US1.
- **Polish (T038–T043)**: depends on the stories being delivered.

### Parallel opportunities

- T008 and T010 run beside their siblings; T019, T025, T029, T033, T036 are all `[P]` component rows against different files.
- US2 and US4 are genuinely independent of US1 and of each other — with capacity, three people could take US1, US2, and US4 concurrently once Foundational lands.
- **T004 parallelises with nothing**, and pretending otherwise is how a plan discovers in week two that it was week one's work.

### MVP

**Setup + T004 + Foundational + US1.** That delivers the feature's central claim — a run holds only what its task needs, and Vault is what refuses the rest. US2–US5 add attribution, durability, honesty, and refusal clarity on top of a property that already holds.

---

## Notes

- **Eval gate omitted deliberately**: this feature promotes no pack, prompt, model, or policy, so Principle VIII is N/A — recorded here rather than left as a silent absence.
- The `[P]` marker means different files and no dependency on incomplete work.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- **T004 is the honest risk in this plan.** If the entity binding turns out to require something the platform cannot supply — a customer IdP feature, or a Vault configuration the enclave cannot express — the tier analysis in ADR-0056 changes and the ADR should be amended before the code is. That is a better outcome than discovering it in T020.
