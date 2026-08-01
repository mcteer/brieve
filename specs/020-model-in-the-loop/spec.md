# Feature Specification: A model chooses, and the choice is governed

**Feature Branch**: `spec/020-model-in-the-loop`

**Created**: 2026-08-01

**Status**: Draft

**Input**: ROADMAP gap 0e — "No model is in the loop; a dispatched run executes a scripted tool sequence." The last substantive item on the page, and the one the platform exists for.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11, R15** (total interception — the thing being intercepted has never been a real decision until now). **R4** (evidence over claims: every governance guarantee is currently asserted around a `step % len(tools)`). **R2, R3** (the authority a chosen tool runs under). |
| **ADRs touched** | **ADR-0022, ADR-0039** (the qualified model matrix and per-role bindings — exercised for real rather than resolved and discarded). **ADR-0017, ADR-0019** (the primary adapter, whose `build_governed_agent` has taken a model since it was written). **ADR-0032** (governance outermost). **None amended** — this implements what they decided. |
| **Evidence class** | **Attestation-relevant.** The trail currently records that a tool ran under an authority. It will record that a **model chose** that tool and the choice was governed, which is a different claim and the one the platform's purpose rests on. |

## What already holds, and what does not

**Holds, and it is a great deal.** Every durability and governance guarantee is real and
asserted against live infrastructure: kill/resume, fencing, re-observe-never-re-execute, grant
expiry, hash-chained evidence, hooks failing closed, authority manufactured per allocation from
an attested identity. 019 added a served surface a client reaches, and a run started through it
authorizes itself and writes a trail naming the caller.

`build_governed_agent(model, ...)` exists at `src/adapters/pydantic_ai/agent.py:102`, takes a
model, and installs governance outermost so no capability downstream can produce an ungoverned
execution.

**Does not hold.** **No production caller passes it a model.** The only real provider call in
the tree is `adapters/anthropic_scorer.py`, which scores evals rather than runs. A dispatched
run picks each step's tool arithmetically:

```python
def _tool_for_step(tools: list[str], step: int) -> str:
    return tools[step % len(tools)] if tools else ""
```

**Why nothing noticed.** Everything downstream of the choice is correct, so every row about
interception, ordering, refusal, and evidence passes — about a sequence nobody chose. 019's
lane would not catch it either: the dispatch entrypoint runs, completes, and writes evidence.
It simply never consults a model.

## Clarifications

### Session 2026-08-01

- Q: When a model names a tool the definition does not permit, what happens? → A: **Refused,
  and offered back to the model.** The denial becomes context; the model may choose again
  within the same step budget. **Governance is a signal, not only a wall** — and the risk that
  buys is explicit: an agent that keeps asking must not be able to grind past its ceiling. So
  retries are bounded, every refusal is recorded, and exhausting the bound is itself a recorded
  terminal outcome. The rejected alternative — a denial ends the run — is simpler and would push
  people toward over-broad ceilings to avoid brittleness, which is a worse outcome by a
  different route.
- Q: What stands in for the model in the merge lane? → A: **A scripted double, and a row
  proving it faithful.** Fast and hermetic — and worthless on its own, because a double nobody
  checks is a double that drifts. A row asserts the double and a real provider agree on the
  same fixture. **Without that row this is the exact shape 020 exists to end**: something
  correct, tested, and standing in for the thing that was never exercised.
- Q: Where is the choice recorded? → A: **A new audit event type**, beside the existing tool
  bracket. A reader must be able to tell a chosen tool from a scheduled one, and **a refused
  choice never opens a bracket** — so a field on the bracket would leave the single most
  important record with nowhere to live. This adds to the audit schema, which is sealed core
  (Principle V) and needs the review that entails.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A model chooses a tool and governance sees the choice (Priority: P1)

A dispatched run reaches a step. Instead of computing an index, it asks a model what to do
next, given the task and the tools the definition permits. The model names a tool. That name
enters the same governed entry every scripted name entered — refused if it must be, recorded
either way.

