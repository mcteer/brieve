# Specification Quality Checklist: A browser login for the dev lane

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-01
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

**On "no implementation details".** The spec names `tests/harness/dev_idp.py`, three
`.well-known` paths, PKCE, and RFC 7591. These are **measured evidence of the current gaps** and
the names of existing behaviour that must not be rebuilt — not design. Nothing in the requirements
says how registration is stored, what the discovery document contains, or how the issuer becomes
reachable; those are `/speckit-plan`'s. This matches how 020, 021, and 022 cited concrete platform
vocabulary in their "what already holds" sections.

**The hardest requirement is FR-006, and it deserves attention at clarify.** The advertised issuer
is one value with two consumers holding different views of the network — a container that must
reach the host, and a host process that must resolve the same name. Several answers exist
(`/etc/hosts`, a LAN address, a proxy, separate internal and external URLs), they differ in what
they require of a developer's machine, and the spec deliberately states the constraint rather than
picking one. **This is the requirement most likely to be satisfied in a way that works only for
whoever tested it.**

**One assumption is flagged in the spec as needing confirmation rather than repetition**: that
real-IdP deployments need no change. It is asserted from reading the configuration path, not from
running against Auth0. The spec says so explicitly because three claims asserted that way in this
repository over the past two days turned out to be false — a test docstring's count, a suite size,
and `stop_run`'s audit coverage, the last of which was labelled *measured* and was not.

**SC-009 is unusual and deliberate.** It permits two outcomes — the trap is fixed, or its message
names the cause — and forbids a third: leaving it silent. The feature makes that trap *more* likely
to be hit, because browser-issued tokens will outlive provider restarts, so shipping without
addressing it would be a net regression in the thing this feature exists to improve.
