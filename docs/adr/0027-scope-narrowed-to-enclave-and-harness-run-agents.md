# ADR-0027: Narrow the product to the enclave and the agents it runs

- **Status**: Accepted
- **Date**: 2026-05-20
- **Amends**: [ADR-0012](0012-runtime-versus-attach-posture.md) (attach posture becomes a compatibility statement), [ADR-0014](0014-two-layer-runtime-protection.md) (layer two is external)
- **Relates to**: [ADR-0011](0011-harness-first-sdks-at-perimeter.md), [ADR-0025](0025-enclave-is-the-default-topology.md)

## Context

[ADR-0012](0012-runtime-versus-attach-posture.md) committed to a second posture:
wire-level governance for agents the platform does not run, delivered through a mesh
guardrail. [ADR-0014](0014-two-layer-runtime-protection.md) gave that posture its
mechanism.

Two things changed the calculation. The primary adapter's native hook points turned out to
subsume the function the wire-level filter was intended to provide *for agents the harness
runs* — the semantic enforcement is better done in-process, which was always the position
([ADR-0006](0006-in-process-fail-closed-enforcement.md)), and the in-process
implementation is now demonstrably sufficient.

More importantly, the mesh guardrail for *foreign* agents is the product vendor's own
security-services motion. Building it here would duplicate a vendor initiative — precisely
what adopt-first exists to prevent ([ADR-0002](0002-adopt-first-migrate-and-delete.md)) —
and would stretch this project across two quite different problems: governing agents it
runs, and containing agents it does not.

A project this small cannot do both well, and doing the second badly would undermine
confidence in the first.

## Decision

**The product is the enclave and its harness-run agents.**

The mesh guardrail for foreign agents is **the vendor's motion, not this project's**. The
enclave **coexists with it** — an organization running both gets sensible behavior, and
the platform's traffic is well-formed for a mesh to observe — but this project does not
implement, ship, or support it.

This **amends [ADR-0012](0012-runtime-versus-attach-posture.md)**: the attach posture
becomes a compatibility statement rather than a committed second offering. It **amends
[ADR-0014](0014-two-layer-runtime-protection.md)**: layer two remains architecturally real
and is now unambiguously external. The corresponding roadmap line item is removed.

## Consequences

Scope narrows to something a focused team can do excellently, and the boundary is easy to
state: if the harness runs the agent, the platform governs it; if not, the platform
coexists with whatever does.

Removing a roadmap commitment also removes a category of half-built capability — the worst
outcome available was a partially delivered attach story that adopters relied on.

The cost is honest and immediate. Organizations with existing agent estates get less from
this project than [ADR-0012](0012-runtime-versus-attach-posture.md) implied they would:
the answer is now migrate them into the harness, or govern them with something else.
Some prospective adopters will be disappointed, and some will choose differently as a
result.

There is also a positioning consequence. "We govern the agents we run" is a narrower claim
than "we govern your agents," and it must be stated consistently — including in materials
written while the earlier posture was current, which need correcting rather than quietly
aging.

The decision is recorded as an amendment rather than a supersession because
[ADR-0012](0012-runtime-versus-attach-posture.md) and
[ADR-0014](0014-two-layer-runtime-protection.md) remain correct about the architecture;
what changed is which parts of it this project builds.
