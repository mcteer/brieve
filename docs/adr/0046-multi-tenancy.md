# ADR-0046: One platform, isolated tenants — using the products' own isolation primitives

- **Status**: Accepted
- **Date**: 2026-05-06
- **Source**: gap review ([GR-1](GR-1-gap-review.md))
- **Relates to**: [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0035](0035-audit-as-a-governed-read-path.md), [ADR-0042](0042-duplicate-detection-and-precedent-cache.md)

## Context

Organizations adopting this platform have multiple teams, and those teams must not see each
other's estates, audit records, or costs. The question is how that separation is achieved.

Deploying a separate enclave per team is the naive answer, and it defeats the purpose: the
platform exists to give an organization *one* governed path, and five enclaves is five
drifting paths with five upgrade schedules and five policy sets — exactly the fragmentation
the anti-fragmentation rule exists to prevent
([ADR-0025](0025-enclave-is-the-default-topology.md)).

Building a bespoke tenancy layer inside the platform is the other option, and it means
inventing isolation primitives when the products being governed already have good ones —
namespaces, projects, and their equivalents, each with mature access control and audit
separation. Reimplementing that would duplicate vendor capability and, worse, produce a
second isolation model that could disagree with the first.

There is a subtler risk that appears only in a multi-tenant deployment: every optimization
that shares state across runs — caches, indices, precedent — becomes a potential
cross-tenant leak, and the leak is silent.

## Decision

**One shared platform, isolated tenants**, using the managed products' own isolation
primitives rather than a bespoke tenancy layer: separate namespaces in the trust fabric,
separate projects and organizations in the infrastructure products, separate namespaces on
the orchestrator.

Per tenant: **budgets, metrics, and audit views**. Evidence queries are tenant-scoped by the
same authorization core that scopes everything else
([ADR-0035](0035-audit-as-a-governed-read-path.md)).

**Shared state never crosses a tenant boundary.** Caches, in-flight indices, and precedent
are tenant and team scoped by construction, never global
([ADR-0042](0042-duplicate-detection-and-precedent-cache.md)) — a cross-tenant hit would be
a confidentiality breach regardless of how useful it would be.

The result an organization gets is **one governed golden path, not several drifting ones.**

## Consequences

An organization operates a single platform with a single upgrade schedule and a single
policy surface, while teams remain properly separated. Using the products' own primitives
means isolation is enforced by systems already trusted and audited for exactly that
purpose, rather than by a layer this project invented.

It also keeps the enclave's footprint proportional: one deployment serves the organization,
so the operational cost does not multiply with team count.

The costs are real and concentrated in one place: **cross-tenant isolation becomes the
platform's highest-severity failure mode.** A scoping bug is not a bug, it is a
confidentiality breach — which is why isolation gets its own test class rather than
incidental coverage, parameterized across every surface.

Tenant-scoping shared state also reduces its value. A globally shared precedent cache would
have a far higher hit rate than a tenant-scoped one; that difference is the price of
correctness and is paid deliberately.

Depending on the products' isolation primitives means inheriting their granularity. Where a
product's isolation boundary is coarser than a tenant needs, the platform cannot make it
finer — the honest answer is to say so rather than to layer something on top that appears
to.
