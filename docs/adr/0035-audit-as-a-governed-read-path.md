# ADR-0035: Estate-state queries, and the audit plane as a governed read path

- **Status**: Accepted
- **Date**: 2026-07-01
- **Relates to**: [ADR-0009](0009-adlc-stages-and-observability-planes.md), [ADR-0018](0018-grounded-reporting.md), [ADR-0034](0034-conversational-web-ui.md), [ADR-0036](0036-cost-estimation-boundaries.md)
- **Amended**: 2026-08-01 (022) — the governed-read discipline extends past the audit plane

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

## Amendment, 2026-08-01 (022): the discipline extends past the audit plane

**"Evidence access is itself audited" was implemented exactly as written, and the scope turned
out to be too narrow.** It bound the audit plane, and nothing else. Measured against the running
service, nine of seventeen operations returned records about runs and threads and wrote nothing —
while both surfaces told every connecting client that every operation was recorded in a
tamper-evident trail.

**The sharpest case shows why the narrow scope was wrong.** ADR-0018's `RunReport` deliberately
omits a run's result so a tenant-scoped report cannot route around the subject-only restriction on
`get_run_result`. That reasoning is sound and the code holds it — and `get_run_result` itself
recorded nothing about who read it. The artifact that could not leak the result was audited; the
one that served it was not. The discipline was protecting the derived thing and not the source.

**Amended scope**: an operation that touches a **run or a thread** records. One that touches
neither does not. Runs and threads are records of *activity*; agent definitions are
*configuration*, and reading one discloses how the platform is set up rather than what anyone did
with it. That boundary is drawn on volume as much as principle — the two catalogue reads are the
highest-frequency calls a connected client makes, and the trail is never sampled, so recording
them would be a permanent cost for the least informative entries.

**The original decision's structural safeguard is kept, and is now load-bearing twice.** This ADR
already required the meta-audit to be written to a stream *separate from the one being read*,
because appending to the queried run's chain would mean reading evidence writes into the evidence
being read. ADR-0018 made that stronger than it was when written: `RunReport` compiles from a run's
chain, so a read appended there would put "who read this run" inside the report of that run —
including reads of the report — growing every time anyone looked. Read records therefore live in
`record-access:{tenant}` and carry the read object's correlation id as a **field**, so an auditor
holding a run id can still find its readers through the same governed query.

**A second stream, not the existing one**, and the cost is stated rather than discovered: an
auditor asking who looked at anything in a tenant now queries two. Merging them was the simpler
option and was rejected on volume profile — an evidence read is a deliberate act during a review,
`list_runs` is what an idle editor calls, and merged the second would permanently bury the first
in the stream an auditor opens first.

**Reconciliation is unaffected and terminates**: `emit_reconciled` writes to
`audit-reconcile-{basis}` under the platform tenant, a third stream, never the one it compared. So
sweeping `record-access` does not grow it — and `record-access` *is* swept like any other stream,
because a record of who looked that is exempt from the check that its two copies agree would be
the one stream nobody verifies.

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
