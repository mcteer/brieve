# Implementation Plan: Code mode becomes reachable

**Branch**: `039-code-mode-reachability` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/039-code-mode-reachability/spec.md`

## Summary

036 satisfied ADR-0041's gate and shipped a capability nobody can reach. This closes that, and
measurement found the gap is **three layers deep rather than two**.

The two the spec anticipated: the program tool is **registered nowhere**, so a ceiling naming it
refuses `unknown_ceiling_entry`; and the run allocation **never installs the runtime**, while CI
does — which is why 036's rows are green.

The third, and the reason this plan is not a two-line change: **the platform, not the model,
supplies every tool's arguments.** `resolve_step_tool` asks the model for a *name*; the entrypoint
invokes it with one fixed argument shape, `{"path": ..., "cas": 0}`, whose own docstring calls it
*"a fixture affordance."* A program is an argument, so the model has no channel to send one.

**The fix is structured output, not a toolset** (R7). `build_governed_agent` already takes
`output_type` and every caller passes `str`; a structured type there is the framework's own
mechanism. The model returns a tool **and its arguments**, and `resolve_step_tool` carries them to
the governed invoke. **Giving the agent a toolset was the first design and cost far more than it
looked** — it moves execution inside `agent.run_sync`, bypassing bounded retry, `already_chosen`
re-observation honesty, `TOOL_CHOSEN`, and the chooser's own contract.

So the work is: **register** the tool, **install** the runtime where dispatched work runs, and
**widen the model's answer** from a name to a name-with-arguments. Then prove it — against a real
budget, because the arithmetic has never met one, and **fix a defect that only a reachable code
mode can reach** (R8).

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

**Project Type**: single project. New: registration in `src/surfaces/`, a structured choice type
on the chooser, a call ordinal on the run, one demonstration definition in the dev estate.

**Performance Goals**: **the cost is the interpreter in the install**, not runtime latency. Every
dispatched run will carry a Rust interpreter it mostly will not use, on the allocation's critical
path. Stated rather than absorbed (R2).

**Constraints**: `invoke_tool` stays the sole execution entry and code mode must not become a
second way to reach a tool — ADR-0041's gate is satisfied at the seam and must survive being made
reachable. An environment without the runtime must keep refusing with a stated reason
(`SandboxUnavailableError`), never an import failure. No shipped definition gains the capability
(FR-012). The 038 row asserting unreachability is **inverted, never deleted** (FR-013).

**Scale/Scope**: one tool, one extra, one widened answer, one key fix, one demonstration
definition. The smallest change that makes an existing proven property true of the running
platform — plus the one defect that property's absence had been hiding.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Nothing is built. The seam, the ledger, the audit member, the runtime binding and the toolset mapping all exist; this wires them. The one genuinely new artefact is a demonstration definition, which is configuration. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The program tool is an ordinary registered tool; every call a program makes already round-trips `invoke_tool` by construction at the seam. **The shape of a governed step is unchanged**: the model answers, the platform invokes, the bracket wraps it. What widens is the *answer* — a name becomes a name and its arguments. **`GovernedToolset` still has no production caller**, and this feature deliberately does not give it one (R7): that would mean the model calling tools directly, which changes what a governed step *is* and deserves its own record rather than arriving as a side effect. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | `SandboxUnavailableError` exists precisely so a missing runtime refuses with a stated reason rather than surfacing an ImportError three frames down, and an environment without the extra must keep doing exactly that (FR-007). The seam's three-way distinction — policy deny visible to the program, exhausted bound terminating the run, superseded lease propagating — is asserted against a real budget for the first time (R4). |
| IV — Zero Standing Credentials; Authority Per Task | **N/A** | No credential path changes. A program runs under the run's existing authority and reaches tools through the ceiling that already bounds it. |
| V — Sealed Core, Versioned Seams | **Pass, with TWO narrowings** | No audit member is added — `PROGRAM_SUBMITTED` exists — and the registry gains an entry through the ordinary `register` path. **But two sealed-core areas change, not one.** (1) **The hook engine's idempotency key** (R8): a suffix appears only where the ordinal is non-zero, so every key a non-sandbox call produces is byte-identical to today. (2) **Durability** (R13): `intents` gains an `arguments` column and `IntentRecord` a matching field, **additive and defaulted to `{}`** on `resume_count`'s precedent, so every existing row reads back unchanged and every existing construction site still compiles. The second was missed in the first pass — the plan claimed one sealed-core touch when the widening it plans requires two, because a resumed step re-invokes and had nothing to re-invoke *with*. Both carry the security-maintainer review Principle V requires. |
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
└── model_chooser.py          # THE THIRD LAYER (R7). `output_type` becomes a STRUCTURED choice —
                              #   a tool name AND its arguments — so the platform still invokes
                              #   and the model still only answers. Bounded retry,
                              #   `already_chosen` and `TOOL_CHOSEN` all survive untouched

src/core/choice/recorded.py   # the recording format widens, and a BARE NAME still parses as a
                              #   choice with NO arguments — four existing conformance suites feed
                              #   recordings through `recording(*answers)` with bare names, and
                              #   they are the rows proving model-driven runs work at all

src/core/choice/bounded.py    # `resolve_step_tool` carries the model's arguments to the invoke
                              #   in place of `_PROBE_ARGUMENTS`, which its own docstring calls
                              #   "a fixture affordance, and it always was" — and whose NEXT
                              #   sentence is stale: a raising handler DOES deny `tool_error`
                              #   (engine.py:374), so the silent-success risk it warns of is gone

src/core/durability/schema.sql # R13: `intents` gains an `arguments` column, additive and
src/core/durability/types.py   #   defaulted to `{}` on `resume_count`'s precedent. A pending
                              #   step RE-INVOKES, and once the arguments are the model's there
                              #   is nothing to re-invoke with. NOT the audit trail — `TOOL_CHOSEN`
                              #   carries the name and nothing else, by argument
src/core/observation/bracket.py #  where the IntentRecord is CONSTRUCTED (bracket.py:41) — one
src/core/durability/postgres.py #  caller, engine.py:247, and it already holds the arguments

src/core/run.py               # + a call ordinal, default 0
src/core/sandbox/seam.py      # SETS it on entry, CLEARS it in a `finally` — scoped to the
                              #   submission, because nothing resets a run-level counter between
                              #   steps, and an elevated one would key the NEXT direct call
                              #   `run:1:tool:3`. The `finally` matters: the seam deliberately does
                              #   not catch a superseded lease or an exhausted bound, which are the
                              #   paths US4 exercises
src/core/sandbox/hooks.py     # R10: a GOVERNANCE hook denying the program tool when
                              #   `call_ordinal > 0`. NOT a name check in the seam — the seam has
                              #   "no blocklist, no allowlist, and no special case", and a check
                              #   there would sit before `invoke_tool` and never be recorded
src/core/hooks/engine.py      # R8: the idempotency key folds the ordinal in ONLY when non-zero,
                              #   so every existing key is byte-identical. Without this, a
                              #   program calling one non-repeatable tool twice writes ONE intent
                              #   for TWO effects — `ON CONFLICT DO NOTHING`, silently

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

- **II** — the first design gave the chooser's agent a toolset and read as a strain on this
  principle. The corrected design (R7) is not a strain at all: the shape of a governed step is
  unchanged, and only the model's *answer* widens. `GovernedToolset` remains without a production
  caller — recorded as a real gap rather than closed as a side effect, because closing it means
  deciding whether a model may call tools directly.
- **V** — the earlier "no sealed-core change" was wrong. R8's fix touches the hook engine's
  idempotency key. It is a narrowing — the suffix appears only where the ordinal is non-zero, so
  every key a non-sandbox call produces is unchanged — but it carries the review Principle V
  requires rather than being argued past.
- **VI** — the honest reading of "lean" changed rather than the verdict. Nothing operated is
  added; what changes is what every dispatched allocation carries. That is a real cost paid for
  a capability most runs will not use, and `pyproject.toml`'s comment is amended rather than left
  describing the old posture.

**The widening's real cost, found by measuring the resume path**: once arguments come from the
model, nothing persists them. `intents` carries `tool_name` and no arguments, `already_chosen` is
`{step: tool_name}`, and a pending step **re-invokes** — so every model-driven run would resume
with an empty argument map. The intent carries them (R13), because the entrypoint already argues
that case for the name — *"a second store holding the same fact would eventually disagree with
it."* **The trail does not**, because `record_choice` argues the opposite rule for itself: no
model output beyond the name, since the model may have read a secret out of a tool result. Two
stores, opposite rules, and the reason is what each is for.

**A limit stated rather than solved**: resume re-runs a program **from the start** — there is no
mid-program checkpoint — so a program that branches on a tool result may re-issue a different
second call, leaving a recorded intent for a call the re-run never makes. Its effect happened and
re-observation establishes that; the program's control flow has moved on regardless. K13b
therefore asserts ordinal alignment for a **deterministic** program and records the divergence
case, because asserting it unconditionally would claim something the design cannot deliver.
Solving it means checkpointing inside a program — a different and much larger feature.

**And one capability refused rather than bounded**: a program can call the program tool, because
the seam keeps no allowlist. Refused by a **hook** rather than by the seam, so the denial is
decided by the pipeline that decides everything else and is recorded (FR-005). Refused at the seam (R10) — nesting is absent from 036's Deferred
list, so it is permitted by omission rather than by argument, and shipping reachability would make
it live. A depth limit was rejected: a limit is a decision about how much nesting is useful, and
there is no evidence about that yet.

**The risk moved into the record rather than resolved**: widening the chooser's answer changes
what **every** model-driven run's model is asked to produce, not only code-mode runs. The blast
radius is far smaller than the toolset design's — the platform still invokes, so nothing about a
step's governance moves — but a model that must now emit a structured object can emit a malformed
one, and `resolve_step_tool`'s bounded retry is what absorbs that. Tasks assert the retry covers
a malformed *object*, not only an unpermitted *name*.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Every dispatched allocation installs a Rust interpreter** it mostly will not use, against Principle VI's default | FR-003 says a capability reachable in testing and absent in production is the defect this feature closes, and closing half of it does not close it. The allocation that runs dispatched work must carry what code mode needs | **A second jobspec** installing the extra only for code-mode runs halves the cost and doubles the substrate — two allocations whose postures must stay identical, which is the fragmentation Principle VII forecloses and which 038's two-jobspec experience says drifts. **Lazy installation at first use** puts a package install inside a governed step, on the run's critical path, with no bound |
| **The chooser's answer widens** from a name to a name-with-arguments, changing what every model-driven run's model is asked to produce | A program is an argument, not a name. The platform supplies every tool's arguments today (R7), and no amount of registration makes a program travel through a name-shaped channel | **Giving the agent a toolset** was the first design and costs far more: it moves execution inside `agent.run_sync`, bypassing bounded retry, `already_chosen` re-observation honesty, `TOOL_CHOSEN`, and the chooser's own contract. **A hand-rolled string protocol** invents a calling convention this platform would own and parse. Structured output is the framework's own mechanism, reachable through a parameter the code already passes |
| **The hook engine's idempotency key changes shape** | A program calling one non-repeatable tool twice writes ONE intent for TWO effects — the seam never advances `step_index`, and the insert is `ON CONFLICT DO NOTHING` (R8). That defeats duplicate-side-effect rejection, which the constitution names as an in-force gate | **Advancing `run.step_index` from inside the seam** corrupts the run's own accounting to fix the key's: it is the entrypoint's counter and the checkpoint reads it. **Leaving it** ships a hole that only a looping program reaches — which is every realistic program |

None is a new operated component, so no named-trigger ADR is owed. The first is a stated cost;
the second is a bounded change whose bound — the platform still invokes — tasks must assert; the
third is a narrowing that leaves every existing key byte-identical.
