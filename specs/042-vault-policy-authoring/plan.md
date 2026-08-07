# Implementation Plan: Vault policy authoring, end to end

**Branch**: `spec/042-vault-policy-authoring` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/042-vault-policy-authoring/spec.md`, measured
against the tree at the 043 merge (`0b5f30b`).

## Summary

The change-proposal workflow's first product. An agent reads what Vault policies exist and
what is attached to them (`vault_policy_read`, new pack tool), reasons against the pinned
Vault operating guides, authors the change through 041's tier unchanged, measures the impact
with **Vault's own capability checks** — a scratch policy pair and a throwaway token, all
inside one tool call (`vault_policy_impact`), always destroyed — and opens a proposal whose
PR body carries the diff, the platform-rendered impact evidence, and the citations. The
central refusal: the trust-fabric policies that bound the agent are structurally unreachable,
three independent layers deep, and a row proves the safety case can lose.

**The finding that shapes the plan** (research R8): nothing in this platform writes to Vault
through the workload identity today — `vault_write` is a stub and the agent grant carries no
write capability. The scratch write is the platform's first real governed write to Vault, so
the client, the grants, and the token role are all built here, not assumed.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed), matching the tree

**Primary Dependencies**: none added. Vault is spoken to through the existing
`VaultDatabaseCredentials` client (stdlib urllib + attested JWT login), extended with four
additive methods (R8). No hvac, no HCL parser (R10)

**Storage**: the trust fabric (Vault) — `scratch-check` token role, `scratch_policy_check`
grant, published protected set at `harness-authority/data/protected-policies`; the audit
trail (Postgres) for records. Proposal store keeps reference-not-body, unchanged

**Testing**: pytest — unit + hermetic conformance (V1–V14, V18); `enclave`-marked rows
V15–V17 fail-not-skip against the dev enclave; live legs PL1–PL3 (named runner: Dan)

**Target Platform**: the enclave (Nomad + Vault Enterprise + Postgres), darwin dev host

**Project Type**: single project — additions to `src/surfaces/`, `packs/vault/`,
`infra/modules/trust-fabric/`; zero edits inside `core/authoring`

**Performance Goals**: one impact check ≤ a few seconds (policy writes + ≤2 token mints +
bounded capability queries); scratch token TTL 60s bounds credential lifetime

**Constraints**: the impact instrument is real or absent — no fixture mode exists (FR-007);
an unrunnable check refuses the proposal (FR-008); destruction is in-call `finally` +
service sweep (FR-022/023)

**Scale/Scope**: 2 new pack tools, 1 hook, 1 request wrapper, 4 client methods, 3
trust-fabric additions, ~18 conformance rows, 1 new ADR (0068)

## Constitution Check

*Named-runner obligation*: V15–V17 and PL1–PL3 have no automated runner. **Dan runs them
before merge**; the contract records this and the implementation PR records the outcomes.

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Vault answers the impact question; the platform only routes and renders. No HCL parser is built (Vault's is authoritative); no new dependency |
| II — Total Interception; One Governed Tool Layer | **Pass** | Both new capabilities are registered pack tools through the full pipeline (FR-024); native transport on the pack's own recorded determination; no new northbound verb — the request is a dispatch payload, as 041 established |
| III — Fail-Closed, In-Process Enforcement | **Pass** | The protected-set refusal is a GOVERNANCE pre-hook (R5 layer 2), fail-closed on an unreadable protected set (V5); 038's own record — "a conformance row over a module function would have been green" — is why it is a hook |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | Scratch tokens: 60s TTL, minted per check under the allocation's attested identity, never persisted. The new grant is a separate revocable policy on the existing `agent-run` role. **The run never holds authority to change what bounds it**: `allowed_policies_glob` admits only `scratch-agent-*`, and Vault refuses the rest even with the platform's hooks removed (V16). No new standing credential; the exception list stays at three |
| V — Sealed Core, Versioned Seams | **Pass** | Four additive client methods, named here for review (R8, 043's precedent); `core/authoring` untouched (FR-014/015, SC-008 diff row); the hook uses the existing registration seam |
| VI — Lean by Default | **Pass** | No new operated component, no new dependency; the sweep joins the existing persistent service (R11) |
| VII — Anti-Fragmentation | **Pass** | One client extended rather than a second one written; handlers join the one platform table; identical across substrates |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | 041's write-cell qualification consumed unchanged; the impact evidence is a product answer, not a model output, so nothing new is eval-gated; guidance grounding stays on the pinned corpus |
| IX — Evidence Over Claims | **Pass** | The impact section is platform-rendered from Vault's answers — the model never writes it (R9); citations resolve or the absence is disclosed (FR-012); the proposal remains a model-gated artifact a human merges, never an approval |
| X — The Decision Record Governs | **Pass** | ADR-0068 (new, Proposed) records the scratch mechanism; ADR-0025/0038/0062/0064/0066 consumed, none amended |

**Gate result**: **PASS — proceed** (Phase 0 and Phase 1 artifacts generated; re-checked
post-design, verdicts unchanged)

## Project Structure

### Documentation (this feature)

```text
specs/042-vault-policy-authoring/
├── plan.md              # This file
├── research.md          # R1–R14: the decisions and the measurements behind them
├── data-model.md        # PolicyRecord, ProtectedSet, ScratchCheck, ImpactResult, request
├── quickstart.md        # Hermetic → single live call → back-stop → end to end
├── contracts/
│   └── conformance-policy-authoring.md   # V1–V18, PL1–PL3, named runner
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/
├── core/durability/credentials.py      # +write_path/delete_path/create_token/capabilities (R8)
├── surfaces/
│   ├── handlers.py                     # +vault_policy_read, +vault_policy_impact (R7)
│   └── dispatch/
│       ├── policy_authoring.py         # NEW: request wrapper (target_policy), protected-set
│       │                               #      hook, registration for the policy-authoring run
│       └── entrypoint.py               # threads the 042 registration (mirror of 041's)
├── (core/authoring/ — ZERO edits; the product-blindness gate keeps asserting it)

packs/vault/pack.toml                   # +2 [[tools]]; +policy-authoring workflow declaration

infra/modules/trust-fabric/
├── policies.tf                         # +scratch_policy_check grant
├── auth.tf                             # agent-run role: +scratch_policy_check; service role:
│                                       #   +sweep grant
├── scratch.tf                          # NEW: scratch-check token role; protected-set publication
└── (a unit row scans this module: V6 completeness, V7 namespace)

tests/
├── unit/                               # V6, V7, client methods, ImpactResult composition
├── conformance/authoring/              # V1–V14, V18 hermetic; V15–V17 enclave-marked
└── evals_live/                         # PL1 single-call probe (smoke shape)

docs/adr/0068-*.md                      # the scratch-measurement record
```

**Structure Decision**: single project, additions at the surfaces/pack/infra layers only.
The one deliberate asymmetry: everything product-aware lands in `surfaces/dispatch/
policy_authoring.py` and `handlers.py`, so the product-blindness gate over `core/authoring`
— which caught 041 — is the enforcement that this feature stayed where it belongs.

## Complexity Tracking

No Constitution Check violations to justify. The nearest judgment call, recorded:
`vault_policy_impact` performing five product operations inside one tool call could read as
a pipeline bypass of granularity — it is the opposite (R1): splitting it would turn "always
destroyed" into model discretion, and each internal operation still runs under the one
Vault grant the ceiling and hooks admitted.
