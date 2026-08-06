# Quickstart: Code mode becomes reachable

**Feature**: 039 | **Date**: 2026-08-05

How to prove each layer, and — for the three rows most likely to be quietly wrong — how to prove
they can **fail**. Every scenario has a row behind it; see [contracts/](contracts/).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra sandbox` — **the `sandbox` extra is
  required**, and Scenario B exists to check what happens without it.
- Scenarios A–D run hermetically. **Scenario E needs the enclave** (`make dev-up`) and is the
  only one that proves the thing the feature is for.

**Run the rows where they block merges.** `make check` does **not** collect
`tests/conformance/`. A green `make check` says nothing about any row below — 038's
implementation had three hermetic rows red for an hour while `make check` stayed green.

## Scenario A — A definition can enter code mode

```sh
uv run --extra adapters --extra surfaces --extra sandbox \
  pytest tests/conformance/adapter -q -k reachable
```

Expected: K1–K3 pass. A program submitted through the **registry** runs; a definition whose
ceiling omits the tool is refused `authority_insufficient`; the program is recoverable from the
trail as the cause of the calls that followed.

**Worth reading rather than only running: K1.** It resolves the tool *from the registry* and
goes through `invoke_tool`. A row that called the handler directly would assert what 036 already
asserts — and would have passed every day of the month this capability was unreachable.

## Scenario B — Where the runtime is absent, the refusal is honest

```sh
uv run --extra adapters --extra surfaces \
  pytest tests/conformance/adapter -q -k unavailable    # note: NO --extra sandbox
```

Expected: K4–K5 pass. The refusal names the absent capability. It is **not** an import error
surfacing from three frames down, and **not** a partial success.

**Prove it can fail.** Re-run this with `--extra sandbox` present: K4 must **fail**, because a
row that passes whether or not the runtime is installed is asserting nothing about its absence.

## Scenario C — Still governed

```sh
uv run --extra adapters --extra surfaces --extra sandbox \
  pytest tests/conformance/adapter -q -k "parity or governed"
```

Expected: 036's parity rows **and** K6/K6a pass together. A program that calls a permitted tool,
a denied tool, and a name that does not exist produces the same records those calls issued
directly would — and the invented name refuses as *not registered*, through the registry rather
than through any blocklist.

**K6a is the one to read.** It asserts the model-facing toolset routes through `GovernedToolset`
and that the toolset is built from the run's **effective scope**. That second clause is the bound
on this change's blast radius: giving the agent a toolset affects every model-driven run, and
building it from effective scope means a run whose ceiling omits the program tool sees nothing new.

## Scenario D — The budget

```sh
uv run --extra adapters --extra surfaces --extra sandbox \
  pytest tests/conformance/adapter -q -k budget
```

Expected: K8–K10 pass. A program making N calls consumes N+1 steps, **measured**; a program that
exhausts the budget **ends the run**; and three outcomes stay distinguishable — finished, denied,
stopped by the bound.

**Prove the bound is a bound.** Change the program in K9 to catch the failure its call raises and
continue. The run must still end. If the program can catch it and carry on, the exhausted-bound
path has been converted into a program-visible failure — which the seam's docstring names as the
most plausible way code mode ships a hole.

**And note what K8 does not do.** It counts steps rather than asserting the arithmetic, because
an assertion that N calls cost N+1 passes against an implementation where the bound never fires.

## Scenario E — In the environment where dispatched work actually happens

```sh
make dev-up
# then dispatch a run whose definition carries the program tool, with a program to submit
```

Expected: the program runs **in the allocation**. The trail carries `PROGRAM_SUBMITTED` with the
program verbatim, and each inner call as its own governed step, under one correlation ID.

**This is the row the whole feature exists for (K7).** Every other row here could pass while the
capability remained unreachable in production — which is exactly the state 036 left, with green
parity rows, for a month. `verify-the-production-caller` and `run-the-served-process` are the
same lesson from two directions, and this scenario is where both are settled.

**Check the install, not only the run.** Confirm the allocation's command carries `--extra
sandbox`. Without it the run would refuse honestly (Scenario B), which is correct behaviour and
is **not** this feature being finished.

## Scenario F — The guard was inverted, not deleted

```sh
uv run --extra adapters --extra surfaces --extra sandbox \
  pytest tests/conformance/authoring -q -k producing
```

Expected: the 038 row that asserted the program tool is registered **nowhere** now asserts it is
**reachable** — same row, opposite claim (K11).

**Check it exists rather than that it passes.** A deleted guard also produces a green suite. The
property being watched is that code mode's reachability is a **deliberate state** rather than an
accident, and this feature exists because that property stopped being watched.
