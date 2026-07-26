# Data Model: Deployment Module Tree

**Feature**: `specs/006-deployment-module-tree`
**Date**: 2026-07-25

The "entities" here are module interfaces and configuration objects rather than runtime records.
What matters is which of them may vary between environments, because FR-002's claim rests entirely
on that boundary being drawn in one place.

## The axes of variation

Two, and only two. Conflating them is how a tree fragments.

| Axis | What it controls | Example |
| --- | --- | --- |
| **Substrate** | *Where* components run and what runs them | Containers on a workstation vs instances on customer infrastructure |
| **Profile** | *Posture* — how hardened the deployment is | Whether the bootstrap credential is revoked; which seal is configured |

Profile is not a substrate difference and must not live in the substrate module. A workstation
could in principle run the production profile; that it usually does not is a convenience, not a
constraint. Keeping the axes separate is what lets FR-002 say "the substrate is the only delta"
while the dev and production roots still differ in posture.

## Module interfaces

### `trust-fabric` *(substrate-independent — the product)*

| Input | Type | Rules |
| --- | --- | --- |
| `agent_definitions` | map of object | Each supplies ceiling policy name, allowed paths, owner, description |
| `nomad_jwks_url` | string | Where Vault verifies workload identities; **substrate-supplied** |
| `database_endpoint` | string | Host:port as reachable *from Vault*; **substrate-supplied** |
| `profile` | `"development"` or `"production"` | Selects posture, not placement |
| `seal_config` | object, nullable | Null means the environment's default seal. Non-null is passed through untouched |

| Output | Meaning |
| --- | --- |
| `jwt_auth_path` | Mount a workload authenticates against |
| `database_creds_path` | Where a workload reads a dynamic credential |
| `ca_certificate` | Control-plane CA, for clients that must trust it |
| `configuration_digest` | **Stable hash of every configured element.** The thing SC-001 compares. Computed from resolved inputs and literal configuration only — a digest derived from resource attributes is unknown until apply, and comparing two unknowns passes while proving nothing |

**Validation**: this module MUST NOT reference a substrate resource, a container, an instance, or a
provider that only one substrate has. That is the property making FR-002 checkable rather than
aspirational, and it is asserted by inspection of the module's inputs — a substrate leak shows up
as a new input this table does not list.

### `substrate-*`

| Output | Meaning |
| --- | --- |
| `vault_address` | Where the trust store answers |
| `nomad_jwks_url` | Fed into `trust-fabric` |
| `database_endpoint` | Fed into `trust-fabric` |

**Validation**: a substrate module MUST NOT configure trust. If it creates a policy, a role, or a
registry entry, the delta has escaped its layer.

## ConfigurationDigest

The evidence behind SC-001.

| Field | Rules |
| --- | --- |
| `auth_methods` | Mount paths and types, sorted |
| `auth_roles` | Role names with bound claims, audiences, token policies and TTLs |
| `policies` | Policy names and their normalised rule text |
| `secrets_engines` | Mount paths and types, sorted |
| `registry_entries` | Registered agent display names and their ceiling policies |
| `database_roles` | Role names, creation/revocation statement text, TTLs |

**Validation**: computed from the *planned* configuration, so it needs no running infrastructure
(the clarified reading of SC-001). Two applications of the tree to different substrates MUST
produce identical digests. Deliberately excludes anything substrate-derived — addresses, container
identifiers, instance names — because including them would make the digests differ by construction
and the comparison meaningless.

## ProductionPostureItem

Four, each with a recorded disposition. FR-010 is satisfied by the *presence* of a disposition, not
by any particular one.

| Item | Disposition | Recorded where |
| --- | --- | --- |
| Transport security | Implemented — PKI-issued, self-signed bootstrap | `modules/trust-fabric/pki.tf` |
| Bootstrap credential lifecycle | Implemented for `profile = "production"` | `modules/trust-fabric/` |
| Unseal shape | Seam only; development default is 1-of-1 shamir | `seal_config` input |
| High availability | **Deferred** — unverifiable without multi-node infrastructure | research.md, and the 005 conformance caveat it keeps alive |

**Validation**: exactly four items, each with a non-empty disposition. An item whose disposition is
absent fails FR-010 — silence is the failure mode, not deferral.

## BringUpContract

What is true when bring-up reports success.

| Guarantee | Assertion |
| --- | --- |
| Scheduler reachable | Leader responds |
| Trust store reachable and **unsealed** | Seal status reports unsealed and active |
| Trust fabric configured | Auth mount, ceiling policies, registry entries, database engine all present |
| Dynamic credentials issuable | A credential is minted and it authenticates |
| State store reachable and migrated | Schema objects present |
| Substrate volumes intact | Persistent state survived the last stop |

**Validation**: every guarantee is machine-checkable. A guarantee that can only be confirmed by
reading something is not a guarantee — it is a hope, and it is the drift FR-008 exists to prevent.

## Failure catalogue

Carried forward from the proof. Each entry is a condition, the symptom it presents as, and where
that symptom points *instead of* its cause — the last column being why these cost time.

| Condition | Presents as | Points at |
| --- | --- | --- |
| Scheduler's container driver disallows volume mounts | Task fails to start | The workload definition, which is correct |
| Fresh named volume owned by root; trust store runs as a non-root uid | Crash loop on permission denied | Storage, not ownership |
| Capability written in short form | Every apply replaces the container and **reseals the store** | A race, which it is not |
| Trust store data moved to a differently-named node | Unseals, then permanently standby, every call answering "sealed" | The seal, not the node identity |
| Configuration applied against a sealed store | Resources vanish from state; the next apply fails on conflict | The configuration, not the seal |
| State store volume destroyed while the trust store holds the rotated credential | Every credential fails authentication | The credential path, not the coupling |
| Configuration state deleted or orphaned while its resources still run | Next apply fails on a name conflict | The new configuration, not the abandoned state |

**Validation**: FR-013 requires each to be prevented or detected-and-explained. Detection must name
the cause column, not the symptom column.
