# Specification Quality Checklist: Northbound API

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-27
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

- **FR-014 refuses a gate row on purpose.** ADR-0033's four-transport parity cannot be
  asserted by the first transport — parity is a property *between* surfaces, and with one
  there is nothing to compare. Claiming it would be exactly the passing stub ADR-0047
  forbids. What this feature owes instead is FR-012: making the comparison possible.
- **The audit read path is new capability, not an extended query.** Before this, evidence was
  written and never read through the platform. FR-010 exists because reading evidence is
  itself an auditable act — the integrity of an audit trail includes knowing who read it.
- FR-003 is stated absolutely because a single exception would become the integration path
  everyone uses. ADR-0033's wording is "no static API keys, on any surface, ever".
- Clarify (2026-07-27) settled what the surface actually is, which the first draft assumed
  without stating: **run lifecycle and evidence, not direct tool invocation.** A caller
  invoking a tool through the API would act beside the agent rather than through it — a
  second path to the governed core, which is the shape Principle II exists to prevent.
- It also settled that starting a run returns a handle rather than blocking. Runs are
  durable and long by design; an API that blocked until completion would contradict the
  feature that exists to let work outlive a process.
