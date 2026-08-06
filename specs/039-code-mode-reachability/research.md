# Research: Code mode becomes reachable

**Feature**: 039 | **Date**: 2026-08-05

Measured against merged main, each finding named so it can be re-checked when something moves.
**R3 is the one that changes the feature's shape**: the gap is three layers deep, not two, and
the third was invisible from the spec because the spec described the path correctly and the path
does not exist in production.

## R1 — The tool is registered nowhere, and the ceiling vocabulary is derived from registration

**Measured**: `grep PROGRAM_TOOL_NAME` returns `src/core/sandbox/program_tool.py` and its
`__all__`, and nothing else. `src/surfaces/toolset.py` registers the fixture tools
(`echo`, `plan`, `apply`) and then whatever the packs declare; `PLATFORM_HANDLERS` in
`src/surfaces/handlers.py` binds no handler for it.

**Consequence, which is sharper than "the tool is missing"**: `toolset.py` records that the
ceiling vocabulary is *derived from what actually registered* — *"a pack that loads is a pack
whose tools a ceiling may name"*. So a definition whose ceiling names the program tool does not
get a permission it cannot use; it gets **`unknown_ceiling_entry` at run start**, and the error
names the ceiling rather than the missing registration. An operator would go and look at the
trust fabric, which is fine, and at the pack manifests, which is fine, and not at a surface
module that never registered it.

**Decision**: registration is a platform-tool registration on 038's precedent
(`author_file`, `read_subject`, `open_proposal`), not a pack tool. Code mode is not product
knowledge — a program that calls Terraform tools and one that calls Vault tools are the same act.

## R2 — The runtime is installed in CI and absent where dispatched work runs

**Measured**:

- `.github/workflows/ci.yml:34` — `uv sync --frozen --extra adapters --extra surfaces --extra sandbox`
- `infra/jobs/agent-run.nomad.hcl:185` — `uv run --extra adapters --extra surfaces python -m surfaces.dispatch.entrypoint`

So 036's parity rows are green because they run **where the runtime exists**, and the allocation
that runs dispatched work does not carry it. `pyproject.toml` keeps `sandbox = ["pydantic-monty==0.0.19"]`
optional deliberately, *"so the base install never grows a Rust interpreter for a capability most
runs do not use"*.

**Decision**: the allocation installs the extra. **The cost is stated rather than absorbed**:
every dispatched run then carries a Rust interpreter it mostly will not use, and the install is
on the allocation's critical path. Principle VI is not violated — a library behind an extra is
not an operated component, so no named-trigger ADR is owed — but "optional" stops meaning
"absent from the thing that runs" and starts meaning "absent from the base install", which is a
weaker claim than the one the pyproject comment makes today.

**Alternative considered and rejected**: a separate jobspec that installs the extra, dispatched
only for definitions that use code mode. It halves the cost and doubles the substrate — two run
allocations whose postures must stay identical, which is the fragmentation Principle VII
forecloses and 038's two-tier experience says drifts.

## R3 — The model cannot emit a program, and this is the finding that reshapes the feature

**The spec's FR-001 asks for submission "through the same path every other capability is reached
by." Measured, that path cannot carry a program.**

There are two ways a tool is reached in this platform, and neither works:

**(a) The dispatched invoke loop passes one fixed argument shape to every tool.**
`entrypoint.py:68` — `_PROBE_ARGUMENTS = {"path": "conformance/probe", "cas": 0}` — and its
docstring names itself: *"A fixture affordance, and it always was."* Every tool the loop invokes
gets those arguments. A program needs a `program` argument and would receive a path and a CAS
index.

**(b) The model names a tool; it does not call one.** `src/adapters/model_chooser.py` builds the
agent with `output_type=str` and **no toolsets at all**, under a system prompt reading *"Answer
with EXACTLY ONE tool name from the permitted list and nothing else — no punctuation, no
explanation, no quotes."* The entrypoint then invokes the named tool with the probe arguments
above.

**So `GovernedToolset` — the adapter mapping that routes a model's tool calls through
`invoke_tool` — has no production caller.** Its own module docstring describes the property
correctly; the chooser's comment concedes the shape in passing: *"were this agent ever given a
toolset, no capability downstream could produce an ungoverned execution."* **Were.**

**Why this matters more than it looks.** A program is not a tool name. It is an *argument* —
model-authored text of arbitrary length, submitted as the body of one call. A model that can only
answer with a bare tool name has no channel to send one. Registering the tool and installing the
runtime would produce a capability that is reachable in principle and unreachable in fact, which
is the same defect this feature exists to close, one layer down.

