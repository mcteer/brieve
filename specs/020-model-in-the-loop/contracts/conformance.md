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

## The rows, as shipped

**No longer a sketch.** The table below is the set that landed, by module and function name.
019's contract carried a provisional table through six analysis passes, which is why the
previous version of this section carried a label saying it was one.

### `tests/conformance/choice/test_a_model_chooses.py`

| Row | Asserts | Requirement | Lane |
| --- | --- | --- | --- |
| `test_a_model_choice_is_executed` | The tool invoked is the one a model named, in an order round-robin would not have produced; and the choice is recorded **before** its outcome | FR-001, SC-001 | enclave |
| `test_a_toolless_run_is_distinguishable` | The `invoke_tools` carve-out says so per step rather than showing as an absence | FR-002a, FR-002b | enclave |
| `test_no_arithmetic_selection_remains` | No `_tool_for_step` and no subscript-by-modulo anywhere in `src/`, **parsed rather than grepped** | FR-002, SC-002 | hermetic |
| `test_the_contract_states_what_this_gate_does_not_assert` | This document still records its own limits | FR-009 | hermetic |

### `tests/conformance/choice/test_a_choice_is_governed.py`

| Row | Asserts | Requirement | Lane |
| --- | --- | --- | --- |
| `test_an_unpermitted_choice_is_refused_by_existing_enforcement` | Refused, and refused by a **built-in governance hook** — discriminated on provenance, not outcome | FR-003, FR-004, SC-003 | enclave |
| `test_a_refusal_returns_to_the_model` | A second choice at the same step, numbered as successive attempts | FR-004a | enclave |
| `test_the_rechoice_bound_is_terminal` | The bound holds at 3 and the run ends terminally with no tool executed | FR-004b, SC-003a | enclave |
| `test_every_refusal_is_recorded` | Three attempts and at least two denials, not one entry | FR-004c, SC-003b | enclave |
| `test_a_malformed_choice_is_distinguishable` | `malformed` ≠ `named`, and a non-tool never reaches the pipeline | Edge case | enclave |
| `test_an_empty_choice_ends_the_run` | Terminal, and no tool is defaulted to | US1 scenario 3 | enclave |
| `test_repetition_is_bounded_by_the_step_budget` | A model naming one permitted tool forever is stopped by the existing budget | Edge case | enclave |
| `test_no_provider_credential_reaches_an_allocation` | The credential is in no jobspec and no recorded choice | GATE:no-secret-leak | enclave |

### `tests/conformance/choice/test_the_model_is_bound.py`

| Row | Asserts | Requirement | Lane |
| --- | --- | --- | --- |
| `test_the_bound_model_is_the_one_used` | Two definitions bound to different cells record different models | FR-005, SC-004 | enclave |
| `test_an_unqualified_model_refuses_before_any_call` | `unqualified_cell`, before anything is constructed | FR-006 | hermetic |
| `test_a_withdrawn_cell_refuses` | `cell_withdrawn` — the case registration-time validation misses | FR-006 | hermetic |
| `test_no_binding_refuses_rather_than_defaults` | `no_binding_for_role`, never a default | FR-006 | hermetic |
| `test_a_fabric_with_no_matrix_refuses_rather_than_going_inert` | Deliberately unlike `manufacture._resolve_binding_map` | FR-006 | hermetic |

### `tests/conformance/choice/test_the_double_is_faithful.py`

| Row | Asserts | Requirement | Lane |
| --- | --- | --- | --- |
| `test_the_merge_lane_needs_no_provider` | A fixture chooser answers with no credential, and the enclave ships **no `live` cell** | FR-011, SC-006 | hermetic |
| `test_a_fixture_cell_without_a_recording_names_a_permitted_tool` | Absent recording is defined; a **short** one is still loud | FR-011 | hermetic |
| `test_the_identifier_the_matrix_pins_is_the_one_called` | `provider/model@version` → the client's form, version included | FR-005 | hermetic |
| `test_the_double_is_faithful` | Double and real provider agree in **shape** on one fixture | FR-011a | **`live_model`, named runner** |

### `tests/conformance/durability/test_model_driven_resume.py`

| Row | Asserts | Requirement | Lane |
| --- | --- | --- | --- |
| `test_a_model_driven_run_resumes` | Killed mid-flight, revived, prefix re-observed | FR-008, SC-005 | enclave |
| `test_resume_reissues_no_provider_call` | No choice at a step below the checkpoint, and the interrupted step honours the tool on its **open intent** | FR-008, SC-005 | enclave |

**The recording is the instrument for the resume rows.** It holds exactly as many answers as
the revived run may ask for, so a run that re-asked for a step it had already done would
exhaust it and fail the allocation. "No repeated provider call" is enforced by a stand-in that
runs out, not inferred from a log.

### Where FR-007 is asserted

`test_a_fixture_cell_without_a_recording_names_a_permitted_tool` covers the provider-failure
path's construction; the terminal handling itself is exercised by the entrypoint's
`ChooserUnavailable` arm, which records `provider_unavailable` and fails the allocation. **No
row drives a genuinely unreachable vendor**, because the merge lane may not depend on one —
recorded here as a limit rather than claimed as coverage.

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

### The result (T041) — 2026-08-01

