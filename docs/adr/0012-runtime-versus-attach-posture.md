# ADR-0012: Harness-as-runtime leads; governance-attach is the committed second posture

- **Status**: Proposed — decided by early-adopter evidence
- **Date**: 2026-03-04
- **Relates to**: [ADR-0011](0011-harness-first-sdks-at-perimeter.md), [ADR-0014](0014-two-layer-runtime-protection.md)

## Context

[ADR-0011](0011-harness-first-sdks-at-perimeter.md) establishes that structural
guarantees require running the agent inside the harness. But organizations that have
already built agents — and by the time this platform is adoptable, many will have —
face a migration cost before they get any governance at all. For some, that cost is
prohibitive, which means the choice is not between strong and weak governance but
between weak governance and none.

This creates a genuine strategic uncertainty that cannot be resolved by argument. Either
early adopters primarily want a governed runtime to build *new* agents in, or they
primarily want to bring *existing* agents under control. The two answers imply different
investment priorities: one leads to deepening the runtime, the other to building
enforcement that can wrap agents the platform does not run.

Guessing wrong in either direction is expensive. Guessing right by luck is not a
strategy.

## Decision

**Harness-as-runtime is the lead offering.** It carries the structural guarantees and
receives primary investment.

**Governance-attach is a committed second posture, not a hedge**: wire-level enforcement
for organization-run agents via the mesh guardrail path, combined with embedded
enforcement where the agent can be instrumented
([ADR-0014](0014-two-layer-runtime-protection.md)). It is committed because the demand
is real, and second because its guarantees are weaker.

**Early-adopter behavior decides investment priority.** Rather than settling the
question by argument, the first cohort's actual usage — do they build new agents in the
harness, or do they arrive with existing agents needing containment — determines where
subsequent effort goes. This is an experiment with a defined decision point, not an
open-ended deferral.

## Consequences

The platform ships with a defensible answer for both populations while committing its
depth to one, which avoids the two failure modes of building half of each or building
the wrong one confidently.

Making the decision explicitly evidence-driven has a discipline benefit beyond this
question: it establishes that a strategic uncertainty can be recorded as an open
experiment with a decision point, rather than being resolved by whoever argues most
persistently.

The costs are honest ones. Maintaining a second posture at all — even at lower
investment — costs design attention and creates a second set of assurance claims to keep
accurate. There is also a messaging hazard: two postures with different guarantee
strengths invite conflation, and every piece of collateral must be precise about which
one it describes.

Until the decision point is reached, some design questions stay open longer than they
otherwise would, because they have different answers depending on which posture leads.
That is the cost of not guessing, and it is worth paying.

This ADR remains **Proposed** by design; it will be resolved to Accepted with a stated
outcome once the evidence is in, rather than being quietly forgotten.
