# Specification Quality Checklist: Customer-supplied context — endorsed, pinned, and citable

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

**The measured section names files, and that is deliberate.** "What is true today" cites
`corpus.py`, `answer.py` and 044's `CONSOLE_RECORDS` because this estate requires a spec to
rest on what was measured against merged main rather than on what an earlier document claimed —
the ROADMAP's own preamble records two wrong recommendations produced in one session by a
document asserting a shape the platform did not have. The **requirements** name no technology.

## Clarify session — 2026-08-07

Four questions asked and answered; all four integrated into the spec and its requirements.

| Taxonomy area | Status |
| --- | --- |
| Domain & data model | **Resolved** — Q1 settled the endorsement's unit (a source, not a document) |
| Interaction & UX | **Resolved** — Q2 made provenance per-citation and *data rather than presentation* |
| Integration & governance | **Resolved** — Q3 gave endorsements their own record and named the four-place cost |
| Lifecycle | **Resolved** — Q4 settled sync as an act somebody takes, never a schedule |
| Non-functional (performance, scale) | **Outstanding, low impact** — no volume target is stated for a synced source; reasonable defaults exist and the pinned corpus's 238 documents is the working precedent |
| Terminology | **Clear** — "endorsed source", "synced copy", "citable document", "provenance" used consistently |

**Each answer carried a cost that is now written down rather than discovered**: source-level
endorsement means a document added upstream is citable without a fresh human act (bounded by the
sync record); a fourth console record means four places must be updated together (bounded by a
check that they agree); and no scheduler means content is exactly as stale as the last
deliberate act (bounded by making that age visible).

**Two decisions were made rather than deferred**, both recorded in Assumptions:

1. **MCP servers are excluded.** The ROADMAP describes one panel over Git repositories and MCP
   configurations and warns in its own text that these are "two features of very different
   size". Resources cannot be digest-pinned the way a cloned repository can; tools are a
   capability source colliding with Principle VIII's eval gating and with the ceiling vocabulary
   being assembled before a run starts. Splitting them is the ROADMAP's own recommendation
   followed, not a narrowing invented here.
2. **Sync-then-answer, never fetch-at-answer.** The platform's existing reasoning transfers
   intact, and the alternative would make "pinned" untrue for the new content while leaving it
   true for the old.

**FR-022 is unusual and deliberate**: a requirement that the feature *state* whether customer
content is a tenant dimension on the existing corpus or a second parallel one. Both are
defensible; what is not defensible is the answer emerging from whichever was easier to write.
This is the same shape as 042's FR-023, which required establishing whether a gate covered its
path — and that turned out to be a real defect.

**FR-019 states a triviality on purpose.** In a single-customer deployment, "one customer's
material cannot be cited to another" is satisfied by there being one customer. Saying so is what
stops the boundary from being assumed, and it is the hook a later multi-tenancy feature needs.

**Three areas are candidates for `/speckit-clarify`** rather than being guessed here: whether
endorsement is per-source or per-document, how the disclosure reads when an answer mixes
material, and whether a fourth console record is the right shape or the endorsement belongs
inside an existing one.
