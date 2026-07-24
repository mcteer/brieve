# ADR-0008: Ship no gateway or registry product — provider interfaces are the deliverable

- **Status**: Accepted
- **Date**: 2026-03-04
- **Supersedes**: ADR-0005; the default-gateway clause of [ADR-0006](0006-in-process-fail-closed-enforcement.md)
- **Relates to**: [ADR-0002](0002-adopt-first-migrate-and-delete.md), [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0007](0007-lean-profile-by-default.md)
- **Requirements**: R6, R16

## Context

Early designs assumed the platform would need to supply an AI gateway and a tool
registry, and [ADR-0005](0005-adopt-gateway-substrate.md) selected a specific
open-source substrate to adopt for that purpose.

Three things undermined that assumption. First,
[ADR-0006](0006-in-process-fail-closed-enforcement.md) established that enforcement
must live in the harness's own fail-closed hook pipeline and can never be anchored in a
gateway — which removed the security rationale for owning one. Second, organizations
adopting this platform increasingly already operate gateways and registries; asking
them to run ours alongside theirs creates duplication and a policy-jurisdiction
argument nobody wins. Third, the Lean deployment profile
([ADR-0007](0007-lean-profile-by-default.md)) runs neither component at all, which
means shipping them would mean maintaining infrastructure the default deployment does
not use.

There was also a distribution problem with adopting a substrate wholesale: taking an
upstream project's as-is, unsupported posture and redistributing it inside a governance
product transfers a support obligation to this project that it cannot honor.

## Decision

**This project ships no gateway product and no registry product, ever.**

What it ships instead is the seam: **provider interfaces** — Registry, Gateway, Eval,
Durability, Observability — each with a **conformance suite** that defines correct
behavior for any implementation behind it. Organizations bring their own components and
implement the interface, or use the Lean profile, which requires neither.

The interfaces are semantically versioned with deprecation windows, and an
implementation is considered correct when it passes its conformance suite — not when it
resembles a reference implementation.

## Consequences

The platform integrates with whatever an organization already runs instead of competing
with it, and the Lean profile stays genuinely lean — a governed stack that requires no
gateway, no registry service, and no additional operated components.

This also settles a scope question permanently. "Should we build a gateway" is not
reopened by each new integration request; the answer is to state the interface and let
an implementation satisfy it.

The cost is that the project cannot guarantee end-to-end behavior of components it does
not ship. A poorly implemented provider degrades the experience in ways the project can
detect (conformance failures) but not prevent. This shifts weight onto the conformance
suites: they are the entire quality mechanism for the provider surface, so they must be
thorough, and writing them is real work that accompanies every seam.

It also means the project must resist a recurring request. Operators without an
incumbent gateway will ask for a recommended one, and the honest answer is guidance —
an evaluation shortlist, not an endorsement or a bundled component.

Two obligations follow: every provider seam ships with its conformance suite, and the
interfaces carry the semver and deprecation promise on which the operator upgrade story
depends.
