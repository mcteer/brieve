# Specification Quality Checklist: The MCP surface gets a server

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-31
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

**On "no implementation details".** The spec names no library, protocol method, port, or
module. It does name *the platform's own prior decisions* — that the other surface is served,
that the transport class exists and is exercised, that a supervisory loop has a home — because
those are the facts that make this feature's scope what it is. A spec that omitted them would
be readable and would describe a much larger feature than the one intended.

**Where the spec deliberately says less than it could.** Three places, each because the answer
belongs to planning: how the caller's credential reaches the server, what protocol transport
carries the session, and how the served process is arranged relative to the supervisory loop.
Each is a real decision with more than one defensible answer, and each is *constrained* by
requirements rather than left open — FR-009 through FR-013a bound the first, FR-001 and FR-014
bound the second, and FR-015a bounds the third.

**After clarification (4 questions, all answered).** Two of the four turned an assumption into
a requirement: FR-013a fixes one subject per session, and FR-015a forbids the served transport
and the supervisory loop from sharing fate. Both were things the spec had left to planning and
that planning could reasonably have got wrong in a way nothing would catch.

**The one that needed care.** "One session, one subject, fixed at the handshake" reads as
contradicting FR-013's per-operation validity check, and does not: *who* the session belongs to
is settled once, *whether they may still act* is settled every time. Recorded explicitly under
FR-013a, because the plausible misreading — verified once, at the handshake — produces exactly
the session-outlives-credential defect FR-013 exists to prevent.

**Re-validated after integration**: 16/16 items still passing. Requirement count 28, success
criteria 10.

**Verified against the tree, not assumed** (2026-07-31): the transport class is constructed
nowhere in `src/`; no protocol framing exists anywhere in the tree; the protocol SDK is a
declared dependency nothing imports.
