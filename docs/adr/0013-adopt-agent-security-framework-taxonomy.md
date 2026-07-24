# ADR-0013: Adopt the vendor Agent Security Framework taxonomy

- **Status**: Accepted
- **Date**: 2026-03-11
- **Relates to**: [ADR-0002](0002-adopt-first-migrate-and-delete.md), [ADR-0010](0010-enablement-as-versioned-product-layer.md), [ADR-0014](0014-two-layer-runtime-protection.md)

## Context

Any platform in this space needs a vocabulary for what it does — a way of naming the
capability areas so that adopters, auditors, and its own documentation can be consistent.
The temptation is to invent one, because an invented taxonomy can be shaped exactly to
the product's contours and makes the product look like the category.

The vendor whose products this platform governs publishes an Agent Security Framework
with an established taxonomy: Identity, Traceability, Runtime Protection, and
Observability. It also defines an adoption motion — readiness assessment, then a first
secured workflow, then enterprise-wide rollout — and an enablement tier structure that
adopters already recognize.

Inventing a parallel taxonomy would mean every conversation with an adopter starts by
reconciling two vocabularies that describe the same things, every piece of material
needs a mapping table, and the platform positions itself as an alternative to the
framework rather than an implementation of it. That is worse on every axis that matters,
and it is precisely the duplication that the adopt-first discipline exists to prevent
([ADR-0002](0002-adopt-first-migrate-and-delete.md)).

## Decision

**Adopt the published framework's taxonomy and motion rather than defining a parallel
one.**

- Capability areas are named **Identity, Traceability, Runtime Protection,
  Observability**, and the architecture maps onto them explicitly.
- The adoption motion follows the published sequence: **readiness assessment → first
  secured workflow → enterprise-wide**.
- The enablement layer ([ADR-0010](0010-enablement-as-versioned-product-layer.md))
  aligns to the established tier structure, and the maturity ladder maps to the
  framework's own progression.

The platform positions itself as **a productized implementation of the framework**, not
a competing model.

## Consequences

Adopters encounter one vocabulary rather than two. Assessment findings map directly onto
platform capabilities without a translation layer, which shortens the distance between
"here is your gap" and "here is the thing that closes it." Collateral, enablement
material, and audit conversations all inherit that alignment.

Adopting the taxonomy also imposes useful discipline internally: capability areas that
look thin against the framework are visible as gaps rather than hidden by a
self-flattering structure of our own devising.

The costs are the ordinary costs of dependence. The taxonomy evolves on someone else's
schedule, and a change upstream means updating the architecture's mapping, the
enablement material, and the collateral. Areas where this platform does something the
framework does not name are awkward to place, and the temptation will be to stretch a
category rather than acknowledge the mismatch.

There is also an ecosystem consideration: adopting a single vendor's taxonomy makes the
platform legible to that vendor's customers and slightly less legible to everyone else.
Given that the platform exists to govern that vendor's products, the trade is
straightforward — but it is a trade, and a broader-market posture later may require
publishing a mapping to a neutral framework rather than switching.
