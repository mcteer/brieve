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

## Still open — reviewed 2026-08-01

**Deliberately open, with a trigger, rather than quietly forgotten.** This is the only
Proposed record in the repository, and a Proposed record that becomes permanent by inattention
is a failure of the process ([`docs/adr/README.md`](README.md)). Reviewed after 020; **not
resolved**, and the reasons are worth writing down so the next review starts from here rather
than from the beginning.

**What has been settled since.** [ADR-0012](0012-runtime-versus-attach-posture.md) was Accepted
2026-07-29 — harness-as-runtime leads — on the platform's own construction rather than on the
cohort behaviour it named. Its Resolution says explicitly that its evidence "is weaker than
what [ADR-0011] was waiting for, so this resolution does not automatically resolve it."

**What 020 adds, and what it does not.** This ADR's load-bearing claim is that harness-run
guarantees are *structural and provable by conformance test*, as against the cooperative
guarantees an attach posture offers. Until 020 that claim held structurally and had never been
exercised by a real agent decision: the harness owned the only path to tools, and nothing ever
*chose* to take it. A model now chooses, the choice enters the same governed entry, an
over-reach is refused by the existing enforcement, and the trail records all of it. **The
distinction this ADR rests on is now demonstrated rather than asserted.**

That strengthens the decision. It is not the evidence the record asked for, which was about
what adopters want.

**What is not built.** "Extension SDKs live at the perimeter — custom hooks, packs, providers."
Packs are real: two ship, with eval suites. `hooks/` and `providers/` are directories holding a
README each. Acceptance would not require them — Accepted records routinely describe work not
yet done (ADR-0018, ADR-0040, ADR-0044) — but the perimeter model is a plan here, not a fact,
and a review that skipped past that would be reading the tree generously.

**What would resolve it.** Any one of:

1. **A first adopter**, which is the evidence the record actually names. It decides both this
   and whether ADR-0012 was resolved on the right basis.
2. **A decision that the dependency was mis-stated** — that the cohort evidence decides
   ADR-0012's investment question and not this one, whose substantive claims (harness-first;
   SDKs extend rather than replace; any reduced-assurance tier labels itself at every point it
   makes a claim) are positions on honest labelling and do not turn on what buyers want. This
   is the most likely resolution and it is a maintainer's call, not an inference from the tree.
3. **An embedded-mode tier being built**, which would force the reduced-assurance language to
   become concrete and settle the third paragraph of the Decision by construction.

Recorded rather than resolved, because resolving it on (2) means revising what a prior record
says about its own dependency, and that is a judgement to make deliberately rather than in
passing.
