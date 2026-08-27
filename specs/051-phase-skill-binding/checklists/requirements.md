# Specification Quality Checklist: Adopted skills reach the phase that needs them

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-26
**Updated**: 2026-08-26 — after `/speckit-clarify` (3 questions, 4 answers integrated)
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

All items pass. Both original markers resolved in clarify, and a third question — not
anticipated at specify time — added a user story the feature would otherwise have shipped
without.

**What clarify changed:**

- **FR-012** — bindings are `plan`, `write`, `judge`. Plan is bound because its output is
  Write's instruction, not because of anything Plan emits.
- **FR-012a** — `research` and `propose` stop claiming practice they will not receive.
- **FR-013 / FR-013a** — binding and re-qualification ship together; no runtime state for a
  binding that is not in force.
- **FR-014 – FR-018 and User Story 4** — adopted practice this platform cannot perform is
  declared in the manifest and surfaced in the pull request, rather than delivered as
  instructions the model will either fail or falsely report.

**Discovered while clarifying, and load-bearing for the above:**

1. All five Terraform phase instructions already claim both skills as practice. The spec
   originally said only `write`; corrected.
2. Phase-agent promotion is all-five-or-none and gates on both suites, which is what makes
   FR-013's answer cost nothing extra.
3. The vendored skill instructs `terraform fmt -recursive` and `terraform validate`, and no
   registry tool exists for either. This is what produced Q3 and User Story 4.

**Ready for `/speckit-plan`.**