**Decision**: the feature includes **giving the model a channel to emit a program** — the agent
gains a toolset so the model issues a real tool call with arguments, which is what
`GovernedToolset` was built for and has never been given. That is the smallest change that makes
FR-001 true rather than nearly-true.

**This is why the spec deliberately named no module.** FR-001 says *"the same path every other
capability is reached by"* and does not say which path that is — so measurement was free to
discover that the path is a name-shaped channel, and the requirement still reads correctly. Had
the spec named the registry, the plan would have satisfied it and shipped an unreachable
capability for the second time.

**Alternative considered**: extend the chooser's string protocol to carry a program — e.g. a tool
name followed by a payload. Rejected: it invents a second calling convention alongside the
framework's own, and it puts model-authored program text through a parser this platform would own.

**Superseded by R7. The rejection above was a false dichotomy** — it weighed a toolset against a
hand-rolled parser and never considered **structured output**, which is the framework's own
mechanism and was reachable through a parameter this code already passes. See R7.

## R4 — The bound is real arithmetic against a budget nothing has ever tested

**Measured**: `core/bounds.py` — `BoundsTracker.record_progress` increments `steps_taken`, and
`invoke_tool` calls `run.bounds.check()` before executing and `record_progress` after an allowed
call. So the arithmetic 036 recorded is not a convention: **the submission is one step and each
inner call is another**, because every one of them goes through `invoke_tool`.

**And the three failure modes are already distinguished at the seam** (`seam.py`): a policy deny
becomes an in-sandbox failure the program can see and route around; an exhausted bound
propagates and terminates the run; a superseded lease propagates for the same reason. The
docstring says getting that backwards *"is the most plausible way this feature ships a hole."*

**What has never happened**: a program running against a real budget. The distinction exists in
code and has never been exercised by a program that actually ran out of room.

**Decision**: US4's rows drive a program to budget exhaustion and assert the run ends, rather
than asserting the arithmetic. **Measuring rather than asserting** is the point — SC-005 says so
in its own text, and an arithmetic assertion would pass against an implementation where the
bound never fires.

## R5 — The 038 row that must be inverted, not deleted

**Measured**: `tests/conformance/authoring/test_producing.py` asserts
`PROGRAM_TOOL_NAME not in toolset.py`, with the message *"run_program is now registered; W3's
caveat is stale and this row should be promoted to drive the production path rather than the
seam."*

**Decision**: that row is **rewritten to drive the production path**, which is what its own
failure message asks for. FR-013 and SC-007 forbid deletion.

**Why the spec made this a requirement rather than leaving it to implementation**: the obvious
move when a guard fails is to delete the guard. The property it watches — *code mode's
reachability is a deliberate state, not an accident* — is exactly the property whose absence
created this feature. 036's parity rows pass today while the capability they describe cannot be
reached; a row that stops watching is how that happens again.

## R6 — What this feature must not decide, and the one thing registration forces

**Measured**: 036's Deferred section names *"choosing which definitions use code mode by policy —
whether code mode is a per-definition setting, a per-pack property, or a platform default is
configuration design."*

**Decision**: no shipped definition gains the program tool in its ceiling. The dev estate gets
**one** definition carrying it, existing so the capability can be demonstrated end to end — which
is what SC-001 requires — and that is a fixture rather than a policy.

**The line, stated because it is thin**: registration forces *that a ceiling can name it*. It
does not force *which ceilings do*. A demonstration definition answers the first; it is not an
answer to the second, and the plan should not let it become one by accident.

---

*R7–R9 came from the first analyze pass. R7 corrects R3's decision; R8 is a defect 036 shipped
that only a reachable code mode can reach.*

## R7 — The narrow path R3 missed: the model returns arguments, not a tool call

**R3 was right about the gap and wrong about the fix.** The gap is real and worth restating
precisely, because the corrected fix follows from stating it exactly:

> **The platform, not the model, supplies every tool's arguments.**

Measured: `resolve_step_tool(run, task=…, permitted=…, chooser=…, arguments=_PROBE_ARGUMENTS,
already_chosen=…)`. The model returns a **name**; the entrypoint invokes it with a fixed argument
dict. A program is an argument, so the model has no channel — that much R3 had right.

**What R3 compared, and what it omitted.** It weighed *"give the agent a toolset"* against
*"extend the string protocol with a parser this platform would own"*, and correctly refused the
second. It never considered the third: **structured output**. `build_governed_agent` already takes
`output_type`, and every caller passes `str`. A Pydantic model there is the framework's own
mechanism — no parser, no invented convention.

**And the toolset path costs far more than R3 accounted for.** Measured, giving the agent a
toolset moves execution inside `agent.run_sync`, which bypasses **four** properties 031 built:

