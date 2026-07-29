# Tasks: Capability Packs and Eval Gates

**Input**: Design documents from `/specs/013-capability-packs/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. This feature *is* a gate discipline — a version of it without tests
would be the passing stub ADR-0047 forbids, wearing the feature's own name.

**Organization**: Setup → Foundational (the seams every story needs) → US1–US5 in priority
order → Polish & gates. Gate tasks are tagged and live in the phase that delivers the
behaviour they guard.

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | Unqualified cell, withdrawn cell, no-fallback stop, tier violation, digest mismatch, incomplete promotion |
| **Conformance** | Four eval suites; the structural rows (product-blind core, no bypass, no widening, no auto-tracking); the live-model lane |
| **Correlation / evidence** | `MODEL_GATE`, `MATRIX_FALLBACK`, provenance-at-read into the run record |
| **Eval** | The whole of Phase 8 — this is the feature that brings them online |
| **No-secret-leak** | The provider key is a dev-lane secret: never in a jobspec, never read by a run, never in a pack |

## Path Conventions

Single project: `src/`, `tests/` at repository root. **`packs/` and `evals/seed/` at the
repository root** rather than under `src/` — they are content, and product knowledge inside
the Python package tree would ship in the distribution that Principle I says is
product-blind.

---

## Phase 1: Setup

- [X] T001 Add an `evals` dev extra to `pyproject.toml` carrying the scoring harness and, for the live lane only, one model-provider SDK. Comment why it is an extra and not a base dependency: the platform's default posture is "calls no model", which `pyproject.toml` currently states in as many words, and this feature must not change that for anyone who is not running the live lane
- [X] T002 [P] Add `@pytest.mark.live_model` to `pyproject.toml`'s marker list with the reason inline — needs a paid credential and is non-deterministic, so it is never in a blocking lane
- [X] T003 [P] Create `packs/README.md` explaining why this directory is at the repository root: content, not code, and `src/core` stays product-blind
- [X] T004 [P] Create `evals/seed/README.md` — the root of the judge chain (ADR-0052). It states that these labels are a human's judgement, that they are reviewed like code, and that a seed set which stops being representative silently weakens every gate above it

**Checkpoint**: `make check` green with the new extra resolving.

---

## Phase 2: Foundational (blocking all user stories)

**Purpose**: the manifest, the loader, the matrix reader, the registry field, and the two
audit events. No story is demonstrable until this phase completes.

### The two sealed-core additions

- [X] T005 Add `risk_class` to `ToolRegistration` and `ToolRegistry.register` in `src/core/registry/memory.py` — additive and defaulted so every existing caller is unchanged. The docstring records finding F2: this has been in the glossary since the beginning and in no code, so Principle II's provision for demanding process isolation on `secret_touching` and `destructive` tools has never been actionable
- [X] T006 Add `MODEL_GATE` and `MATRIX_FALLBACK` to `AuditEventType` in `src/core/audit/schema.py`. The `MODEL_GATE` docstring records F3 — there is no approval event to be confused with, so this **establishes** the distinction rather than repairing one, and when human approvals gain an event the two are already separate. `MATRIX_FALLBACK` is separate because "a model decided something" and "the model that ran was not the model that was pinned" are different questions

### Pack records and loading

- [X] T007 Create `src/core/packs/__init__.py` with the package intent: packs are content, the core stays product-blind, and a manifest declares while the platform decides
- [X] T008 [P] Create `src/core/packs/manifest.py`: `PackManifest`, `ToolDeclaration`, `RiskClass` (`read | write | destructive | secret_touching`), `SkillPin`, `WorkflowDeclaration`, **`PackHookDeclaration`** (`name`, `phase`, `capability_kind`, `handler`). Frozen dataclasses; `provenance` is `adopted | authored` and `adopted` requires an `upstream` table. **`ToolDeclaration` carries `observer`, `product_mode`, and `product`** — the first because the registry calls an observer *required in practice* for a non-repeatable tool (without one an interrupted step resolves to `CANNOT_DETERMINE` and parks the run, so every `write` and `destructive` pack tool would ship with 005's re-observation unreachable), the other two because the registry raises a `ValueError` when `product_mode != none` without them and a pack should refuse in its own vocabulary rather than surface a driver error
- [X] T009 [P] Create `src/core/packs/loader.py`: `PackLoader` protocol, `FilesystemPackLoader`, `InMemoryPackLoader`. Loading verifies **every content digest** and refuses `digest_mismatch` naming the file; refuses `observer_required` when a non-repeatable tool declares no observer; refuses `incomplete_product_binding` when `product_mode != none` without `product`/`product_action`; **refuses `governance_hook_from_pack` when any hook declares `capability_kind = governance`** — verification at load rather than at review, because review is when someone looked and load is when it matters
- [X] T010 Create `src/core/packs/registration.py`: manifest → `ToolRegistry` registrations with risk class preserved. **Loading executes nothing from the pack** — a declaration names a handler, and the handler is resolved from what the platform already provides
- [X] T011 Create `src/core/packs/isolation.py`: which packs a definition reaches, the no-widening check against its ceiling, and ambiguous-tool-name refusal. A tool name is qualified by its pack; an unqualified name reachable from two packs refuses rather than resolving by load order, because load order changes without anyone deciding it did
- [X] T010a [GATE:fail-closed] Register pack hooks in `src/core/packs/registration.py`, **non-governance kinds only**, and add rows in `tests/component/test_pack_hooks.py`: a pack declaring a `governance` hook is refused at load; a registered pack hook runs in its phase; **`GovernanceCapability` still runs first with pack hooks present**. `has_required_governance_hooks` identifies the built-ins by `capability_kind == GOVERNANCE`, so a pack able to register at that kind could satisfy the platform's own enforcement-is-whole check with its own hook — enforcement authored by whoever ships a pack, which is what Principle III exists to prevent
- [X] T010b [P] Row in `tests/component/test_pack_hooks_use_narrowed_context.py`: a pack hook does not read `HookContext.run`. That field says third-party hooks must not depend on it and that the context narrows before the Hook SDK seam ships — pack hooks are third-party and arrive **before** that seam, so a pack depending on `run` today is a pack the seam breaks tomorrow
- [X] T011a Create `src/core/packs/workflows.py`: `WorkflowRecord` (`name`, `minimum_tier`, `paved`) and tier comparison. **The manifest already declared `workflows[]` and nothing in the platform had a runtime shape for one**, so tiers had nothing to bound and US5's rows would have asserted a refusal against a concept that did not exist. Deliberately minimal — a workflow here is a named, tiered thing a definition may or may not run, which is all ADR-0045 needs; what a workflow *does* is pack content
- [X] T012 [P] Component rows in `tests/component/test_pack_loading.py`: manifest parsing, digest verification and its refusal, two packs side by side, ambiguous name refused, and that a malformed manifest refuses the whole load rather than partially loading. **Plus the two new refusals**: a non-repeatable tool with no observer, and a product-mode binding missing its product — both at load, both in the pack's vocabulary
- [X] T012a [GATE:fail-closed] Derive `KNOWN_TOOLS` / `KNOWN_ACTIONS` from loaded packs at the two sites that must agree with reality — `src/surfaces/api/service.py` and `tests/conformance/identity/conftest.py`. **`tests/unit/test_ceiling_record_shape.py` keeps its own literal vocabulary and gains a comment saying why**: it is a hermetic unit row about the *parser*, and pulling pack loading into it would put content on the fast lane to test something that has nothing to do with packs. **Without this the first real pack is unusable**: `parse_ceiling_record` refuses any ceiling naming a tool outside the known set (`unknown_ceiling_entry`), so a Vault pack declaring `vault_read` makes a correct ceiling record look like a broken one, and the error points at the wrong artifact. `entrypoint.py` already derives from `registry.tool_names()` — it is the only site that does
- [X] T012b [P] [GATE:conformance] Row in `tests/conformance/packs/test_tool_vocabulary_comes_from_packs.py`: no hardcoded tool-name set survives in `src/` or in any lane that resolves a real ceiling. **`tests/unit/test_ceiling_record_shape.py` is a declared exemption with its reason inline**, on the `ENCLAVE_PATHS` pattern — an allowlist whose membership is asserted, so adding a second is a decision somebody makes on the record. Asserted structurally, because three copies of a constant is how the fourth gets missed. **Wire `tests/conformance/packs` into the Makefile conformance recipe in this same task** — the directory is created here and T043 would not wire it until Phase 8, leaving these rows unrun for six phases. 010 lost a feature's rows to a directory no lane enumerated; wiring at birth is the fix, and doing it later is the same gap in slow motion

### The matrix

- [X] T013 Create `src/core/evals/__init__.py` with the package intent: gates are records, not claims
- [X] T012c Create the **definition-bindings record** — `harness-authority/data/definition-bindings/<id>` carrying `packs[]`, `binding_map`, and `tier` — with its Terraform in `infra/modules/trust-fabric/`, written by the **same apply as the ceiling** so no window exists where a definition has one and not the other. Beside the ceiling rather than on the registration, for the reason `ceilings.tf` already records: the registry engine serves its own format. **This is the record the whole feature reads** — FR-005's isolation, the binding-map validation, and tier resolution all consume these three fields, and until analyze pass 8 they lived in the glossary and in four tasks' logic and in no record at all
- [X] T012d [P] Add the reader to `src/core/authority/vault_fabric.py` — `resolve_definition_bindings(agent_definition_id)`, refusing loudly when absent, on the 010 ceiling pattern
- [X] T013a [GATE:fail-closed] Grant `read` on `${vault_mount.harness_authority.path}/data/model-matrix/*` **and `data/definition-bindings/*`** in `infra/modules/trust-fabric/policies.tf`, beside the ceiling and role-binding grants. **Before T014, not in Polish** — the policy covers exactly two prefixes today, so without this the matrix is unreadable at run time AND Vault answers **403 rather than 404**, which makes "no matrix" indistinguishable from "not allowed to look" and reports an unreachable trust fabric for a matrix that merely lacks a grant. The `data/policies/*` block directly below documents this exact trap from 010; copy its reasoning rather than rediscovering it
- [X] T013b [P] Row in `tests/conformance/identity/test_matrix_is_readable.py` (`host_enclave`): the run role can read the matrix path against the live fabric. A row rather than a Terraform review, because the grant being present in HCL and the grant being effective are different claims — 010 learned that when the registry engine appended policies nobody had declared
- [X] T014 Create `src/core/authority/matrix.py`: `QualifiedCell`, the Vault-backed matrix reader (010's ceiling pattern — operator-authored, read-only to runs, refused loudly when absent), and `validate_binding_map`. Each cell carries `qualified_by` (`fixture | live`) and the judge that scored it. **In `core/authority`, not `core/evals`** — a cell is an authorization fact, it is read on the run path at every run start, and a matrix module inside a package named `evals` invites someone to import the scoring harness into a run. `core.evals` writes cells through this module; nothing on the run path imports `core.evals` at all
- [X] T015 [P] Extend `OPERATION_REASONS` in `src/core/runs/refusals.py` with this feature's vocabulary: `unqualified_cell`, `cell_withdrawn`, `no_qualified_fallback`, `pack_exceeds_ceiling`, `above_tier`, `digest_mismatch`, `promotion_incomplete`, `injection_suspected`, `insufficient_eval_coverage`, `pack_not_loaded`. Added to the frozen mapping rather than invented at call sites — the 010 rule
- [X] T016 [P] Component rows in `tests/component/test_matrix_reader.py`: a green cell resolves; an absent matrix refuses loudly rather than resolving to empty; `qualified_by` round-trips; **a model identifier that is not `provider/model@version` is refused at parse** — an alias or a bare name is the moving target FR-011 forbids, caught at the identifier rather than only at the lookup
- [X] T016a [P] [GATE:conformance] Row in `tests/conformance/packs/test_run_path_does_not_import_evals.py`: no module reachable from `core.run` imports `core.evals`. The layering I3 names, asserted rather than trusted to naming

**Checkpoint**: `make check` green; a pack loads and registers tools; the matrix reads.

---

## Phase 3: User Story 1 — A pack makes the platform competent at one product (P1) 🎯 MVP

**Goal**: two packs load, their tools are callable through the ordinary pipeline, and no
core module names a product.

**Independent test**: load both packs, start a run whose definition names one pack's tools,
watch them reach the same hooks every other tool does — then grep `src/core` for a product
name and find nothing.

- [X] T017 [US1] Create `packs/vault/pack.toml` and `packs/vault/skills/` — **authored**, in the same open Agent Skills format `hashicorp/agent-skills` uses (FR-027d), so contributing upstream is a pull request rather than a rewrite. Vault runs in the enclave, so this is the pack whose tools are exercised against a live product. Declare at least one `paved` workflow, so US5 has something a lower tier may run
- [X] T018 [US1] Vendor the Terraform pack: `packs/terraform/pack.toml`, `skills/` copied unmodified from [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) at a pinned commit, and `packs/terraform/skills/PROVENANCE.md` recording repository, commit, licence (MPL-2.0), and retrieval date. **Adopted**, which is what gives ADR-0004's supply chain a genuine subject. **The injection-lens review of this content happens at vendoring, here, and its result goes in `PROVENANCE.md`** — not deferred to T030's promotion path, which governs *bumps*. Content arriving for the first time has never been reviewed by anything, and treating first-import as a bump would let it in unread
- [X] T019 [US1] Replace the hand-built registry in `src/surfaces/dispatch/entrypoint.py` with pack loading — **the line a previous feature signposted** ("when they land, this is the line they replace"). Keep the fixture tools available for definitions that name no pack, so 008–012's rows are unchanged
- [X] T019a [US1] [GATE:fail-closed] Build `depends_on` from loaded manifests — tool name → `ToolDeclaration.product` — and pass it wherever `resume_run` is called, in `src/surfaces/dispatch/entrypoint.py`. **The parameter is constructed nowhere in the tree**: three occurrences, all inside `resume.py` itself, so every suspension today falls back to the tool name while `SuspendedRunIndex.awaiting()` matches on the **product**. That function's own docstring states the consequence — "a suspension carrying only a tool name will not be matched by a product recovering" — and it was harmless while every tool was `echo` and reached no product. A Vault pack tool reaches a real one, so without this a suspended step **never resumes and nobody is told**, which is precisely the human-out-of-the-loop claim ADR-0049 makes. Row in `tests/component/test_suspension_names_the_product.py`: a suspended pack-tool step awaits `vault`, not `vault_read`, and the sweeper matches it on recovery
- [X] T019c [US1] [GATE:fail-closed] Add `probe` to the manifest and resolve it into the `HealthChecker`: `PackManifest.probe` names a probe the platform provides (resolved the way T010 resolves tool handlers — **never pack code**, because the checker is the single owner of "reachable"), loading refuses `probe_required` when any tool declares a `product` and the pack names no probe, and `src/surfaces/mcp/server.py` supplies the resolved probes instead of falling through to `unconfigured_probe` for pack products. **Without this every Vault pack tool is denied while Vault is running fine**: `HealthChecker.products()` derives its subject set from `registry.products()`, so a pack's product is monitored the moment it loads — but `unconfigured_probe` returns `(False, "no probe configured for this product")`, which records `UNHEALTHY`, which makes `dependency_pre_hook` deny every call with `dependency_unavailable` naming a product that is up. 009's docstring states the assumption 013 breaks — "this platform fakes product APIs by constitutional decision, so there is nothing here to reach yet" — and FR-027b is exactly the feature that stops it being true. Refused at load, not discovered at the first denial, because the denial blames the product. Rows in `tests/component/test_pack_probe_is_required.py`: a pack declaring a product with no probe refuses at load; a pack with one records `HEALTHY` and its tools are not denied
- [ ] T019b [P] [US1] [GATE:correlation] Record the loaded packs and their content digests in the `RUN_START` payload in `src/core/run.py`. **FR-020's pinning holds per-load, not per-run**: `CheckpointBlob` carries no content identity, so a run resumed in a new allocation reloads `packs/` from disk and verifies digests *against the manifest sitting beside them* — edited content verifies clean and the run continues at a different skill version, silently. Payload only, so no seam moves. Row in `tests/component/test_run_record_names_its_packs.py`: the run record names each loaded pack and digest, and a run whose pack content changed between checkpoint and resume is distinguishable from one whose did not. This is what lets an attestation name the pack version the way FR-021 already makes it name consulted guidance
- [X] T020 [P] [US1] [GATE:conformance] Structural row in `tests/conformance/packs/test_core_is_product_blind.py`: no module under `src/core` contains a product name, with `vault_fabric` and `credentials` excluded **by name and with a comment** — those are the trust fabric, not the product, and a pattern-only check would either miss the distinction or forbid the wrong thing. **Second assertion, and it is the one SC-002 actually promises**: the commit that adds the *second* pack changes no file under `src/core` — `git diff --stat` against the pack-adding commit, empty. The conformance contract says this is shown by the diff rather than argued, so the row runs the diff
- [X] T021 [US1] [GATE:conformance] Row in `tests/conformance/packs/test_no_bypass_path.py`: every pack tool is a `ToolRegistry` registration, and no pack-specific invocation path exists. Asserted structurally — there is no pack-tool code path, which is the whole design
- [X] T022 [US1] [GATE:fail-closed] Rows in `tests/component/test_pack_cannot_widen.py`: a pack declaring a tool outside its definition's ceiling refuses `pack_exceeds_ceiling`; zero paths grant from a manifest. **The most plausible defect in this feature** — a pack that grants reads as the pack system working
- [X] T023 [P] [US1] Enclave row in `tests/conformance/identity/test_pack_tools_dispatch.py` (`host_enclave`): a run whose definition names the Vault pack reaches a real Vault tool through the real pipeline, in an allocation
- [X] T022a [P] [US1] [GATE:no-secret-leak] Row in `tests/component/test_pack_tool_arguments_are_redacted.py`: a pack tool's arguments reach the trail as keys and content hashes, never raw — with a `secret_touching` fixture whose argument value must not appear anywhere in the audit entry. True today by inheritance from the pipeline's `redact_arguments`, and asserted nowhere; a `secret_touching` tool's arguments are exactly what must not land raw
- [X] T023a [P] [US1] Row in `tests/component/test_eval_status_is_not_reachability.py`: **a pack's eval status and its tool reachability are separate facts**, and passing one does not imply the other. Terraform's gates go green while its tools are fixture-backed by decision, so nothing may report that pack as end-to-end proven. Green gates over a capability that cannot run is the edge case; keeping the two facts distinguishable is the answer

**Checkpoint**: US1 demonstrable; the core is provably product-blind.

---

## Phase 4: User Story 2 — A definition cannot pin what has not been qualified (P1)

**Goal**: the matrix binds. Unqualified cells are refused at definition time; withdrawn ones
at run start; fallback goes only to qualified cells or the run stops.

**Independent test**: pin a qualified cell and run; pin an unqualified one and watch the
definition refuse before anything executes; withdraw a pinned cell and watch the run refuse.

- [X] T024 [US2] Wire binding-map validation into definition registration in `src/core/authority/matrix.py` — refuses `unqualified_cell` **naming the cell**, at definition time. **The path is `core/authority`, not `core/evals`**: this task and T026 named the `evals` path for eight passes after T014 moved the module, and implementing them as written would have created exactly the import T016a's conformance row forbids — the row failing against its own tasks
- [X] T025 [US2] Wire the second validation into `src/core/authority/manufacture.py`, **not** `start_governed_run`. That function already receives the fabric (which reads the matrix) and `agent_definition_id` (whose binding map is being validated), so the resolution belongs there and the run-start signature does not move — a change that would touch the adapter, the entrypoint, and the in-process dispatcher for no gain. Follows the precedent in that function's own docstring, where the `grant` parameter was made optional rather than breaking the seam because "a break bought nothing". **Not redundant**: a cell can be withdrawn after a definition pinned it, and validating only at registration would let a withdrawn cell keep running because nothing re-asked — the reasoning that makes 010 resolve a ceiling per run
- [X] T026 [US2] Implement fallback in `src/core/authority/matrix.py`: search for another qualified cell for the same `(pack, role)` and **return** the fallback as a `MatrixFallback` record; if none, refuse `no_qualified_fallback`. **Returned rather than written** — this module has no sink and no tenant, and the emit belongs to T026a. The path is `core/authority`, not `core/evals`, for the reason recorded at T024
- [X] T026a [US2] [GATE:correlation] Carry the fallback to the sink: add `matrix_fallback` to `ManufacturedAuthority` in `src/core/authority/manufacture.py` (additive, defaulted) and emit `MATRIX_FALLBACK` from `start_governed_run` in `src/core/run.py`, which already holds `sink` and `tenant`. **`MATRIX_FALLBACK` had no writer at all until analyze pass 11**: the fallback resolves inside `manufacture_authority`, which takes no audit sink and no `tenant_id` — and `AuditEntry` requires one — while the function returns a frozen record with nowhere for "cell A was unavailable, cell B was used" to travel. **Do not add a sink parameter to `manufacture_authority`**: it raises `AuthorityRefuseError` and lets `start_governed_run` record `AUTHORITY_REFUSED`, and the fallback follows the same rule in the other direction. FR-010's recording is the load-bearing half — a fallback nobody can see is a definition that does not describe what ran
- [X] T026b [US2] [GATE:fail-closed] Make resume refuse the way run start does, in `src/core/durability/resume.py`: catch `AuthorityRefuseError` around the `manufacture_authority` call and return `ResumeDecision(state=STOPPED, stop_reason=<reason_code>)`; add `matrix_fallback` to `ResumeDecision` so a resumed run's fallback reaches a sink too. **Resume was uncovered by every task in this feature** — the word appeared nowhere in this file. `resume_run` acquires the lease and *then* manufactures authority with no `except`, so a withdrawn cell would throw past a contract that returns a recorded `stop_reason` for every other failure, **with the lease held**. D6's whole rationale is that a cell can be withdrawn, which makes this an ordinary mid-flight state, not a fabric error. Rows in `tests/component/test_resume_refuses_withdrawn_cell.py`: `cell_withdrawn` and `pack_not_loaded` each stop with the reason recorded, and zero steps proceed
- [X] T027 [P] [US2] [GATE:fail-closed] Rows in `tests/component/test_matrix_refusals.py`: unqualified refused at definition time naming the cell; withdrawn refused at run start; fallback records; no-fallback stops. Each asserts **zero runs proceeded**
- [ ] T027a [P] [US2] [GATE:fail-closed] Rows in `tests/component/test_pack_removed_while_pinned.py`: a definition naming a pack that is no longer loaded refuses `pack_not_loaded` **at run start**, not at tool-call time — the same shape as `cell_withdrawn` one level up, and it went unnoticed for six passes because the refusal vocabulary looked complete. Refusing at run start rather than mid-run means the person is told before anything executes rather than after a step has already run
- [ ] T028 [US2] [GATE:conformance] Row in `tests/conformance/packs/test_no_auto_tracking.py`: no alias, no "latest", no configuration that resolves to a moving target. Asserted as an absence, with a positive control that constructs one and confirms the check fires
- [ ] T028a [P] [US2] [GATE:fail-closed] Row in `tests/component/test_cells_are_per_role.py`: **the same pack and the same model, qualified for `summarize` and refused for `write`.** The cheapest possible test of the dimension ADR-0039 exists to add — and the one that fails loudly if the reader keys on `(pack, model)` and ignores `role`, which every other matrix row would still pass
- [ ] T029 [P] [US2] [GATE:correlation] Row in `tests/component/test_model_gate_is_not_an_approval.py`: a `MODEL_GATE` event is distinguishable from any human approval in the trail, and a model verdict never satisfies an approval requirement (FR-015)

**Checkpoint**: US1+US2 is the MVP — packs load and the matrix binds.

---

## Phase 5: User Story 3 — An upstream skill bump is a reviewed change (P2)

**Goal**: promotion requires provenance, injection-lens review, and a passing eval. All
three.

**Independent test**: propose a bump; confirm each missing check blocks it independently;
confirm a skill carrying an injection attempt is refused.

- [ ] T030 [US3] Create `src/core/evals/promotion.py`: `promote_skill()` **and `promote_model_version()`**, both requiring their checks in full. A model bump is a new cell needing qualification (US2 scenario 4) — T028 asserts auto-tracking does not *exist*, and this is the positive case behind that negative: the path a deliberate bump actually takes. Skills additionally require all three of provenance, injection lens, and evals; Provenance verifies the pinned commit exists upstream and the content hashes to what was recorded
- [ ] T031 [US3] Implement the injection lens in `src/core/evals/promotion.py` — pattern-based over skill content for instruction-shaped text targeting the agent: overriding system instructions, exfiltrating context, redirecting tool use. **Deliberately not model-scored**: that would make promotion depend on a model, which needs a qualified cell, which needs the gates — a second regress with no seed set to terminate it. Docstring records it as a floor rather than a guarantee. **The pattern set lives in-repo at `src/core/evals/injection_patterns.py` and is reviewed like code** — it is an artifact the platform executes against every skill bump, so ADR-0030's pinned-vs-fetched rule puts it firmly on the pinned side; a lens whose patterns arrived from anywhere else would be an ungated input to a gate
- [ ] T032 [P] [US3] [GATE:fail-closed] Rows in `tests/component/test_skill_promotion.py`: each of the three checks missing blocks independently; a pinned skill does not change when upstream does; an overlay's relationship to its baseline survives a bump (FR-019)
- [ ] T033 [P] [US3] Rows in `tests/component/test_injection_lens.py`: known injection shapes refused and recorded; benign skill content passes; **one row asserts a novel phrasing the lens does NOT catch**, so the floor is documented by a test rather than only by a docstring

**Checkpoint**: the supply chain has teeth.

---

## Phase 6: User Story 4 — What the agent consulted is part of the record (P2)

**Goal**: provenance-at-read. What the agent consulted is archived as published at that
moment.

**Independent test**: consult guidance, change it upstream, confirm the run record still
names what was actually read.

- [ ] T034 [US4] Create `src/core/packs/consulted.py`: record URL, timestamp, and content hash into the run record at read time. **The source is a fixture, and the record says so** — the validated-design corpus left with US6, so nothing in 013 gives an agent real guidance to read. This builds and proves the mechanism against a controlled document; the first real corpus arrives with the answering feature, and `contracts/conformance-packs.md` records that the mechanism is proven and the corpus is not
- [ ] T035 [P] [US4] [GATE:correlation] Rows in `tests/component/test_provenance_at_read.py`: the triple is archived; changing the fixture afterwards does not change the record; an executed artifact is always pinned, so the executed/consulted distinction holds in both directions. One row asserts the honest limit — **the mechanism is proven against a fixture, not against a corpus**, so a green run here is not evidence that consulting real guidance works

**Checkpoint**: attestation can name its inputs.

---

## Phase 7: User Story 5 — A definition's tier bounds what it may compose (P2)

**Goal**: the tier restricts workflows, and it is a property of the definition.

**Independent test**: two definitions, different tiers, same pack — the lower one confined
to paved workflows regardless of what the request asks for.

- [ ] T035a [P] [US4] Emit aggregate retrieval targets as OTel counters in `src/core/packs/consulted.py`, **adding `src/core/telemetry/counters.py` — that package today contains `spans.py` and one function, and no metrics path at all**. `counters.py` rather than riding span attributes, decided here rather than left to the implementer (analyze pass 12 flagged the task for declining to choose): ADR-0031 wants a **ranking**, and span attributes make that a query over traces at review time while a counter is read directly. What was looked up and how often (FR-026, ADR-0031). **A counter, not a table**: Principle VI, and the ranking is read at a lifecycle review rather than by a run, so nothing needs it queryable in-process. This is the skill-authoring backlog, and a section's retrieval rate falling after a pack release is the evidence that distillation worked
- [ ] T036 [US5] Add tier resolution to `src/core/packs/isolation.py`: a workflow above the definition's tier refuses `above_tier`. **Tiers bound workflows, never tools** — the ceiling answers about tools, and two mechanisms answering one question is the duplication ADR-0044 forbids
- [ ] T037 [P] [US5] [GATE:fail-closed] Rows in `tests/component/test_competency_tiers.py`: lower tier confined to paved workflows; higher tier composes; a request asking for behaviour above the tier is refused — **the tier wins, because it belongs to the definition and not the request**
- [ ] T038 [P] [US5] Row in `tests/component/test_tiers_do_not_duplicate_the_ceiling.py`: a tier change never alters which tools are reachable — the disjointness ADR-0044 requires, asserted rather than assumed

**Checkpoint**: all five stories demonstrable.

---

## Phase 8: The eval gates

**Purpose**: Principle VIII online. This is the phase the roadmap has been waiting for.

- [ ] T039 [GATE:eval] Create `src/core/evals/suites.py`: the four suites as sets of cases with expected outcomes — `must_deny`, `must_decline`, `citation_accuracy`, `estate_state`. **Report fidelity is deliberately absent**, with an explicit skip citing ADR-0018 in the output rather than silence (FR-013a)
- [ ] T040 [GATE:eval] Create `src/core/evals/scoring.py`: `Scorer` protocol, `FixtureScorer` (replays a recorded response), `LiveModelScorer` (calls a provider, reading its credential from **one named constant — `EVAL_PROVIDER_KEY`, defined in `scoring.py` and referenced nowhere as a literal**). **Name the provider and its configuration surface here**: which provider, where the base URL comes from, and how the dev lane obtains a key. 012 hit this exact shape — the dev IdP had to be *served*, not merely written — and a scorer with nowhere to call is the same defect one layer up. The suites, thresholds, and refusals are **identical across both** — only the scorer differs, which is what makes "the machinery is real even when the substrate is a recording" true rather than aspirational.
  **State the subject explicitly, because nothing else does**: a suite scores a **governed agent constructed from a definition** — its pack, its tier, and the binding-map cell for the role under test — built through `build_governed_agent`. Both scorers take that same subject, which is what lets a fixture be a recording *of it* rather than of an unnamed shape. Without this, `FixtureScorer` and `LiveModelScorer` have no agreed input and a fixture recorded against one shape cannot be replayed against another
- [ ] T040b [GATE:eval] Draft `docs/adr/0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md` **here, before any cell is qualified** — not in Polish. FR-012a says the regress must be "resolved and recorded before any cell is qualified", and a Phase 9 draft would record it after the gates had already written cells. T046 then only cross-references it
- [ ] T041 [GATE:eval] Create `evals/seed/` with **at least 20 human-labelled verdict cases spanning all four suites, including at least three the judge should REJECT** — a floor, so "representative" is checkable rather than aspirational and a seed set of two happy paths cannot qualify a judge. ADR-0052 records the floor and the obligation to grow it with the suites. **A seed set below the floor fails the gate rather than warning** — a floor nothing enforces is a suggestion, and this one is the root of the judge chain. Then and `src/core/evals/judge.py` implementing the chain: the first judge is qualified against the seed, every later judge by a judge already qualified. A judge pointed at itself refuses rather than closing the loop
- [ ] T040a [GATE:eval] Make an **unrunnable suite raise** in `src/core/evals/suites.py` and `scoring.py` — missing fixtures, an absent provider key in the live lane, an unreadable pack. It must never skip, never return an empty result set, and never pass (SC-005a, FR-014). **With a positive control**: a row that removes a fixture and asserts the harness fails, because an absence check nobody has seen fire proves nothing. 012 shipped this defect twice — an accessibility lane that skipped when playwright was missing, and an enclave lane that could report a pass without standing the stack up — and both times the fix was the same: a lane that cannot run reports failure
- [ ] T041a Create `src/core/evals/schema.sql` for eval cases and results, and apply it **at bring-up** in `infra/bin/enclave-up`'s existing schema pass — the same statement block as the evidence, dependency, run-index, and thread schemas, **including its `SET ROLE brieve`**. Every dynamic credential is a distinct role, so a table created under one is owned by a user that will not exist next week, and the next credential fails DDL with "must be owner of table" — including on `CREATE INDEX IF NOT EXISTS`, which checks ownership before existence. 005 paid for this once and the block's comment says so. 012 shipped exactly this defect by leaving `run_inputs` to migrate-on-boot, and every dispatched run died with `relation ... does not exist`; that script's comment now says the rule has bitten four times, and this is the chance not to make it five
- [ ] T042 [P] Write `packs/vault/evals/` and `packs/terraform/evals/` cases for each suite — **at least five cases per suite per pack, including at least two the agent must refuse or decline**. A floor for the same reason the seed set has one (T041): a suite of one happy path greens a gate while asserting nothing, and content is where that is easiest to let slide. **A pack below the floor is refused at load** (`insufficient_eval_coverage`), not warned about — refusing at load puts the failure where the pack is added rather than where a gate later reports a number nobody reads
- [ ] T043 [GATE:eval] Add `make evals` (fixtures, blocking) and `make evals-live` (`live_model` marker, named runner) to the `Makefile`. **`tests/conformance/packs` was wired at T012b**, where the directory is born — this task adds only the eval targets
- [ ] T044 [P] [GATE:eval] Rows in `tests/component/test_judge_chain.py`: the first judge qualified against the seed; a later judge qualified by a qualified judge; a judge pointed at itself refused; **a cell recorded without a judge is refused unless it is the seed-qualified first**; and **the record names what qualified the first judge, with that answer depending on no unqualified judge** (SC-015) — the mechanics and the *recorded answer* are different claims, and only the second is what an investigator reads
- [ ] T045 [P] [GATE:no-secret-leak] Row in `tests/conformance/packs/test_provider_key_is_dev_lane_only.py`: the provider credential appears in no jobspec, is read by no run path, and is absent from every pack manifest. **Asserts against `scoring.EVAL_PROVIDER_KEY`, imported — never against a string literal.** A no-secret-leak row matching a name nothing defines passes forever regardless of what leaks, and the name currently exists only in the quickstart

---

## Phase 9: Polish, records, and the gate run

- [ ] T046 [P] Complete `docs/adr/0052-...` (drafted at T040b): the three bounded options, why external attestation imports trust the platform cannot inspect and a declared floor makes the chain's root unarguable, and the **maintenance obligation** — a seed set that stops being representative silently weakens every gate above it. Add the outcome now that the gates have run
- [ ] T047 [P] Update `docs/glossary.md`: `risk class` now exists in code; add `capability pack` cross-references, `qualified cell`, `competency tier`, and `seed set`
- [ ] T048 [P] [GATE:conformance] Apply every break fixture from `contracts/conformance-packs.md` to the tree, watch the row fail, revert: a pack that grants; a cell qualified by the cell it qualifies; a withdrawn cell that keeps running; a skill bumped without review; an alias resolving to latest; a model verdict filed as an approval. **A row nobody has seen fail is a row nobody knows works**
- [ ] T049 [P] Update `ROADMAP.md`: 013 shipped; four of five eval-gate rows move Deferred → In force; report fidelity recorded as still-owed against ADR-0018; portal answering unblocked
- [ ] T050 [P] Record rows **In force** in `specs/013-capability-packs/contracts/conformance-packs.md`, and note in `specs/012-conversational-portal/`'s record that answering's dependency is now met
- [ ] T050a Record in `contracts/conformance-packs.md` whether a **fixture-qualified `write` cell is usable**, and why. A `write` cell is a model permitted to make changes, and in the blocking lane its qualification is against a recording — the spec calls this the sharpest edge in the feature and carried it no further. Either require `live` qualification for `write` specifically, or state plainly that fixture qualification suffices and what that costs. **What is not acceptable is leaving it to whoever reads the per-cell table to infer**
- [ ] T051 [GATE:conformance] Run `make check`, `make conformance`, and `make evals` against a live enclave on a clean tree, and walk `specs/013-capability-packs/quickstart.md` sections 2–7. Then run `make evals-live` as the named runner and **record each cell's `qualified_by` in the per-cell table** — a cell absent from that table is not qualified (SC-013)

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─→ Phase 2 Foundational ─→ Phase 3 US1 (MVP start)
                                          ─→ Phase 4 US2 (MVP complete)
                                          ─→ Phase 5 US3 (needs US1's packs)
                                          ─→ Phase 6 US4 (needs US1's packs)
                                          ─→ Phase 7 US5 (needs US1's workflows)
                                                     ─→ Phase 8 Eval gates (needs US2's matrix)
                                                                ─→ Phase 9 Polish
```

**Orderings that are not obvious from the phases**, and which an implementer following the
graph alone would otherwise hit backwards:

- **T012c → T012d → T011, T024, T036.** The definition-bindings record must exist before
  anything reads `packs[]`, `binding_map`, or `tier` — which is isolation, matrix validation,
  and tier resolution, i.e. most of US1, US2, and US5.
- **T013a → T014.** The Vault grant must exist before anything reads the matrix. Without it
  the reader gets a 403 that presents as an unreachable fabric, so the failure blames the
  wrong system and the debugging goes to Vault's health rather than to a missing policy line.
- **T011a → T017.** `WorkflowRecord` must exist before the Vault pack declares a `paved`
  workflow, because the manifest field has nothing to parse into otherwise.
- **T012a → T023.** The tool vocabulary must derive from packs before the enclave row starts
  a run against a real pack tool; otherwise the ceiling reader refuses a correct record.
- **T012b → everything in `tests/conformance/packs`.** That task creates the directory *and*
  wires it into the conformance recipe, so later rows land in a lane that runs.
- **T026 → T026a → T026b.** The fallback is a returned record before anything emits it, and
  `start_governed_run` emits before resume does the same one layer up. Reversing the first
  two produces the defect pass 11 found: an event specified with no writer.
- **T019 → T019a, T019c.** Packs must load before `depends_on` can be built from their
  manifests — and T008 must have put `product` on `ToolDeclaration` before there is anything
  to map. **T019c → T023**: without a resolved probe the pack's product records `UNHEALTHY`
  and the dependency gate denies the enclave row's tool call, naming a product that is up.
- **T041a → T042.** The eval schema exists before cases are written against it.
- **T040b → T041 → any qualification.** ADR-0052 records the regress's resolution *before* a
  cell is written, because FR-012a requires it recorded first and a Polish-phase draft would
  document the answer after the gates had already relied on it.

Otherwise: **US3, US4, and US5 are mutually independent**, each needing only Foundational
plus US1. **Phase 8 depends on US2**, because a gate that qualifies cells needs a matrix to
write them to. **T018** (vendoring Terraform) can start any time after T008 — it is content,
not code.

## Parallel opportunities

- **Setup**: T002 ∥ T003 ∥ T004.
- **Foundational**: T008 ∥ T009; T011a ∥ T012; T012b ∥ T013b (different lanes); T015 ∥ T016
  ∥ T016a once T014 lands.
- **After US1+US2**: Phases 5, 6, and 7 run in parallel.
- **Phase 8**: T042 (cases, content) ∥ T041 (the chain, code); T045 ∥ both.
- **Polish**: T046 ∥ T047 ∥ T049 ∥ T050.

**Not parallel, despite looking it**: T013a and T014 (the grant gates the reader), and
T012a and T012b (the row asserts what the task establishes).

## Implementation strategy

**MVP = Phase 3 (US1) + Phase 4 (US2)**: packs load and the matrix binds. That is the
smallest thing that is recognisably this feature — product knowledge the platform can use,
and models it may only use once demonstrated.

Phase 8 is what the roadmap has been waiting for and is deliberately last among the
building phases: the gates need something to gate. Phase 9's break fixtures are not optional
polish — 011 found one fixture in four survivable, and it was the one guarding the defect
that feature was most likely to reintroduce.
