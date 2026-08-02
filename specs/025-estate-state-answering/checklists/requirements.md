# Specification Quality Checklist: Estate-state answering

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

**All three markers resolved at clarify (2026-08-02), and a fourth question was asked because one
answer created it.** 16/16 items passing; the two previously unchecked are now checked.

- **FR-006 → the evidence plane only.** The `estate_state` cases asking about live product
  configuration are reauthored. They were authored in 013 for a capability that did not exist, so
  they are evidence of the defect this lineage keeps closing rather than evidence of intent.
- **FR-004b → tenant and roles.** Both already exist on the authenticated subject. **This one changed
  a success criterion rather than just filling a blank**: tenant-only bounding would have made SC-001
  vacuous, since two analysts in the same tenant would receive identical answers — which is not the
  property ADR-0035 describes. That was found by asking what the criterion would actually measure.
- **FR-010 → the existing `ask`, routed by the platform.** Chosen over a separate operation. The
  objection raised against it — that routing would be a decision no gate scores — was not a reason to
  refuse the choice but a requirement it created, so routing is now FR-010a–d and SC-009/SC-010.
- **The fourth question followed from the third.** Once routing existed, *how* it decides was
  load-bearing: a model router would make Principle VIII's gates apply to routing and would have to
  be scored against recordings, which is the exact defect being closed. Deterministic and recorded.

**On "no implementation details".** Now checked. The spec names the governed read path, `ask`, the
`estate_state` suite and the Qualified Model Matrix — existing platform vocabulary and measured
constraints, not design. Nothing says how scope is computed, how routing recognises an estate
question, what an estate reference looks like, or how the suite is scored. The FR-006 answer imported
no design: "read the evidence plane, hold no product credential" is a boundary, not a mechanism.

**One requirement is deliberately unusual.** FR-012 makes *identifying a past live failure* a
requirement rather than a task. The failure is known, its case ids were lost to a truncated capture,
and "we do not know which cases failed" is a state a feature can carry forward forever — so it is
written where it blocks completion.

**Two criteria forbid a third outcome**, in the shape 023's SC-009 established. SC-008: a caller must
not be able to tell "no records" from "not yours", *and* an investigator must. SC-009: routing must
be right in both directions — the guidance-to-estate misroute is checked by the **absence** of an
access record, because that direction reads someone's records for a question that was not about them.
