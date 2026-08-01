<!-- SPDX-License-Identifier: Apache-2.0 -->
# Data model: 020 — a model chooses

Two new entities and one changed one. Nothing here is stored beyond the trail.

---

## Choice

What a model named at a step, and what became of it.

| Field | What it is | Rules |
| --- | --- | --- |
| `step_index` | Which step it belongs to | From the run, never from the model |
| `attempt` | Which try this is at that step | Starts at 0; bounded — see below |
| `named` | The tool the model named | May be anything the model emits, including nothing and including a name that does not exist |
| `permitted` | Whether governance allowed it | **Decided by the existing enforcement**, never by the choosing code |
| `model` | Which model was asked | From the definition's binding map, validated against the qualified matrix |

**A Choice is recorded whether or not it was permitted** (FR-004c). A run denied four times and
permitted on the fifth is a different event from one permitted immediately, and a trail showing
only the success would describe the wrong run.

### The state transition that matters

```
                  ┌──────────────── refused, attempt < bound ───────────┐
                  ▼                                                     │
   step ──▶ CHOOSING ──▶ named ──▶ [governance] ──▶ permitted ──▶ EXECUTED
                  │                     │
                  │                     └── refused, attempt = bound ──▶ TERMINAL
                  │
                  └── nothing named ──────────────────────────────────▶ TERMINAL
```

**The loop back is the feature and the bound is what keeps it honest.** Governance as a signal
means a denial teaches the model something; without the bound it means an agent grinds against
its ceiling until something gives, which is governance as a suggestion.

**The bound is per step, not per run.** A run that legitimately needs several tools should not
inherit a smaller budget because an earlier step took two attempts.

---

## Binding

role → model, from the definition. **Exists already and has never been load-bearing.**

- MUST be validated against the qualified matrix **before any provider call** (FR-006). A model
  the matrix does not qualify must not be reached, not merely not used.
- No binding for the role MUST refuse the run rather than default. A default model is an
  ungoverned model choice, which is the same defect as an ungoverned tool choice one level up.

---

## Step *(changed)*

Unchanged in shape. What changes is that its tool now has an **author**, and the trail says so.

Previously `tools[step % len(tools)]` — an index nobody chose. Every governance guarantee this
platform holds was asserted around that expression, which is the whole reason this feature
exists.

---

## What is NOT modelled

- **The model's reasoning.** Not recorded. It is not a governance fact, it would carry whatever
  the model read from tool results into the trail, and the no-secret-leak posture applies to
  what is recorded about a choice as much as to a tool result.
- **A conversation.** One choice per step, which is what the loop already brackets. Multi-step
  planning is out of scope.
