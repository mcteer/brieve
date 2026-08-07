# Specification Quality Checklist: Authoring becomes reachable

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

**Both markers resolved 2026-08-07** and recorded in the spec's Clarifications section. Publishing
is in scope against real GitHub (FR-020), reached over **adopted vendor CLIs** — `git` for clone
and push, `gh pr create` for the proposal (FR-021).

**The transport answer was reversed during clarification, and the reversal is the useful part.**
MCP was chosen first, on Principle II's *MCP where a server exists* clause read as a default. It
is a *determination made at registry review*, and the determination came out the other way: the
external surface is a clone, a push and one proposal, while an MCP server would put a process,
its supply chain and its own auth model inside the hardened tier that exists to handle untrusted
repository content — exposing dozens of tools where the publishing task's whole scope is
`open_proposal`. **The Principle VI trigger this feature briefly owed is no longer owed**, because
no additional operated component is introduced.

**Clarification added four more decisions** (2026-08-07): the subject is a platform-produced clone
of `target_repository` rather than an operator-supplied path; a permanent `write` cell is
qualified through ADR-0063's mechanical scorer; the version-control host becomes a named product
with a probe; and the proposal's description carries rationale plus provenance.

**Clarification found a live hazard, which is the pass's most valuable output.** `dependency_products()`
builds its tool→product map only from pack manifests, and the trio are *platform* tools — so a run
suspended on `open_proposal` would have carried a tool name with no product, and `toolset.py`
already states that such a suspension is never matched by the product recovering. It would have
waited forever. FR-029 and FR-030 close it, and FR-030 deliberately generalises: the trio are the
first instance, not the only possible one.

**Three obligations remain, and are requirements rather than notes:**

- **FR-024 owes a named runner.** The enclave row publishes to a real repository; the
  constitution's Quality Gates require a blocking row with no automated runner to name who runs
  it, in the conformance contract.
- **FR-023 owes a recorded determination.** Principle II makes MCP-versus-native a registry-review
  decision. This one was made, reversed, and needs its reasoning written down where the next
  transport question will look for it.
- **An operator prerequisite exists** — a GitHub App installation on a maintainer-owned
  repository. Recorded in Assumptions, since this feature does not provision it.

**The "Content Quality — no implementation details" item passes with a stated exception.** The
*The gap, measured* section names specific files, functions and a grep result. That is normally a
spec smell; here the entire feature premise is that merged code claims a capability it does not
have, and the claim is only checkable if the measurement is reproducible. The requirements
themselves stay behavioural.

**16/16 items passing.** Nothing is unchecked; the spec is ready for `/speckit-plan`.
