# Specification Quality Checklist: Task-scoped authority manufacture

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-31
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
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

**Two `[NEEDS CLARIFICATION]` markers remain, both deliberate**, and both are questions
ADR-0056 explicitly handed to this feature rather than settling. Neither has a reasonable
default, and guessing either would decide the control's strength by accident:

1. **FR-015 — what a resumed run presents in place of the person's token.** The person is
   gone and the grant is what authorises, but something must carry that grant into the
   resumed allocation without becoming a durable credential that could re-mint authority on
   its own. The candidate answers differ in what an attacker who reads the run record gets.

2. **Assumptions — how a task's entailed scope is determined.** This decides how tight the
   narrowing can be and how much an agent definition's author must declare up front. Deriving
   it from requested tools is cheap and coarse; declaring it per definition is precise and
   pushes work onto authors. The wrong answer here is the one that over-grants to be safe,
   which is how a ceiling becomes decorative.

A third question ADR-0056 raised — how an estate knows which arrangement is in force — did
**not** need a marker: it has a reasonable default (report it, name the reason, never default
to the stronger reading) and is specified as FR-016 through FR-018.

These are for `/speckit-clarify` to resolve, not for planning to assume.
