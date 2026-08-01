<!-- SPDX-License-Identifier: Apache-2.0 -->
# Contract: choosing

What a model is asked, what it may answer, and what becomes of each answer.

---

## What the model is given

- The task the run was started for.
- **The tools its definition permits** — the ceiling, not the platform's catalogue. A model is
  not shown what it may not have.
- What has happened so far in this run, including **any refusals at this step**.

## What it may answer

| Answer | What happens |
| --- | --- |
| A permitted tool | Enters the same governed entry a scripted name entered. Executed. Recorded as chosen. |
| A tool outside the ceiling | **Refused by the existing enforcement**, recorded against the choice, and returned to the model as context. It may choose again while the bound allows. |
| A name that is not a tool | Refused as a malformed choice — distinguishable from a tool named and denied, because the two mean different things to whoever reads the trail. |
| Nothing | The run ends in a recorded terminal state. It does not default to a tool. |

## What the platform guarantees

**No new path to a capability.** The chosen name goes where the scripted name went. If that
were untrue, every interception guarantee this platform holds would be about a path a model
does not take.

**The refusal is the core's.** The choosing code never decides permission — it asks, carries
the answer, and records what happened.

**The bound is enforced by the platform, not the model.** A model cannot extend its own
attempts, and exhausting them is terminal and recorded.

**A provider failure is terminal.** There is no fallback to arithmetic selection. A fallback
would be taken exactly when the provider is down, silently reverting the platform to a scripted
sequence while every governance row continued to pass.

## What it does NOT guarantee

**That the choice is good.** Whether a model chooses well is an eval question (Principle VIII).
This asserts the choice is *governed*, not that it is *right* — and those are different claims
that a working demonstration will invite a reader to merge.
