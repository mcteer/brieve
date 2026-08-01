# Specification Quality Checklist: A report compiles from records, or it says it could not

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-01
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
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

**15 of 16 pass. One [NEEDS CLARIFICATION] marker remains, for `/speckit-clarify`.**

- **FR-016 — does read-back apply to every effect claim or only non-repeatable ones?** Every
  observer in the tree was built for non-repeatable tools. Requiring read-back for repeatable
  reads costs a live product call per claim to re-derive a fact the trail already holds; not
  requiring it leaves a class of claim asserted from the record alone, which is most of what
  ADR-0018 is worried about. The answer decides how much of US3 exists.

**Resolved during specify, by the maintainer: a report serves the human and the gate, for
different purposes, from the same data.**

That answer did more than close FR-015. It produced **FR-015a**, which nothing in the original
draft had: if the gate scores a different object from the one a person reads, the gate is not
gating what anyone sees. That is this platform's recurring failure shape — something correct,
tested, and standing beside the thing that matters — and it now has a requirement and a success
criterion instead of being available as an implementation shortcut.

It also forced **FR-015b** as a consequence rather than a choice: a person reading it means it is
requestable; the portal is a thin client, so that means the API; ADR-0033 binds parity across
every implemented pair, so that means MCP too. **The surface-parity row grows**, and the plan
inherits that as owed work rather than discovering it late.

**What was NOT marked, and why.** Several details were resolved by informed guess and recorded in
Assumptions rather than escalated — that observers are the read-back mechanism, that the evidence
read path is consumed unchanged, that `get_run_result` stays as it is. Each has a clear default
supported by something already in the tree, which is the bar for guessing rather than asking.

**What was NOT marked, and why.** Several details were resolved by informed guess and recorded in
Assumptions rather than escalated — that observers are the read-back mechanism, that the evidence
read path is consumed unchanged, that `get_run_result` stays as it is. Each has a clear default
supported by something already in the tree, which is the bar for guessing rather than asking.

**The risk this spec is most exposed to** is not in the requirements but in FR-013a's corpus.
ADR-0018 names it itself: the labeled material events are "the thing most likely to be skipped
under schedule pressure, which would leave the decision nominally in force and practically
unenforced". A feature that shipped `RunReport` and a thin corpus would close the owed gate row on
paper and leave the property untested — and it would look exactly like success.
