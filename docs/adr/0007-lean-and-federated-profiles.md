# ADR-0007: Two deployment profiles; nothing blocking that could be a library

- **Status**: Accepted
- **Date**: 2026-02-19
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0008](0008-no-gateway-or-registry-product.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0028](0028-named-trigger-for-added-components.md)
- **Requirements**: R12

## Context

Governance platforms accrete infrastructure. Each component is individually justified —
a gateway for model traffic, a service mesh for mTLS, a workload identity system, a
policy server, a message queue for audit, a separate store for evaluation data — and
collectively they produce something that takes a quarter to stand up and a dedicated
team to operate.

That outcome is fatal here for two reasons. The requirement is explicitly that this be
simple to adopt: an organization should be able to get a governed stack running quickly,
not budget a program for it. And every operated component is a component that can fail,
which for a fail-closed system ([ADR-0006](0006-in-process-fail-closed-enforcement.md))
means a component that can stop work.

At the same time, larger organizations genuinely do run gateways, registries, and
identity infrastructure, and integrating with those is not optional either. A design
that only serves the minimal case cannot serve them; a design that assumes their
infrastructure cannot serve anyone else.

## Decision

**Two profiles, with the lean one as the default.**

- **Lean** is the default and the baseline: no gateway, no separate workload-identity
  system, registry state on the control plane, embedded policy engine, one Postgres.
  The minimum set of operated components that delivers the full governance guarantee.
- **Federated** integrates the components an organization already operates —
  gateways, registries, identity infrastructure — through the provider interfaces
  ([ADR-0008](0008-no-gateway-or-registry-product.md)). It adds integration, not
  capability: the guarantees are identical in both profiles.

Governing both is a standing architectural rule:

> **Nothing blocking may be added that could instead be a library, a signed cache, or an
> asynchronous emitter.**

A capability that can be a library is a library. State that can be a cached, signed
snapshot is a snapshot, not a service call. Telemetry that can be emitted asynchronously
is never in the request path. Adding an operated component to the blocking path requires
a named trigger recorded as a decision
([ADR-0028](0028-named-trigger-for-added-components.md)) — not a general argument that
it would be useful.

## Consequences

The default deployment is small enough to stand up quickly and to reason about
completely: the list of outages that stop work is short and enumerable, and everything
else degrades to stale rather than stopped. That property is what makes a fail-closed
system operable — operators can hold the whole failure model in their heads.

Organizations with existing infrastructure integrate it without the platform assuming
they have it, and organizations without it are not required to acquire it. Neither
profile is a lesser version of the other.

The cost is a persistent design constraint that will feel arbitrary in individual cases.
The convenient implementation of some future feature will be a new service, and this
rule will require the harder library-or-cache design instead. The rule holds because the
alternative is not one extra service — it is the accumulated dozen, arrived at one
reasonable decision at a time.

Maintaining behavioral parity across both profiles is an ongoing testing obligation: a
feature that works only when a gateway is present has broken the guarantee that the
profiles differ in integration, not capability.
