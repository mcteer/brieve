# Specification Quality Checklist: A question gets an answer, and the answer never acts

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

**On "no implementation details".** The spec names `Role`, four eval suite files, and the corpus.
All are cited as **measured evidence of what already exists** or as prior decisions, not as design.
Nothing in the requirements says how retrieval works, how citations are represented, or how the
provider is called — those belong to `/speckit-plan`. Same convention as 020–023.

**The finding this spec exists to record, and the thing to challenge first.** Four eval suites for
answering are **already in force and green**: `estate_state`, `citation_accuracy`, `must_decline`,
`must_deny`, five cases each with enforced floors. They score a `recorded` string per case,
described in the suite as *"what a previously-observed run of this case produced"* — and **no
answering path has ever existed**, so no such run happened. The recordings were authored.

That makes this the sixth instance of the shape ROADMAP gap 0d names and the most convincing-looking
one, because everything about the gates is real except what they score. FR-015 and SC-008 exist to
close it, and they are the requirements most likely to be quietly dropped as "the suites already
pass".

**Two assumptions are flagged in the spec as needing early confirmation rather than repetition.**
That the existing case shape fits a real answering path — if it does not, regenerating the
recordings is a larger change than it looks. And that guidance and estate-state share one answering
path — if they need two, this is two features and should be split rather than widened.

**The scope question for `/speckit-clarify`.** This is plainly larger than 020–023. Whether it
ships as one feature or splits — by conversation class, or by separating the answering path from
the corpus work — is the decision that most changes what gets built, and the spec deliberately
states the constraint rather than choosing.
