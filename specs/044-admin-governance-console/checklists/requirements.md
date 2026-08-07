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

## Clarify session — 2026-08-07

Four questions asked and answered; all four integrated into the spec and its requirements.
Coverage after the session:

| Taxonomy area | Status |
| --- | --- |
| Functional scope & boundaries | **Resolved** — Q4 settled that all three record types ship together |
| User roles & permissions | **Resolved** — Q2 made `admin` disjoint from the existing two |
| Integration & external dependencies | **Resolved** — Q1 (portal only, no parity owed), Q4 (connection failure is connectivity, not governance) |
| Security & compliance | **Resolved** — Q3 requires the gate gap fixed, not merely recorded |
| Accessibility | **Resolved without asking** — the standard has an obvious default (same WCAG 2.2 AA bar); what needed recording was the measured gap: today's rows walk `/`, a thread, and `/delete`, so a new page would be uncovered while the lane stayed green |
| Lifecycle / state transitions | **Outstanding, low impact** — whether a pending change may be withdrawn, and how pending changes surface alongside in-force configuration. Reasonable defaults exist and the mechanism is the fabric's; deferred to planning |
| Terminology | **Outstanding, low impact** — "console" is used throughout; "interface" and "settings panel" appear only when quoting the original ask |

**One answer overrode the recommendation, and the spec carries the cost rather than hiding it.**
Q4 was recommended as judge-plus-bindings only; the maintainer chose to include product
connections. FR-018c exists because of that choice: a connection can be perfectly well-governed
and simply wrong, which is a failure mode bindings do not have, so "the fabric accepted it" must
never read as "the product answered".

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
