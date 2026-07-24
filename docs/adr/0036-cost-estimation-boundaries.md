# ADR-0036: Cost is estimated and gated, never managed or reported

- **Status**: Accepted
- **Date**: 2026-07-01
- **Supersedes**: the cost boundary of [ADR-0035](0035-audit-as-a-governed-read-path.md)
- **Relates to**: [ADR-0018](0018-grounded-reporting.md), [ADR-0034](0034-conversational-web-ui.md)

## Context

Infrastructure changes cost money, and the moment before a change is applied is exactly
when knowing the cost is most useful. Estimation belongs in the platform: it is decision
support at the point of decision, and it is a natural policy input alongside risk class
and change windows.

The hazard is that cost is a category with enormous gravitational pull. A platform that
estimates cost will immediately be asked to track spend, produce chargeback reports,
reconcile invoices, and answer "what did we actually spend last quarter." Each request is
reasonable, and following them leads to building a cost-management product — a different
product, with different data requirements, different accuracy obligations, and different
consumers.

The specific danger is not scope creep in the abstract. It is that an **estimate** and an
**actual** look identical when rendered as a number in a report. If an estimate appears in
an evidence packet, someone will eventually treat it as an audited financial figure, and
the platform will have manufactured a false record without anyone intending to.

## Decision

**Adopt the product's own native estimation.** No pricing engine is built here; other
estimation tools integrate through existing run-task mechanisms.

**Cost becomes a policy-gate input** alongside risk class and change windows: an estimate
above a threshold can require approval, or block.

**Three layers, with a hard boundary after the second:**

1. **Estimate** at design time — decision support before the change.
2. **Attribution tags** at deploy time — so the organization's own tooling can attribute
   spend accurately.
3. **Actuals stay with the organization's tooling.** The platform does not track spend,
   reconcile invoices, produce chargeback, or issue financial reporting.

**The boundary is enforced in-product, not merely documented:**

- **Inline labeling** — every figure is labeled an estimate, with its scope stated
  adjacent to the number.
- **A must-decline evaluation class** — requests for spend actuals, chargeback, or
  audit-grade cost reporting are declined with a pointer to the appropriate tooling, and
  this is release-gating.
- **A shared-responsibility statement** making the division explicit.
- **Naming discipline** — estimation and gating, never management or reporting.
- **Estimates are excluded from evidence.** Cost figures do not appear in attestation
  reports or evidence packets, where they could be mistaken for audited financial records.

## Consequences

Adopters get cost visibility where it changes decisions, and cost becomes enforceable
policy rather than advisory information — which is a genuine capability, delivered without
building a pricing engine.

Enforcing the boundary in-product rather than in documentation is what makes it hold.
Documented scope boundaries erode under user pressure; a must-decline evaluation class that
gates releases does not, and inline labeling means no figure travels without its
qualification attached.

Excluding estimates from evidence is the most important clause and the least obvious. It
prevents the platform from producing something that looks like a financial record and is
not — a failure that would be discovered by an auditor rather than by a test.

The costs are user-facing friction. Someone will ask for spend actuals and receive a
decline, which feels like a limitation rather than a discipline. Estimation accuracy is
also inherited from an upstream engine: when an estimate is wrong, the platform surfaced it
and owns the user's experience of it, regardless of where it came from.

There is a maintenance obligation as well. The must-decline class has to keep pace with new
ways of asking the same question, or the boundary quietly develops gaps.
