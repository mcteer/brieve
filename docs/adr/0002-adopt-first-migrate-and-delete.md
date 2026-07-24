# ADR-0002: Build glue only — adopt upstream capability, and delete what upstream absorbs

- **Status**: Accepted
- **Date**: 2026-01-15
- **Relates to**: [ADR-0001](0001-framework-agnostic-core.md), [ADR-0008](0008-no-gateway-or-registry-product.md), [ADR-0037](0037-tool-transport-policy.md)

## Context

This project sits downstream of vendors who are actively building in the same space.
Product MCP servers, agent identity primitives, policy engines, secrets management,
workload identity federation, evaluation tooling, and observability pipelines are all
either shipping or on published roadmaps from the vendors whose products this platform
governs.

A platform in that position faces a recurring temptation: the upstream implementation
is missing a feature, or is immature, or is inconvenient to depend on, so the platform
builds its own. Each instance is individually defensible. Collectively they produce a
codebase that duplicates what better-resourced teams maintain, drifts from upstream
semantics, and must be maintained forever — while the differentiating work goes
undone.

The inverse failure also exists: refusing to build anything until upstream ships it,
which leaves real gaps unaddressed and makes the platform unusable in the present.

## Decision

**Build glue only.**

Any capability the upstream vendors ship or have on a published roadmap is **adopted**,
not rebuilt. Where a genuine gap exists today, the platform may build a thin bridge —
but the bridge is written to be disposable.

When upstream absorbs a capability the platform had bridged, the platform **migrates
onto the upstream implementation and deletes its own**. Deletion is the operative word:
a bridge kept "just in case" after upstream ships is a permanent maintenance liability
and a source of behavioral divergence.

The recurring reviews are where this discipline is exercised rather than merely
intended: adoption status is reassessed on a fixed cadence, and superseded bridges are
scheduled for removal.

## Consequences

The codebase stays small enough to audit, which matters directly — regulated operators
re-scan the dependency and code surface, and every component the project owns is
surface they must review. Effort concentrates on the governance layer, which is the
part nothing upstream provides.

The cost is dependence on upstream timelines and priorities. Where an upstream
implementation is immature, the platform inherits that immaturity or writes a bridge it
knows it will throw away — work that feels wasted at the moment of writing and is not.
It also requires accepting upstream semantics that may not be exactly what the platform
would have chosen, and adapting rather than forking.

There is an ongoing cost in vigilance: someone has to notice when upstream ships
something the platform has bridged. Without the recurring review, bridges quietly
become permanent, which is precisely the outcome this decision exists to prevent.

This decision constrains later decisions rather than standing alone — it is the
reasoning behind not shipping a gateway or registry product ([ADR-0008](0008-no-gateway-or-registry-product.md))
and behind migrating tool transports onto official servers as they mature
([ADR-0037](0037-tool-transport-policy.md)).
