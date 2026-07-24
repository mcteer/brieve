# ADR-0006: Enforcement lives in-process and fails closed

- **Status**: Accepted (the default-gateway clause superseded by [ADR-0008](0008-no-gateway-or-registry-product.md))
- **Date**: 2026-02-12
- **Supersedes**: [ADR-0005](0005-adopt-gateway-substrate.md)
- **Relates to**: [ADR-0008](0008-no-gateway-or-registry-product.md), [ADR-0019](0019-governance-capability-runs-first.md), [ADR-0037](0037-tool-transport-policy.md), [ADR-0041](0041-code-mode-requires-hook-parity.md)
- **Requirements**: R7

## Context

Every agent platform needs a point where policy is applied to what the agent does. The
conventional answer is a gateway or service mesh: route all traffic through a chokepoint
and enforce there. It is operationally familiar, it centralizes configuration, and it
works — as long as the traffic actually goes through the chokepoint.

That conditional is the problem. Network-anchored enforcement is only as strong as the
network's configuration, and network configuration is exactly the thing that drifts:
a pod scheduled on the wrong node pool, a sidecar that failed to inject, a direct
egress route added for debugging, an SDK that bypasses the proxy. Each is an ordinary
operational event, none of them looks like a security incident, and every one of them
silently removes the guarantee.

For a platform whose central claim is that agent actions cannot escape their governed
scope, "enforced unless something is misconfigured" is not a claim worth making. The
guarantee has to hold under misconfiguration, or it is not a guarantee.

There is a second failure mode independent of placement: what happens when the
enforcement path itself errors. A policy engine that is unreachable, a registry snapshot
that will not parse, an identity service that times out. The convenient behavior is to
allow and log; the correct behavior is to deny.

## Decision

**Enforcement is in-process and fails closed.**

Every tool invocation passes pre- and post-execution hooks running inside the agent
runtime itself — identity injection, registry resolution, policy evaluation, approvals,
redaction, audit. This pipeline is not optional, not configurable away, and not
delegated.

**Enforcement is never anchored in a gateway, mesh, or any external component.** Where
an organization runs such components, they are defense-in-depth: welcome, integrated
through provider interfaces, and never load-bearing. The platform's guarantee does not
depend on them being present or correctly placed.

**Failure denies.** Any error in the enforcement path — policy engine unreachable,
registry unresolvable, identity unavailable, hook raising an exception — results in the
call being denied and audited, never allowed through.

## Consequences

The guarantee survives misconfiguration, which is what makes it stateable to an auditor.
An agent whose network path is wrong does not quietly become ungoverned; it stops
working, loudly, which is the correct failure direction for a system with this threat
model.

It also removes the platform's need to own network infrastructure, which cascades:
without enforcement depending on a gateway, the case for shipping one collapses
([ADR-0008](0008-no-gateway-or-registry-product.md)), and the Lean profile becomes
possible.

The costs are real. Fail-closed means an enforcement-path outage stops work rather than
degrading it — the blocking dependency list is short by design, but it is not empty, and
operators must understand which outages stop runs. In-process enforcement also means the
pipeline runs on every call in the hot path, so its performance is the platform's
performance.

Most consequentially, this decision constrains everything downstream that touches tool
invocation. Any execution mode that cannot demonstrate per-call hook parity is
unadoptable in the governed path regardless of its other merits
([ADR-0041](0041-code-mode-requires-hook-parity.md)), and the ordering of the governance
capability relative to other capabilities becomes a conformance assertion rather than a
convention ([ADR-0019](0019-governance-capability-runs-first.md)).

Two standing obligations follow: the conformance suite asserts fail-closed behavior on
every enforcement path, and every hook contributed to the platform ships with a test
proving it denies on internal error.
