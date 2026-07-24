# ADR-0009: An eight-stage agent lifecycle, and three observability planes joined by one correlation ID

- **Status**: Accepted
- **Date**: 2026-02-26
- **Relates to**: [ADR-0018](0018-grounded-reporting.md), [ADR-0020](0020-otel-only-backends-at-the-collector.md), [ADR-0031](0031-retrieval-telemetry-as-authoring-backlog.md), [ADR-0035](0035-audit-as-a-governed-read-path.md)
- **Requirements**: R4, R10, R13

## Context

Agents are not ordinary software. Their behavior is determined by a combination of code,
prompts, skills, models, policy, and tool definitions — each of which can change
independently, and several of which are natural-language artifacts that no compiler
checks. A change to any of them changes production behavior. Treating agents as
applications, with a build-and-deploy lifecycle, leaves most of what actually determines
behavior ungoverned.

The second problem is evidential. When something goes wrong — or when an auditor asks
what happened — the question is not "what did the service log" but "what did this agent
do, on whose behalf, under what authority, following which decisions, producing which
change in which product." Answering that requires joining data that conventionally lives
in separate systems with separate identifiers: prompts and reasoning in one place, policy
decisions in another, product runs in a third, and audit somewhere else entirely.

There is also a tension between two legitimate needs. Traces and metrics are operational
telemetry: high volume, worth sampling, valuable for weeks. Audit is evidence:
sampling it destroys it, and it must survive for years. Storing them the same way serves
neither.

## Decision

**A defined agent development lifecycle in eight role-gated stages**, covering the full
set of behavior-determining artifacts rather than code alone: design, develop, evaluate,
stage, release, operate, evaluate-in-production, and retire.

Gating is by role, not by ceremony: security co-signs design and release; ops co-signs
release; compliance reviews release when the change is evidence-relevant. Each feeding
lifecycle — core and adapters, packs, prompts and skills, policy, models — promotes
through its own gate, so a prompt change is governed as deliberately as a code change.

Two stage properties are load-bearing. **Develop runs the identical harness locally with
hooks in warn mode**, so "works locally, fails governance in production" is structurally
impossible. **Retire archives the pinned definition with its audit trail**, so an agent
that no longer exists can still be reconstructed and explained.

**Observability is three planes, never conflated:**

- **Traces** — sampled, with errors and denials always kept; retained days to weeks.
- **Metrics** — aggregated; retained months.
- **Audit** — never sampled, append-only, hash-chained per run, retained per profile,
  exportable to a SIEM.

**One correlation ID joins all three**, and is propagated *into the products* — stamped
into product run metadata and request headers — so the chain prompt → hook decisions →
tool call → product run → product audit entry → resulting change is walkable in either
direction. **Every hook decision is a span**, which makes "why was this denied" a query
rather than an investigation.

## Consequences

Behavior-determining artifacts are governed as artifacts. A prompt bump, a model bump,
and a code change all pass gates appropriate to their risk, which is the only way a
system whose behavior is this distributed can be kept under control.

The correlation ID propagated into products is the single most valuable evidential
property the platform has, and it is cheap only because it was designed in from the
start — retrofitting an identifier through a product boundary after the fact is
usually impossible. It is also fragile in a specific way: any code path that fails to
propagate it breaks the chain silently, which is why propagation is a standing
engineering rule and a review checklist item rather than a convention.

Separating the planes means audit costs what audit costs — never sampled, retained for
years — while traces stay affordable. It also means three retention policies, three
storage decisions, and three sets of access controls rather than one.

The eight stages are heavier than most teams are used to, particularly for prompt and
pack changes that feel like content edits. That weight is the point, but it is a real
adoption cost, and the enablement material exists partly to make it bearable.

This decision creates the substrate that later evidence decisions build on: grounded
reporting reconciles claims against these records
([ADR-0018](0018-grounded-reporting.md)), the audit plane's governed read path is
defined over it ([ADR-0035](0035-audit-as-a-governed-read-path.md)), and production
traces feed the evaluation flywheel at stage seven.
