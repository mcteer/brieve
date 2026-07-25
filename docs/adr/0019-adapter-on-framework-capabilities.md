# ADR-0019: Restructure the adapter on framework capabilities; governance runs first

- **Status**: Accepted
- **Date**: 2026-04-15
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0017](0017-primary-adapter-selection.md), [ADR-0027](0045-tiered-capabilities.md), [ADR-0040](0040-deferred-tool-disclosure.md), [ADR-0041](0041-code-mode-requires-hook-parity.md)

## Context

The primary framework introduced a capability model — composable units that contribute
tools, hooks, and behavior to an agent — along with native support for human-in-the-loop
interruption, deferred tools, and deferred loading. These are close analogues of things
the adapter had been implementing itself.

Under the adopt-first discipline ([ADR-0002](0002-adopt-first-migrate-and-delete.md)) and
the adapters-are-glue rule ([ADR-0001](0001-framework-agnostic-core.md)), that is a clear
signal: capability-shaped machinery the adapter maintains should move onto the framework's
own mechanism.

Doing so raises one serious question. If governance is expressed as a capability
alongside other capabilities, and capabilities compose, then **composition order
determines whether governance is enforced**. A capability that contributed a tool and ran
before the governance capability would produce an ungoverned tool call — the exact hole
[ADR-0006](0006-in-process-fail-closed-enforcement.md) exists to close, reintroduced
through a framework feature rather than a network path.

The framework's code-execution mode raises the same question in a different form:
tool calls issued from model-written code in a sandbox must still round-trip through the
hook pipeline, and sandbox safety is not the same property as preserved governance.

## Decision

**The adapter is restructured on the framework's capability model.** Capability packs
become framework capabilities; HCL definitions compile to agent specifications; native
human-in-the-loop and deferred-tool mechanisms replace adapter-maintained equivalents.

**Governance is itself a capability — and its ordering is a conformance assertion.** The
GovernanceCapability (identity injection, hook pipeline, redaction, audit) **runs first
among co-resident capabilities and fails closed**, and the conformance suite asserts both
properties directly rather than trusting configuration.

**Capability loading is a governed event**: deferred loading is hooked, audited, and
ceiling-checked, so what an agent can pull into itself at runtime is bounded by the same
authority model as what it can do.

**Code mode is off by default in regulated profiles** pending verified per-tool
interception — later hardened into an unconditional gate
([ADR-0041](0041-code-mode-requires-hook-parity.md)).

A glossary is introduced to resolve naming collisions between the framework's vocabulary
and this platform's.

## Consequences

The adapter gets thinner, which is the correct direction — machinery the framework
maintains is machinery this project does not. Native interruption and deferred tools are
better than the adapter's versions and are maintained by someone else.

Making governance ordering a *conformance assertion* rather than a configuration
convention is the load-bearing part. It converts a property that could silently break
during a refactor into a test that fails, which is the only durable form of this
guarantee.

Treating capability loading as a governed event closes a subtler gap: without it, an
agent's effective toolset at runtime could exceed what its definition declared, which
would make the definition a weaker record than it appears.

The costs are dependency-shaped. The adapter now tracks a specific framework's capability
model closely, so upstream changes to that model land on the adapter directly — the core
is insulated, the adapter is not, which is by design but is not free. The naming collision
is a permanent low-grade tax: two vocabularies using the same words for different things,
requiring care in every document and code review.

Deferring code mode also means declining a real efficiency gain until interception can be
proven, which is the right ordering and a visible cost while it lasts.
