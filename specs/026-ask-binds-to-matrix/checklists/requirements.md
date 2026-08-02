# Specification Quality Checklist: Asking binds to the Qualified Model Matrix

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-02
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

**All three markers resolved at clarify (2026-08-02). 16/16 items passing.**

**This spec closes a gap between what the repository claims and what it does.** 024's SC-006 and
its conformance contract both assert *"an unqualified cell refuses before any provider call"*.
Measured against merged `main`: no module on the answering path references the matrix, and the
matrix record holds no `ask` cell for any pack. Principle VIII is a MUST, so this is a
constitutional gap in shipped code — which is why US3 is a user story rather than a documentation
task.

**A measurement changed one decision's price.** Refusing every ask reads like turning off a shipped
operation. It is not: `served.py` configures neither `ask_provider` nor `ask_model`, so every
deployed surface already answers 503, and the only things that change are test fixtures. That was
checked before the question was asked, and it is why the constitutionally correct option was also
the cheap one.

**The binding lives in the trust fabric, not in deployment config**, and that split is the point:
*where* a model is reachable from is assembly, *which* model is permitted is governance. Putting
the binding in a jobspec would have made Principle VIII configurable by whoever deploys.

**Per-source cells rather than one.** An operator can qualify a model to summarise a tenant's
records without licensing it to cite documentation. It also dissolves the corpus-has-no-pack
problem — the record names each cell instead of deriving one from a pack the corpus does not
belong to.

**SC-001 is verified at the provider, not the response.** A refusal returning the right status
while still having called the model would satisfy a response-level check and violate the
requirement. "Unreachable, not merely unused" is only visible in the provider's own call count.

**One assumption is flagged rather than resolved**: the existing substitution record's shape
assumes a run id, and an ask has none — the same collision 024 hit when its ask record could not
reuse the run-shaped model-gate event. Recorded so design does not discover it late.
