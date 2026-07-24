# ADR-0030: Executed artifacts are pinned; consulted artifacts are fetched fresh

- **Status**: Accepted
- **Date**: 2026-05-27
- **Amends**: [ADR-0023](0023-validated-designs-as-judgment-layer.md), [ADR-0029](0029-retrieval-in-existing-postgres.md)
- **Relates to**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0021](0021-connectivity-tiers.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)

## Context

[ADR-0004](0004-adopt-skills-as-governed-supply-chain.md) pins skills, for a good reason:
instruction content the agent executes is behavior, and ungated behavior change is
unacceptable.

Applying the same rule to reference guidance produces a bad outcome. Validated designs are
corrected, updated, and extended upstream; a pinned corpus means the agent reasons from
guidance that may be months stale, and — worse — an attestation claiming alignment with a
baseline that has since changed is misleading in a way nobody can detect from the report.

But fetching *everything* fresh is equally wrong: it would make executed behavior depend on
whatever upstream published this morning.

The distinction that resolves it is not about content type or trust level. It is about
**what the artifact does**: whether the agent *executes by* it or *consults* it. Executed
artifacts determine behavior and must be pinned. Consulted artifacts inform judgment and
should be current.

## Decision

**The artifact-class rule:**

> **What the agent executes is pinned. What the agent consults is fetched fresh.**

- **Executed** — skills, prompts, policies, models, pack code. Pinned, eval-gated,
  promoted deliberately.
- **Consulted** — reference guidance and validated designs. Retrieved live at design and
  verification time.

**Provenance is captured at read**: URL, timestamp, and content hash are archived with the
run record, so attestation cites guidance *as published at the moment of the decision*
rather than as it stands today.

**The index is a discovery accelerator, never a source of truth.** It finds the right
document; the document is then read from the source. This amends
[ADR-0029](0029-retrieval-in-existing-postgres.md) — the index locates, it does not
answer.

**Air-gapped snapshots are the labeled exception**: disconnected estates use date-stamped
bundle snapshots, and the staleness is stated in the record rather than hidden
([ADR-0021](0021-connectivity-tiers.md)).

## Consequences

The agent reasons from current guidance while behaving in pinned, reviewed ways — which is
the combination both properties require and neither achieves alone.

Provenance-at-read is what makes alignment attestation honest over time. A report can say
"this design followed the baseline as published on this date, hash so-and-so," and that
claim remains true and checkable years later, when the baseline has moved on. Without it,
every alignment claim silently decays.

Making the index a discovery accelerator rather than an answer source closes a subtle
failure: a stale index entry becomes a stale search result, not a stale fact in an
architecture.

The costs are latency and dependence. Live retrieval is slower than reading an index and
adds an external dependency at design time — mitigated by the connectivity tiers, but real.
Upstream structural changes degrade retrieval before anyone notices, which is why retrieval
health is monitored rather than assumed
([ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)).

The rule also demands classification discipline. Every new content type must be classified
as executed or consulted, and getting it wrong in the permissive direction — treating
executed content as consultable — is a governance hole rather than a performance problem.