| Property | Where it lives | Lost under a toolset |
| --- | --- | --- |
| bounded retry on a bad answer | `resolve_step_tool` | the model calls directly; nothing bounds it |
| `already_chosen` re-observation honesty | `resolve_step_tool`, FR-008 | *"re-asking could return a different tool from the one whose bracket is open"* |
| `TOOL_CHOSEN` recorded per step | the entrypoint | the call happens inside the agent loop |
| `choose() -> str` as the step's contract | `model_chooser` | meaningless — the tool already ran |

**Decision**: the chooser's `output_type` becomes a structured choice — a tool name **and its
arguments** — and `resolve_step_tool` carries those arguments through to the governed invoke in
place of `_PROBE_ARGUMENTS`. Every property in the table survives untouched, because the shape of
the step is unchanged: the model still answers, the platform still invokes, the bracket still
wraps it.

**What this deliberately does not do**, recorded so it is not mistaken for an oversight:
`GovernedToolset` **still has no production caller**. That is a real gap — a mapping built in 004
whose central claim is unexercised outside a test — and it is **not this feature's to close**.
Closing it means deciding whether the model calls tools directly, which is a change to what a
governed step *is*, and it deserves its own record rather than arriving as a side effect of
making code mode reachable.

## R8 — A looping program silently loses an intent record

**Measured**, three facts that only matter together:

1. `core/hooks/engine.py:450` — the idempotency key is `f"{run_id}:{run.step_index}:{tool_name}"`.
2. **The seam never advances `step_index`** — grep returns nothing in `seam.py`, `program_tool.py`
   or `state.py`. Every inner call a program makes carries the submission's step index.
3. `core/durability/schema.sql:99` — `PRIMARY KEY (run_id, idempotency_key)`, and
   `postgres.py:246` records intents with **`ON CONFLICT (run_id, idempotency_key) DO NOTHING`**.

**So a program that calls the same non-repeatable tool twice produces one intent record for two
effects.** `bracket_call` calls `call()` unconditionally after recording intent, so the second
effect happens; the insert is a silent no-op; and `resolve_open_intents` later re-observes **once**
for **two** effects.

That is the shape the entire non-repeatable/observer machinery exists to prevent, and the
constitution names **duplicate-side-effect rejection** as an in-force durability gate.

**Dormant until now, and detonating on the first realistic program.** Nothing has ever run a
program, and a loop is the whole point of code mode — *"N inner calls cost N+1 steps"* presumes
one. 036 shipped this; only reachability reaches it.

**Decision**: `GovernedRun` carries a **call ordinal scoped to the submission** — the seam sets it
on entry and **clears it on exit** — and `_idempotency_key` folds it in **only when it is
non-zero**:

```
ordinal == 0  ->  f"{run_id}:{step_index}:{tool_name}"        # byte-identical to today
ordinal  > 0  ->  f"{run_id}:{step_index}:{tool_name}:{ordinal}"
```

**Existing keys are unchanged**, which is not a nicety: altering every key would invalidate 014's
durability rows and break resume for any run in flight. The new suffix appears only where a
situation that could not previously arise now does.

**Alternative rejected**: advancing `run.step_index` from inside the seam. It is the *run's* step
counter, set by the entrypoint's loop and read by the checkpoint; mutating it from inside a tool
would corrupt the run's own accounting to fix the key's.

**Scoped to the submission rather than to the run, and the first draft of this decision got that
wrong** — it said "the seam increments it per inner call" and said nothing about where it stops.
`run.step_index` is reset per step by the entrypoint; nothing would have reset an ordinal. So a
run whose step 0 ran a three-call program would carry `call_ordinal == 3` into step 1, and the
next **direct** call would key `run:1:tool:3` — destroying the byte-identical guarantee **only
after a program runs**, which is to say only in the case this feature exists to create.

**Set on entry, cleared on exit**, so outside a program the ordinal is always 0. That also makes
resume coherent: a re-run program re-issues ordinals 1..N and they line up with the intents
recorded the first time, which a run-scoped counter could never do.

## R9 — Three smaller things the plan left to be discovered

**The runtime's injection point.** `core` must not import an adapter (Principle I), and
`SandboxRuntime` is a Protocol. The concrete Monty binding lives in
`src/adapters/pydantic_ai/sandbox_runtime.py`, and the handler lives in `src/surfaces/handlers.py`
— a **surface**, which may import an adapter. Stated rather than discovered, because the obvious
wrong move is to reach for it from `core/sandbox/`.

**What the fixture chooser can emit, and where it lives.** Measured: `build_chooser` in
`src/adapters/model_chooser.py` returns `RecordedChooser(parse_recording(recording))` for the
fixture provider — **not** a test harness module. Every dispatched conformance row goes through
it, so **widening the answer changes what a recording must contain**, and `parse_recording` is
part of this feature whether or not anyone planned it. If a recording can carry only a bare name,
the enclave row proves the allocation carries the runtime and **not** that a model can reach it —
a weaker claim than SC-001 makes, wearing the stronger one's clothes.

