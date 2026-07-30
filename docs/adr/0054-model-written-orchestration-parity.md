# ADR-0054: Model-written orchestration: per-call and per-delegation governance parity

- **Status**: Proposed
- **Date**: 2026-07-29
- **Extends**: [ADR-0040](0040-deferred-tool-disclosure.md), [ADR-0041](0041-code-mode-requires-hook-parity.md)
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0019](0019-adapter-on-framework-capabilities.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md), [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0043](0043-judge-screened-precedent-reuse.md)
- **Requirements**: R4 (evidence over claims), R7 (total interception)

## Context

[ADR-0041](0041-code-mode-requires-hook-parity.md) made code mode conditional on a hard
gate: every tool call issued from sandboxed code must round-trip the full hook pipeline, or
code mode does not ship in the governed path. That record deliberately left the *how*
unresolved, because at the time no sandbox architecture made the condition obviously
satisfiable. Verified per-call parity was a requirement without a mechanism.

Two upstream projects now bear directly on this, and the reason to write a record about them
is that one changes the *character* of ADR-0041's condition and the other extends it to an
object the platform has not governed before. Both are recorded here as external observations
as of 2026-07-29, not as endorsements.

**Monty** ([github.com/pydantic/monty](https://github.com/pydantic/monty), MIT, v0.0.17) is a
Rust Python interpreter whose banner reads *"Experimental — not ready for prime time."* Its
relevant property is architectural rather than incremental: it has **no ambient
capabilities.** Filesystem, network, and environment access do not exist inside it. Every
external effect is an external function call the host explicitly provides. Its `start()` /
`resume()` pair makes execution **pause at every external function call**, returning a
snapshot — function name and arguments — to the host, which performs the call and resumes
with the result. Interpreter state serializes to bytes for cross-process resume, and the
runtime enforces limits on memory, allocations, stack depth, and execution time, with
cancellation. Upstream states it will power code mode in Pydantic AI via a `CodeModeToolset`.

**DynamicWorkflow** (the `pydantic-ai-harness` package, MIT, 0.x, imported from
`pydantic_ai_harness.experimental.dynamic_workflow`) is code mode moved up a level. The
orchestrator model writes one Monty-sandboxed Python script in which each **sub-agent is an
async function** — fan-out via `asyncio.gather`, chaining, voting — and the whole tree runs
inside a single tool call, with **only the final value returning** to the orchestrator's
context. The sub-agent **roster is pre-declared by the developer**; the model composes the
call graph, never the agent set. `max_agent_calls` is an exact host-enforced ceiling on
sub-agent runs that holds under concurrent fan-out, and the tree's token spend rolls up to
the parent run's usage. A `reveal()` affordance lets the **host** add a pre-provisioned agent
mid-run, which the model learns about through a signature note. The `run_workflow` OTel span
carries the model-written script verbatim. Upstream states it is unstable specifically
because structured sub-agent inputs and **durable workflows** have not settled the call
contract.

The tension worth naming is not "are these good libraries." It is that the second one
introduces an invocation class the platform's records do not cover. ADR-0041 governs a *tool
call* from model-written code. A sub-agent invocation is a **delegation** — it manufactures
authority, it acts on behalf of a subject, and it produces effects under someone's grant.
Every argument in ADR-0041 applies to it with more force, and none of ADR-0041's text
mentions it, because when that record was written the object did not exist here.

## Decision

**Model-written orchestration is governed at two boundaries, not one: per tool call, as
ADR-0041 already requires, and per delegation.** Adoption of either upstream project is
conditional on the requirements below; this record adopts neither.

### Monty sharpens ADR-0041's condition from conditional to structural

Monty's architecture makes hook parity **structurally satisfiable rather than hoped-for.**
The external-function seam is the only exit from the sandbox, and `start()`/`resume()` pauses
*at* that seam — so routing every resume through `invoke_tool` makes the interception point
the runtime's own topology rather than a discipline the integration must maintain. That is a
materially stronger position than "the sandbox is secure," which
[ADR-0041](0041-code-mode-requires-hook-parity.md) correctly refused to accept as sufficient.

Adoption conditions, each conformance-asserted:

- **The external-function table exposed to Monty contains only the governed toolset.** No raw
  host functions. The break fixture: a host-side handler that bypasses `invoke_tool` **must
  fail the suite** — an assertion, not a review note.
- **Monty snapshots are checkpoints.** The credential-free-checkpoint discipline
  ([ADR-0026](0026-delegation-grants-and-per-step-tokens.md)) extends to serialized
  interpreter state verbatim, including the adapter's `CredentialInCheckpointError` class, and
  is conformance-asserted rather than assumed from the fact that the sandbox holds no
  ambient credentials.
- **Monty's resource limits map onto bounded execution**, and the limits are set by the
  harness core, never by workflow code. A bound the sandboxed program can raise is not a
  bound.
- **Wall-clock and timing primitives are unavailable inside the sandbox.** This helps
  determinism and is worth having. It does **not** by itself defeat trigger-conditioned
  payloads, and must not be cited as if it did.

### DynamicWorkflow generalizes ADR-0041 to delegations

**Every sub-agent invocation crossing the Monty→host boundary is a delegation and binds
host-side to the governed delegation path — never to a raw framework `Agent.run`.**

- **Act-chain narrowing.** The sub-agent runs under **its own registered definition and
  ceiling, scoped at or below its parent, never above**, on the same correlation ID. This is
  the RFC 8693 act chain and the founding inter-agent mandate — mutual authentication, scope
  limited to the approved task, traceable to the originating agent — applied to an
  orchestration tree.
- **The roster is the registry.** Only registered, ceiling-bound definitions may appear in a
  `DynamicWorkflow` roster. The model's freedom is the call graph; the agent set is not
  negotiable. Conformance: an unregistered roster entry **refuses at workflow construction**,
  fail-closed.
- **`reveal()` is disclosure economics for agents** — [ADR-0040](0040-deferred-tool-disclosure.md)'s
  doctrine applied to a new object. Host-controlled, registration a precondition, each reveal
  an audited event. It changes what the model **knows about**, never what exists or what is
  permitted, which is exactly the property that made deferred tool disclosure a pure
  optimization.
- **`max_agent_calls` is a host-enforced execution bound**, on the standing posture that a
  bound is a bound. Tree-level usage roll-up onto the parent run serves per-workload cost
  attribution rather than merely reporting.
- **The model-written script is a first-class audit artifact.** The run record carries **the
  program that caused the delegations**, not merely their effects — the `run_workflow` span's
  script lands in the audit trail. Principle IX: an orchestration whose effects are recorded
  and whose cause is not is an orchestration nobody can reconstruct.
- **Voting and adversarial-review patterns inside workflows are judge-class verdicts.** They
  may gate steps and **never** satisfy an approval policy assigns to a human, and audit
  distinguishes the two ([ADR-0043](0043-judge-screened-precedent-reuse.md)).
- **Data minimization is a mitigant, not a control.** Intermediate sub-agent outputs never
  enter the orchestrator's context; only the final value returns. That structurally reduces
  the [ADR-0038](0038-integration-uplift-workflows.md) exfiltration surface and **does not
  substitute for its must-deny evaluations.**

### Maturity gate: track, do not build on

Both projects are **watched, not adopted.** Watch signals, stated so a future reader can
check them rather than re-derive them:

- **Monty** — the API stabilizes past `0.0.x`; classes and `match` land; `CodeModeToolset`
  ships in stable Pydantic AI; and ideally a third-party security review of the interpreter,
  because the moment the platform relies on it, Monty's isolation claim becomes load-bearing
  for governance rather than merely for correctness.
- **DynamicWorkflow** — the import path loses its `experimental` segment; the call contract
  settles; and the **durable-workflows extension lands.** That last one matters most here:
  workflow state entering checkpoints invokes the credential-free-checkpoint condition above,
  and it is the piece upstream itself names as unsettled.

Adoption of either lands with the deferred-disclosure and code-mode roadmap work, gated on
the conformance conditions in this record.

## Consequences

ADR-0041's gate becomes checkable rather than aspirational. Its condition — demonstrate that
every tool call from sandboxed code round-trips the pipeline — was a requirement without a
mechanism, and an architecture where the sandbox's only exit *is* the interception point turns
the demonstration into a conformance suite rather than an argument. That is a real
improvement in the platform's position on its own hardest efficiency question.

Extending the parity requirement to delegations forecloses a gap that would otherwise have
opened quietly. Model-written orchestration is exactly the shape where a framework's
convenience path — call the framework's agent directly, it is right there — produces
ungoverned authority manufacture at scale, and it would look like a working feature. Writing
the requirement down before the capability arrives means the integration is measured against
it rather than retrofitted to it.

The record also settles something structural about where model freedom belongs. The roster is
fixed and the call graph is free, which is the same division the platform already draws
between a definition's ceiling and a run's requested scope: the *set* of permitted things is
authored and reviewable, and the *composition* is where a model may be creative. A design
that let a model name its own sub-agents would be a definition writing its own ceiling.

The costs are not small. Governing delegations per-invocation means authority manufacture on
a path that upstream designed for speed, and the act-chain requirement means every sub-agent
needs a registered definition — so an orchestration of five specialists is five registrations
and five ceilings authored before the workflow can run at all. That is friction exactly where
the upstream value proposition is fluency, and it will feel like the platform fighting the
tool. It is the same trade ADR-0041 already made and should be expected to feel the same way.

Carrying the model-written script into the audit trail has a cost worth stating: the script is
model output, of unbounded length, entering an append-only record. Whether it is stored whole,
hashed with the text held elsewhere, or bounded with a documented truncation rule is
unresolved here and is a real design question — the same question the trail already answers
differently for turn content and for tool arguments.

And the honest limit on data minimization: intermediate outputs not entering the
orchestrator's context is a genuine structural mitigant, but the sub-agents themselves read
whatever their tasks require, and an exfiltration path through a sub-agent's own tool calls is
untouched by it. The must-deny evaluations remain the control; this is a narrowing of the
surface, not a closing of it.

## Notes

**Status is Proposed, and this record adopts nothing.** No dependency is added, no code is
written, and both upstream projects are outside their own stability commitments — Monty's
banner and DynamicWorkflow's `experimental` import path both say so. Upstream facts above are
external observations as of 2026-07-29 and will drift; the watch signals are the durable part.

This record **extends** [ADR-0040](0040-deferred-tool-disclosure.md) and
[ADR-0041](0041-code-mode-requires-hook-parity.md) to a new invocation class. It supersedes
nothing, and neither of those records changes status here.
