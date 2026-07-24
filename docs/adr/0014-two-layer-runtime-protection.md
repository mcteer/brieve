# ADR-0014: Runtime protection is two-layered — in-process hooks, plus an optional wire-level guardrail

- **Status**: Accepted
- **Date**: 2026-03-11
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0012](0012-runtime-versus-attach-posture.md), [ADR-0013](0013-adopt-agent-security-framework-taxonomy.md)

## Context

[ADR-0006](0006-in-process-fail-closed-enforcement.md) settled that enforcement lives
in-process and never depends on network placement. That decision is about where the
*guarantee* attaches, and it stands.

It leaves a separate question open. In-process hooks see semantics: which tool, which
arguments, whose authority, what risk class — everything needed for meaningful policy.
What they cannot see is traffic that does not go through them, which by construction
means traffic from processes the harness does not run. Organizations running their own
agents alongside the harness ([ADR-0012](0012-runtime-versus-attach-posture.md)) have
exactly that traffic, and a wire-level control is the only thing that can observe it.

There is also a defense-in-depth argument that regulated adopters make independently: a
single enforcement layer, however well designed, is a single point of failure in a
security review. Organizations that already operate a service mesh will ask why the
platform does not use it.

The hazard is obvious from [ADR-0006](0006-in-process-fail-closed-enforcement.md): the
moment a wire-level layer exists, it becomes tempting to rely on it, and reliance
reintroduces exactly the misconfiguration-shaped hole that in-process enforcement was
chosen to eliminate.

## Decision

**Runtime protection is two layers with an explicit hierarchy.**

- **Layer one — in-process hooks.** The semantic, fail-closed baseline. Always present,
  never optional, and solely responsible for the platform's guarantee. Everything the
  harness runs is governed here.
- **Layer two — wire-level guardrail.** A mesh-based control with pluggable policy
  engines, available in the Federated profile
  ([ADR-0007](0007-lean-and-federated-profiles.md)) for organizations that operate the
  infrastructure. It observes and constrains traffic — including from agents the harness
  does not run — and is **defense-in-depth only**.

**Layer two never becomes load-bearing.** No guarantee is stated that depends on it; the
Lean profile omits it entirely and loses nothing the platform promises. Where it is
present, it constrains what layer one already governs, plus traffic layer one cannot see
— and for that unseen traffic, it delivers wire-level containment, not the semantic
governance layer one provides.

Both container orchestrators are first-class runtimes for this layering, so the pattern
does not assume a single substrate.

## Consequences

Organizations with existing mesh infrastructure get value from it, and security reviewers
asking about defense-in-depth have a real answer — without the platform's guarantees
becoming contingent on infrastructure it does not control.

The layering also gives the attach posture ([ADR-0012](0012-runtime-versus-attach-posture.md))
a concrete mechanism: agents the harness does not run can be constrained at the wire even
though they cannot be governed semantically. What that constraint can and cannot claim is
bounded here rather than left to marketing.

The costs are honest. Two enforcement layers means two policy expressions that can
disagree, and a divergence between them is a confusing failure mode to debug — which is
why policy jurisdictions are kept disjoint rather than duplicated across engines. There
is ongoing pressure to let layer two carry weight, especially from operators who find
network-level policy more familiar; resisting that is a standing design discipline, not
a one-time decision.

Layer two also brings operational surface that only Federated adopters pay for, which is
the correct place for it, but it means the two profiles have genuinely different
operational footprints even though their guarantees are identical.
