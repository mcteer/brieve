# Specification Quality Checklist: Deferred disclosure and code mode

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-05
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

**16/16 passing, up from 15/16.** The one item that changed state is *"No [NEEDS CLARIFICATION]
markers remain"* — three markers were resolved in the 2026-08-05 clarification session.

### What the clarifications settled

- **FR-015 — one boundary, not two.** Per-call parity only; ADR-0054 stays Proposed. The
  delegation boundary has no substrate to govern, and a rule asserting something nothing
  exercises is ADR-0047's failure mode written into an ADR instead of a test.
- **FR-014 — the platform owns the sandbox seam.** The runtime sits beneath a boundary the
  platform defines, so parity is asserted against the platform's own code rather than a
  `0.0.x` upstream's behaviour. This follows from a measurement, not from caution: the runtime
  does not enforce which functions a program may call, so the boundary was already ours.
- **FR-006 — discovery is recorded, never refused.** The middle position, and the one with a
  cost the other two do not have: it obliges an amendment to ADR-0040, whose Decision says
  "No registry, hook, or audit change".

### Two obligations this feature now carries, recorded so they are not discovered late

1. **An ADR amending ADR-0040 must land in the same change** (FR-006b). Shipping the audit
   change without it would leave the platform doing something its own record says it does not
   do — the defect ADR-0060 closed at the constitutional level one day earlier.
2. **A Principle V review is required, and for two reasons rather than one.** The adapter
   changes shape, *and* the audit schema gains a discovery record. The last several features
   needed no such review; that run is not evidence this one can skip it.

### Deliberate strictness

- **SC-004** requires that a deliberately introduced bypass make the suite **fail**. Stated as
  an outcome rather than a technique so it survives whatever mechanism the plan picks. A suite
  that stays green with a bypass present has demonstrated nothing, and ADR-0041's gate is a
  demonstration requirement.
- **SC-002 was split into two rows** (invariant + ratio) during clarification, as a default
  rather than a clarification: the original "materially less" could not fail a test. They fail
  for different reasons, which is the point.
- **FR-006c** exists because the trail must not let "the model looked for a way to delete a
  bucket" read as "the model attempted to delete a bucket". One is intent, the other is an act.

### Recorded for whoever plans this

The spec names a supply-chain trap rather than leaving it to be stepped on: the sandbox
runtime's obvious package name resolves to an unrelated project on the public index. FR-014b
requires it be adopted as *identified* content — ADR-0004's discipline applied to a runtime
dependency instead of a document.
