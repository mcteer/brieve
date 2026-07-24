# GR-1: Gap review — shared-responsibility dispositions

- **Status**: Recorded
- **Date**: 2026-05-06
- **Produced**: [ADR-0045](0045-tiered-capabilities.md), [ADR-0046](0046-multi-tenancy.md)
- **Relates to**: [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0036](0036-cost-estimation-boundaries.md)

## What this is

This is not a decision record. It is the recorded outcome of a structured gap review — a
pass over the architecture looking for capabilities assumed but never decided, and for
boundaries assumed but never stated.

Two findings were substantial enough to become decisions in their own right and are
recorded separately: [ADR-0045](0045-tiered-capabilities.md) (competency tiers) and
[ADR-0046](0046-multi-tenancy.md) (multi-tenancy). The remainder were **boundary
dispositions** — statements about where this platform's responsibility ends and the
adopting organization's begins. They are recorded here because they are load-bearing for
what the platform promises, and because an unstated boundary is one the platform will be
assumed to cover.

## Dispositions

**Data lifecycle: mechanism ships, values belong to the organization.** The platform ships
the inventory and the controls — data classes (checkpoints, traces, captured content, audit,
evaluation corpora, retrieved-guidance archives), where each lives, per-class configurable
retention, and the erasure story per class including how it interacts with write-once
storage and legal hold. **Every retention value is the organization's policy, not a
platform default with a compliance implication.** The platform does not decide how long an
organization keeps evidence.

**Private module registry content integrity is the organization's responsibility.** The
platform governs how modules are *consumed* — which agent, under whose authority, through
which approvals — not whether the module content itself is sound. An organization's private
registry is its own supply chain, and the platform does not audit, scan, or vouch for its
contents. This is stated explicitly in the shared-responsibility statement rather than left
to inference.

**Control-plane disaster recovery is organization-relative, with one exception.** Backup
cadence, recovery point and time objectives, and cross-region posture depend on the
organization's own requirements and are theirs to set. The platform ships **one thing that
is not optional: a fleet re-bootstrap runbook** — the procedure for re-establishing the
trust fabric and re-registering the agent fleet after a total loss. That procedure is
specific to this architecture and cannot be improvised during an incident.

**Cost governance is delegated, with two things retained.** Budgets and chargeback belong to
the organization's own gateway and financial tooling. The platform retains **attribution
propagation** — correlation ID, agent, definition, and tenant on every model call, so the
organization's tooling can attribute accurately — and **run-level loop bounds**, so a
runaway run cannot consume without limit. This disposition was later extended and made
enforceable by [ADR-0036](0036-cost-estimation-boundaries.md), which added design-time
estimation and cost as a policy-gate input while holding the same boundary.

## Consequences

Stating boundaries explicitly is what makes the shared-responsibility model honest. Each of
these is a place where an adopter could reasonably assume the platform covers something it
does not, and discovering that assumption during an audit is far worse than reading it
during evaluation.

The retained items matter as much as the delegated ones. Attribution and loop bounds are the
minimum the platform must keep for a delegated cost model to work at all — without
attribution the organization's tooling cannot see what the platform did, and without bounds
delegation becomes an uncapped liability.

The fleet re-bootstrap runbook is the one place this review converted "the organization's
responsibility" into a platform deliverable, and correctly: it is the only part of disaster
recovery that requires knowledge of this architecture rather than of the organization's own
infrastructure.

The ongoing obligation is that the shared-responsibility statement must stay accurate as the
platform grows. A boundary that quietly moves — a capability added that adopters assume
covers more than it does — reintroduces exactly the gap this review closed.
