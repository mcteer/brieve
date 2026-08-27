# ADR-0065: Code mode is decided against

- **Status**: Proposed
- **Date**: 2026-08-06
- **Supersedes**: ADR-0041
- **Relates to**: [ADR-0040](0040-deferred-tool-disclosure.md), [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0064](0064-version-control-is-a-platform-capability.md)
- **Requirements**: R5, R11, R12

## Context

036 built code mode: a model writes a program, a suspendable interpreter runs it, and every
call the program makes suspends and routes through `invoke_tool`. ADR-0041 gated that on
verified per-call hook parity, and the gate was satisfied at the seam. 039 was specified to
close the remaining gap — the capability was registered nowhere and the run allocation never
installed the runtime, so no definition could reach it in the running platform.

**Two things surfaced during 039's planning that together end the case for it.**

**The runtime is upstream pre-release with no timeline.** `pydantic-monty==0.0.19` is early
software. It is fine to depend on where the seam's conformance rows run; it is not something
to install into every dispatched allocation, which is what reachability requires. 039's own
Complexity Tracking already carried that cost as a stated tradeoff — *every dispatched
allocation carries a Rust interpreter it mostly will not use* — and the tradeoff only pays if
the interpreter is dependable.

**And code mode was being conflated with the platform writing code.** It is not that. Code
mode changes how a model *invokes tools*: a loop over twenty resources becomes a few lines
instead of twenty round trips, and fewer tool schemas need to sit in the prompt. Writing code
as a **work product** — a Terraform template, a Python script, a patch — is 038's subject
(`author_file`, `open_proposal`), and it shares nothing with this beyond the word.

Once that conflation is undone, code mode is an efficiency optimization for tool invocation,
carrying a pre-release runtime, for a platform where **nothing has ever run a program outside
a test**.

## Decision

**Code mode is not a capability this platform offers.** `run_program` is not registered, the
`sandbox` extra is not installed into any allocation, and no definition's ceiling names it.

**036's code stays in the tree, dormant and marked.** `core/sandbox/` (the seam, the program
tool, the ledger), `src/adapters/pydantic_ai/sandbox_runtime.py`, `SandboxUnavailableError`,
the `PROGRAM_SUBMITTED` audit member and the five conformance suites remain. Removal is its
own feature: `PROGRAM_SUBMITTED` is in the audit schema, which Principle V seals, and a
capability decided against is not the same as one deleted in a hurry.

**The guard 038 wrote stays, and its message is corrected.**
`tests/conformance/authoring/test_producing.py` asserts `PROGRAM_TOOL_NAME not in
toolset.py`. That assertion now records a decision rather than a gap — but its failure message
reads *"run_program is now registered; W3's caveat is stale and this row should be promoted to
drive the production path rather than the seam."* That message would invite someone to reverse
this ADR by reading a test, so it is rewritten to say code mode was decided against and to
point here.

**ADR-0041's reasoning survives its subject.** *"Sandbox safety and preserved governance are
different properties"* is not about code mode; it is about the general temptation to accept an
isolation boundary as a governance argument. It applies to any future execution substrate, and
is the reason this ADR supersedes 0041 rather than deleting it.

## Consequences

**What this costs.** The efficiency case was real: a model that must emit one structured call
per action spends round trips and context that a program would not. That cost is now paid
indefinitely. ADR-0040's deferred disclosure addresses the context half directly and needs no
sandbox; the round-trip half is simply accepted.

**What it does not cost.** No governance property depended on code mode. `invoke_tool` remains
the sole execution entry, and it has one fewer caller.

**A containerized workload is not an argument against this ADR being needed.** Agents run in
isolated containers, and that boundary sits between the agent and the infrastructure. It says
nothing about a program reaching the filesystem, the network, or the environment's credentials
*without passing the tool layer* — which is inside the same container. If code mode is ever
revisited, the suspendable interpreter is what makes governance structural, and running model
code with plain `exec()` because the container looks secure is precisely the inference ADR-0041
was written to refuse.

**What replaces 039.** Its analysis outlived its subject. The platform's real gap is that
`author_file`, `read_subject` and `open_proposal` are registered nowhere either — 038 shipped
the same reachability shape 036 did — and, separately, that a model cannot supply a tool's
arguments at all: `_PROBE_ARGUMENTS` is a hardcoded constant passed for every tool a model
names. Both become their own features.
