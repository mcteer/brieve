# ADR-0011: Harness-first for structural guarantees; extension SDKs at the perimeter

- **Status**: Proposed
- **Date**: 2026-03-04
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0012](0012-runtime-versus-attach-posture.md), [ADR-0032](0032-delegated-run-versus-local-loop.md)

## Context

There are two ways to govern an agent. The platform can *run* it — the agent executes
inside a harness that owns the tool layer, the identity flow, and the hook pipeline — or
the platform can *attach to* it, offering libraries an externally written agent calls
into.

The difference is not stylistic. In the harness case, the guarantees are structural: an
agent cannot make an ungoverned tool call because the harness owns the only path to
tools, and it cannot exceed its ceiling because it never holds a credential that would
let it. In the attach case, the guarantees are cooperative: they hold as long as the
agent's author uses the SDK correctly and does not, for convenience or ignorance, reach
around it.

Cooperative guarantees are worth something — considerably more than nothing — but they
are a different claim, and conflating the two would be dishonest to exactly the
audiences who care most.

## Decision

**Harness-first.** The primary offering runs agents inside the governed harness, where
the guarantees are structural and provable by conformance test.

**Extension SDKs live at the perimeter**: they let organizations extend the harness —
custom hooks, packs, providers — rather than replace it. They are how you add behavior
to a governed runtime, not how you govern an ungoverned one.

A possible **embedded-mode tier at reduced assurance** is acknowledged for agents that
cannot run inside the harness. Any such tier must state its reduced assurance plainly
rather than implying parity, in the same way integration paths already distinguish what
they can evidence ([ADR-0032](0032-delegated-run-versus-local-loop.md)).

## Consequences

The strongest guarantees are available and are honestly labeled, which is what makes them
usable in a regulated setting. Assurance claims stay tied to what the architecture
actually enforces, not to what a well-behaved integrator would do.

Restricting to harness-run agents narrows the initial addressable surface: organizations
with substantial existing agent estates cannot bring them under full governance without
migrating them, and migration is not always feasible. That constraint is the reason the
attach posture is being evaluated in parallel
([ADR-0012](0012-runtime-versus-attach-posture.md)) rather than dismissed.

The reduced-assurance tier carries a permanent presentational risk: any tier that offers
partial guarantees will be read as offering full ones by someone who did not read
carefully. Whatever form it takes, its documentation, its reports, and its attestation
language must state the limitation at every point where a claim is made — not once in a
footnote.

This decision remains **Proposed** pending the evidence the attach experiment is
designed to produce.
