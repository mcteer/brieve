# Specification Quality Checklist: Wire resume into the dispatched path

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
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

**16/16 on the first pass**, verified rather than asserted: the spec body was grepped for
`resume_run`, `entrypoint.py`, `dependency_products`, `RUN_STEP_INDEX`, `step_index`,
`start_governed_run`, `ResumeDecision`, and `SuspendedRunIndex`, and contains none of them.

**A first draft of these notes claimed two iterations and a fixed implementation-naming
failure. That did not happen** — one write was rejected by a tool precondition and rewritten
with the same content, which is not a revision. The claim is removed rather than left as a
tidier story, because a checklist that invents its own process is the same defect as a
conformance row that overstates its scope, and this feature exists to fix one of those.

**The risk that made it worth checking is real**, though it did not materialise. This feature is
a wiring change, and a wiring change is most naturally described by naming the two things being
wired — so the pull toward `resume_run` and `entrypoint.py` in requirement text is strong. The
spec says "the resume path" and "the dispatched path" instead. The **Input** block keeps the
original names deliberately: it quotes what was reported, and quoting a finding is not
specifying a solution.

**Three things carried forward rather than resolved**, all visible in the spec:

- **The feature is not justified by a live defect, and the Assumptions say so twice.** Fixture
  tools are repeatable, bracket re-recording is a no-op, and dispatched invocation is opt-in.
  The temptation was to write this as urgent; it is not urgent, it is *load-bearing for the next
  feature that dispatches real writes*. Overstating it would have been the easier spec and the
  dishonest one.
- **FR-019 and FR-020 are unusual and deliberate.** Most specs do not tell you how a property
  must be *proven*. This one must, because the entire finding is that a passing function-level
  row did not imply a working deployed path — so "assert it through a dispatch" is a
  requirement, not a testing preference. A version of this feature that wired the path and
  proved it with another function-level test would reproduce the defect exactly.
- **FR-020 obliges a record change, which is rare for an FR.** It exists because fixing the
  wiring while leaving 005's contract scoped to the function would fix half the problem: the
  claim would then be true and still unproven, which is a different flavour of the same
  mismatch.

**Nothing was marked [NEEDS CLARIFICATION].** Every ambiguity had a defensible default from the
existing records — grant expiry stops rather than parks (ADR-0049 over 005's original text),
suspensions name products rather than tools (the recovery sweep's own vocabulary), and
substituting a qualified binding is permitted while substituting an unqualified one is not
(013's matrix rule). Where a default came from a superseded text, the spec says which record
won.