**A stale comment nearly produced a finding that does not exist.** `_PROBE_ARGUMENTS`' docstring
says *"a handler exception does not make `outcome.allowed` false — `allowed` is `decision ==
"allow" and not evidential_gap`, both of which hold when the body throws."* **Measured, that is no
longer true**: `engine.py:374` returns `decision="deny", reason_code="tool_error"` when
`execution_error_code is not None`. So a model supplying arguments that make a handler raise gets
an honest denial, and the risk the comment describes is gone.

The comment is in the code this feature modifies, which is the worst place for a stale one — it
is read by whoever is changing that path, at the moment they are deciding what is safe.

**Identical governance, and what "identical" means.** A direct call from the step loop is invoked
with arguments the **platform** chose; an inner call carries arguments the **program** wrote. The
*pipeline* is identical — same entry, same hooks, same bracket — and the *provenance of the
arguments* is not. K6 asserts the first; saying so keeps it from reading as the second.

---

*R10–R12 came from the third analyze pass, scoped to R7's and R8's fixes. Both CRITICALs are
about what those fixes **collide with** rather than about the fixes themselves.*

## R10 — A program can submit a program, and nobody has decided whether it may

**Measured**: the seam routes *every* request to `invoke_tool` — its own docstring says *"no
blocklist, no allowlist, and no special case: `open`, `eval`, `__import__` and a name the model
invented are all requests, and the registry decides."* That is the property that makes the
governance claim airtight, and it has a consequence nobody has faced: **if a definition's ceiling
names the program tool, a program running under it can call `run_program`.**

The demonstration definition this feature authors does exactly that, so nesting is reachable the
moment the feature ships.

**Two problems, and the second is worse than the first.** Recursion is unbounded except by the
step budget — a program that submits a program that submits a program consumes steps and nothing
else stops it. And the submission-scoped ordinal (R8) breaks: the inner submission sets it on
entry and **clears it on exit**, zeroing the outer program's counter mid-flight, so the outer's
remaining calls re-key from 1 and collide with intents already written.

**Decision**: **a program tool call from inside a program is refused**, with a stated reason, at
the seam. One check, and it names what it refuses.

**Not because recursion is obviously wrong** — it is a coherent thing to want, and a bounded form
might be useful. It is refused because **nobody has decided it**. It is absent from 036's Deferred
list, which means it is currently permitted by *omission* rather than by argument, and shipping
reachability would turn an unexamined omission into a live capability. A refusal is reversible by
a later record; an unbounded recursion that shipped is not.

**Alternative considered**: a depth limit. Rejected for this feature — a limit is a decision about
how much nesting is useful, and there is no evidence about that yet. Refusing states the position
honestly; a depth of 1 would pretend to an answer.

## R11 — Widening the recording format would break four suites that already exist

**Measured**: `parse_recording` is `"plan,apply,-"` → `["plan", "apply", "-"]` — comma-separated
bare names. It is consumed on the **dispatched** path via `build_chooser`, and four conformance
suites already supply recordings through a `recording(*answers)` helper:
`conformance/choice/harness.py`, `conformance/choice/test_a_model_chooses.py`,
`conformance/durability/test_model_driven_resume.py`, `conformance/reports/test_the_run_observes.py`.

**Decision**: the widened format **accepts a bare name as a choice with no arguments**, so every
existing recording parses exactly as it does today and all four suites are untouched.

**The same discipline K13a applies to keys.** A format change that requires every existing caller
to move is a change with a blast radius nobody measured — and here the callers are the rows that
prove model-driven runs work at all. A row asserts the old form still parses, so the compatibility
is a property rather than an intention.

## R12 — What a resumed program can and cannot promise

**The honest limit behind K13b.** A program interrupted mid-flight leaves open intents at
sub-step granularity, and resume re-runs the program **from the start** — there is no mid-program
checkpoint. So the re-issued ordinals line up with the recorded intents **only while the re-run
issues the same calls in the same order**.

**A program that branches on a tool result may diverge.** If the first attempt called A then B,
and the re-run calls A then C, then B's effect happened and the resumed program never learns it —
the intent for B is resolved by re-observation, which establishes *what happened*, and the
program's own control flow has moved on regardless.

**Stated rather than solved.** Solving it means checkpointing inside a program, which is a
different feature and a much larger one; K13b therefore asserts alignment for a **deterministic**
program and the divergence case is recorded as a limit. A row that claimed alignment
unconditionally would be asserting something the design cannot deliver.

