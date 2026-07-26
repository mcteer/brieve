# Implementation Plan: Deployment Module Tree

**Branch**: `spec/006-deployment-module-tree` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-deployment-module-tree/spec.md`

## Summary

Restructure `infra/` into a parameterized tree: one substrate-independent **trust-fabric module**
applied identically everywhere, one **substrate module** per environment shape, and thin
**environment roots** that compose them. Move the conformance suite into a scheduled Nomad job so
it holds its own workload identity, which deletes the last static-token path in the repository.
Publish what bring-up guarantees, and make a command assert it rather than a human read it.

The thing to hold onto: **`vault-trust.tf` already is the product.** It was written to apply
unchanged against a production Vault and it does. What is missing is not new trust logic but the
*structure* that lets one copy of it serve two environments — plus the production posture the
proof deliberately skipped, which is where the real decisions are.

## Technical Context

**Language/Version**: HCL (Terraform ≥ 1.9) and Nomad jobspec. No Python change to `src/`; the only
repository code touched is the test-side credential path that FR-006 deletes

**Primary Dependencies**: Existing — `hashicorp/vault` and `kreuzwerker/docker` providers, Vault
Enterprise 2.0.3+ent (floor: the agent registry was introduced there), Nomad 2.0.4. **New**: Vault's
PKI secrets engine for TLS, already confirmed available under the current licence

**Storage**: Terraform state stays local per environment root. Remote state is an operator concern
and is a recorded deferral, not an omission — see FR-010 handling below

**Testing**: The tree is verified by *applying* it (FR-016). Three checks: a configuration-identity
comparison across two substrates using plan-level application, a bring-up contract assertion, and
the durability conformance rows now running inside an allocation. No new Python test tiers

**Target Platform**: Workstation (Docker Desktop) for the development substrate; VM/instance-shaped
for production. Kubernetes remains an accommodation whose *requirements* this feature documents and
whose implementation it does not build (ADR-0025)

**Project Type**: Infrastructure. Sealed core is untouched, which makes this the first feature since
002 with no Constitution Principle V exposure

**Performance Goals**: N/A. Bring-up wall-clock is a usability concern, not a gate. The one real
constraint is that the conformance-in-allocation path must not make `make conformance` so slow that
people stop running it — it is already the only place the durability rows execute

**Constraints**: Substrate is the only permitted delta (FR-002); bootstrap order Terraform → Vault →
Nomad → harness is the only ordering that terminates (ADR-0048); the trust store is never scheduled
by the substrate it constrains (FR-004)

**Scale/Scope**: One enclave, one tenant. Multi-tenancy (ADR-0046) and multi-region are out of scope

### The FR-010 decision — production posture

FR-010 requires each of four items to be implemented or deferred **with a reason**. This is the
plan's central judgment call, so it is stated in one place rather than distributed through the
design. Reasoning in [research.md](./research.md).

| Item | Decision | Why |
| --- | --- | --- |
| **TLS from the control plane's own CA** | **Implement** | Without it the workload identity JWT and the database credential cross the network in clear text. On a loopback workstation that is tolerable; the moment the tree is applied to real infrastructure it is not, and a tree whose first production use is insecure by default is worse than no tree |
| **Bootstrap credential revocation** | **Implement**, production profile only | ADR-0015's flow requires it and it is cheap. Dev keeps the root token, because revoking it there would break the re-apply loop that makes the enclave usable — recorded as a profile difference, which is exactly what profiles are for |
| **Unseal shape** | **Seam only** | Auto-unseal binds to whatever KMS the operator runs. Implementing one variant would privilege one cloud and still leave every other operator writing their own. The tree exposes the seal configuration as a parameter with the dev default being the 1-of-1 shamir it already uses |
| **High availability** | **Defer, with a reason** | The largest item by far, and the only one that cannot be verified without multi-node infrastructure this project does not have. Deferring it keeps the feature shippable and honest; implementing it badly would produce a tree that claims HA and has never survived a node loss |

**The HA deferral has a consequence that must not be lost**: 005's conformance caveat persists —
fencing and parking are proven against single-node behaviour, and multi-node partition remains
unexercised. Landing this feature does not close that, and the conformance contract says so.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.0.1**; re-check if the version advances.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Composes Terraform, Vault, and Nomad. No orchestrator, no secrets manager, nothing reimplemented |
| II — Total Interception; One Governed Tool Layer | N/A | No tool path changes |
| III — Fail-Closed, In-Process Enforcement | Pass | Provisioning fails closed: sealed store refuses configuration, missing prerequisite fails bring-up by name, absent identity yields no credential |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, and strengthens it** | Deletes the last static-token path in the repository (FR-006) and revokes the bootstrap credential in production. The conformance suite stops being the exception to Principle IV and becomes an instance of it |
| V — Sealed Core, Versioned Seams | N/A | `src/` is untouched. The only repository code change is deleting a test-side credential class |
| VI — Lean by Default | Pass | No new operated component. The PKI engine is a new *use* of Vault, which is already in the baseline, not a new thing to run |
| VII — Anti-Fragmentation | **Pass — this is the feature** | One tree, substrate as the only permitted delta, asserted by comparison rather than asserted in prose |
| VIII — Eval-Gated Promotion | N/A | No packs, prompts, models, or policies |
| IX — Evidence Over Claims | Pass | Correctness demonstrated by applying the tree (FR-016), not by reading it. The identity comparison is produced, not claimed |
| X — The Decision Record Governs | Pass | Binds ADR-0025, 0048, 0015, 0007. The HA deferral and the unseal seam are recorded here rather than left silent |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1: still **PASS**. Three notes for review:

- **Principle IV is strictly better after this feature than before.** `DevVaultCredentials` is the
  only place in the tree where a static token substitutes for an attested identity, and it exists
  solely because the suite had nowhere to run. Giving it somewhere to run removes it.
- **Principle VII is the whole feature, so its check is not a formality.** SC-001 must be produced
  by comparing two applications. A design where the comparison is aspirational would pass this
  gate on paper and fail its purpose.
- **Principle VI — the PKI engine.** Using Vault to issue Vault's own certificates is a new
  bootstrap dependency and deserves naming: the first certificate cannot come from a PKI that is
  not yet serving. The design handles it with a short-lived self-signed bootstrap cert, replaced by
  a PKI-issued one once the engine is up.

## Project Structure

### Documentation (this feature)

```text
specs/006-deployment-module-tree/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── module-interface.md
│   ├── bring-up-contract.md
│   └── substrate-requirements.md
├── checklists/requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source (repository root)

