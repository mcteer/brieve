# Specification Quality Checklist: Estate answering at real volume

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

**16/16 passing.** Both markers were resolved by the maintainer on 2026-08-02 and are recorded in
the spec's Clarifications section:

- **FR-004** — bound per record type rather than per read. The defect is *competition*, not size:
  at any row count, common types crowd out rare ones. Rejected alternatives are recorded with their
  reasons, because both are the kind that look obviously better in six months — summarising would
  make the read path compose (ADR-0018), and a two-pass read would double the latency of an
  already two-minute path and leave an access record for a read that answered no question.
- **FR-006** — the answer states that it was bounded. The trail already serves the *investigator*;
  the *asker* is the one about to act on a partial answer.

**Two things this spec deliberately does not do**, both recorded rather than silently dropped:

- **FR-009** — role visibility is not widened. Whether `operator` should see authority records is a
  governance question, and the related finding (025's eval suite scores `estate_state` with a
  question no operator can ask) is recorded for decision.
- The **ordering fix** already exists on a branch, verified to fail against the old behaviour, and
  is held for this feature rather than merged alone — it is necessary and demonstrably not
  sufficient.

**One risk worth carrying into planning**: FR-004's question-to-types mapping is a new thing to
maintain, and getting it wrong produces a false negative that looks like an honest empty answer —
the same failure mode US1 exists to fix, arriving by a different route. SC-007's named questions
are the guard.
