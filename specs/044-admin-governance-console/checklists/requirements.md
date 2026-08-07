# Specification Quality Checklist: The admin console — governance configuration leaves Terraform

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-07
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

**Named records and paths are measurement, not implementation.** The spec cites
`harness-authority`, `controlled_paths`, `authority_submit.py` and ADR-0039's vocabulary in its
"What is true today" section. That section exists to state what was *measured against merged
main* rather than inferred, which this estate requires of a spec — and 043's ROADMAP entry
records what happens without it: a document asserting a shape the platform does not have,
producing two wrong recommendations in one session. The requirements themselves name no
technology.

**Three decisions were made rather than deferred as clarifications**, each recorded in
Assumptions with its reasoning:

1. **Judge-disabled semantics** — answer with the absence disclosed, on 033's *disclose rather
   than suppress*. The alternatives (answer silently, decline) are named in the ROADMAP entry;
   silently reintroduces gap 0g by configuration, and declining means disabling a check
   disables answering. Settled once here because the question recurs for every toggle.
2. **Scope of records** — the settings the maintainer named (judge, role bindings, product
   connections), not every operator-authored record. Ceilings and the protected set stay estate
   governance until the shape is proven.
3. **The role-vocabulary mismatch** — FR-018 requires it resolved explicitly (widen by
   amendment, or drop the name) rather than choosing between them in the spec, because the
   choice is an ADR question and constitution v1.6.0 warns that a closed list growing by
   interpretation is not a closed list.

**FR-023 is unusual and deliberate**: a requirement to *establish and state* whether the
existing gate covers its path. The measurement says it does not — `authority_controlled_path`
defaults to a KV path absent from `controlled_paths` — but whether that is a defect or a
deferral changes what this feature must build, and asserting either without checking would be
the guess this estate refuses.
