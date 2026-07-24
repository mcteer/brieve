# ADR-0031: Skills and retrieval are complementary; retrieval telemetry ranks the authoring backlog

- **Status**: Accepted
- **Date**: 2026-06-03
- **Extends**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0023](0023-validated-designs-as-judgment-layer.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md)
- **Relates to**: [ADR-0009](0009-adlc-stages-and-observability-planes.md)

## Context

With both a pinned skill corpus and live guidance retrieval in place, an obvious question
follows: which one should answer a given request, and does having both mean one is
redundant?

They are not redundant, and treating them as alternatives produces bad outcomes in either
direction. Relying only on skills means the agent is confidently wrong about anything not
anticipated by an author, including guidance published after the last skill release.
Relying only on retrieval means every routine task pays retrieval cost and latency, with
quality varying by how well the corpus happens to cover the request — and pinned,
eval-gated behavior is lost.

There is also a resourcing question underneath. Skill authoring is expensive expert work
with no natural prioritization signal, so it tends to be allocated by whoever asks loudest
or by guesswork about what users need.

A third hazard is specific to mixing the two sources. If output does not distinguish
between an organization's own standard and retrieved vendor guidance, a retrieved
recommendation can be read as an internal requirement — **authority laundering**, where
guidance acquires an authority it was never granted.

## Decision

**Skills first for the anticipated; retrieval on gap for the long tail** and for guidance
published after the last skill release. The two are complementary layers, not competing
sources.

**Retrieval telemetry is the skill-authoring backlog.** Aggregated retrieval targets —
what the agent had to look up, and how often — rank what should be distilled into skills
next. This is reviewed at the lifecycle's production-evaluation stage
([ADR-0009](0009-adlc-stages-and-observability-planes.md)), alongside traces.

The signal is bidirectional: **a section's retrieval rate falling after a pack release is
evidence the distillation worked.** Skill authoring becomes measurable rather than
faith-based.

**Outputs mark provenance** — organization standard versus retrieved guidance — so a
reader can tell what carries local authority and what is a vendor recommendation. This
prevents authority laundering.

Retrieval evaluations assert that **current guidance was sought and applied**, not that
particular strings appeared, and a structural canary detects upstream reorganization
before it silently degrades retrieval quality.

## Consequences

Routine work is fast and eval-gated; unusual work is still answerable. The platform is not
limited to what its authors anticipated, which is the difference between a useful expert
system and a brittle one.

Turning retrieval telemetry into an authoring backlog is the most valuable secondary effect
here: it converts a cost signal into a product-improvement signal, and it is empirical
rather than anecdotal. Teams usually cannot answer "what should we document next" with
evidence; this design can.

Provenance marking closes a genuine trust problem. Without it, the platform gradually
becomes a laundering mechanism by which "the vendor suggests" becomes "our policy
requires," which is corrosive precisely because it is invisible.

The costs are ongoing measurement obligations. Retrieval telemetry must be collected,
aggregated, and actually reviewed — an unreviewed backlog signal is just storage. The
canary needs maintenance, since upstream structure changes are exactly the events it exists
to catch and exactly the events that break canaries.

Writing retrieval evaluations that assert *behavior* rather than string matching is harder
than the naive version, and the naive version is the tempting one — an eval that checks
whether a phrase appeared will pass while the agent quietly stops consulting guidance at
all.
