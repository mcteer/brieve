# ADR-0045: Skills and workflows are authored in competency tiers

- **Status**: Accepted
- **Date**: 2026-05-06
- **Source**: gap review ([GR-1](GR-1-gap-review.md))
- **Relates to**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0010](0010-enablement-as-versioned-product-layer.md), [ADR-0023](0023-validated-designs-as-judgment-layer.md)

## Context

The platform serves users whose expertise differs by orders of magnitude. A developer who
has never configured a secrets engine and a platform engineer who has designed several need
different things from the same agent: the first needs a paved path with the decisions
already made, the second needs the freedom to compose.

Serving only the novice produces a system experts find obstructive and route around.
Serving only the expert produces a system novices cannot use safely — which defeats the
platform's premise, since the novice is precisely the user the expertise is meant to reach.

Building two products is the obvious answer and the wrong one: two content sets to author,
two behaviors to evaluate, and a cliff between them that users fall off exactly when their
competence grows.

There is a separate but related problem. The enablement ladder
([ADR-0010](0010-enablement-as-versioned-product-layer.md)) describes an organization's
progression from operating to extending to governing, but nothing in the product enforced
or reflected it. Progression was a training concept with no technical expression.

## Decision

**Skills and workflows are authored in competency tiers, and a definition pins a tier.**

- **Lower tiers** expose only fully-paved, heavily-verified golden paths. Decisions are
  already made; the agent follows a validated route.
- **Higher tiers** grant compositional freedom — the ability to assemble, deviate, and
  design — to users and definitions qualified for it.

The tier is a property of the **definition**, not of the user's request, so what an agent
may compose is bounded at design time and reviewable like any other part of the definition.

One mechanism serves three purposes at once: it is the **enablement ladder** made
operational, the **maturity model** made visible, and **least privilege** applied to
capability rather than to credentials.

## Consequences

A novice and an expert use the same platform, and the difference between their experiences
is a pinned tier rather than a different product. Progression is continuous — an
organization advancing up the ladder raises tiers on definitions it is ready for, rather
than migrating between systems.

Making the tier a definition property rather than a runtime choice is what keeps it
governable: it is reviewed, approved, and audited with everything else in the definition,
and an agent cannot elect a higher tier for itself.

Fusing the enablement ladder to a technical mechanism is the part with the most leverage.
Training progression that has no product expression tends to be aspirational; here,
"this team has graduated to Extend" has a concrete meaning — the tiers their definitions
may pin.

The costs are authoring costs. Content must be written with a tier in mind, and the same
capability may need expression at more than one tier — a paved version and a compositional
one. That multiplies authoring and evaluation work, and it requires authors to think about
audience explicitly rather than writing for the reader they most resemble.

Tier boundaries are also a judgment call that will be argued over: what counts as
sufficiently paved is not self-evident, and the line will move as the platform learns which
paths are genuinely safe to leave open.
