# Research: Deployment Module Tree

**Feature**: `specs/006-deployment-module-tree`
**Date**: 2026-07-25

## Decision: Modules plus environment roots, not workspaces

- **Decision**: `infra/modules/{trust-fabric,substrate-*}` composed by thin roots under
  `infra/environments/{dev,production}`. Each root has its own state and its own provider
  configuration.
- **Rationale**: FR-001/FR-002. What differs between environments includes *the Vault endpoint
  itself*, and a Terraform workspace shares one provider configuration across workspaces. Using
  workspaces would mean the substrate difference lives in conditional expressions inside shared
  files — the fragmentation this feature exists to end, wearing a different hat.
- **Why the layout matters for the assertion**: FR-002 has to be *checkable*. With separate roots
  composing a shared module, "the delta is confined to the substrate" is a structural property
  anyone can see, and the plan-level comparison confirms it. With conditionals it becomes a claim
  about code paths that a reviewer has to trace.
- **Alternatives considered**: Terraform workspaces (above). A single root with `-var-file` per
  environment (same objection: provider configuration is not variable-driven in the way needed).
  Terragrunt (a new tool to learn and operate, for a two-environment problem — Principle VI).

## Decision: TLS is implemented, bootstrapped by a self-signed certificate

- **Decision**: Vault's PKI secrets engine issues the control plane's certificates. Vault itself
  starts with a short-lived self-signed certificate, and once the PKI engine is configured its
  listener certificate is replaced by a PKI-issued one.
- **Rationale**: FR-010. Without TLS the workload identity JWT and the database credential cross
  the network in clear text. On a loopback workstation that is tolerable; the moment this tree is
  applied to real infrastructure it is not — and a tree whose *first production use* is insecure by
  default is worse than having no tree, because it looks finished.
- **The bootstrap circularity, named**: the first certificate cannot come from a PKI engine that is
  not yet serving. This is the same shape as ADR-0048's Vault-under-Nomad argument and has the same
  resolution — something outside the loop goes first. A self-signed certificate with a deliberately
  short life is that something, and its replacement is part of apply rather than a follow-up task
  someone forgets.
- **Alternatives considered**: An operator-supplied certificate (pushes the problem out of the tree
  and makes the dev path require one too). Terminating TLS at a proxy (a new operated component for
  a problem Vault already solves). Leaving TLS to the operator entirely (the silent-absence failure
  FR-010 exists to prevent).

## Decision: The bootstrap credential is revoked in production and kept in development

- **Decision**: The production profile revokes the bootstrap root token once configuration is
  applied. The development profile keeps it, and says so.
- **Rationale**: ADR-0015's flow requires revocation, and it is cheap to do. But revoking it in
  development would break the re-apply loop that makes the enclave usable day to day, and an
  enclave that is painful to re-apply is one people stop re-applying — which costs more safety than
  the retained token does on a workstation.
- **Why this is a profile difference and not a substrate one**: it is a posture choice, not a
  question of where things run. Keeping it out of the substrate layer preserves FR-002's claim that
  the substrate is the only delta — profiles are a separate, declared axis.
- **Alternatives considered**: Revoke everywhere (breaks the dev loop). Keep everywhere (violates
  ADR-0015 and is the shape that must not reach a deployment). Leave it to the operator (silent
  absence again).

## Decision: Unseal is a seam with a development default, not an implementation

- **Decision**: The seal configuration is a module parameter. The development default is the
  existing 1-of-1 shamir; production supplies an auto-unseal configuration from its own
  environment.
- **Rationale**: FR-010. Auto-unseal binds to a specific KMS. Implementing one variant would
  privilege whichever cloud we picked and still leave every other operator writing their own, so
  the honest deliverable is the seam plus documentation of what must be supplied.
- **The deferral is narrow on purpose**: the *seam* is in scope and testable — a production root
  must be able to express an auto-unseal configuration without editing the trust-fabric module.
  What is deferred is shipping a KMS-specific variant.
- **Alternatives considered**: Implement transit auto-unseal against a second Vault (a second Vault
  to operate, which is a real cost for a development convenience). Ship a cloud KMS variant (picks
  a cloud).

## Decision: High availability is deferred, and the consequence is recorded

- **Decision**: Single-node Vault and single-server Nomad remain. HA is deferred with a reason
  rather than attempted.
- **Rationale**: It is the largest of the four posture items and the only one that cannot be
  verified without multi-node infrastructure this project does not have. A tree that claims HA and
  has never survived a node loss is worse than one that says it is single-node.
- **The consequence, stated so it is not lost**: 005's conformance caveat persists. Fencing and
  parking are proven against single-node behaviour, and multi-node partition remains unexercised.
  Landing this feature does **not** close that gap, and both the roadmap and the conformance
  contract must continue to say so.
- **What would trigger it**: the first deployment target that requires it, or the first time
  single-node behaviour is suspected of hiding a fencing defect. Recorded as a named trigger rather
  than "later".
- **Alternatives considered**: Three-node raft in dev (heavier workstation footprint, and still not
  a real partition test — three containers on one host share a failure domain). Implement HA only
  in the production root (untested code on the path that matters most, which is the worst place for
  it).

## Decision: The conformance suite runs as a batch Nomad job with the working tree mounted

- **Decision**: `infra/jobs/conformance.nomad.hcl` is a batch job whose task mounts the repository
  working tree and runs the suite, holding a Nomad workload identity bound to its own Vault role.
  `make conformance` submits the job and surfaces its exit status.
- **Rationale**: FR-005/FR-006/SC-002. This is the whole point — the suite must present a real
  attested identity rather than a development token. Mounting the working tree rather than building
  an image keeps the edit-test loop usable; an image build per run would make the durability rows
  something people avoid running, and they are already the only place those guarantees are checked.
- **The deletion this enables**: `DevVaultCredentials` in `tests/conformance/durability/conftest.py`
  is removed, not merely bypassed. While it exists, someone can reach for it.
- **Honest cost**: the suite's failure output now arrives through allocation logs rather than
  directly, which is a worse debugging experience than a local pytest run. Mitigated by having the
  entry point stream and surface the exit status, not by pretending the cost is zero.
- **Alternatives considered**: Build a container image per run (slow enough to discourage running).
  Keep a host-run path alongside (leaves the static token in the tree, which is what FR-006 forbids).
  Give the host process a Vault approle (a standing credential on a workstation — the thing
  Principle IV forbids).

## Decision: Bring-up publishes a contract that a command asserts

- **Decision**: The bring-up contract is a document, and `enclave-verify` asserts each of its
  guarantees against a running environment. `enclave-up` runs the verification before reporting
  success.
- **Rationale**: FR-008. A contract nobody checks drifts from reality, and the drift surfaces as a
  confusing test failure in whatever suite trusted it. Making the assertion executable means the
  contract is either true or loudly false.
- **Alternatives considered**: Document the guarantees only (drifts). Have each test suite check its
  own prerequisites (every suite reimplements the same checks, and they disagree).

## Decision: The proof directory is deleted, its failure catalogue is not

- **Decision**: `infra/dev-enclave/` is removed. The six recorded traps move into the tree's
  documentation as a first-class section.
- **Rationale**: FR-015/SC-010 as clarified — two applicable trees is the fragmentation this
  feature ends. But the trap catalogue is the most expensive knowledge the proof produced, and
  deleting it with the directory would mean paying for it twice.
- **Alternatives considered**: Keep the proof as reference (SC-010 forbids a second applicable
  tree, and "reference" erodes into "the one that works"). Delete everything (throws away the
  catalogue).
