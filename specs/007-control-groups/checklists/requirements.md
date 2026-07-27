# Specification Quality Checklist: Control Groups

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-26
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

- FR-012 and SC-009 are stated as *negative* requirements — nothing here may pause a run.
  Unusual for a spec, and deliberate: this feature's subject is humans authorizing, which is
  exactly the shape that tends to grow a run-time interrupt if nobody writes down that it
  must not.
- The quorum mechanism is the control-plane Vault's own Control Groups, confirmed licensed
  against the running enclave rather than assumed from documentation. FR-014 forbids building
  a second one.
- The roadmap's "unblocks 005's parked-run resolution" claim is deliberately not carried
  forward; it assumed run-time consent, which ADR-0049 (Proposed) rejects.
- Clarify (2026-07-26) added three requirements the first draft missed, all of the same
  kind — the gate's own lifecycle. Who creates the first quorum policy (provisioning, before
  the bootstrap credential is revoked); what happens to a request nobody answers (it expires,
  and expiry means no change); and which policy version governs a request in flight (the one
  in force when it completes, or tightening is advisory).
- Plan (2026-07-26) confirmed the premise by checking rather than assuming: Control Groups
  is licensed on the running enclave. The whole design is "configure the trust fabric's
  mechanism", so a false premise there would have made the plan wrong end to end rather
  than merely inconvenient.
- The plan adds one small core module (observe and record) and no dependencies. If a later
  pass finds this feature growing an approval engine, that is the signal the premise broke.
- Analyze (2026-07-26) found six issues, all fixed. Two were worth the pass on their own:
  FR-004 and FR-007 described one act in two requirements, which would have shown a
  reviewer two ticks for one test; and break-glass was specified as gated by Control
  Groups, which is impossible — root regeneration already requires a quorum of unseal-share
  holders and is a `sys` operation outside normal policy paths. Verified against the CLI
  rather than corrected from memory.
- Two tasks assumed this feature adds a conformance row. It does not; both were removed
  rather than left as scaffolding for something that does not exist.
- Analyze pass 3 found the same defect twice more, in the two documents pass 2 did not
  check: the plan's Summary and the quickstart. The pattern is worth recording — each pass
  fixed the requirements and missed a document that *restates* them, and those restatements
  are what a reader trusts most (the Summary because it is first, the quickstart because it
  is what you run).
- The fix applied this time was a sweep of all seven artifacts for restatements of the
  superseded design, not just the two findings the pass reported. That turned up three more
  in research.md, data-model.md, and the gated-paths contract.
