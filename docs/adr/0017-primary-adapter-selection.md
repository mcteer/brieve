# ADR-0017: Pydantic AI is the primary adapter; the second adapter is demand-driven

- **Status**: Accepted
- **Date**: 2026-04-01
- **Amends**: [ADR-0001](0001-framework-agnostic-core.md) (dual-framework retained as architecture, resequenced as investment)
- **Relates to**: [ADR-0019](0019-adapter-on-framework-capabilities.md)
- **Requirements**: R16

## Context

[ADR-0001](0001-framework-agnostic-core.md) established a framework-agnostic core with
thin adapters, and named two frameworks. It did not say which one to build first, and
treating them as equal investments turned out to be a mistake in sequencing rather than
in architecture: two adapters built simultaneously means neither is deep enough to prove
the abstraction, and the conformance suite has nothing to be validated against.

Choosing a primary requires criteria that matter for *this* platform rather than general
framework quality. Three did.

**Determinism at boundaries.** In regulated environments, a framework that silently
coerces a malformed tool argument into something plausible is a liability — the failure
becomes invisible and the audit record becomes wrong. Strict validation that fails loudly
is worth more here than ergonomic leniency.

**Auditable dependency surface.** Regulated adopters re-scan the dependency tree at every
review cycle. A framework with a large, fast-moving transitive tree imposes that cost on
every adopter, repeatedly.

**Reviewer-tractable code.** Workflow code is read by security reviewers and auditors who
are not the people who wrote it. Plain typed code that can be followed line by line is a
different artifact from a graph assembled at runtime, even when both are correct.

Against those criteria the choice was clear. The other framework's distinctive strengths
— graph orchestration, checkpointing, interrupts — are precisely the capabilities the
harness core already provides framework-independently, so a second adapter adds reach
rather than capability.

## Decision

**Pydantic AI is the primary and reference adapter.** Every boundary — tool arguments,
results, model outputs, dependencies — passes strict schema validation, failing loudly
with bounded retries rather than coercing silently.

**The LangGraph adapter is a demand-driven fast-follow**, built when an adopter needs it
rather than speculatively.

**The core stays framework-agnostic**, and the conformance suite remains defined against
both adapters so the abstraction cannot rot in the interval. This amends
[ADR-0001](0001-framework-agnostic-core.md) in sequencing only: dual-framework support
remains the architecture; it is no longer a simultaneous investment.

## Consequences

One adapter gets deep enough to prove the abstraction, and the conformance suite gets a
real implementation to be validated against — which is what keeps the second adapter a
bounded piece of work rather than a rewrite.

Choosing on determinism and auditability rather than developer ergonomics is a deliberate
statement about who this platform serves. It will occasionally make the platform less
pleasant to build in than an alternative would be, and that is the correct trade for
software whose output is read by auditors.

The costs are straightforward. Adopters standardized on the other framework wait, and
"demand-driven" means they must ask rather than find it shipped. Defining the conformance
suite against a framework with no adapter behind it yet requires discipline — it is
tempting to let the suite drift toward what the primary adapter happens to do, which
would silently convert the abstraction into a single-framework design.

There is also a concentration risk worth naming: the primary adapter's framework becomes
a dependency the platform is deeply committed to in practice, even though the core is
not. If that framework changed direction badly, the architecture would survive but the
schedule would not.
