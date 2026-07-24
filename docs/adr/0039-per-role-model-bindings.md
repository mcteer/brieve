# ADR-0039: Definitions pin per-role model bindings, not a single model

- **Status**: Accepted
- **Date**: 2026-07-21
- **Amends**: [ADR-0022](0022-qualified-model-matrix.md) (matrix dimensionality)
- **Relates to**: [ADR-0021](0021-connectivity-tiers.md), [ADR-0034](0034-conversational-web-ui.md), [ADR-0043](0043-judge-screened-precedent-reuse.md)

## Context

[ADR-0022](0022-qualified-model-matrix.md) established that model competence is not
transferable across packs, and pinned a qualified model per definition. Practice showed the
same argument applies one level deeper: competence is not transferable across *kinds of
work* either.

The work an agent does within a single run is heterogeneous. Answering a question requires
grounding and speed. Planning a change requires decomposition and risk judgment. Writing
code requires correctness at the token level. Reviewing output requires calibrated
skepticism. Condensing requires fidelity. A model that is excellent at one is routinely
mediocre at another, and cost and latency profiles differ by an order of magnitude across
them.

Pinning one model per definition forces a compromise on every axis at once — typically
paying a code-generation model's price and latency to answer a question, or accepting a
fast model's planning.

The obvious fix, letting a run pick models per step, would reintroduce exactly the
ungoverned-input problem [ADR-0022](0022-qualified-model-matrix.md) closed. Whatever the
mechanism, qualification has to keep pace with it.

## Decision

**A definition pins a binding map, not a model**: a closed role vocabulary — **ask, plan,
write, judge, summarize** — mapped onto Qualified Model Matrix cells. Extending the
vocabulary is itself a recorded decision.

**Qualification gains a dimension**: (pack × model × **role**), each cell gated by a
role-specific evaluation suite — ask reuses the guidance and estate-query classes; plan
scores decomposition, tool selection, and risk identification; write runs golden-task
correctness; judge measures agreement with human-labeled verdicts, calibration, and
deny-rate stability. **A binding is only expressible against a green cell.**

**Ask semantics**: the default role for conversational surfaces, serving read and guidance
only — **ask answers, it never acts.** Actions raised in conversation hand off to plan and
write runs with their own approvals.

**Judge semantics**: a judge verdict is a **recorded model claim** that may gate a step, and
**never satisfies an approval requirement policy assigns to a human.** Audit always
distinguishes model gates from human approvals. Setting judge to the same model as writer is
permitted but evaluated as bound — the self-review blind spot shows up in the judge suite,
not in a prohibition.

**Evaluation-time judges are themselves pinned, promoted artifacts**: a judge change is a
gate change.

**No silent fallback.** An unavailable bound model falls back only to another qualified cell
for that pack and role, recorded — or the run parks. Substituting an unqualified model is
never permitted.

Prompt bundles gain per-role sections; cost and latency budgets apply per role, with ask
carrying the tightest. Gateway attribution records the serving role and binding. Air-gapped
binding maps resolve entirely within bundle-delivered models
([ADR-0021](0021-connectivity-tiers.md)).

## Consequences

Each kind of work runs on a model qualified for it, which improves quality and cost
simultaneously rather than trading one for the other. The run record can now answer which
model answered, which planned, which wrote, and which reviewed — a materially better
evidential story than "the agent used model X."

The judge role adds inline review without weakening human oversight, because the
never-satisfies-a-human-approval rule is stated as an invariant rather than left to
configuration. That clause is the difference between a useful quality gate and a quiet
erosion of accountability.

The costs are combinatorial. The evaluation matrix gains a dimension, and every role
multiplies the qualification work — which is exactly why the vocabulary is closed and
extending it is a recorded decision rather than a configuration change.

Per-role prompt sections add authoring surface, and the no-silent-fallback rule means
availability problems surface as parked runs rather than degraded output. That is the
correct direction and it will occasionally be unpopular.
