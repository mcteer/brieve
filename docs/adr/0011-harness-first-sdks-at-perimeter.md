# ADR-0011: Harness-first for structural guarantees; extension SDKs at the perimeter

- **Status**: Accepted (2026-08-05) — resolved on basis (2) below. See Resolution
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

~~This decision remains **Proposed** pending the evidence the attach experiment is
designed to produce.~~ **Superseded by the Resolution below**: the dependency was
mis-stated. Struck rather than deleted — what a record believed about its own blocker is
part of how it got here.

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

## Resolution

**Accepted 2026-08-05, on basis (2): the dependency was mis-stated.** This record named "the
evidence the attach experiment is designed to produce" as its blocker. That evidence is about
*what adopters want*. This record's substantive claims are not.

Read them back: harness-run guarantees are structural rather than cooperative; extension SDKs
extend a governed runtime rather than govern an ungoverned one; any reduced-assurance tier
must label itself at every point it makes a claim. **Every one of those is a position on
honest labelling.** None becomes truer or falser depending on what a first cohort buys. A
buyer who wanted cooperative guarantees called structural would not make them structural; they
would make the claim dishonest, which is precisely what the third clause exists to prevent.

The blocker was borrowed from [ADR-0012](0012-runtime-versus-attach-posture.md), which asks a
genuinely cohort-dependent question — *where to invest* — and was right to wait for usage and
right, in the end, to resolve without it. Sharing that dependency was an error of adjacency:
the two records sat next to each other and one took the other's trigger.

**What this does not claim.** ADR-0012's own Resolution says its evidence "is weaker than what
[ADR-0011] was waiting for, so this resolution does not automatically resolve it" — and that
remains correct. This is not resolution-by-inheritance. The dependency is being *withdrawn*
after examination, by the maintainer, which is the deliberate judgement the Still-open section
said basis (2) required.

**What 020 and 037 contribute, stated so it is not overread.** 020 made the load-bearing
distinction demonstrated rather than asserted: a model chooses a tool, the choice enters the
same governed entry, an over-reach is refused by existing enforcement, and the trail records
all of it. 037 added a second demonstration from the other direction — an analysis agent whose
ceiling contains nothing to be redirected to, running in a tier that bounds what its process
can reach. Structural guarantees now have two worked examples. **Neither is adopter evidence,
and neither is why this is being accepted** — they are why the claim now reads as a description of a
built thing rather than as an intention.

**What remains unbuilt, recorded so acceptance does not imply otherwise.** "Extension SDKs
live at the perimeter — custom hooks, packs, providers." Packs are real: two ship, with eval
suites and a promotion path. `hooks/` and `providers/` hold a README each. Accepting a record
that describes unbuilt work is ordinary here — ADR-0018 waited four months for 021, ADR-0040
for 036 — but the perimeter model is a **plan, not a fact**, and anyone citing this record for
it should know that.

**The embedded-mode tier stays acknowledged and unbuilt.** Basis (3) — building one — would
have settled the Decision's third paragraph by construction. It has not been built, so the
reduced-assurance language remains a commitment about how such a tier *must* present itself
rather than a description of how one does. If it is ever built, that paragraph is the
requirement it inherits, not a preamble to be re-litigated.