**Why this priority**: it is the feature. Everything else here is a property of it.

**Independent Test**: run a task whose correct tool is not the one round-robin would have
picked, and observe the model's choice executed and recorded.

**Acceptance Scenarios**:

1. **Given** a definition permitting several tools, **When** a run executes, **Then** the tool
   invoked is the one a model named, and the trail records it as chosen rather than scheduled.
2. **Given** a model naming a tool the definition does not permit, **When** the run reaches it,
   **Then** it is refused by the same governed entry that refuses any other unpermitted tool,
   and the refusal is recorded against the model's choice.
3. **Given** a model naming no tool, **When** the run reaches that step, **Then** the run ends
   in a recorded terminal state rather than looping or defaulting to a tool.

---

### User Story 2 - The model is the one the matrix bound (Priority: P1)

The definition's binding map names a model per role. The run uses **that** model — not one a
process defaulted to, and not one an operator exported into an environment.

**Why this priority**: an ungoverned model choice is the same defect as an ungoverned tool
choice, one level up. ADR-0022 and ADR-0039 exist for this and have never been load-bearing.

**Independent Test**: two definitions bound to different models produce runs that used
different models, evidenced from the trail.

**Acceptance Scenarios**:

1. **Given** a definition whose binding map names a model, **When** a run starts, **Then** the
   provider call is made against that model.
2. **Given** a binding map naming a model the matrix does not qualify, **When** a run starts,
   **Then** it is refused before any provider call is made.
3. **Given** no binding for the role, **When** a run starts, **Then** it is refused rather than
   defaulted.

---

### User Story 3 - A model-driven run is still durable (Priority: P1)

The run is killed mid-flight and resumes. Steps already executed are re-observed, never
re-executed — including the model's own calls.

**Why this priority**: every durability guarantee this platform has was established against a
deterministic sequence. A model is not deterministic, and "re-observe, never re-execute" means
something stronger when replaying would produce a *different* choice.

**Independent Test**: kill a model-driven run mid-flight; it resumes and completes with exactly
one execution per step.

**Acceptance Scenarios**:

1. **Given** a run killed after step N, **When** it resumes, **Then** steps 0..N are
   re-observed and not re-executed, and no provider call is repeated for them.
2. **Given** a resumed run, **When** it continues, **Then** the choices already made are the
   ones honoured — a replay that re-asked the model would be re-execution wearing observation's
   clothes.

---

### Edge Cases

- **The provider is unreachable.** The run must fail in a recorded, terminal way — never
  silently fall back to a scripted sequence, which would make the platform's central claim
  false exactly when nobody is watching.
- **The model returns something that is not a tool name.** Refused as a malformed choice,
  distinguishable from a tool that was named and denied.
- **The model names the same tool forever.** Bounded by the existing step budget; a model
  cannot extend a run.
- **The model's output contains a secret** it read from a tool result. The no-secret-leak
  posture applies to what is recorded about a choice, not only to tool results.
- **Two runs of the same task choose differently.** Correct, and the evidence must make both
  legible rather than reading as a defect.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A dispatched run MUST obtain each step's tool from a model, given the task and
  the tools the definition permits.
- **FR-002**: `_tool_for_step`'s arithmetic selection MUST NOT remain reachable from a
  production run. A fallback that survives is a fallback that will be taken.
- **FR-003**: The chosen tool MUST enter the same governed entry every scripted tool entered.
  No new path to a capability may be introduced by the model's involvement.
- **FR-004**: A choice the definition does not permit MUST be refused by the existing
  enforcement, and the refusal MUST be recorded **against the choice** — distinguishable from a
  tool the platform never offered.
- **FR-004a**: A refused choice MUST be returned to the model as context, and the model MAY
  choose again within the same step.
