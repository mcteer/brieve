# ADR-0024: Durability is a provider seam; the default is a library, not a service

- **Status**: Accepted
- **Date**: 2026-05-06
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0008](0008-no-gateway-or-registry-product.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0028](0028-product-identity.md)

## Context

Agent work is long-running. A single task may span hours: waiting on infrastructure to
converge, on a human approval, or on a change window to open. Any of that time can be
interrupted — a pod rescheduled, a node drained, an upgrade rolled through, a network
partition.

Surviving interruption requires durable execution: checkpoints, timers, exactly-once
semantics, replay. The mature answer in this space is a dedicated workflow engine, and
those engines are genuinely good. They are also services — a cluster to run, upgrade, and
operate — which collides directly with the lean-by-default rule
([ADR-0007](0007-lean-and-federated-profiles.md)) that forbids adding an operated
component where a library would do.

There is a second, subtler question. Durable execution frameworks have opinions about
state and replay. If the platform's governance semantics — re-authentication on resume,
idempotency of side effects, what a checkpoint may contain — were expressed in a
particular engine's terms, then swapping engines would change the security properties.
That is unacceptable: the guarantees cannot be a function of the durability
implementation.

## Decision

**Durability is a provider seam, with harness semantics defined above the interface.**

These belong to the harness and hold identically for every provider:

- **Re-authentication on resume** — never token replay.
- **Idempotency** of side effects, with stable keys.
- **The checkpoint schema**, including the rule that checkpoints hold state and never
  credentials ([ADR-0026](0026-delegation-grants-and-per-step-tokens.md)).
- **State ownership** — what the harness owns versus what the provider may hold.

**The Lean default is library-grade durable execution**: timers, exactly-once semantics,
and replay implemented as a library over the Postgres the deployment already runs — no
new operated service, consistent with [ADR-0007](0007-lean-and-federated-profiles.md).

**A dedicated workflow engine attaches through the provider interface** when a named
trigger justifies it ([ADR-0028](0028-product-identity.md)) — scale,
an existing deployment, or requirements the library cannot meet.

**Durable timers and signals are adopted for approval pends and change windows**, so a
run waiting on a human or a maintenance window survives restarts as naturally as one
waiting on infrastructure.

## Consequences

The default deployment gets durable multi-hour execution with zero additional operated
components, which is what makes "governed stack, quickly" compatible with "runs that
survive anything."

Defining the semantics above the interface means the security properties are provider-
independent: swapping durability backends changes performance and operational
characteristics, never whether resume re-authenticates or whether a checkpoint could
contain a credential. Those properties are asserted identically against every provider by
the conformance suite — which is what makes the seam trustworthy rather than merely
tidy.

The costs are honest. A library-grade implementation will not match a mature engine at
extreme scale or in exotic failure modes, and the platform is now maintaining durable-
execution code that a dedicated engine would have provided. That is a deliberate trade of
engineering effort for operational simplicity, and it is only correct while the library
genuinely suffices — the named-trigger mechanism exists so that the point where it stops
sufficing is a recorded decision rather than a slow degradation.

The durability conformance scenarios are also demanding to write and slow to run:
kill-and-resume, re-observe-never-re-execute, re-authenticate-never-replay, fencing
against double resume, parking on grant expiry, duplicate side-effect rejection, and
draining across upgrade. They are non-negotiable, and they are a real ongoing cost in
both engineering time and CI minutes.
