# ADR-0037: Tool transport policy — MCP where mature, native tools otherwise

- **Status**: Accepted
- **Date**: 2026-07-14
- **Relates to**: [ADR-0002](0002-adopt-first-migrate-and-delete.md), [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md)
- **Requirements**: R5, R6

## Context

The platform's tool layer was originally described as "MCP everywhere": every
interaction with a managed product goes through an MCP server, with no exceptions. The
mandated requirement behind it (R5) asks for a *standard tool abstraction layer*, and
names MCP as an example rather than a mandate — but the architecture had hardened the
example into a rule.

Practice found the rule's edges quickly. Reference guidance is published as
documentation on the web, with no MCP server and no prospect of one. Official product
MCP servers vary widely in maturity: one product's server is mature and supported,
while another's is beta, documented as local-use-only, and covers a fraction of the
product's API surface. Many third-party services the platform must integrate with have
ordinary APIs and no MCP server at all.

Under a strict reading, each of these forces the project to author and operate an MCP
server purely so that the transport is uniform — building and maintaining a process per
integration, for no security benefit, in direct tension with
[ADR-0002](0002-adopt-first-migrate-and-delete.md).

The resolution came from asking where the guarantees actually attach. Identity
injection, risk classification, policy, approvals, redaction, audit, and the correlation
ID all attach at the **tool boundary** — when the agent invokes a registered tool. They
do not depend on what protocol that tool speaks to reach the far side. The enforceable
property is interception coverage, not protocol uniformity.

## Decision

**The governed unit is the registered, hook-wrapped tool. Transport is a property of a
tool, not an architectural mandate.**

- **MCP is used where a server exists, is mature, and is supported.** That
  determination is made at registry review, recorded on the registry entry, and
  revisited at each recurring review, with migration onto official servers as they
  mature ([ADR-0002](0002-adopt-first-migrate-and-delete.md)).
- **Otherwise the pack ships native tools** — in-process, typed API integrations —
  carrying identical registry metadata (owner, provenance, risk class, data
  classification), identical lifecycle, and the identical hook pipeline.
- **No MCP server is authored solely for protocol uniformity.**
- **Registry review may require process isolation** (that is, MCP) for secret-touching
  or destructive risk classes, where the isolation itself is the mitigation.
- **API calls outside a registered tool remain prohibited** in core, adapters, packs,
  and extensions. Non-tool egress stays limited to the enumerated classes: model
  inference, identity, and telemetry.

Immediate consequence at the time of this decision: the Vault pack integrates through
native Vault API tools, because the official Vault MCP server is beta, documented for
local use, and limited in coverage. Adopting it is a recurring-review action, not a
code-hunt.

## Consequences

Integration cost drops sharply for the long tail of services with ordinary APIs, and
the project stops writing disposable server processes that exist only to satisfy a
protocol rule. Adoption of official servers becomes a governed lifecycle event with a
recorded rationale, rather than an ambient assumption.

The security properties are unchanged, which is the point — both transports pass the
same hooks, carry the same registry metadata, and produce the same audit records. The
conformance suite asserts tool-call parity regardless of transport.

The cost is a genuine loss of process isolation for native tools: a compromised
in-process tool sits inside the agent runtime rather than behind a process boundary.
The risk-class escape hatch exists precisely for this, and it puts the judgment where
the information is — at registry review, per tool, rather than in a blanket rule.

There is also an added judgment burden. "Exists, is mature, and is supported" is not
self-evaluating, and it will be argued over. Recording the determination on the registry
entry makes the argument reviewable, and the recurring review makes stale determinations
visible.

This decision amends the "MCP everywhere" reading of R5. The requirement's original
text — a standard tool abstraction layer, with MCP as an example — is satisfied at the
tool boundary, where enforcement attaches.
