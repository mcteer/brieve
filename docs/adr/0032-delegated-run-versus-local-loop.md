# ADR-0032: Two integration paths, differentiated by what is governed

- **Status**: Accepted
- **Date**: 2026-06-10
- **Relates to**: [ADR-0011](0011-harness-first-sdks-at-perimeter.md), [ADR-0018](0018-grounded-reporting.md), [ADR-0033](0033-four-transports-one-authorization-core.md), [ADR-0039](0039-per-role-model-bindings.md)
- **Requirements**: R15

## Context

Developers work in editors with their own agents, and those agents are configurable to call
external tools. That creates two genuinely different ways to consume the platform, which
look similar from the outside and are not.

In the first, the editor asks the platform to run a workflow: the agent loop executes
server-side, inside the enclave, under everything — pinned model, pinned prompts and
skills, hook pipeline, retrieval discipline, grounded reporting, durable execution.

In the second, the developer's own editor agent does the reasoning locally and calls
platform tools along the way. Every tool call is fully governed — scope, hooks, policy,
redaction, audit, correlation ID — but the *reasoning* is not: unpinned model, editor-local
context, no evaluation gating, no grounded run report.

Both are legitimate and useful. The danger is conflating them in **attestation**. A run
report from the second path that reads like one from the first would claim evidence of
agent behavior when only the tool calls were observed. In a regulated setting that is not a
nuance — it is the difference between a defensible claim and an indefensible one.

There is a related architectural hazard: exposing product tools directly to the editor
would let the editor's agent reach products without passing the hook pipeline, which would
defeat the governance entirely.

## Decision

**Two paths, named and differentiated by what is governed.**

- **Path A — delegated run.** The editor invokes a workflow; the loop executes server-side
  under full governance. Carries **full attestation weight**.
- **Path B — local loop, governed tools.** The editor's agent reasons locally and calls
  platform meta-tools. **Every security property holds** — scope, hooks, policy, redaction,
  audit, correlation ID on each call — **and the reasoning is ungoverned.**

**Attestation states its scope per path.** Path B **evidences tool calls, not agent
behavior.** Reports and evidence packets say which path produced them.

**Regulated profiles may restrict Path B** to read- and guidance-class meta-tools,
requiring Path A for anything write- or destructive-class.

**The editor surface remains a governed façade, never a passthrough.** The editor sees a
small set of platform meta-tools, never the product tools directly.

## Consequences

Developers get to work where they already work, without the platform having to govern their
editor — which it cannot do and should not claim to. One integration serves every editor,
because the platform's contract is with the tool call, not with any editor's features.

Naming the paths is what makes honest attestation possible. Without the distinction, either
Path B's evidence gets overclaimed, or Path A's genuine strength gets discounted to match
the weaker case. With it, each says what it can support.

The façade rule preserves the guarantee at the boundary that matters: the editor holds no
product credentials, token exchange happens server-side, and a prompt-injected local model
cannot exceed the developer's governed scope.

The costs are explanatory and ongoing. Two paths with similar surfaces and different
assurance require careful documentation, careful report language, and careful sales
conversation — and the distinction will be flattened by someone at every opportunity.
Restricting Path B in regulated profiles is also friction exactly where developer
experience is most visible.

The meta-tool layer is additional design and maintenance surface: each meta-tool must be
useful enough to be worth using and coarse enough not to become a passthrough by
accretion. That balance needs holding on every addition.
