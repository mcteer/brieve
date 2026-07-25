# ADR-0001: A framework-agnostic governed core with thin framework adapters

- **Status**: Accepted
- **Date**: 2026-01-15
- **Relates to**: [ADR-0002](0002-adopt-first-migrate-and-delete.md), [ADR-0017](0017-primary-adapter-selection.md)
- **Requirements**: R16

## Context

Building an agent platform requires choosing an agent framework, and the field moves
fast enough that any choice made today will look dated within a year. Frameworks
compete on orchestration ergonomics — graph execution, state machines, retry semantics,
streaming — and each has its own idioms for tools, state, interrupts, and run context.

Committing the platform to one framework would tie the governance guarantees to that
framework's lifecycle: its breaking changes become ours, its abandonment becomes our
migration, and its idioms leak into how our enforcement is expressed. Supporting
several frameworks by writing the platform several times is worse: guarantees drift
between implementations, and the drift is invisible until an audit finds it.

The observation that resolves this: orchestration is the commodity layer. Multiple
mature frameworks do it well and are actively maintained. What no framework provides —
and what this project exists to build — is the governance layer: per-task authority
that cannot exceed the requesting human, fail-closed enforcement on every tool call,
registry-gated tool access, and an audit trail that reconciles to records. That layer
has no reason to know which framework is orchestrating.

## Decision

The platform is a **framework-agnostic governed core** with **thin adapters** binding it
to specific agent frameworks.

The core holds identity, the hook pipeline, the tool client, policy, durability,
telemetry, registry clients, and the pack loader. **The core never imports an agent
framework.** Adapters import the core, never the reverse.

An adapter maps exactly four concepts from its framework onto core machinery:

- framework tools → hook-wrapped governed tool calls
- framework state → the durability layer
- framework interrupts → approval hooks
- framework run context → identity and correlation

That mapping is the adapter's entire permitted contents. **If an adapter contains more
than glue, the abstraction is wrong — the logic belongs in core.** A shared conformance
suite runs identically against every adapter, so the abstraction cannot rot quietly.

## Consequences

Governance guarantees are stated and enforced once, in one codebase, and cannot diverge
between frameworks — the conformance suite makes divergence a test failure rather than
a discovery. Adopting a new framework becomes a bounded piece of work: implement four
mappings, pass the suite. Framework churn is absorbed at the edge instead of
propagating through the platform.

The cost is a layer of indirection that would be unnecessary in a single-framework
product, and a discipline that has to be actively maintained: the pressure to put "just
this one thing" in an adapter is constant, because the framework-specific path is
always the shorter one at the moment of writing. The four-mapping rule exists to make
that pressure resolvable in review without argument — a reviewer does not have to
adjudicate what "thin" means, only whether the code is one of the four mappings.

It also means the platform cannot expose a framework's distinctive orchestration
features directly. Where a framework offers something genuinely valuable that the core
lacks, the answer is to add it to the core framework-agnostically, not to leak it
through an adapter.

This decision creates a standing obligation: every adapter ships with, and passes, the
shared conformance suite, including the governance-ordering and fail-closed assertions.