| Directory | On `main` | With 020 | Δ |
| --- | --- | --- | --- |
| `tests/conformance/adapter` | 12 | 12 | — |
| `tests/conformance/api` | 46 | 46 | — |
| `tests/conformance/authority` | 12 | 12 | — |
| `tests/conformance/deployment` | 22 | 22 | — |
| `tests/conformance/durability` | 48 | **50** | +2 (`test_model_driven_resume.py`) |
| `tests/conformance/evidence` | 17 | 17 | — |
| `tests/conformance/identity` | 28 | 28 | — |
| `tests/conformance/mcp` | 56 | 56 | — |
| `tests/conformance/mcp_served` | 19 | 19 | — |
| `tests/conformance/packs` | 30 | 30 | — |
| `tests/conformance/portal` | 8 | 8 | — |
| `tests/conformance/choice` | 0 | **21** | +21 |

**SC-008 holds: no pre-existing directory lost a row.**

`make check` and the full `make conformance` both pass on a live enclave — the latter
end to end, including `choice lane passed`, on 2026-08-01.

**One environmental hazard, recorded because it cost hours and will recur.** The dev
enclave's Nomad agents run on the host and sign workload identities with host time; Vault
and every allocation run in the container VM. When that VM's clock drifts behind — measured
at 919 seconds on this machine — every dispatched run dies at startup with
`invalid not before (nbf) claim: token not yet valid`, and it presents as a *different
subset* of rows failing each run, each with an empty audit trail. That reads as a flaky new
feature rather than an environment fault.

Two things came out of it, and only the first is a fix to this repository:

- **Every workload-identity role now sets 120s of clock leeway** (`infra/modules/trust-fabric/auth.tf`).
  They had none, so an attested identity could be rejected before it was a second old — which
  is not a security property, it is a lottery in the identity path.
- **The VM clock itself must be resynced** before a long gate run
  (`docker run --rm --privileged alpine hwclock -s`). The leeway does not excuse real drift,
  and a drift large enough to exceed it is a machine to fix rather than a number to raise.

A stale `mcp` allocation is the other thing to check first: the sweeper and the audit shipper
both run in it, and a token minted before a policy change does not gain the policy. Three
rows failed on that and passed immediately once the allocation was replaced.

### The demonstration (T039, FR-012, SC-007) — performed 2026-08-01 by Dan McTeer

One call to a real provider, by hand, never in a lane. **The step that proves the wiring
carries a real inference call**, which a recording cannot.

| | |
| --- | --- |
| **Model identifier (the matrix's form)** | `anthropic/claude-opus@5` |
| **Called as** | `anthropic:claude-opus-5` |
| **Route** | `build_governed_agent`, unchanged since 004 — its first production caller |
| **Task** | "Read the current value stored at conformance/probe." |
| **Permitted** | `vault_read`, `vault_write` |
| **Chose** | `vault_read` — permitted |
| **Re-asked after being told `vault_write` was refused** | `vault_read` again |

**What this shows and does not.** It shows a real model reached through the governed agent and
answered with a permitted tool name, and that a refusal carried back as context did not push it
into a different tool. It does **not** show the choice was good — the model picking the obvious
read tool for a read task is exactly the persuasive-but-weak evidence this contract warns about
two sections down.

### The fidelity row (T033, FR-011a) — run 2026-08-01 by Dan McTeer

`pytest tests/conformance/choice/test_the_double_is_faithful.py -m live_model` — **passed**,
double and live provider both returning a well-formed choice from the permitted set.

**It failed first, and the failure was worth more than the pass.** The fixture paired the read
task above with `("echo", "plan")`, and the live model answered NONE — correctly, since neither
tool reads a secret. The double answered from its script regardless. That is not a fidelity
defect; it is an incoherent fixture, and the row caught it. FR-011a presumes the permitted set
contains something the task could plausibly want, because a fixture that does not is testing
whether a model will invent a use for the wrong tool — the opposite of what this platform wants
from one.

### Principle V review (T040, FR-009a) — 2026-08-01, Dan McTeer

The audit-schema change is **one additive `AuditEventType` member**, `TOOL_CHOSEN`. Reviewed
as the sealed-core change Principle V names, against an approved spec, with the review recorded
here rather than assumed:

- **Additive only.** No member renamed, removed, or given a new meaning. Research F1 measured
  that the enum is unversioned and that no test asserts its membership; `tests/unit/test_audit_chain.py::test_widening_the_event_vocabulary_moves_no_existing_hash`
  now pins a digest so a change to the canonical encoding cannot happen quietly.
- **No payload change to any existing event.** The new one carries `run_id`, `step_index`,
  `attempt`, `model`, `named`, `outcome` — and, on the provider-failure path only, `reason`.
- **No secret surface.** The model's reasoning, prompt, and output beyond the tool name are
  never recorded. What a model read out of a tool result cannot reach the trail through this
  event.
- **Fail-closed.** The entry is written **before** the tool is invoked, so a choice that cannot
  be recorded cannot execute.

**Approved.** The obligation the plan recorded as owed is discharged here.

---

## Who runs these rows — 2026-08-01

**The enclave lane does not run on every pull request.** These rows are run by a named party
before merge — **Dan McTeer** — via `make conformance` in full on a live enclave. That is the
model the constitution describes for a blocking row no automated check executes.

Run the full `make conformance`, not the individual lanes. The two defects that lane caught on
its last day were both COMPOSITION failures, visible only when everything ran together.
