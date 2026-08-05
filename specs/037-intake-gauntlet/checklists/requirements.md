# Specification Quality Checklist: The intake gauntlet

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

**16/16 passing.** Three markers were resolved in the 2026-08-05 clarification session, and
each answer took the harder option rather than the cheaper one:

- **FR-015 — a purpose-built range, not the test fake.** Reusing the fake would have meant
  amending a merge-blocking guard to accommodate a convenience. That is the shape this
  repository refused when it declined psycopg rather than loosen the licence gate, and
  declining it again is the same call. The range becomes an operated component with a stated,
  reviewable posture and a named trigger (Principle VI).
- **FR-020 — the analyzer gets ADR-0052's mechanism and its own floor.** Human-labelled cases
  in the repository, a floor that fails rather than warns — but calibrated to intake's attack
  classes rather than inherited from the judge's answering suites. Inheriting the number would
  have measured the wrong thing at the right threshold.
- **FR-025 — the manual path stays, and using it is recorded.** A pipeline whose absence
  blocks all adoption is an availability problem presenting as a security control, and it
  pushes people toward editing the pin directly, which leaves no record at all. A recorded
  bypass can be reviewed for becoming routine; a forbidden one becomes invisible.

Each resolution added sub-requirements rather than a sentence, because each carries an
obligation the implementer would otherwise have to infer: FR-015a (the guard is not weakened),
FR-020b (the floor is not inherited verbatim), FR-025b (the manual path is not quieter than
the automated one).

**This feature builds three things ADR-0053 assumed.** The hardened isolation tier (ADR-0038,
Accepted, unimplemented), the golden-task corpus, and the analyzer's eval class are all
absent from `src/` and `infra/`. The roadmap calls the last of these "owed before it can be
specified"; the maintainer chose to specify it here rather than as a separate feature, so it
carries the same weight as the pipeline.

**The requirement most likely to be quietly weakened is FR-013** — separate identities for
the specimen and the observer. Every other stage can be got right while this one collapses,
and the result is the injection surface the gauntlet exists to inspect. SC-005 states it as
an assertion rather than a design property for that reason.

**FR-027 is a constraint on language, not behaviour**, and it is deliberate: this feature
will be tempting to describe as making adopted skills safe. It does not. Detonation catches
only what the corpus provokes.