```text
infra/
├── modules/
│   ├── trust-fabric/          # substrate-INDEPENDENT — the product
│   │   ├── variables.tf       # agent definitions, JWKS URL, database endpoint, profile
│   │   ├── auth.tf            # JWT auth backend + roles (agent ceilings, harness)
│   │   ├── registry.tf        # agent registry entries, identity entities
│   │   ├── policies.tf        # ceiling policies, harness database policy
│   │   ├── database.tf        # database secrets engine, dynamic role, rotate-root
│   │   ├── pki.tf             # control-plane CA, certificate issuance
│   │   └── outputs.tf
│   ├── substrate-docker/      # dev: containers on a workstation
│   └── substrate-vm/          # production shape — interface + reference implementation
├── environments/
│   ├── dev/                   # substrate-docker + trust-fabric
│   └── production/            # substrate-vm + trust-fabric, profile = production
├── jobs/
│   ├── postgres.nomad.hcl
│   ├── harness-probe.nomad.hcl
│   └── conformance.nomad.hcl  # NEW — the suite as a scheduled workload
└── bin/
    ├── enclave-up             # bring-up, publishing the contract
    ├── enclave-down
    └── enclave-verify         # asserts every contract guarantee holds

tests/conformance/durability/conftest.py   # DevVaultCredentials DELETED (FR-006)
Makefile                                    # dev-up/down/status become tree entry points
```

**Structure Decision**: modules + environment roots rather than workspaces or `-var-file`
switching. Workspaces share one state and one provider configuration, which is exactly wrong when
the substrate — including the Vault endpoint itself — is what differs. Separate roots make the
delta *visible in the file layout* rather than hidden in a variable, which is what FR-002 has to be
able to assert.

`infra/dev-enclave/` is deleted, not kept alongside (FR-015, SC-010). Its README's hard-won failure
catalogue moves into the tree's own documentation, because that content is the part worth keeping.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
