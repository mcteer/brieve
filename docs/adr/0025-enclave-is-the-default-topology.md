# ADR-0025: The agent management enclave is the default topology

- **Status**: Accepted (default-versus-edition refined by ongoing experiment)
- **Date**: 2026-05-13
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0028](0028-product-identity.md)
- **Requirements**: R2, R12

## Context

[ADR-0015](0015-control-plane-vault-as-trust-fabric.md) established that the trust fabric
must sit structurally outside every agent's reach. That principle answers where *identity*
lives, but leaves the physical question open: where does the platform itself run?

Running it inside a managed estate is the convenient answer and the wrong one. It puts the
governing system inside the blast radius of the systems it governs, and it means the
platform's own infrastructure is reachable from workloads it is supposed to contain. The
isolation that identity achieved logically is undone physically.

There is a second consideration, less obvious. Adopters must stand this up, and the
standing-up is the first impression of a product whose entire proposition is that governed
infrastructure work can be made simple. A deployment story requiring a Kubernetes platform
team excludes exactly the organizations most in need of the product, and contradicts its
premise on day one.

## Decision

**A dedicated agent management enclave is the default topology**: an isolated,
self-scaffolded cluster — a standalone orchestrator, the control-plane Vault, and Postgres
— built and operated exclusively by the human and CI driven Terraform module the project
ships.

It sits **adjacent to every estate it manages, never inside one**. Authority flows
hub-and-spoke, manufactured per task, with **no standing credentials** to any managed
estate. **Agents are structurally excluded from managing their own platform.**

The baseline deliberately omits a service-discovery layer: native discovery covers a
static topology, mutual TLS comes from the control plane's own certificate authority, and
network segmentation is Terraform-managed firewall rules reviewed in the same pull
requests as everything else. It re-enters only per named trigger
([ADR-0028](0028-product-identity.md)).

**The Terraform module tree is the product's front door.** Day zero is a human-reviewed
plan and apply that stands up the trust fabric before any agent exists — the correct
root-of-trust ceremony, and a working demonstration of the products the platform governs.

**Kubernetes deployment remains supported as an accommodation**, under a hard
anti-fragmentation rule: identical core, identical control-plane posture, identical packs,
identical conformance suite. **The substrate is the only permitted delta.**

## Consequences

The containment story is physical as well as logical, which is what makes it defensible in
a security review: the platform is not merely configured to be separate from the estates it
governs, it is separately deployed.

Three well-understood systems plus the project's own software is a small enough footprint
to stand up quickly and to reason about completely — which is what makes the simplicity
requirement achievable rather than aspirational. The day-zero ceremony doubles as a
demonstration, leaving real infrastructure behind.

The anti-fragmentation rule is the load-bearing constraint here, and it will be under
constant pressure. Every substrate-specific optimization is individually attractive and
collectively fatal: two substrates that diverge become two products to certify, and the
divergence is invisible until an adopter on the wrong one hits a gap.

The costs are real. The enclave is infrastructure the adopting organization must run,
separate from anything they already operate, with its own lifecycle. Choosing a standalone
orchestrator over the more familiar one means some operators encounter an unfamiliar
system. And omitting service discovery from the baseline means the topology must stay
static enough for that omission to hold — the named trigger exists because it will not
hold everywhere.

The default-versus-edition question — whether the enclave remains the sole default or
becomes one of two supported shapes — is being refined by adopter experience rather than
settled here.
