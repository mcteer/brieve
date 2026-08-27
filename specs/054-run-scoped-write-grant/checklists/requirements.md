# Specification Quality Checklist: A run's write grant names only its own workspace

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

**The mechanism is deliberately NOT chosen here.** It would have been easy to write "mint a
signed JWT per run" into the spec, because 016 already built that substrate and the temptation
to justify parked work is real. FR-009 requires the cheapest sufficient mechanism to be
established by evidence instead, and SC-006 requires the rejected alternatives to be recorded
with what ruled each out. That is a research obligation for planning, not a clarification for
the user — nobody can answer it from preference.

**The specific thing to disprove first**: Vault Identity templated policies resolve against an
entity that is per *agent definition*, not per run. Two concurrent runs of the same definition
are the case that breaks them. If that can be worked around, the expensive path is unnecessary.

**One assumption is load-bearing and is flagged for planning to assert rather than accept**:
that the `b7c2a2f` pipeline guard holds. This feature is the layer beneath it and does not
re-close the route above.

**Three questions were resolved in the 2026-08-27 clarification session**, adding FR-012
through FR-017 and SC-007 through SC-009:

1. Only runs whose requested tools declare a write path get a grant at all — stricter than
   today, where every dispatched run carries the estate-wide one.
2. Grants renew while the run is alive and stop when it is not, so a slow Build is a normal
   Build rather than a failed measurement.
3. A resumed run gets a fresh credential naming the same workspace.

**The third answer was corrected by the maintainer and is better for it.** The option offered
was "fresh grant, same workspace"; the answer added the constraint that makes it safe —
*re-deriving* scope at resume can widen it, and a resumed run holding a wider grant would
defeat the feature while appearing to work. FR-017 now covers every re-mint, not just resume,
and requires a widened one to be refused **and detectable**. That hazard was not in the spec
before the question was asked.

**Numbers in this spec are measurements, not estimates.** The 200/200/204 was observed against
the live dev enclave on 2026-08-27 and is cheap to reproduce; the ~36,000-line divergence of
the archive tag is a `git diff --stat`.
