# Specification Quality Checklist: Grounded means relevant, not merely resolvable

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

**Both markers resolved 2026-08-07.** Relevance is decided by a model asked whether the
surviving claims answer the question, in a **separate call**, from its **own qualified cell**,
against a **human-labelled seed set**.

**The spec ruled out two mechanisms by measurement before asking**, and recording that is half
its value: product scoping would make this case decline and would undo 035, since architecture
questions are frequently cross-product; claim-to-citation support checking is buildable and
would not catch this at all, because each claim here *is* supported by the passage it cites.
The gap is answer-to-question.

**Three costs are stated rather than absorbed**, and they are what a reviewer should push on:

- a **second model call** on every ask that survives citation resolution;
- a **new qualified cell** somebody must promote, because qualification for one role does not
  transfer (the existing judge was qualified on refusal verdicts);
- a **human-labelled seed set** somebody must write. This is the expensive clause and the one
  that erodes quietly — 038's corpus requires an author on every reference for exactly this
  reason, and FR-015 requires at least one seed the judge can *fail*.

**What this spec deliberately does not do.** It does not touch the corpus (ADR-0004), does not
edit the failing case, and does not relax citation resolution. Each of those would make the
symptom go away, and this estate has a name for two of them.

**The hardest requirement to satisfy is FR-004, not FR-001.** Declining more is easy; declining
*this* while still answering everything the platform answers today is the actual problem, and
SC-003 and SC-004 exist to stop a fix that buys its decline by becoming useless.
