# ADR-0023: Vendor validated designs are the architectural-judgment layer

- **Status**: Accepted
- **Date**: 2026-04-29
- **Relates to**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0021](0021-connectivity-tiers.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)

## Context

Skills ([ADR-0004](0004-adopt-skills-as-governed-supply-chain.md)) teach an agent *how*
to do things: the mechanics of writing a module, configuring an auth method, structuring
a workspace. They do not settle *architectural* questions — how this deployment should be
structured for this scale, in this topology, under these availability requirements. That
judgment is what separates a competent operator from an expert one, and it is exactly what
the platform promises to make available.

The vendor publishes validated designs: reference architectures reviewed and maintained by
the people who build the products. They are precisely the missing layer, and they are
maintained by someone else — which under adopt-first is the answer.

Two hazards come with using them. Validated designs are *guidance*, not policy: an
organization's own standards legitimately override them, and an agent that treats vendor
guidance as binding will produce architectures that conflict with local requirements. And
in the other direction, an agent that silently departs from a validated baseline produces
something that looks vendor-endorsed and is not — which is worse than an obvious
deviation, because nobody knows to check.

## Decision

**Adopt vendor validated designs as the architectural-judgment layer**, with pinned
corpora per capability pack, retrieved at design and verification time through
deferred-loading retrieval rather than loaded into every run.

**Precedence is explicit and ordered:**

> skills < validated-design baseline < explicit organization policy

Skills provide mechanics; validated designs override them on architectural questions;
an organization's own stated policy overrides both.

**Silent deviation is prohibited.** Where a design departs from the validated baseline,
the deviation is recorded in a **deviation register** with its reason — visible in the
output and available as evidence. Deviating is permitted; deviating invisibly is not.

Corpus updates pass the same supply-chain gate as skills
([ADR-0004](0004-adopt-skills-as-governed-supply-chain.md)) and ship in offline bundles
for disconnected estates ([ADR-0021](0021-connectivity-tiers.md)). An alignment
attestation report joins the evidence catalog, so an organization can show where its
estate follows the baseline and where it deliberately does not.

## Consequences

The agent gains architectural judgment without the platform having to author it, and that
judgment stays current because it is maintained upstream. The precedence order resolves
what would otherwise be a recurring ambiguity — three sources of guidance with no stated
ranking is a guarantee of inconsistent output.

The deviation register turns a liability into evidence. An estate that deviates for good
reasons can now demonstrate that the deviations were deliberate and reasoned, which is a
stronger compliance position than either blind conformance or undocumented divergence.

The costs are mostly retrieval-shaped. Guidance must be found at the right moment and
applied without flooding context, which is why it is deferred-loaded rather than
preloaded — and retrieval that misses produces confidently unfounded architecture, so
retrieval quality becomes a governance property rather than a performance one.

Deviation detection is genuinely hard: recognizing that a proposed design departs from a
baseline requires understanding the baseline structurally, not textually. Getting this
wrong in the permissive direction produces silent deviation, which is precisely what the
decision forbids.

There is also a dependency on upstream publishing cadence and structure. When the
guidance corpus is reorganized upstream, retrieval degrades before anyone notices — which
is why retrieval health is monitored rather than assumed
([ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)).
