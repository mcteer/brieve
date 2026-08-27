# Specification Quality Checklist: A finished authoring run leaves no proposal behind

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — all three resolved in clarify
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

All items pass. `scripts/check-specs.sh` is green.

**The three markers this spec opened were the point of it, and all three are now answered.**
Issue #219 named them as things to decide rather than assume, and a reasonable-default guess on
any one is how this ships broken:

1. **When** → terminal state. The answer matches 041's trigger but **not** its reasoning, and
   the difference is load-bearing: the proposer handoff writes a non-terminal checkpoint, so
   terminal is reached only after `open_proposal` succeeds. A run that can still resume has not
   been scrubbed. That was established from the code, not inherited.
2. **What** → file bodies and the model-authored rationale. FR-032 already classes the
   rationale as content reaching the customer's repository, so the narrow answer 041 took for
   intents would have contradicted a decision already made here.
3. **What survives** → a path-and-digest manifest. It preserves a field the proposal's
   provenance already records rather than adding one, and it is the smallest thing that lets a
   reviewer prove a merged pull request is the proposal the run made.

**What clarify changed in the spec**: FR-008 rewritten to name the two cleared fields and the
two kept ones; FR-009 (digest manifest survives), FR-010 (terminal-state trigger) and FR-011
(the never-terminal gap, recorded rather than closed) added; the two following FRs renumbered;
SC-007 added; two assumptions added, one of which — that terminal state is only reached after
publish — is the safety argument FR-010 rests on and is flagged so a lifecycle change
invalidates it visibly.

**Three P1 user stories**, which is unusual and deliberate. US1 is the requirement; US2 the
constraint that stops it becoming an attestation gap; US3 the way it breaks durability.
Shipping US1 alone deletes the content *and* the ability to say what happened.

**One gap shipped knowingly.** FR-011: a run that never reaches terminal state is never
scrubbed, and that is the case holding content longest. Closing it needs a sweeper and a
staleness threshold — a separate decision, recorded rather than absorbed.

**Ready for `/speckit-plan`.**
