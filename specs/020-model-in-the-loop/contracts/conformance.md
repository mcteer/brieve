<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 020 — a model chooses

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row is executed by an automated check**, against a **dispatched run** — not a
constructed agent. The adapter's governance is already asserted by existing rows; what is
unasserted is that a real run consults a model and the choice is governed.

**FR-012's demonstration is NOT a row.** One call to a real provider, performed by hand and
recorded with its output. **A named party is responsible for it before merge** — the
constitution requires that of any blocking row no automated check executes, and 019 had to
learn this the hard way when a success criterion needing a person was tagged onto an automated
row that proved something else.

Everything in the merge lane uses the double. **The double is proven faithful by a row**
(FR-011a) rather than trusted — a stand-in nobody checks is the exact shape this feature exists
to end.

---

## The rows

Named provisionally; `/speckit-tasks` fixes them, and **this table is a sketch until T-final
replaces it with the rows as shipped.** 019's contract carried a stale table for six analysis
passes; labelling it is cheaper than remembering.

| Row | Asserts | Requirement |
| --- | --- | --- |
| a model's choice is executed | The tool invoked is the one a model named | FR-001, SC-001 |
| no arithmetic selection remains | `_tool_for_step` is unreachable from a production run | FR-002, SC-002 |
| the choice enters the governed entry | No new path to a capability | FR-003 |
| an unpermitted choice is refused | By the **existing** enforcement, not by new logic | FR-004, SC-003 |
| a refusal returns to the model | The model may choose again | FR-004a |
| the bound is terminal | Exhausting re-choice ends the run, recorded | FR-004b, SC-003a |
| every refusal is recorded | Not only the last before success | FR-004c, SC-003b |
| the bound model is the one used | From the binding map, validated first | FR-005, SC-004 |
| an unqualified model refuses first | Before any provider call | FR-006 |
| a provider failure is terminal | And never falls back to a sequence | FR-007 |
| resume does not re-ask | Prior steps re-observed, no repeated provider call | FR-008, SC-005 |
| the trail names the chooser | A distinct event; chosen is legible from scheduled | FR-009 |
| the double is faithful | Double and real provider agree in **shape** on one fixture | FR-011a |
| the lane needs no provider | The merge lane passes with none | FR-011, SC-006 |
| nothing stopped running | Per-directory collection counts | SC-008 |

---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047.

- **Not that the choice is good.** Whether a model chooses *well* is an eval question
  (Principle VIII). These rows assert the choice is governed. **This is the limit most likely
  to be misread**, because a demonstration of a model picking the right tool is far more
  persuasive than what it actually proves.
- **Not that the model is safe.** The ceiling bounds what it may reach; nothing here asserts
  anything about what it says or intends.
- **Not that two runs agree.** A model may choose differently on identical input. That is
  correct, and a row demanding agreement would be asserting determinism the feature does not
  claim.
- **Not that the double behaves like any particular model.** FR-011a asserts **shape** — a
  well-formed choice from the permitted set. Demanding the double and a real provider pick the
  same tool would assert a model's judgement rather than the platform's contract.

---

## Known limits, recorded rather than closed

**The fidelity row costs a provider call.** It cannot run in the merge lane, so it runs where
the demonstration runs — behind a named runner. That makes FR-011a's guarantee *periodic*
rather than continuous, and a double could drift between checks. Recorded because the
alternative is a merge lane that needs a vendor, which is a gate that stops running.

**Resume with a model is the deepest claim here.** "Re-observe, never re-execute" means
something stronger when replaying would produce a *different* choice. The row asserts no
repeated provider call — which is the observable property. It cannot assert what a second call
*would* have returned, and does not try.

---

## SC-008 and the demonstration

Both to be completed when the feature lands: per-directory collection counts against `main`,
and the recorded real-provider call with its output, the model used, the choice made, and
whether it was permitted.
