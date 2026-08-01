# Specification Quality Checklist: The trail records who looked, or the surface stops saying it does

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-01
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

**On "no implementation details".** The spec names operations (`get_run_result`), an existing
audit event type (`EVIDENCE_READ_REFUSED`), a test file, and a vocabulary constant
(`INDISTINGUISHABLE_TO_CALLER`). These are cited as *measured evidence of the current gap* and as
*named prior decisions*, not as design. Nothing in the requirements says how a record is written,
where the rule lives, or what shape any new event type takes — those belong to `/speckit-plan`.
The convention matches 020 and 021, both of which cited concrete platform vocabulary in their
"what already holds" sections.

**On "no [NEEDS CLARIFICATION] markers".** ~~The central open question is carried as a stated
assumption.~~ **Resolved by clarify, 2026-08-01.** Three questions answered; FR-001 now states the
rule rather than requiring one to exist.

**Re-validated after clarify — still 16/16, and one item changed state on the way.**
"Requirements are testable and unambiguous" was **passing on a technicality** before clarify and
now passes properly. FR-001 said a rule must exist and be decidable, which is testable only in the
sense that one can check whether a document exists; it named no rule, so no implementation could be
wrong against it. It now names one, and FR-002 enumerates the six operations it covers and the two
it does not.

**One contradiction clarify found in this spec, worth recording because it was mine.** The original
FR-005 required a read record to join the correlation id "so reading a run appears in that run's
walk". `src/surfaces/api/evidence.py` had already rejected that exact shape — appending to the
chain being read means reading evidence writes into the evidence being read — and 021's `RunReport`
made it worse, since it compiles from a run's chain and would have grown a claim about its own
readers each time anyone looked. FR-005/005a/005b now carry the correlation id in a separate stream
instead. **Nothing in the spec-writing process would have caught this**; it surfaced only from
reading the implementation of the thing being extended.

**One item still worth a second look at plan.** SC-004 ("an operation added without an audit
disposition fails a check that names it") is verified by adding one and observing the failure —
a deliberately-broken state, not a passing row. That is the right shape for a guard and matches the
existing `test_the_operation_list_here_matches_what_shipped`, but it should be confirmed achievable
as a standing check rather than assumed.

**SC-011 is a deliberate negative and should not be quietly deleted at plan.** It asserts the two
catalogue operations *remain* unrecorded. A check that pins a non-behavior looks like dead weight
until someone widens coverage by accident; this is what makes that a visible decision instead of a
drift.
