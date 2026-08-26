# Specification Quality Checklist: Adopted skills reach the phase that needs them

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-26
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Two items fail, both for the same reason: **FR-012 and FR-013 carry the specification's two
[NEEDS CLARIFICATION] markers**, and until they resolve neither has acceptance criteria a
test could be written against.

- **FR-012 (which phases bind which skill)** is a scope question. `write` is certain — it is
  the request. Whether `plan` and `judge` also bind, and whether the security skill binds
  narrower than the style guide, changes what this feature covers and how many eval cells
  it touches.
- **FR-013 (eval re-qualification)** is a Principle VIII question. Phase agents were tuned
  and scored against instruction content that did not include a skill; binding one changes
  the artifact those scores describe. Whether re-qualification gates the binding or follows
  it decides whether this feature is a day or a promotion cycle.

Both were raised before `/speckit-specify` ran and are recorded here rather than answered,
because answering them is `/speckit-clarify`'s job. Two markers, under the limit of three.

**Content Quality note**: the spec names `terraform-style-guide`, `AGENTS.md`, `pack.toml`
and `content_pins`. These are read as *domain artifacts of this platform* rather than
implementation choices — a reader cannot understand what is being asked for without them,
and every one already exists and is named in the ADRs this feature touches.
