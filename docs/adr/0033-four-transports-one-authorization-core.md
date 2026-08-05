# ADR-0033: Four transports over one authorization core

- **Status**: Accepted — amended in part by [ADR-0060](0060-three-transports-the-cli-is-withdrawn.md)
- **Amended by**: [ADR-0060](0060-three-transports-the-cli-is-withdrawn.md) — the transport
  enumeration is now three (MCP, API, portal) and the CLI device-grant clause is withdrawn.
  Everything else below stands: one authorization core, parity as a conformance-asserted
  test, OIDC-always, no static API keys.
- **Date**: 2026-06-24
- **Supersedes**: the console-trigger clause of [ADR-0007](0007-lean-and-federated-profiles.md) / [ADR-0008](0008-no-gateway-or-registry-product.md), for the minimum portal
- **Relates to**: [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0032](0032-delegated-run-versus-local-loop.md), [ADR-0034](0034-conversational-web-ui.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md)
- **Requirements**: R15

## Context

The platform had grown a tool-server surface for editors and a CLI, and a web portal was
becoming unavoidable — most of the personas the platform serves (compliance, operations,
executives, procurement, new joiners) do not work in an editor. An API surface was likewise
implied by anyone wanting to automate against the platform.

Four surfaces is where authorization architectures usually go wrong. Each surface acquires
its own authentication, its own notion of who the caller is, and — inevitably — its own
subtly different authorization checks. The classic outcome is an API that permits what the
UI forbids, discovered by an attacker or an auditor rather than by a test.

There was also an identity question with no good local answer. Any user store the platform
maintains is a credential store it must secure, a joiner-mover-leaver process it must
support, and a second source of truth about who works at the organization. All three are
solved problems that belong to the organization's identity provider.

## Decision

**Exactly four transports — tool server, API, CLI, and portal — as clients of one
authorization core.**

**Parity is conformance-asserted**: the same operation attempted through any transport
produces the same verdict and equivalent audit events. This is a test, not an intention.

**Human authentication is always against the organization's own OIDC identity provider**,
using the flow appropriate to the transport: authorization code with PKCE for the portal,
device authorization grant for the CLI, OAuth 2.1 for the tool server. **Machines use
workload identity federation. There are no static API keys, on any surface, ever.**

**Surface authentication is the root of the delegation chain.** Whichever transport a human
arrives through, their authenticated identity becomes the subject of every subsequent
exchange and appears in every audit record — so non-repudiation depends on it.

**Identity-provider claim-to-role mapping is governed configuration**, and changing it is an
authority change gated by multi-party approval
([ADR-0016](0016-control-groups-gate-authority-changes.md)) rather than an administrative
edit.

## Consequences

The failure mode where one surface is weaker than another is closed structurally, and the
conformance assertion keeps it closed as surfaces evolve — which matters most for the API,
the surface most likely to grow features quietly.

Delegating identity to the organization's provider means joiner-mover-leaver, multi-factor
policy, and session lifetime are all handled by the system that already handles them, and
the platform holds no credential store to compromise. Prohibiting static API keys removes
the single most common source of long-lived credential leakage — and it applies to
automation, which is where the temptation is greatest.

Treating claim-to-role mapping as an authority change closes a real escalation path: without
it, someone with configuration access could grant themselves a role rather than being
granted one.

The costs are adoption-shaped. Every deployment now requires identity-provider integration
before anything works, which is a real prerequisite and occasionally an organizational
negotiation. The device grant flow is unfamiliar to some CLI users. And four transports mean
four client implementations to maintain in step, with parity tests that must be extended
every time an operation is added.
