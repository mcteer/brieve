# Specification Quality Checklist: How the platform holds a model credential

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-02
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**All three markers resolved at clarify (2026-08-02). 16/16 items passing.**

**This is the first feature in this repository whose subject is a constitutional collision.**
Principle IV says *"Machines use workload identity federation; static API keys are prohibited
without exception"*, and it separately names exactly one permitted standing credential. A vendor
model key is a static API key. Three consecutive features — 024, 025, 026 — needed one, deferred
it, and recorded the deferral; the capability they built is complete, gated, and unusable.

**The decision was not invented here.** ADR-0044 already carries the rule — *federate where the
product validates external identity, broker only where it cannot* — and a model vendor validates
no workload identity. The clarify answer follows the existing rule to its conclusion rather than
choosing freely, which is why the option that reads as "bending the principle" is in fact the one
the decision record already implied.

**FR-002 is the unusual requirement and it is the honest one.** The posture must be reconciled
with the constitution *in the open*: either the sentence is amended deliberately, or the posture
satisfies it. A platform quietly contradicting its own constitution would be worse than one that
amended it and said why — and this repository has spent three features demonstrating what happens
when a document and a system disagree.

**FR-005b records a real limitation rather than solving it.** One vendor account means shared
billing, shared rate limits, and revocation that cannot single out a tenant. That is a property
people discover late; it is named so the next feature to want per-tenant scoping finds it.

**FR-013a puts the eval lane's exemption where the lane is**, not only in this spec. An exemption
a reader has to infer is the loophole it was meant not to be.
