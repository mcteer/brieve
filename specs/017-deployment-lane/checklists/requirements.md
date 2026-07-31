# Specification Quality Checklist: A deployment lane — every deployed process is proven to run

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-31
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

One round of correction was needed, on the axis this feature is most exposed to.

**Implementation detail throughout the first draft.** It named the container runtime, the
scheduler, the secrets manager, specific job files, a test marker, and a CI lane. The
gate's *subject* is infrastructure, which makes it unusually tempting to write the spec in
infrastructure vocabulary — but the requirement is "assert the deployed process answers",
and every product name is a planning decision. Rewritten to "served surface", "trust
fabric", "deployment definition", "bounded time". Verified by search rather than by
reading: no product, language, protocol or file name appears in the spec.

**Clarify asked three questions and all three changed the spec.**

1. *Scope* — the dispatched run entrypoint is in, and it turned out to be where **three of
   the five** known instances of this failure class lived. A gate over long-lived surfaces
   alone would have caught two of five. This was the highest-impact question on the page and
   the spec was materially wrong without it: it said "three served surfaces" and would have
   shipped a gate missing the majority of its own motivating evidence. Added Story 5 (P1, on
   the evidence rather than on symmetry) and FR-013, which requires *dispatching* one rather
   than reading a prior run's records — a process that can no longer start still leaves last
   week's evidence behind.
2. *Measurability* — SC-004 promised a "bounded, stated time" and stated none. Now per
   process rather than per gate, because a whole-gate budget reports whichever process was
   slow as the gate overrunning, which is the misattribution FR-004 exists to prevent.
3. *Intermittency* — nothing addressed it, and it is the single most likely way this gate
   degrades. FR-014 forbids retries outright, SC-008 makes flakiness a defect in the gate,
   and the cost is recorded in Assumptions rather than left implicit: infrastructure noise
   will occasionally block a merge, and that is accepted because retrying is exactly how
   this class of defect returns to invisibility.

**The two open questions from the input are deliberately not in the prose, and are not
markers either.** The input named them: whether this joins the existing automated lane or
becomes a third, and what "answered" has to mean. The second is already answered
*behaviourally* by FR-003 and FR-009, which state what the assertion must distinguish
without choosing a mechanism — so it needs no marker. The first is entirely a planning
decision, left to `/speckit-plan`, with the resource constraint recorded as an edge case
and as FR-007 so the plan cannot quietly ignore it.

**SC-007 is deliberately falsifiable.** It requires recording which of the five known
instances the gate would *not* have caught. A success criterion that could only be
satisfied by good news is not a criterion.

Two things flagged for planning rather than fixed here:

- **FR-005 and FR-008 pull in different directions.** Enumerating processes from the
  deployment definitions satisfies "covered by construction"; a contributor's machine may
  not have those definitions loaded the same way. Real tension, and the plan's to resolve.
- **FR-013 and FR-014 together are demanding.** Dispatching a real run on every gate
  invocation, with no retry permitted, puts the gate's determinism at the mercy of the
  dispatch path's own reliability. That is the right pressure — an unreliable dispatch path
  *is* a defect — but the plan should expect it to surface one.
