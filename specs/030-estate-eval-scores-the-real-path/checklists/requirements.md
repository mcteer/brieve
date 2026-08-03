# Specification Quality Checklist: The estate eval scores the path a person's question takes

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

- **FR-002** — each case declares the role that could ask it, and both `operator` and
  `compliance-analyst` are scored against their own subsets. No case is rewritten to fit a single
  role, because a case's role is a property of the case.
- **FR-004** — scope narrowing only. It is the piece this feature's finding is about, it needs no
  evidence store, and it keeps the blocking lane hermetic.

**Two obligations this spec deliberately hands to planning rather than settling:**

- **FR-002a** — what a passing suite then *means* for a matrix cell. The matrix's `role` is the
  **agent** role; a case's declared role is the **asker's visibility**, which is a different axis.
  Whether a cell records the visibility roles its evidence covers, or whether qualification simply
  requires every declared role to pass, changes what a cell asserts — and ADR-0022 says a qualified
  cell means evaluation demonstrated this combination. **A decision record is expected.**
- **FR-004a** — what the suite still does not exercise (the governed read and its access record,
  temporal windows, the per-type bound) must be written where the suite is read. An unstated gap of
  exactly this kind is what produced this feature, so leaving the new one unstated would be the
  same mistake with a shorter fuse.

**One risk to carry into planning**: US3 withdraws or re-earns two live cells that are bound and
answering questions through the deployed portal right now. Withdrawal makes that surface refuse
until an operator rebinds — correct behaviour, and it must not be discovered by a person
mid-question (FR-010).
