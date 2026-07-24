# ADR-0034: A conversational portal, as a thin client of the API

- **Status**: Accepted
- **Date**: 2026-06-24
- **Relates to**: [ADR-0032](0032-delegated-run-versus-local-loop.md), [ADR-0033](0033-four-transports-one-authorization-core.md), [ADR-0035](0035-audit-as-a-governed-read-path.md), [ADR-0039](0039-per-role-model-bindings.md)
- **Requirements**: R15

## Context

The platform's developer surfaces assume an editor or a terminal. Most of the people it
serves have neither: compliance analysts asking what a control looks like in practice,
operators checking estate state, executives asking what changed this quarter, procurement
evaluating a capability, new joiners learning the products.

Building a separate interface per persona is the conventional answer and a poor one — five
interfaces to maintain, five places for authorization to drift, and a rigid mapping between
job title and available function that never matches how people actually work.

A conversational interface fits better: the same surface serves every persona, and what
differs is scope, not layout. But conversational interfaces bring two specific hazards. If
the client does any orchestration or calls models directly from the browser, it has
manufactured an ungoverned local loop ([ADR-0032](0032-delegated-run-versus-local-loop.md))
by accident, in the surface most visible to non-technical users. And an unbounded assistant
invites every question a user has, which makes quality unevaluable and answers unreliable
outside its competence.

## Decision

**A conversational web portal is the primary surface for personas who do not live in an
editor** — and it is a **thin client of the API**: no business logic, no orchestration, no
model calls from the browser. Everything happens server-side, through the same
authorization core as every other transport
([ADR-0033](0033-four-transports-one-authorization-core.md)).

**Threads are tenant-scoped run state**, persisted like any other run state, so
conversations survive restarts and are auditable by correlation ID. Per-user rate limits
and loop bounds apply — this is the easiest surface on which to consume resources
accidentally.

**Answers are grounded, with visible citations.** The portal serves three conversation
classes: guidance from vendor documentation and validated designs, estate-state questions
answered within the asker's own scope
([ADR-0035](0035-audit-as-a-governed-read-path.md)), and governed actions.

**Scope is explicit and enforced**: this is an assistant for these products and this
estate, not a general chatbot. Off-topic requests decline politely, which is what keeps the
evaluation surface tractable and the answers trustworthy.

## Consequences

One surface serves every persona, with scope rather than layout doing the differentiating —
which means a new persona needs a role mapping, not a new interface. Conversations being run
state means a portal session is as auditable as any other execution, rather than being a
side channel.

The thin-client rule is the security-critical part. It keeps the portal from becoming an
ungoverned loop, and it is the kind of constraint that must be stated early because
retrofitting it after client-side features accumulate is impractical.

Explicit scope is what makes quality measurable: a bounded assistant can be evaluated
against its domain, while an unbounded one can only be evaluated against everything, which
means not at all.

The costs are direct. The portal is a second technology stack with its own build, test,
dependency, and accessibility obligations. Declining off-topic requests will occasionally
frustrate users who wanted a general assistant, and the decline must be graceful enough not
to feel broken. Thin-client discipline also means some interactions that would be snappy
with client-side state require a round trip — a deliberate trade of responsiveness for
governability.
