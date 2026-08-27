# Specification Quality Checklist: A phase card delegates to the skill it is bound to

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

**Zero clarification markers, and that is a claim rather than a convenience.** The feature
description named three things to decide rather than assume. All three were decidable from
measurement taken before the spec was written, and each is recorded in Assumptions with the
evidence rather than as a preference:

- *What the card keeps* — resolved by FR-002/FR-003 and the "genuinely the platform's own"
  assumption. The boundary is: delegate what the skill states, keep what contradicts it (and
  say so), keep what is about this platform rather than about Terraform.
- *Whether SC-002 becomes measurable* — reframed as an outcome with both branches specified
  (SC-004), because "it turns out not to be" is a legitimate result and must not be edited away.
- *How widely it applies* — measured rather than assumed: `packs/vault` is 2 of 8 against
  terraform's 16 of 16, so this is one pack's cleanup plus a rule every pack is held to, and
  vault serves as the passing control the rule is satisfiable.

**Two claims in the spec are measurements, and should be re-derived rather than trusted if
this spec is read long after 2026-08-27**: the 16-of-16 and 2-of-8 overlap counts, and the
finding that every "tag" occurrence in the terraform guide is inside a fenced code block. Both
were produced hermetically and are cheap to reproduce.

**One assumption is load-bearing and is flagged for the plan to assert rather than accept**:
that delegation is safe because 051 made absent delivery fail-closed. If that were not true,
this feature would trade a duplicated rule for a silently missing one.
