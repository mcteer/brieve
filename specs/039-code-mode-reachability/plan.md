# Implementation Plan: Code mode becomes reachable

**Branch**: `039-code-mode-reachability` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/039-code-mode-reachability/spec.md`

## Summary

036 satisfied ADR-0041's gate and shipped a capability nobody can reach. This closes that, and
measurement found the gap is **three layers deep rather than two**.

The two the spec anticipated: the program tool is **registered nowhere**, so a ceiling naming it
refuses `unknown_ceiling_entry`; and the run allocation **never installs the runtime**, while CI
does — which is why 036's rows are green.

The third, and the reason this plan is not a two-line change: **the model has no channel to emit
a program.** The chooser builds its agent with `output_type=str` and **no toolsets**, under a
prompt demanding *"EXACTLY ONE tool name … no punctuation, no explanation"*; the entrypoint then
invokes that name with one fixed argument shape, `{"path": ..., "cas": 0}`, which its own
docstring calls *"a fixture affordance."* A program is not a name — it is model-authored text
submitted as an argument. **`GovernedToolset`, the mapping built to route a model's tool calls
through `invoke_tool`, has no production caller at all.**

So the work is: **register** the tool, **install** the runtime where dispatched work runs, and
**give the model a toolset** so it issues a real tool call with arguments. Then prove it —
against a real budget, because the arithmetic has never met one.

## Technical Context

**Language/Version**: Python 3.12 (matches repository)

**Primary Dependencies**: **none new.** `pydantic-monty==0.0.19` already exists behind the
`sandbox` extra; this feature installs that extra where dispatched work runs rather than adding
a dependency. `GovernedToolset` and the seam are built.

**Storage**: none new. The sandbox ledger is per-run and in-memory; programs are recorded in the
existing trail.

**Testing**: pytest — new conformance rows in `tests/conformance/adapter/` beside 036's, which
own the seam's parity; the reachability rows are new and belong with them rather than in a
fourth location. One dispatched row in the enclave lane, because SC-001 says *"in the environment
where dispatched work actually happens"* and no hermetic row can assert that.

**Target Platform**: unchanged. The change is what the run allocation installs, not where it runs.

**Project Type**: single project. New: registration in `src/surfaces/`, a toolset on the chooser's
agent, one demonstration definition in the dev estate.

**Performance Goals**: **the cost is the interpreter in the install**, not runtime latency. Every
dispatched run will carry a Rust interpreter it mostly will not use, on the allocation's critical
path. Stated rather than absorbed (R2).

**Constraints**: `invoke_tool` stays the sole execution entry and code mode must not become a
second way to reach a tool — ADR-0041's gate is satisfied at the seam and must survive being made
reachable. An environment without the runtime must keep refusing with a stated reason
(`SandboxUnavailableError`), never an import failure. No shipped definition gains the capability
(FR-012). The 038 row asserting unreachability is **inverted, never deleted** (FR-013).

**Scale/Scope**: one tool, one extra, one toolset, one demonstration definition. The smallest
change that makes an existing proven property true of the running platform.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Nothing is built. The seam, the ledger, the audit member, the runtime binding and the toolset mapping all exist; this wires them. The one genuinely new artefact is a demonstration definition, which is configuration. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The program tool is an ordinary registered tool; every call a program makes already round-trips `invoke_tool` by construction at the seam. **Giving the chooser's agent a toolset is the first production use of `GovernedToolset`** — the mapping whose whole purpose is that the framework's own execution path is never taken. That strengthens Principle II rather than straining it: today the model names a tool and the entrypoint invokes it, which works, and leaves the adapter's governed-toolset guarantee unexercised in production. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | `SandboxUnavailableError` exists precisely so a missing runtime refuses with a stated reason rather than surfacing an ImportError three frames down, and an environment without the extra must keep doing exactly that (FR-007). The seam's three-way distinction — policy deny visible to the program, exhausted bound terminating the run, superseded lease propagating — is asserted against a real budget for the first time (R4). |
| IV — Zero Standing Credentials; Authority Per Task | **N/A** | No credential path changes. A program runs under the run's existing authority and reaches tools through the ceiling that already bounds it. |
| V — Sealed Core, Versioned Seams | **Pass** | **No sealed-core change.** No audit member is added — `PROGRAM_SUBMITTED` exists. The registry gains an entry through the ordinary `register` path; the hook engine, identity flows, durability and adapters are untouched in substance. The adapter gains a *caller*, not a new mapping. |
| VI — Lean by Default | **Pass, with a cost stated** | The runtime stays a library behind an optional dependency, so no named-trigger ADR is owed. But installing it where dispatched work runs means **every** dispatched run carries a Rust interpreter it mostly will not use. "Optional" stops meaning *absent from the thing that runs* and starts meaning *absent from the base install* — a weaker claim than `pyproject.toml`'s comment makes today, and the comment is amended to say so. |
| VII — Anti-Fragmentation | **Pass** | One run allocation, one posture. The rejected alternative — a second jobspec installing the extra only for code-mode runs — halves the cost and doubles the substrate, which is the fragmentation this principle forecloses and which 038's two-jobspec experience says drifts (R2). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No model is promoted and no cell changes. The runtime is pinned exact (`==0.0.19`) and stays pinned; `test_sandbox_dependency_identity.py` already asserts the distribution's identity, which is ADR-0004's discipline applied to a runtime. |
| IX — Evidence Over Claims | **Pass** | The program is recorded as the cause of the calls that follow it (`PROGRAM_SUBMITTED`, verbatim on `TURN_RECORDED`'s argued precedent). What changes is that the trail begins carrying programs that ran **in production** rather than only in tests. |
| X — The Decision Record Governs | **Pass** | **No new ADR and no amendment.** ADR-0041's gate is satisfied and stays satisfied. **ADR-0054 stays Proposed** — its delegation half still has no substrate, and this feature does not give it one. 036's Deferred items stay deferred (FR-012). |

**Gate result**: **PASS — proceed to Phase 0.** One obligation travels with the feature: the
`pyproject.toml` comment about what "optional" buys must be amended in the same change, because
after this it is describing a posture the platform no longer has.

## Project Structure

### Documentation (this feature)

```text
specs/039-code-mode-reachability/
├── plan.md              # This file
├── research.md          # Phase 0 — six findings; R3 reshaped the feature
├── data-model.md        # Phase 1 — what a program is, and what it costs
├── quickstart.md        # Phase 1 — how to prove reachability, and that it can refuse
├── contracts/
│   └── conformance-code-mode-reachable.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/surfaces/
├── handlers.py               # + the program handler, bound in PLATFORM_HANDLERS. Needs the
│                             #   run and a runtime, so it is constructed per run like 038's
│                             #   authoring handlers rather than being a module-level callable
└── toolset.py                # + registration. The registry is the opt-in switch; the CEILING
                              #   decides. A definition whose ceiling omits it has no code mode
                              #   even though the registry knows the name

