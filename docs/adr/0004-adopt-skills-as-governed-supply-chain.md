# ADR-0004: Adopt upstream skills as a pinned, governed supply chain

- **Status**: Accepted
- **Date**: 2026-01-22
- **Relates to**: [ADR-0002](0002-adopt-first-migrate-and-delete.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md)

## Context

The platform's value depends on expertise: an agent that knows how to write good
Terraform, structure a Vault deployment, or wire dynamic secrets into an application.
That expertise lives in prompts and skills — instruction content the agent executes by.

Authoring all of it from scratch would take years and would duplicate work the product
vendors are already doing. Vendor-published skill repositories exist and are actively
maintained by the people who know the products best.

But adopting them naively introduces a serious hazard. Skill content is *instructions
the agent follows*. An upstream repository that auto-updates is an unreviewed channel
into the agent's behavior — a supply-chain risk with the specific property that a
malicious or merely careless change alters what the agent does, in production, with the
authority of whoever invoked it. This is the same class of risk as an unpinned
dependency, except that the "code" is natural language and the failure mode is
behavioral rather than a crash.

There is also a coverage question: upstream skills cover what upstream chose to cover,
which will not include everything this platform needs.

## Decision

**Adopt upstream skill repositories as the expertise baseline, pinned and treated as a
governed supply chain.**

- Skills are **pinned to a version**, never auto-tracked.
- An upstream bump is a **reviewed change**: provenance check, injection-lens review
  (does this content attempt to redirect the agent's behavior or exfiltrate context),
  and a passing eval run before promotion.
- The project authors **overlays** — additions and adjustments layered on the adopted
  baseline — and authors original content only for genuine gaps.
- Skills are *executed* content and therefore pinned, in contrast to consulted
  reference guidance, which is fetched fresh ([ADR-0030](0030-pinned-versus-consulted-artifacts.md)).

## Consequences

The platform inherits a large body of maintained expertise without writing it, and
without owning its upkeep — consistent with the adopt-first discipline
([ADR-0002](0002-adopt-first-migrate-and-delete.md)). Overlay authoring effort
concentrates where the platform actually differs from the baseline.

The pinning discipline means the agent's behavior only changes when someone decides it
should. That is the entire point: behavior is an artifact, and an ungated change to
instruction content is an ungated change to production behavior.

The cost is latency. Upstream improvements do not reach the platform until someone runs
the review and the evals, so the platform is always slightly behind the baseline it
adopts. On a fast-moving upstream this is a real and recurring cost, paid deliberately.

Injection-lens review is a genuinely new review skill — reviewers must read instruction
content adversarially, asking not "is this good advice" but "what could this make the
agent do." That capability has to be built and maintained on the review side, and it is
not the same as ordinary code review.
