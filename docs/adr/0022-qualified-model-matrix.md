# ADR-0022: Models ship as an eval-qualified matrix, pinned per definition

- **Status**: Accepted
- **Date**: 2026-04-22
- **Relates to**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0021](0021-connectivity-tiers.md), [ADR-0039](0039-per-role-model-bindings.md)

## Context

The model is the least predictable component in the system and the one most likely to
change without anyone deciding it should. Providers ship new versions, deprecate old
ones, and silently adjust behavior behind stable-looking identifiers. A platform that
points at "the latest model" has an ungoverned input determining production behavior.

Model quality is also **not transferable across tasks**. A model that writes excellent
Terraform may reason poorly about Vault policy structure; a model that follows
instructions reliably may be weak at grounding answers in retrieved guidance. "Model X is
good" is not a statement the platform can act on — the meaningful unit is a model's
demonstrated competence at a *specific pack's* work.

There is a third constraint that is commercial rather than technical: adopters generally
have an existing relationship with one model provider, and are not free to route work to
whichever provider performs best.

## Decision

**A Qualified Model Matrix of eval-qualified (pack × model) combinations.**

- A definition may only pin a **qualified cell** — a combination demonstrated by
  evaluation, not assumed.
- The matrix is **prescribed per adopter** according to their provider relationship, so
  the platform works within an organization's existing commitments rather than against
  them.
- **Model version bumps promote through evals like any other artifact.** There is no
  auto-tracking of "latest."
- Air-gapped estates qualify the models they will actually run
  ([ADR-0021](0021-connectivity-tiers.md)), with a competency-tuned open-weight model on
  the roadmap as a governed, bundle-delivered artifact for self-hosted deployments.

## Consequences

Model changes become deliberate, reviewable events rather than ambient drift, which is the
only way a platform whose behavior depends this heavily on models can make stable claims
about that behavior.

Qualifying per pack rather than globally matches how model competence actually varies, and
it produces information the platform can act on: when a new model version regresses on one
pack and improves on another, the matrix records exactly that instead of forcing a single
verdict.

Working within an adopter's provider relationship removes a procurement obstacle that
would otherwise block deployment entirely.

The costs are combinatorial and ongoing. Every pack times every model times every version
bump is an evaluation run, and the matrix must be maintained as both dimensions grow —
this is the single largest recurring evaluation cost in the platform. Pinning also means
adopters do not automatically benefit from genuine upstream improvements; they benefit
when someone qualifies them.

The matrix is also a public commitment with an operational tail: a provider deprecating a
qualified model forces re-qualification on their schedule, not the platform's.

This decision was later extended to a third dimension — role — when definitions gained
per-role model bindings ([ADR-0039](0039-per-role-model-bindings.md)), on the same
reasoning that made per-pack qualification necessary in the first place.
