# ADR-0040: Tool and capability disclosure is deferred by default

- **Status**: Accepted
- **Date**: 2026-07-21
- **Extends**: [ADR-0019](0019-adapter-on-framework-capabilities.md)
- **Relates to**: [ADR-0037](0037-tool-transport-policy.md)

## Context

As packs accumulate on a single agent definition — infrastructure, secrets, version
control, guidance retrieval, cost estimation, and whatever integration work adds — the
combined tool surface grows steadily. Front-loading every registered tool's full schema
means paying that context cost on every run, before the task has begun, whether or not any
of those tools is used.

The cost is not merely financial. Context spent on unused schemas is context unavailable for
the task, and a large tool surface presented all at once measurably degrades tool selection:
the model chooses worse when choosing among a hundred options than among the handful
relevant to the work.

The primary framework provides a mechanism for this — capability-level deferred loading,
where a capability costs a catalog line until the model reaches for it, plus tool search so
a run pays only for tools it actually uses.

The question is whether deferring disclosure weakens governance. It does not, and the reason
matters: enforcement attaches at the tool *call*, not at the schema's presence in context.
A tool the model has not yet seen is not a tool outside the registry — it is simply a tool
whose schema has not been loaded.

## Decision

**Deferred disclosure is the default posture across the registered tool layer**:
capability-level deferred loading and tool search, so context is paid for what a run uses
rather than for what a definition permits.

This is **disclosure economics** — distinct from and complementary to transport policy
([ADR-0037](0037-tool-transport-policy.md)), which governs how a tool reaches its far side.

**No registry, hook, or audit change.** Every tool remains registered, every call passes the
full pipeline, every decision is audited. What changes is when the schema enters context.

**Verified by tool-call parity in the conformance suite**: an identical operation must
produce identical governance outcomes whether or not the tool was disclosed eagerly.

## Consequences

Definitions can carry many packs without paying for all of them on every run, which is what
makes broad capability compatible with the efficiency the platform claims. Tool selection
improves as a side effect, because the model chooses from a smaller, more relevant set.

Making parity a conformance assertion is what keeps this a pure optimization. Without it,
deferral would be a plausible place for a governance gap to hide — a tool loaded through a
different path might plausibly follow a different one — and the assertion forecloses that
by test rather than by argument.

The costs are modest and real. Deferred loading adds a step: a run that reaches for an
undisclosed capability pays a small latency cost at that moment rather than at startup. Tool
descriptions also matter more than they did — a model can only reach for a capability whose
catalog line conveys what it does, so terse, accurate descriptions become a quality
requirement rather than a nicety.

This also creates a dependency on a specific framework mechanism, absorbed at the adapter
where framework dependencies belong ([ADR-0019](0019-adapter-on-framework-capabilities.md)).
