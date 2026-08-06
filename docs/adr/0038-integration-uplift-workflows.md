# ADR-0038: Integration and uplift work is a first-class workflow family

- **Status**: Accepted
- **Date**: 2026-07-14
- **Amended by**: [ADR-0064](0064-version-control-is-a-platform-capability.md) (the pack-tool-target clause)
- **Realized by**: 038 — `src/core/authoring/`, `infra/jobs/authoring-tier.nomad.hcl`, `evals/authoring/`
- **Relates to**: [ADR-0023](0023-validated-designs-as-judgment-layer.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md), [ADR-0037](0037-tool-transport-policy.md)

## Context

The platform's workflow families covered producers (platform teams building modules),
consumers (application teams deploying validated architectures), and day-two operations.
A recurring adopter need fits none of them.

A developer wants to use a product feature — dynamic database secrets is the canonical case
— and has no idea where to start. The work is not deploying infrastructure and not
operating an estate: it is **authoring integration code into their own application**, which
requires understanding both the product feature and the specific application, and produces a
change to a repository the platform does not own.

This is where the platform's premise is most directly tested. Turning a task that takes an
expert an afternoon and a novice a week into something that takes minutes is exactly the
value proposition — and it involves the platform reading untrusted application code and
writing code back, which is the riskiest thing it does.

## Decision

**Integration and uplift is a first-class workflow family** alongside producer, consumer,
and day-two operations. The shape: a repository is provided; the agent analyzes the
application, applies pack expertise, authors the integration, and opens a pull request back
to that repository.

Its mechanics ride existing machinery, with four constraints doing the safety work:

- **Repository analysis runs in the hardened untrusted-content isolation tier**, with
  injection-lens hooks. Application code is adversarial input, and the platform treats it
  that way regardless of who supplied it.
- **Expertise is skills-first with retrieval on gap**
  ([ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)) — the same layering as
  everywhere else.
- **Authored code uses secret references only.** Never a secret value in generated code, a
  commit, or a pull-request body.
- **Writes land exclusively as pull requests, scoped to the requester's own repositories,
  with the human as merge authority.** The platform proposes; a person decides.

Version control becomes a first-class pack tool target, with transport chosen by the
standing test ([ADR-0037](0037-tool-transport-policy.md)).

**New evaluation classes gate the family**: integration-correctness golden tasks, and
must-deny cases covering secret values in generated code or pull-request bodies,
exfiltration of analyzed application code, and injection resistance against hostile
repository content.

## Consequences

The platform's value proposition extends from operating infrastructure to *adopting product
capability*, which is where the expertise gap is widest — a developer who has never wired
dynamic secrets is exactly the user the platform exists for.

The pull-request-only constraint is what makes this safe to offer. The agent's output enters
a review process the organization already trusts, the human remains the merge authority, and
the blast radius of a wrong answer is a rejected pull request rather than a broken
application.

This family also has the best demonstration properties in the product: the expertise is
visible in the output, and the governance is visible in the audit trail behind it.

The costs concentrate on the untrusted-content boundary. Analyzing arbitrary application
code is the platform's largest prompt-injection surface, and the isolation tier plus
injection-lens hooks are necessary rather than precautionary. The exfiltration risk is
equally real: an agent that has read a private codebase must not carry it anywhere, which
constrains context handling and requires its own must-deny evaluations.

Integration correctness is also harder to evaluate than infrastructure correctness — a
plan either applies or does not, while integration code can be syntactically fine and
subtly wrong. The golden-task corpus for this family needs to be genuinely good, and
building it is real work.
