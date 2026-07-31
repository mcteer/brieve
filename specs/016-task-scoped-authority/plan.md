# Implementation Plan: Task-scoped authority manufacture

**Branch**: `spec/016-task-scoped-authority` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-task-scoped-authority/spec.md`

## Summary

A run's credential is narrowed at launch to the resources its task entails, instead of
carrying the agent definition's whole ceiling for the run's duration. The platform computes
the entailed paths from the run's requested tools, mints a short-lived grant carrying them as
RFC 9396 `authorization_details`, and Vault — configured as an OAuth resource server —
evaluates that grant against the registered agent's ceiling policies. The refusal that matters
is Vault's, which is what makes this different from the per-action enforcement the hooks
already do: it holds when the platform's own code is wrong.

The signing key never leaves Vault (transit, ES256), the public half is registered as a static
PEM so the issuer serves no endpoint, and no standing credential is added.

**One thing is unresolved and it gates the rest**: how a grant's subject binds to a Vault
Identity entity (research F5). Everything else about the mechanism was established by running
it against the enclave.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Vault v2.0.3+ent (agent registry, `oauth-resource-server`, transit);
existing `VaultIdentityFabric`, `AuthorityScope`, pack loader, durability provider

**Storage**: Postgres — the grant record beside the run's other durable state, under the run
role. Not in the checkpoint (ADR-0026: checkpoints hold state, never credentials)

**Testing**: pytest — `tests/unit`, `tests/component` hermetic; `tests/conformance/authority`
against the live enclave, `enclave` + `host_enclave`

**Target Platform**: Linux/macOS enclave on Nomad; Vault Enterprise

**Project Type**: Single project — governed core plus surfaces

**Performance Goals**: One exchange per run launch and one per resume. No per-action exchange:
the round trip stays out of the hot path (ADR-0056)

**Constraints**: ES256 only (transit JWS marshaling supports ECDSA P-256 alone); Vault RAR
matches paths **exactly** — no wildcards; `jti` mandatory or the token fails schema validation;
every RAR rejection surfaces to the caller as an indistinguishable `403`, with the reason only
in Vault's server log

**Scale/Scope**: Two packs, four agent definitions, ~12 conformance rows. Additive to the
authority path — the existing JWT-auth credential path is untouched

## Constitution Check

*Re-evaluated after Phase 1 design. Verdicts unchanged from the pre-research pass.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The mechanism is Vault's — RAR, resource-server validation, transit signing. This builds the glue that computes a scope and fills in a token the substrate defines. Nothing here reimplements an authorization server. |
| II — Total Interception; One Governed Tool Layer | **Pass** | No new egress class and no new transport. The grant is minted on the existing run-start path against Vault, which is already an enumerated interaction. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | In-process hooks are untouched (F6, FR-011a) and keep enforcing per action. This adds a second boundary outside the process; it removes none. A tool that has not declared its paths **refuses at launch** (FR-004) rather than being granted broadly. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | This is the principle the feature exists to satisfy — it supplies the missing `task scope` term. No standing credential is added: the signing key lives in transit and the issuer authenticates with its own attested workload identity (F3). |
| V — Sealed Core, Versioned Seams | **Pass** | Additive. `AuthorityScope` is unchanged; the pack manifest gains one optional-by-schema, required-for-`secret_touching` field. Sealed-core change, so it carries the spec and security-maintainer review the principle requires. |
| VI — Lean by Default | **Pass** | No new operated component. The static-key registration (F2) removes the JWKS endpoint the first design assumed, and the signing step lives in the path that already starts runs. |
| VII — Anti-Fragmentation | **Pass** | One mechanism across substrates. The tier an estate lands in depends on its IdP, and US4 requires that to be *reported* rather than silently differing. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **N/A** | No pack, prompt, model, or policy promotion. |
| IX — Evidence Over Claims | **Pass** | The launch decision, the refusals, and the arrangement in force are all recorded. The contract states three things the rows do **not** prove rather than letting the feature read as broader than it is. |
| X — The Decision Record Governs | **Pass** | Implements ADR-0056 (Accepted). ADR-0026's two-level authority is consumed, not amended. ADR-0044's disjoint jurisdictions are preserved structurally (F6). |

**Gate result**: **PASS — proceed to Phase 0** *(and Phase 0/1 are complete; re-check clean)*

## Project Structure

### Documentation (this feature)

```text
specs/016-task-scoped-authority/
├── plan.md              # This file
├── spec.md              # Clarified 2026-07-31
├── research.md          # Phase 0 — eight findings, one unresolved and named
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 — section 0 runs before implementation
├── contracts/
│   └── conformance-task-authority.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/core/authority/
├── grant.py             # EXTENDED — `DelegationGrant` and `issue_grant` already exist
│                        #   (005/014). Gains `entailed_paths`; does NOT become a new object.
├── scope.py             # NEW — EntailedScope: derive paths from requested tools
├── grant_token.py       # NEW — assemble + transit-sign the RAR token; no key material here
├── types.py             # unchanged — AuthorityScope stays tool/action only (F6)
└── vault_fabric.py      # extended — read the ceiling paths the grant is bounded by

src/core/packs/
├── manifest.py          # extended — the tool model gains a `paths` field
└── registration.py      # extended — parse and validate the tools' `paths` declaration

src/core/durability/
└── types.py             # extended — persist and read the grant record

src/surfaces/api/
└── runs.py              # extended — mint the grant at launch, on the path that already
                         #   holds an attested identity and already talks to Vault

src/surfaces/dispatch/
└── entrypoint.py        # extended — re-derive the grant token on resume from the record

src/surfaces/mcp/
└── server.py            # extended — report which arrangement is in force (US4)

infra/modules/trust-fabric/
├── task-authority.tf    # NEW — transit key, resource-server profile, static public key
└── ceilings.tf          # unchanged

infra/bin/enclave-up     # extended — activate oauth-resource-server (F1: reversible)

packs/*/pack.toml        # extended — per-tool `paths` declaration

tests/
├── unit/                # scope derivation, grant validation, token assembly
├── component/           # launch/resume behaviour against doubles
└── conformance/authority/   # NEW — wired into the Makefile host lane in the same change
```

**Structure Decision**: Single project, additive throughout. The grant machinery lands in
`src/core/authority/` beside the ceiling reader it depends on; the two surfaces that already
hold attested identities gain the mint and the re-derive. No new package, no new service, and
no new long-lived component — which is what F2 and ADR-0056's per-run exchange bought.

**Corrected during `/speckit-tasks`**: `DelegationGrant`, `issue_grant`, and the provider's
`save_grant`/`load_grant` **already exist** from 005/014 — this plan's first draft listed
`grant.py` as new. The durable-consent object the spec calls a "task grant" is that existing
record with `entailed_paths` added, not a second grant beside it. Two grant objects for one
consent would have been exactly the fragmentation Principle VII forbids, and the correction
also removes the persistence work the task list would otherwise have carried.

## Complexity Tracking

> No Constitution Check violations. This section is empty by design.

The one judgement call worth recording without a violation to justify: the pack manifest
gains a field. The alternative was inferring each tool's paths from its handler code, which
would be a static analysis that breaks the first time a path is computed at runtime — and
would fail **open**, granting access it could not prove was needed. A declaration that
refuses when absent (FR-004) fails closed instead, which is the direction Principle III
requires.
