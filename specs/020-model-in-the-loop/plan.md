# Implementation Plan: A model chooses, and the choice is governed

**Branch**: `spec/020-model-in-the-loop` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-model-in-the-loop/spec.md`

## Summary

Give the governance chassis a real decision to intercept. A dispatched run stops computing
`tools[step % len(tools)]` and asks the model its definition's binding map names. The choice
enters the same governed entry every scripted name entered, is recorded as a choice, and — when
refused — is offered back within a bounded number of attempts.

**Nothing about how governance intercepts changes.** `build_governed_agent` already installs it
outermost and has taken a model since it was written; no production caller ever passed one. This
feature is the caller.

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: `pydantic-ai` (present, with the governed agent already built on it)
and the Anthropic provider (present, used by `adapters/anthropic_scorer.py` for evals). **No new
dependency.**

**Storage**: One additive member on `AuditEventType`. No migration — the enum is unversioned and
nothing asserts its membership (research F1).

**Testing**: `pytest`. New rows drive a **dispatched run** (FR-010), so they belong in the
enclave lanes that already dispatch — `tests/conformance/durability` for the resume half and a
new `tests/conformance/choice` for the rest.

**Target Platform**: The enclave. Model calls in the merge lane go to a double; one recorded
demonstration uses a real provider by hand.

**Project Type**: A change to the run loop, plus one audit event.

**Performance Goals**: None invented. A provider call per step makes runs slower by however
long inference takes; that is the feature, not a regression.

**Constraints**: Re-choice is bounded and exhausting it is terminal (FR-004b). Every refusal is
recorded, not just the last (FR-004c). No fallback to arithmetic selection survives (FR-002).
Resume must not re-issue provider calls (FR-008).

**One carve-out, named rather than left implicit** (FR-002a): the `invoke_tools` flag at
`entrypoint.py:161` is a production path that runs steps and invokes no tool. It stays and
consults no model — a provider call whose answer is discarded is cost and failure surface for
nothing — and FR-002b requires such a run be distinguishable in the trail, so the carve-out
cannot become a way to produce a run that looks governed, executed nothing, and consulted
nobody. Analysis pass 3 found the flag mentioned in no artifact at all.

**Scale/Scope**: One selection site, one audit member, one new conformance directory.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The agent framework chooses; this wires a model to the loop that already brackets choices. No inference, no orchestration invented. |
| II — Total Interception; One Governed Tool Layer | **Pass** | FR-003 forbids any new path to a capability. The chosen name enters the same governed entry — which is the whole point: interception has never had a real decision to intercept. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-007 makes a provider failure terminal with no fallback; FR-004b makes an exhausted re-choice bound terminal. Both fail closed, and research F4 explains why the tempting fallback is the defect. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | Unchanged. The chosen tool runs under the same manufactured authority a scripted one did. The provider credential is `.env`-only and never reaches an allocation's environment (F6). |
| V — Sealed Core, Versioned Seams | **Pass, WITH REVIEW OWED** | **The audit schema is touched.** One additive `AuditEventType` member. Principle V names the audit schema sealed core and requires an approved spec plus security-maintainer review; the spec is approved and the review is owed before merge. See Complexity Tracking — this is recorded as a real obligation, not waved through. |
| VI — Lean by Default | **Pass** | No new dependency, no new operated component. |
| VII — Anti-Fragmentation | **Pass** | One selection site replaces one selection site. The double is injected at the binding, not at the loop, so there is no second path through the loop (F5). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | This *consumes* the qualified matrix and its eval gates rather than promoting anything — FR-005 and FR-006 make those gates load-bearing for the first time. |
| IX — Evidence Over Claims | **Pass** | The feature exists because every governance guarantee is currently asserted around an arithmetic index. FR-010 requires rows drive a dispatched run; FR-011a requires the lane's double be proven faithful rather than trusted. |
| X — The Decision Record Governs | **Pass** | ADR-0022, ADR-0039, ADR-0017, ADR-0019 and ADR-0032 are implemented, not amended. No new ADR needed. |

**Quality Gates — who runs what.** Every row is executed by an automated check. **FR-012's
demonstration is not a row** — a real provider call, performed once by hand and recorded with
its output, on the model 018 and 019 both set. The conformance contract names the runner.

**Gate result**: **PASS — proceed to Phase 0**, with the Principle V review recorded as owed.

**Re-check after Phase 1 design**: **PASS**, unchanged. The sealed-core obligation is the only
item in Complexity Tracking and it did not grow.

## Project Structure

### Documentation (this feature)

```text
specs/020-model-in-the-loop/
├── plan.md              # This file
├── research.md          # Phase 0 — six findings, one unknown carried
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── choosing.md      # What a model is asked and what it may answer
│   └── conformance.md   # The rows, who runs them, what they refuse to assert
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
src/core/audit/schema.py         # +1 AuditEventType member. SEALED CORE — see Principle V
src/core/choice/                 # NEW — asking, bounding, recording a choice
│   ├── __init__.py
│   ├── chooser.py               # the seam a provider or a double satisfies
│   └── bounded.py               # re-choice budget; exhausting it is terminal
src/adapters/pydantic_ai/
│   └── agent.py                 # UNCHANGED — already takes a model, already outermost
src/surfaces/dispatch/
│   └── entrypoint.py            # `_tool_for_step` DELETED; the loop asks a chooser.
│                                # The `invoke_tools` carve-out stays — FR-002a
infra/bin/
│   └── choice-conformance       # NEW — the lane: stand up, run the rows, tear down
tests/harness/
│   └── scripted_chooser.py      # NEW — the lane's double, injected at the binding
tests/conformance/choice/        # NEW — rows against a dispatched run
tests/conformance/durability/    # +resume rows for a model-driven run
```

**Structure Decision**: a new `src/core/choice/` rather than more surface area on the
entrypoint.

The entrypoint's job is to run a loop and bracket steps; deciding *what* to do next is a
different concern with its own failure modes — a bound, a refusal path, and a provider that can
be down. Putting it in the entrypoint would make the loop untestable without a provider and
would put the re-choice bound next to the step budget, where the two would be confused.

`chooser.py` is the seam the double satisfies, and it sits at the **binding** rather than at the
loop, so every line between "the run needs a choice" and "a choice came back" is production code
in both lanes (research F5).

## Phase 1 outputs

- [data-model.md](./data-model.md) — Choice, Binding, and the re-choice budget; the state
  transition that matters is *refused → chosen again → exhausted*.
- [contracts/choosing.md](./contracts/choosing.md) — what a model is asked, what it may answer,
  and what happens to each answer.
- [contracts/conformance.md](./contracts/conformance.md) — the rows, and what they refuse to
  assert.
- [quickstart.md](./quickstart.md) — run a task, watch a model choose, watch a choice refused.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **A sealed-core change: one `AuditEventType` member** | FR-009 requires a reader to tell a chosen tool from a scheduled one, and FR-004c requires every refusal recorded. A refused choice never opens a tool bracket, so without its own event the single most important record has nowhere to live. | **A field on the existing bracket**: rejected in clarification for exactly that reason. **Reusing `PRE_DECISION`**: rejected in research F2 — it records what governance decided about a tool, not who named it, and a field that changes an event's meaning is a second event wearing the first's name. **The obligation stands regardless**: Principle V requires security-maintainer review of an audit-schema change, and research F1 establishes only that the change is additive and unobserved elsewhere — not that it is exempt. |
| **A new `src/core/choice/` package** | Deciding what to do next has its own failure modes — a bound, a refusal path, a provider that can be down — none of which belong beside a step loop. | **Inside `entrypoint.py`**: rejected because the loop would then be untestable without a provider, and the re-choice bound would sit next to the step budget where the two get confused. |

**Not a violation, named so it is not mistaken for one**: no new dependency, no new ADR, no new
operated component, and `build_governed_agent` is untouched. The adapter's governance was always
correct; it has simply never been given a real decision to intercept.
