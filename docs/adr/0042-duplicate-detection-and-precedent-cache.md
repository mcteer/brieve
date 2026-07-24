# ADR-0042: Duplicate detection and precedent reuse — two mechanisms, neither skipping governance

- **Status**: Accepted
- **Date**: 2026-07-21
- **Extends**: [ADR-0024](0024-durability-provider-seam.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0029](0029-retrieval-in-existing-postgres.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)
- **Relates to**: [ADR-0030](0030-pinned-versus-consulted-artifacts.md), [ADR-0043](0043-judge-screened-precedent-reuse.md)

## Context

Two distinct patterns of repeated work appeared, and conflating them produces a mechanism
that serves neither.

**Concurrent duplication**: two people ask for substantially the same work at the same time
— the same repository, the same commit, the same class of task. Both runs proceed, both
consume authority and inference, and both produce a change proposal for the same target.
The second one is waste at best and a conflict at worst.

**Non-concurrent repetition**: the same design work is requested again later. Full
resynthesis is correct if circumstances have changed, and pure waste if they have not.

The obvious response — a cache — is dangerous in a governed system for one specific reason.
A cache hit is a *result computed under someone else's authority*. If reuse skipped the
authorization path, the platform would have built a mechanism by which one user's approved
outcome becomes another user's unapproved action. That is an authority-laundering hole
dressed as an optimization.

## Decision

**Two mechanisms, deliberately separate.**

**1. An in-flight index.** Keyed on repository, commit, and task class, fuzzy-matched using
the retrieval infrastructure already deployed
([ADR-0029](0029-retrieval-in-existing-postgres.md)), and checked **before any tool call
fires**. On collision it surfaces a **coordination offer** — someone is already doing this,
would you like to join or view it — rather than silently duplicating or silently blocking.

**2. A provenance-stamped precedent cache** for non-concurrent repeats. Entries are
staleness-checked the same way guidance content is stamped
([ADR-0030](0030-pinned-versus-consulted-artifacts.md)): a commit that has moved, or
guidance that has been updated since, is a miss.

Governing both:

> **Reuse never skips governance.** The second requester gets their own token exchange,
> their own scope check, and their own approval gate. A precedent supplies a *starting
> point*, never an authorization.

Both are **tenant and team scoped**, never global — cross-tenant reuse would be a
confidentiality breach regardless of how useful it might be.

**A repeated hit is a signal**: stronger than raw retrieval telemetry
([ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)) for ranking what should be
distilled into a skill or a paved workflow, because it identifies work being done
repeatedly rather than merely looked up.

Whether a hit should ever point at the same *environment* rather than the same *design* is
deliberately left as an adopter decision — the platform does not assume that two teams
wanting the same design want the same instance of it.

## Consequences

Duplicated effort is caught before it consumes authority or inference, and the coordination
offer turns a collision into collaboration rather than a race. Repeated design work becomes
cheaper without becoming less governed.

The reuse-never-skips-governance rule is what makes this safe, and it is worth being blunt
about: it discards a large part of the theoretical saving. Every requester still pays the
full authorization path. What is saved is synthesis, not permission — and that is the only
saving available without breaking the platform's central claim.

Making repeated hits an authoring signal converts a caching mechanism into a product
improvement signal, which is the same pattern as retrieval telemetry and equally valuable.

The costs are correctness-shaped. Fuzzy matching on task similarity will produce false
positives, and a coordination offer for unrelated work is an annoyance that erodes trust in
the feature. Staleness detection must be conservative — offering a stale design is worse
than offering none — which is the problem [ADR-0043](0043-judge-screened-precedent-reuse.md)
addresses. And tenant scoping means the cache's hit rate is lower than a global one would
be, which is the correct trade and a real cost.
