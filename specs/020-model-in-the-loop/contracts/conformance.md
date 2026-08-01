<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 020 — a model chooses

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row is executed by an automated check**, against a **dispatched run** — not a
constructed agent. The adapter's governance is already asserted by existing rows; what is
unasserted is that a real run consults a model and the choice is governed.

**Three things here are not rows, and each has a name.**

| | What it is | Who |
| --- | --- | --- |
| FR-012's demonstration (T039) | One call to a real provider, recorded with its output | **Dan McTeer** |
| FR-011a's fidelity row (T033) | The double and a real provider compared on one fixture | **Dan McTeer** |
| Principle V review (T040) | Security-maintainer review of the audit-schema change | **Dan McTeer** |

**The name is written because the phrase is not the thing.** An earlier draft of this contract
said "a named party is responsible for it before merge" and named nobody — which is the
constitution's requirement quoted back at itself. That is the third feature running where a
"named party" clause was satisfied by naming the clause; 019 hit it when a success criterion
needing a person was tagged onto an automated row proving something else.

Dan holds every review role in this repository, so the name was never in doubt — which is
exactly why writing it costs nothing and its absence was pure ceremony.

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

### The baseline (T002)

`pytest --collect-only -q` per directory, taken on `main` at `f947bad` before any 020 code
landed. SC-008 says no pre-existing directory loses rows; this is the number each is compared
against at T041.

| Directory | Rows on `main` |
| --- | --- |
| `tests/conformance/adapter` | 12 |
| `tests/conformance/api` | 46 |
| `tests/conformance/authority` | 12 |
| `tests/conformance/deployment` | 22 |
| `tests/conformance/durability` | 48 |
| `tests/conformance/evidence` | 17 |
| `tests/conformance/identity` | 28 |
| `tests/conformance/mcp` | 56 |
| `tests/conformance/mcp_served` | 19 |
| `tests/conformance/packs` | 30 |
| `tests/conformance/portal` | 8 |
| `tests/conformance/choice` | 0 — created empty by T001 |

**Collection counts, not pass counts**, and the distinction is what SC-008 actually protects.
A row that stops being collected disappears silently; a row that is collected and fails is
loud. Only the first failure mode needs a baseline to be visible at all.

### The demonstration

To be completed when the feature lands: the recorded real-provider call with its output, the
model used, the choice made, and whether it was permitted.

---

## Who runs these rows — 2026-08-01

**The enclave lane does not run on every pull request.** These rows are run by a named party
before merge — **Dan McTeer** — via `make conformance` in full on a live enclave. That is the
model the constitution describes for a blocking row no automated check executes.

Run the full `make conformance`, not the individual lanes. The two defects that lane caught on
its last day were both COMPOSITION failures, visible only when everything ran together.
