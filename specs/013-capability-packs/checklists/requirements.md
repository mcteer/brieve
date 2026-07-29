# Specification Quality Checklist: Capability Packs and Eval Gates

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
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

**16/16.** The three markers were resolved by the 2026-07-29 clarification session, and the
two items that failed before now pass for the same reason: the inner boundary is settled.

**The clarifications shrank the feature in one place and grew it in another**, which is
worth noting because the net is not obviously smaller. Deferring US6 removes the largest
dependency — a corpus, a retrieval path, precedence resolution. Shipping *two* packs rather
than one adds content work, deliberately, because FR-004's claim is about independence and
one pack has nothing to be independent of. That trade is the session's main decision.

**Two things carried forward rather than resolved**, both visible in the spec:

- **A cell qualified against a fixture is qualified against a recording.** The blocking lane
  scores fixtures so a merge gate does not fail for reasons unrelated to the change; a
  marked lane scores a live model. SC-013 exists so the contract cannot record a cell as
  qualified without saying which of the two it means.
- **The judge regress.** FR-012 requires eval-time judges to be eval-promoted artifacts, so
  something qualified the first one. Planning must resolve it; pretending it away in the
  spec would be worse than naming it.

**Six requirements are deliberately negative** — FR-003 (no bypass path), FR-004 (no core
module names a product), FR-010 (no path reaches an unqualified model), FR-011 (no
auto-tracking anywhere), FR-014 (a gate that cannot run reports failure), FR-015 (a model
verdict never satisfies a human approval). All are testable by construction rather than by
observation. FR-004 in particular reads as a slogan until asserted structurally over the
real tree, and SC-012 makes it a diff rather than an argument.