- **FR-004b**: Re-choosing after a refusal MUST be **bounded**, and exhausting the bound MUST
  end the run in a recorded terminal state. Unbounded re-choice is an agent grinding against
  its ceiling until something gives; the bound is what keeps governance-as-a-signal from
  becoming governance-as-a-suggestion.
- **FR-004c**: Every refused choice MUST be recorded, not only the last one. A run that was
  denied four times and permitted on the fifth is a different event from one permitted
  immediately, and a trail showing only the success would describe the wrong run.
- **FR-005**: The model used MUST be the one the definition's binding map names, validated
  against the qualified matrix before any provider call.
- **FR-006**: An unqualified or unbound model MUST refuse the run before any provider call.
- **FR-007**: A provider failure MUST end the run in a recorded terminal state and MUST NOT
  fall back to any non-model selection.
- **FR-008**: Resuming a run MUST re-observe prior steps and MUST NOT re-issue their provider
  calls.
- **FR-009**: The trail MUST record, per step, that a model chose and what it chose, as a
  **distinct audit event type** — enough that a reader can tell a chosen tool from a scheduled
  one, and giving a refused choice somewhere to live even though no tool ran and no bracket
  opened.
- **FR-009a**: Adding that event type touches the audit schema, which Principle V names sealed
  core. It requires the approved spec and security-maintainer review Principle V demands, and
  the plan MUST record that rather than treating the addition as routine.
- **FR-010**: Conformance rows MUST run against a **dispatched run**, not a constructed agent.
  The adapter's governance is already asserted; what is unasserted is that a real run consults
  a model and the choice is governed.
- **FR-011**: Model calls in the merge lane MUST NOT depend on a live provider. A gate that
  cannot run without a vendor is a gate that stops running.
- **FR-011a**: The lane's model double MUST be asserted **faithful** — a row comparing the
  double and a real provider against the same fixture. A double nobody checks drifts silently,
  and the platform would then be asserting governance around a stand-in for the decision this
  feature exists to make real.
- **FR-012**: At least one demonstration MUST use a **real** provider, recorded with its
  output, because a scripted model proves the wiring and not the claim.

### Key Entities

- **Choice**: what a model named at a step, and whether it was permitted. New to the trail.
- **Binding**: role → model, from the definition. Exists; unexercised.
- **Step**: unchanged, except that its tool now has an author.

## Success Criteria *(mandatory)*

- **SC-001**: A dispatched run invokes a tool a model named, evidenced from the trail.
- **SC-002**: 0 production paths select a tool arithmetically.
- **SC-003**: A choice outside the definition's permitted set is refused in 100% of cases, by
  the existing enforcement rather than by new logic.
- **SC-003a**: A run that exhausts its re-choice bound ends terminally in 100% of cases — 0
  runs continue past a ceiling by repetition.
- **SC-003b**: Every refused choice appears in the trail, not only the last before success.
- **SC-004**: Two definitions bound to different models produce runs evidenced as using
  different models.
- **SC-005**: A model-driven run killed mid-flight resumes and completes with exactly one
  execution per step, and no repeated provider call.
- **SC-006**: The merge lane passes with no live provider.
- **SC-007**: One recorded demonstration against a real provider.
- **SC-008**: No pre-existing conformance directory loses rows.

## Out of scope

- **Multi-step planning, sub-agents, or tool-call chaining.** One choice per step, which is
  what the loop already brackets.
- **Prompt engineering quality.** Whether the model chooses *well* is an eval question
  (Principle VIII), not a governance one. This asserts the choice is governed, not good.
- **Streaming or partial results.**
- **Model promotion.** The matrix and its eval gates exist; this consumes them.

## Assumptions

- The adapter's governance is correct and stays unchanged; this feature gives it a real
  decision to intercept rather than altering how it intercepts.
- The binding map and qualified matrix are correct and merely unexercised.
- A dispatched run remains the unit of durability; nothing here changes the step loop's
  bracket semantics, only who names the tool inside it.
