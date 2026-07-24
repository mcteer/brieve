# ADR-0028: Product identity — simple, elegant, efficient

- **Status**: Accepted
- **Date**: 2026-05-20
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0025](0025-enclave-is-the-default-topology.md)
- **Requirements**: R12

## Context

A platform accumulating this many capabilities — identity, enforcement, durability,
evaluation, retrieval, evidence, multiple surfaces — is at permanent risk of becoming
describable only by enumeration. When a project cannot be defined in a sentence, two
things follow: adopters cannot tell whether it is for them, and the team loses its
tiebreaker for design arguments.

The second is the more damaging. Most architectural disagreements here are between a
simpler design that does less and a more capable design that adds an operated component, a
configuration axis, or a concept. Without a stated identity, those arguments are decided by
whoever is most invested, and the result drifts steadily toward the more capable and less
adoptable end.

The lean-by-default rule ([ADR-0007](0007-lean-and-federated-profiles.md)) is the specific
form of that discipline. This decision records the general form.

## Decision

**A one-breath definition is adopted as the positioning of record**: the platform puts
infrastructure expertise in a box — governed, and simple enough to stand up in an
afternoon.

Three adjectives are the standing tiebreaker: **simple, elegant, efficient.**

- **Simple** — a small number of concepts and operated components; the failure model fits
  in one person's head.
- **Elegant** — mechanisms that do several jobs correctly rather than several mechanisms
  that each do one.
- **Efficient** — cheap in context, in operational footprint, and in the human attention
  it demands.

Where a design argument is otherwise balanced, these decide it. The formal product name is
a separate question, deferred.

## Consequences

Design arguments get a tiebreaker that is written down and can be appealed to by anyone,
rather than being resolved by seniority or persistence. That is the practical value here:
"which of these is simpler" is a question with an answer, where "which is better" often is
not.

The positioning also sets adopter expectations correctly. An organization arriving expecting
a comprehensive enterprise platform with a hundred configuration axes will be disappointed,
and it is better that they discover that from the positioning than from a deployment.

The cost is that this occasionally rules out capability that some adopter genuinely wants.
"Simple" means saying no to individually reasonable features, and the accumulated set of
declined features will, at some point, be exactly what a large prospect asked for. The
alternative — saying yes to each — is how platforms become unadoptable, one reasonable
addition at a time.

An adjective-based tiebreaker is also inherently soft: reasonable people disagree about
what is elegant. It works as a forcing function for explicit argument, not as an algorithm,
and it should not be cited as though it settles questions it merely frames.
