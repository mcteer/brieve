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

**16/16 → 16/16.** No item changed state in the clarification session, and it did not fix a
failing spec — it changed what the passing spec describes, which is the more useful outcome and
the one this checklist cannot see. Verified rather than asserted: the spec body was grepped for
`resume_run`, `entrypoint.py`, `dependency_products`, `RUN_STEP_INDEX`, `start_governed_run`,
and `ResumeDecision` both before and after clarification, and contains none of them. The
**Input** block keeps the original names deliberately — quoting a finding is not specifying a
solution.

**A first draft of these notes claimed two iterations and a fixed implementation-naming
failure. That did not happen** — one write was rejected by a tool precondition and rewritten
with identical content, which is not a revision. Removed rather than left as a tidier story,
because a checklist that invents its own process is the same defect as a conformance row that
overstates its scope, and this feature exists to fix one of those.

### What the clarification session changed

**Three questions, and the session made the feature bigger in one place and stricter in two.**
FR count went 20 → 25, SC count 11 → 14.

1. **A resume-attempt cap, chosen over the execution budget as the sole bound.** My
   recommendation was the budget, on ADR-0044 disjointness grounds — two mechanisms answering one
   question. Dan chose the cap, and the objection turns out not to hold: *"how long may this run
   execute"* and *"how many times may it be revived"* are different questions. The decisive case
   is a run whose every resume dies in its first second — it barely spends budget, so a budget
   bound would re-dispatch it almost indefinitely. This is the session's only genuine addition
   (FR-009a/b/c, SC-006a) and the only place a number now has to be chosen.
2. **The dispatch-level assertions are merge-blocking.** The tempting alternative was moving the
   slow flapping row behind a named runner — rejected because the cap is the newest bound and the
   least covered elsewhere, so putting it in the one lane nobody runs automatically would
   relocate this feature's own defect rather than fix it.
3. **Re-observation is asserted against a live product, both directions.** A fixture observer
   would prove the resume path calls *something*, which is narrower than the claim. Deliberately
   **not** extended to the cannot-determine direction, which was offered and declined so two
   decisions did not get bundled — it stays covered by US2 scenario 3 and planning chooses how it
   is exercised.

**Two things stayed out of scope on purpose**, both because they are architecture rather than
description: how a resume is distinguished from a fresh dispatch, and whether the resume decision
needs its own audit event type or rides existing ones. Clarify describes; it does not design.

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
