# Specification Quality Checklist: Vault policy authoring, end to end

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

**Both markers resolved 2026-08-07**, and the answer to one of them **reversed an assumption
this spec had already written**. The impact oracle is a real scratch policy and a real token —
Vault answers, rather than the platform inferring — which means the feature *writes to Vault*, in
a design whose premise was that it only proposes.

That reversal is the most important thing in this document. It is recorded in Clarifications
rather than quietly corrected, the assumption is rewritten to state the exception plainly, and
six new requirements (FR-020 to FR-025) bound it: a reserved namespace, a run-derived name,
never attached, always destroyed including on a kill, detectable when orphaned, through the
governed pipeline, and refused for protected names on the scratch path as well as the authoring
one.

**One cost is owed rather than solved.** Reads keep the allocation's platform identity, so a run
can see policies the requester could not, and the evidence may describe more of the estate than
the requester is entitled to know. Requester-scoped reads are ADR-0044 territory that 013 scoped
out; this is recorded, not fixed.

**The safety case is deliberately a requirement rather than a clarification.** FR-004 to FR-006
forbid authoring the platform's own trust-fabric policies, derived from what the fabric declares
rather than from a list. Principle IV settles this — *"agents are structurally excluded from
managing their own platform"* — so there is nothing to ask.

**"No implementation details" passes with a stated exception.** *The constraint that outranks
everything else* names five specific `vault_policy` resources. The feature's safety case is
unintelligible without knowing that the enclave's Vault holds the platform's own governance
records, and a spec that gestured at it vaguely would be one nobody could check.
