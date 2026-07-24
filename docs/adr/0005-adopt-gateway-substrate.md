# ADR-0005: Adopt an existing gateway and registry substrate

- **Status**: Superseded by [ADR-0006](0006-in-process-fail-closed-enforcement.md) and [ADR-0008](0008-no-gateway-or-registry-product.md)
- **Date**: 2026-01-29
- **Superseded**: 2026-02-12 (enforcement anchoring) and 2026-03-04 (product scope)

## Context

Early design assumed the platform needed to supply two components: an AI gateway to
mediate model traffic, and a registry to catalog and govern tools. Both looked like
prerequisites for the governance story — the gateway as the place to enforce policy on
model calls, the registry as the authority on which tools an agent may reach.

Building either from scratch was clearly out of scope, so the question was which
existing substrate to adopt. An in-family open-source project offered both capabilities
and appeared to be the natural choice.

## Decision

*(This decision is no longer in force. Recorded here for lineage.)*

Adopt the identified open-source project as the gateway and registry substrate,
deploying it as part of the platform.

## Consequences

This decision was superseded in two stages, for two independent reasons.

**Enforcement anchoring** ([ADR-0006](0006-in-process-fail-closed-enforcement.md)):
anchoring policy enforcement in a gateway makes the guarantee only as strong as the
gateway's placement in the network path. Anything that can be bypassed by
misconfiguring an external component is not a guarantee. Enforcement moved into the
harness's own in-process, fail-closed hook pipeline, which removed the security
rationale for owning a gateway at all.

**Product scope** ([ADR-0008](0008-no-gateway-or-registry-product.md)): with
enforcement no longer dependent on it, the remaining case for shipping a gateway and
registry was convenience — and it did not survive contact with three facts.
Organizations adopting the platform increasingly operate their own; the Lean profile
runs neither; and redistributing an upstream project shipped as-is and unsupported
would transfer a support obligation this project cannot honor. Provider interfaces plus
conformance suites replaced the components entirely.

The lasting lesson is recorded here deliberately: the question "which component should
we adopt for X" presumed the platform needed to own X. The better question — where does
the guarantee actually attach — dissolved the requirement instead of answering it. That
pattern recurs (see [ADR-0037](0037-tool-transport-policy.md), where asking where
enforcement attaches dissolved a protocol mandate).
