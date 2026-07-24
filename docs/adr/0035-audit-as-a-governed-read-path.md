# ADR-0035: Estate-state queries, and the audit plane as a governed read path

- **Status**: Accepted
- **Date**: 2026-07-01
- **Relates to**: [ADR-0009](0009-adlc-stages-and-observability-planes.md), [ADR-0018](0018-grounded-reporting.md), [ADR-0034](0034-conversational-web-ui.md), [ADR-0036](0036-cost-estimation-boundaries.md)

## Context

Guidance and governed actions did not cover what several personas actually needed. A
compliance analyst asks which workspaces violate a control; an operator asks what changed
last night; an executive asks how many estates are on the current baseline. These are
questions about **estate state** — a third conversation class, distinct from asking how
something works or asking the platform to do something.

Two design questions followed. Different personas must see different answers to the same
question, and the obvious implementation — a separate interface per persona — was already
rejected ([ADR-0034](0034-conversational-web-ui.md)). Something else has to do the
differentiating.

The harder question concerns the audit plane. Compliance and security questions are
answerable only from audit data, which means the platform must expose a read path into the
one store whose integrity everything else depends on. Exposing it carelessly — a query
interface with broad access, or one that can mutate — would undermine the guarantee the
audit plane exists to provide.

There is also a line worth drawing about what a compliance answer *is*. An assistant that
declares something compliant has issued a verdict it has no standing to issue.

## Decision

**Estate-state queries are a third conversation class**, differentiated by **scope algebra
rather than per-persona interfaces**: everyone asks in the same place, and the answer is
bounded by the asker's own entitlements. A team's developer asks about their team's estate;
a compliance analyst asks across the tenant.

**The audit plane becomes a governed read path** with three properties:

- **Tenant-scoped**, enforced by the same authorization core as everything else.
- **Cannot mutate or mask.** The path reads; it has no capability to alter or suppress.
- **Evidence access is itself audited** — who reviewed which evidence, when. A meta-audit
  record, because the integrity of an audit trail includes knowing who read it.

**Compliance answers surface evidence with citations, never verdicts.** The platform
presents what the records show, with references; a human decides what it means. This
follows the same discipline as grounded reporting
([ADR-0018](0018-grounded-reporting.md)): the platform's job is to make the record
legible, not to adjudicate it.

## Consequences

Every persona is served by one surface, and scope does the work — which means adding a
persona is a role-mapping change rather than a build. It also means the authorization
model is exercised constantly by ordinary use, so a scoping error is likely to surface as
a visible wrong answer rather than as a silent leak.

Meta-auditing evidence access closes a genuine gap. In an investigation, who looked at
what and when is itself material, and an audit trail nobody can review the reviewing of is
incomplete.

Refusing to issue verdicts is the right posture for both legal and practical reasons: the
platform lacks the standing and the context to determine compliance, and a confident wrong
verdict is far worse than a well-cited set of facts. It will nonetheless disappoint users
who wanted a green checkmark, and the interface has to make the distinction feel like rigor
rather than evasion.

The costs are query-shaped. Estate-state questions require correctness against real data —
does the control query return the right violation set — which needs fixture-based
evaluation rather than judgment-based scoring. The read path must be genuinely incapable of
mutation, which is an implementation property to prove rather than assert. And meta-audit
adds write volume to the audit plane proportional to how much the evidence surface is used,
which is a storage cost that grows with adoption.
