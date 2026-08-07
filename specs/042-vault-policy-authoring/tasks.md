# Tasks: Vault policy authoring, end to end

**Input**: Design documents from `specs/042-vault-policy-authoring/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-policy-authoring.md, quickstart.md

**Tests**: Included — the deliverable is largely its rows (V1–V20, PL1–PL3). The safety rows
land before the capability they bound wherever the order is expressible: the protected-set
scans (V6/V7) are Foundational because every later phase stands on the namespace being real.

**Organization**: By user story. US1–US4 are all P1 — but they are not peers: **no increment
ships without US2.** A policy-authoring capability whose safety case lands "next" is the
platform being editable by the thing it governs for exactly the length of that gap.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T004 (unreadable protected set refuses — V5), T006 (the hook refuses on internal error, never allows — asserted in V2, analyze I1), T016 (no ImpactResult → no publish, V13) |
| **Conformance** | T007, T010, T013–T014, T016–T017 — the V-rows; T019–T020 the PL legs |
| **Correlation / evidence** | T013 (the impact call's intent/result bracket joins the trail), T016 (the PR body is platform-rendered from Vault's answers — Principle IX) |
| **Eval** | N/A per research R13 — the impact evidence is a product answer, not a model output; 041's write-cell qualification is consumed unchanged (stated per the template's rule) |
| **No-secret-leak** | T001 (scratch tokens never logged, never recorded, 60s TTL), T007 (V9: no secret value, no `secret/` read in any policy response), T016 (V18: composed body asserted clean) |

## The shape of the work

The instrument is one tool call or it is not safe (R1). Both sides of the diff go through
scratch or the token role's glob stops being absolute (R2). The refusal has three independent
layers, and V3 deletes the middle one to prove the case can lose. And the plan's own finding
governs the order: **nothing has ever written to Vault through the workload identity**, so
the client and the grants (T001/T002) precede everything that assumes they exist.

## Path Conventions

Single project: `src/`, `tests/`, `packs/`, `infra/` at repository root.

---

## Phase 1: Foundational (blocking all stories)

**Purpose**: the write path, the grants, and the protected set — the three things every
story stands on and none may build for itself.

- [X] T001 Extend `src/core/durability/credentials.py` with four additive methods —
      `write_path`, `delete_path`, `create_token(role, policies, ttl)`,
      `capabilities(token, paths)` — reusing the existing login/TLS/timeout handling (R8);
      **sealed-core additive, named in plan's Principle V row**; unit rows in
      `tests/unit/test_vault_client_writes.py` including [GATE:no-secret-leak] — no token
      value in any log, exception message, or return beyond the caller's hands.
- [X] T002 [P] Trust-fabric additions in `infra/modules/trust-fabric/scratch.tf` (new):
      `scratch-check` token role (`allowed_policies_glob = ["scratch-agent-*"]`, TTL 60s,
      `no_default_policy`), protected-set publication to
      `harness-authority/data/protected-policies`; `scratch_policy_check` policy in
      `policies.tf`; attach to `agent-run` role and add the sweep grant to the service role
      in `auth.tf` (R3, R4). `terraform validate` clean. **Verify `harness_authority_read`'s
      path grammar covers `protected-policies`** — if its grants enumerate subpaths, extend
      the grant in the same change (analyze U1; 043's M2 was this shape and was real).
- [X] T003 [P] Unit scans in `tests/unit/test_trust_fabric_protected_set.py`: **V6** —
      every `resource "vault_policy"` name in `infra/modules/trust-fabric/` appears in the
      published protected list; **V7** — no trust-fabric policy name begins
      `scratch-agent-` (FR-020's reserved namespace as a merge gate); **V20** — the
      `scratch_policy_check` grant carries no attach capability (`identity/*`,
      `auth/+/role/*`, `auth/token/roles/*`), so SC-011 rests on a scanned grant rather
      than only on the absence of an attach step (analyze C2).
- [X] T004 [GATE:fail-closed] ProtectedSet reader in
      `src/surfaces/dispatch/policy_authoring.py` (new file): read
      `harness-authority/data/protected-policies` at run start; an unreadable fabric
      refuses — empty-because-outage never reads as nothing-protected (**V5**); hermetic row
      in `tests/conformance/authoring/test_policy_protected.py`.

**Checkpoint**: the namespace is real, the grants exist, the client can write — and nothing
user-facing exists yet.

---

## Phase 2: US2 — The platform's own policies are unreachable (P1) 🎯 the safety case

**Goal**: every route to a trust-fabric policy refuses, structurally, and the refusal can
lose (SC-002, SC-003).

**Independent Test**: ask for a change to `agent_ceiling` in several wordings and via a
planted instruction; every attempt refuses from the platform, and removing the hook makes a
row fail.

- [X] T005 [US2] `PolicyAuthoringRequest` in `src/surfaces/dispatch/policy_authoring.py`:
      041's `AuthoringRequest` extended with `target_policy`; validation refuses
      `policy_protected` **before anything is read** (V1) — 041's `validate()` runs first,
      unchanged.
- [X] T006 [US2] The GOVERNANCE pre-hook in `src/surfaces/dispatch/policy_authoring.py`:
      inspects `author_file` and `vault_policy_impact` arguments; a protected policy name
      refuses and **records the attempt**; an argument supplying a scratch name refuses
      `scratch_name_forged` (V2, V11's hook half); registered for the policy-authoring run
      in `src/surfaces/dispatch/entrypoint.py` on 041's registration pattern.
- [X] T007 [US2] [GATE:conformance] Rows V1–V4 in
      `tests/conformance/authoring/test_policy_protected.py`: V1 (refusal before any read —
      provider records zero calls), V2 (the hook refuses and records), **V3 (with the 042
      hook removed from registration, authoring passes and this row FAILS — SC-003)**,
      V4 (planted instruction recorded by the inherited lens; escalation lands in V2).
      V2 includes the fail-closed leg: an exception raised inside the hook refuses the
      call, never allows it (analyze I1).

**Checkpoint**: the safety case holds and can lose. Nothing can yet read or measure — which
is the right order.

---

## Phase 3: US1 — The agent reads what policy exists (P1)

**Goal**: reasoning starts from the estate, not the prompt (FR-001–003).

**Independent Test**: ask about a named policy; the run reads it and its attachments, the
read is recorded, no secret value appears, and absent/protected/present are three answers.

- [ ] T008 [US1] Declare the tools and the workflow in `packs/vault/pack.toml`:
      `[[tools]] vault_policy_read` and `[[tools]] vault_policy_impact` (both
      `risk_class = "secret_touching"`, `transport = "native"`, `product = "vault"`;
      impact `repeatable = true` with R7's argument in a comment), plus a
      `[[workflows]] policy-authoring` declaration — **without it, 041's
      `pack_declares_no_authoring` refusal blocks every request this feature makes**.
- [ ] T009 [US1] `vault_policy_read` handler in `src/surfaces/handlers.py`: list names,
      read bodies **only outside the protected set** (three states — `present` /
      `protected` / `absent`, R6), attachments from token roles, JWT auth roles, entities
      and groups, bounded with the bound disclosed (FR-010); joins `PLATFORM_HANDLERS`.
- [ ] T010 [US1] [GATE:conformance] Rows V8–V10 in
      `tests/conformance/authoring/test_policy_read.py`: V8 (registered, hook-wrapped,
      ordinary intent/result bracket), V9 [GATE:no-secret-leak] (three distinct states; no
      secret value; no `secret/` path touched), V10 (attachment truncation disclosed).

**Checkpoint**: US1 independently testable — a run can read the estate and nothing else.

---

## Phase 4: US3 — The impact is measured, not asserted (P1)

**Goal**: Vault answers what the change would permit; the check leaves nothing behind
(FR-007–010, FR-019–025).

**Independent Test**: propose a widening change; the evidence shows the widening; a check
that cannot run refuses the proposal; zero scratch artifacts survive.

- [ ] T011 [US3] `vault_policy_impact` handler in `src/surfaces/handlers.py`: the whole
      lifecycle in one call (R1) — derive `scratch-agent-<run>-current/-proposed` from the
      run id (never from arguments), write both bodies, mint one 60s token per side via
      `scratch-check`, query `sys/capabilities` over the stanza-scan ∪ diff-touched path
      set (bounded, truncation disclosed — R10), compose per-path
      `current`/`proposed`/`granted`/`revoked`, destroy both policies in `finally`.
      Vault's parse failure surfaces as `policy_invalid`, never as an impact result.
- [ ] T012 [P] [US3] `ImpactResult` composition unit rows in
      `tests/unit/test_impact_result.py`: granted/revoked set arithmetic; a new policy's
      empty current side; the path cap and its disclosure; glob paths labelled `as-written`.
- [ ] T013 [US3] [GATE:conformance] Rows V11–V14 in
      `tests/conformance/authoring/test_policy_impact.py`: V11 (names derived; forged name
      refuses), V12 (a widening change is visibly wider — the row fails if the evidence
      would read identically without the impact, SC-009), V13 (check cannot run → proposal
      refused `impact_unavailable`, never fabricated), V14 (invalid policy → `policy_invalid`
      from Vault's parser), **V19** (FR-024's ceiling clause, both directions in one
      process: a ceiling naming the new tools reaches them, one omitting them refuses —
      041's `unknown_ceiling_entry` gap, made unrepeatable here; analyze C1).
- [ ] T014 [US3] [GATE:conformance] Enclave rows V15–V17 in
      `tests/conformance/authoring/test_policy_impact_enclave.py`, `enclave`-marked,
      **failing rather than skipping without Vault** (SC-007): V15 (full lifecycle; zero
      `scratch-agent-*` survivors; tokens expired), V16 (**Vault's own ACL refuses a
      protected-name scratch write with the platform hook disabled** — the back-stop holds
      independently), V17 (a planted orphan is swept and the removal audited).
- [ ] T015 [US3] The scratch sweep beside the resume sweeper in the persistent MCP service
      (`src/surfaces/mcp/served.py` + a small module it hosts): list `sys/policies/acl`,
      filter `scratch-agent-*`, delete when the run is not live, audit the removal (R11,
      FR-023).

**Checkpoint**: US3 independently testable — the instrument is real, bounded, and
self-cleaning.

---

## Phase 5: US4 — The proposal carries its evidence (P1)

**Goal**: a reviewer answers "what changed / what does it permit / on what basis" from the
PR alone (SC-001).

**Independent Test**: open a proposal; read only the PR; answer all three; find no secret
value and no trust-fabric body.

- [ ] T016 [US4] [GATE:conformance] Evidence composition in
      `src/surfaces/dispatch/policy_authoring.py`: the impact section rendered **by the
      platform** from Vault's answers into the PR body (R9), citations resolved against the
      pinned corpus manifest at composition, zero resolutions appending the FR-012
      disclosure to `Proposal.disclosures`; publishing refuses `impact_unavailable` when no
      `ImpactResult` exists (V13's publish half, FR-008). Row **V18** in
      `tests/conformance/authoring/test_policy_proposal.py`: body carries diff + impact +
      citations; [GATE:no-secret-leak] no secret value, no trust-fabric policy body,
      asserted over the composed body.

**Checkpoint**: US4 independently testable — the proposal is the product.

---

## Phase 6: US5 — Nothing 041 proved has to be rebuilt (P2)

**Goal**: the tier stays product-blind and single-pathed (FR-014/015, SC-008).

**Independent Test**: the 041 suite passes unedited; exactly one publisher is registered.

- [ ] T017 [US5] [GATE:conformance] Rows in
      `tests/conformance/authoring/test_041_unchanged.py`: SC-008 as a **diff from the
      merge-base** over 041's conformance files (with the `origin/<base>` fallback 043's R9
      had to learn); FR-014 as a registry assertion — exactly one publisher, and
      `open_proposal` is it. `test_core_is_product_blind` runs unedited.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T018 [P] Write `docs/adr/0068-impact-is-measured-by-the-product.md` (Proposed):
      the scratch mechanism, its three bounds, why one call, why both sides, the orphan
      window that remains (R14); index in `docs/adr/README.md`.
- [ ] T019 Apply the trust-fabric additions to the dev enclave and run **PL1** — the
      single-call probe in `tests/evals_live/policy_impact_probe.py` (smoke shape: raw
      capability answers printed, one call before anything bigger); re-seed the model
      credential if the apply clobbers it.
- [ ] T020 Run **PL2** end to end — policy-repository subject → read → author → impact →
      real PR via 041's publisher; answer SC-001's three questions from the PR alone;
      record PL1–PL3 outcomes in `contracts/conformance-policy-authoring.md`.
- [ ] T021 [P] Run `specs/042-vault-policy-authoring/quickstart.md` top to bottom as
      written; fix drift in the doc, not by hand-waving the steps.
- [ ] T022 Update `ROADMAP.md` in the implementation PR: the change-proposal table's Vault
      row closes with the mechanism in one line, and 042's Shipped row lands (the file's
      own landing rule).

---

## Dependencies & Execution Order

- **Foundational**: T001 ∥ T002 ∥ T003; T004 after T002 (the published set must exist to
  read). Nothing else starts before T001/T002 — the write path and grants are the finding.
- **US2 first among stories**: T005–T007 after T004. **No increment ships without this
  phase.**
- **US1**: T008 after T002; T009 after T004+T008; T010 after T009.
- **US3**: T011 after T001+T006+T008 (client, hook, declaration); T012 ∥ T011; T013 after
  T011+T009 (V19 exercises BOTH new tools, so the read handler must be registered too); T014 after T011+T015 (V17 needs the sweep); T015 after T001.
- **US4**: T016 after T011 (an ImpactResult must exist to render).
- **US5**: T017 any time after Foundational; cheapest early-warning if run continuously.
- **Polish**: T018 ∥ anytime; T019 after T002+T011; T020 after everything; T021/T022 last.

## Parallel Example

After T004: `T005+T006` (US2, one file, sequential) ∥ `T008` (pack.toml) ∥ `T003` already
done ∥ `T018` (ADR). After T011 lands: `T012` ∥ `T013` ∥ `T015`.

## Implementation Strategy

Foundational → **US2 (safety)** → US1 (read) → US3 (instrument) → US4 (proposal) → US5 +
Polish. The suggested MVP is Foundational + US2 + US1: a run that can read the estate and
provably cannot touch what bounds it — worthless as a product and complete as a safety
demonstration, which is the right order for this feature. The product arrives with US3+US4.