src/adapters/
└── model_chooser.py          # THE THIRD LAYER (R3). The agent gains a toolset, so the model
                              #   issues a real tool call with ARGUMENTS instead of answering
                              #   with a bare tool name. First production caller of
                              #   `GovernedToolset` — the mapping exists and nothing used it

infra/jobs/agent-run.nomad.hcl  # + `--extra sandbox`. The allocation where dispatched work
                              #   runs carries the runtime, or FR-003 is half-closed
pyproject.toml                # the `sandbox` extra's comment amended: "optional" now means
                              #   absent from the BASE install, not absent from the thing that
                              #   runs, and that is a weaker claim than it makes today
infra/environments/dev/variables.tf   # ONE demonstration definition. A fixture, not a policy —
                              #   registration forces that a ceiling CAN name it, never which do
tests/
├── conformance/adapter/      # reachability rows, beside 036's parity rows
└── conformance/authoring/    # the 038 row INVERTED (FR-013) — never deleted
```

**Structure Decision**: the reachability rows live in `tests/conformance/adapter/` **beside
036's**, not in a new directory. 036 owns the seam's parity assertions and this feature owns the
claim that the seam is reachable; splitting them across two locations would let one be read
without the other, which is the exact mistake — parity rows passing while reachability was
absent — that produced this feature.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed; two were sharpened:

- **II** — the design's largest single change is giving the chooser's agent a toolset, and that
  reads as a strain on Principle II until you notice it is the opposite. `GovernedToolset`'s
  whole purpose is that *"the framework's own execution path is never taken"*, and today that
  guarantee is unexercised in production because the model answers with a string. Using it is
  the first time the adapter mapping's central claim is load-bearing outside a test.
- **VI** — the honest reading of "lean" changed rather than the verdict. Nothing operated is
  added; what changes is what every dispatched allocation carries. That is a real cost paid for
  a capability most runs will not use, and `pyproject.toml`'s comment is amended rather than left
  describing the old posture.

**The risk moved into the record rather than resolved**: giving the agent a toolset changes how
**every** model-driven run behaves, not only code-mode runs — the model gains the ability to
issue tool calls where it previously answered with a name. That is a larger blast radius than
"register a tool", and the plan states it here so tasks can bound it: the toolset is populated
from the run's **effective scope**, so a run whose ceiling omits the program tool sees no change
in what it can do.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Every dispatched allocation installs a Rust interpreter** it mostly will not use, against Principle VI's default | FR-003 says a capability reachable in testing and absent in production is the defect this feature closes, and closing half of it does not close it. The allocation that runs dispatched work must carry what code mode needs | **A second jobspec** installing the extra only for code-mode runs halves the cost and doubles the substrate — two allocations whose postures must stay identical, which is the fragmentation Principle VII forecloses and which 038's two-jobspec experience says drifts. **Lazy installation at first use** puts a package install inside a governed step, on the run's critical path, with no bound |
| **The chooser's agent gains a toolset**, changing every model-driven run rather than only code-mode ones | A program is an argument, not a name. The model's only channel today is a bare tool name (R3), and no amount of registration makes a program travel through it | **Extending the string protocol** to carry a program alongside a name invents a second calling convention beside the framework's own, and puts model-authored program text through a parser this platform would own while the framework already has one. `GovernedToolset` exists precisely so the framework's tool-call shape is what arrives |

Neither is a new operated component, so no named-trigger ADR is owed. The first is a stated cost;
the second is a bounded blast radius, and the bound — the toolset is built from the run's
effective scope — is what tasks must assert.
