# Specification Quality Checklist: A model says what to do, not only what to use

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-06
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

**16/16**, and three things about how it got there are worth carrying into planning rather than resolving here.

**The spec names no module, constant, or table, and the first draft did.** The gap was *found* by
measurement — a specific constant at a specific line, passed to a specific function — and the
description handed to `/speckit-specify` cited all of it. Writing those into the requirements
would have made them describe a fix rather than a property, and they would stop being the right
requirements the moment anything was renamed. FR-001 and FR-004 are worded so they would still be
correct against a different implementation of the same platform. The measurements belong in
research, where planning will restate them.

**Two requirements are pull-in-opposite-directions pairs, deliberately.** FR-004 says what a model
asked for must survive an interruption; FR-006 says it must rest in exactly one place and never in
the permanent record. Both are MUSTs and satisfying either one carelessly breaks the other —
keeping nothing makes revival dishonest, keeping it everywhere makes a model's words permanent
evidence. The tension is the feature's actual design problem and the spec states it rather than
smoothing it. Same shape for FR-001 against FR-002: widen what a model may *say* without widening
what it may *do*.

**SC-003 and SC-005 say "every store" and "every record" on purpose.** The most available way to
pass this feature is a check that exercises one store — and the platform has one whose behaviour
makes new information survive without anyone implementing it, so such a check passes whether or
not the work was done. ADR-0047 is cited in the traceability table for this reason, and the
success criteria are worded so a single-store demonstration does not satisfy them.

**One requirement is not about this feature at all.** FR-013 asks for a merge-blocking check that
every capability the platform defines is reachable or recorded as deliberately unreachable. Two
capabilities have now shipped unreachable behind passing checks, months apart, and both were found
by accident rather than by a gate. It is scoped here because this feature is the one that made the
second instance visible, and because it costs very little beside the rest of the work.
