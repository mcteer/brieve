# ADR-0029: Retrieval runs in the Postgres already deployed — no vector database

- **Status**: Accepted
- **Date**: 2026-05-27
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0023](0023-validated-designs-as-judgment-layer.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md)

## Context

Adopting validated designs as the architectural-judgment layer
([ADR-0023](0023-validated-designs-as-judgment-layer.md)) requires retrieval: finding the
right guidance at the right moment, from a corpus too large to load into context.

The reflexive answer is a vector database, and the reflexive answer collides directly with
the lean-by-default rule ([ADR-0007](0007-lean-and-federated-profiles.md)): another
operated service, in the blocking path of design-time work, for a corpus that is — measured
honestly — not large. Guidance corpora are thousands of documents, not billions of vectors.
That is a scale where a general-purpose database with vector support is entirely adequate,
and the deployment already runs one for checkpoints and run logs.

There is a second, less obvious requirement. Embeddings are only meaningful relative to the
model that produced them. A corpus embedded with one model and queried with another
produces confidently wrong retrieval — and because retrieval failures surface as
plausible-but-unfounded architecture rather than as errors, this is a silent failure mode.

## Decision

**Hybrid retrieval — vector similarity plus full-text search — in the Postgres the enclave
already deploys.** No dedicated vector database.

**Embeddings are build-time artifacts**, computed when the corpus is prepared rather than
at runtime. **The query embedder and the corpus embedder are version-pinned together**, so
they cannot drift apart; changing one requires re-indexing with the other.

A dedicated vector store attaches **only per named trigger**
([ADR-0028](0028-product-identity.md) and the lean rule), behind a **thin retriever
interface** so the substitution is a configuration change rather than a rewrite.

## Consequences

The retrieval capability arrives with zero additional operated components, which keeps the
guidance layer available in the Lean profile rather than making it a Federated-only feature.
Hybrid search is also genuinely better than pure vector similarity for this corpus type,
where exact terminology matters and users search for named things.

Build-time embedding means no embedding service in the request path — one less blocking
dependency, and one less thing to be down. Pinning the embedder pair closes the silent
drift failure, which is the kind of bug that would otherwise be discovered months later
through slowly degrading output quality.

The costs are bounded and real. A general-purpose database will not match a dedicated
vector store at large scale or on advanced retrieval features, and the named-trigger
mechanism exists precisely because that ceiling is real rather than theoretical.
Re-indexing on embedder change is an operational step that must be sequenced correctly,
particularly in offline estates where the corpus ships as a bundle artifact.

Retrieval quality also becomes the platform's responsibility rather than a vendor's. When
guidance is not found, the agent proceeds without it, and the resulting output is confident
and unfounded — which is why retrieval health is monitored rather than assumed.
