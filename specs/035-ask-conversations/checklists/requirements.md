# Specification Quality Checklist: Ask becomes a conversation

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-04
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

**16/16.** Three clarifications were taken and each closed a hole that would otherwise have been
filled by whichever code ran first:

1. **Follow-up routing** — explicit signal wins, silence inherits. Became FR-017/017a/017b and
   SC-010a. The rejected alternative (route on the conversation) is the misroute that cost a day
   on 2026-08-03, where history would pull a documentation question into a read of somebody's
   records.
2. **Declines as context** — the question is carried, the verdict is not. Became FR-014a and
   SC-011a. Feeding a decline back invites the model to decline again by agreement rather than
   by reading.
3. **Transport parity** — full parity, no exception to ADR-0033. Became FR-027a and SC-013. This
   is the one that materially grows the feature, and it was chosen with that cost stated.

Three further gaps were closed with defaults rather than questions, and are recorded in
Assumptions: conversations are kept until deleted, exchanges are ordered by acceptance with two
tabs converging on reload, and the ask surface becomes the conversation surface rather than
gaining a second page beside it.

The specification still names no storage, no context shape, and no delivery mechanism for the
transcript. Those are the plan's.
