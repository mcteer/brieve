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
framework's own, and it puts model-authored program text through a parser this platform would own
and the framework already has. `GovernedToolset` exists precisely so the framework's tool-call
shape is the one that arrives.

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
