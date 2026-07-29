# Specification Quality Checklist: The Conversational Portal

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
**Last validated**: 2026-07-29, after the clarification session
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

**16/16 → 16/16.** No item changed state. The clarification session did not fix a failing
checklist; it changed what the passing spec describes, which is the more useful outcome and
the one this checklist cannot see.

**The previous note said the largest open question was one this checklist could not check —
whether the feature was the right *size*.** That question is now answered, and by evidence
rather than preference: the platform installs zero model providers on purpose, and ADR-0039
makes an `ask` binding inexpressible without a green Qualified Model Matrix cell that
nothing yet produces. The answering classes left. What remains is a portal that dispatches,
watches, stops, and declines.

**Three requirements are deliberately negative**, and all three are testable by construction
rather than by observation — the assertion is that no path exists, which is stronger than
asserting no path was taken:

- FR-002 — no orchestration or model calls in the browser
- FR-014 — no mid-flight solicitation of the person
- FR-017a — a decline or refusal starts no run

FR-009's prohibition on summarizing is a fourth of the same kind, and the one most likely to
be argued with during implementation, because a long thread carrying less forward than it
could looks like a defect rather than a decision.

**One question is deliberately left open**, recorded rather than guessed: a message that
starts no run has no trail entry, so deleting its thread removes the only copy. That is the
single case where the evidence/view split does not hold. Planning decides whether such a
message is written to the trail anyway or is genuinely ephemeral — the second is defensible,
but only if it is chosen rather than defaulted into.
