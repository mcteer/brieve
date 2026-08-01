<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 021 — a report compiles from records

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Most of this feature is hermetic, and that is a deliberate property rather than a convenience.**
The compiler takes records in and returns a report; it holds no query and no credential. So the
rows that matter most — every claim traces to evidence, nothing is softened, the gate scores what
a person reads — need no enclave, no provider, and no live product. A gate that needs
infrastructure is a gate that eventually stops running.

Three groups of rows, and only the second needs the enclave:

| Group | Where | Needs |
| --- | --- | --- |
| Compilation and claim status | `tests/conformance/reports/` | Nothing. Records in, report out |
| Observation at run end, and the surface | `tests/conformance/reports/`, `tests/conformance/api`, `tests/conformance/mcp` | The enclave — a dispatched run that observes, and both transports answering |
| Report fidelity | `packs/*/evals/report_fidelity.toml` via `make evals` | Nothing. Recorded runs, labelled material events |

**No row here needs a live provider or a hand-performed demonstration.** There is no model in this
path at all, which is the point of ADR-0018 — so 020's three named obligations have no equivalent
here.

**That is not the same as no named runner, and an earlier draft of this section said it was.**
The enclave lane has not run on pull requests since #95; it is `workflow_dispatch` only. So the
second group above — a dispatched run that observes, and both transports answering — is executed
by **no automated check**, and the constitution is explicit:

> A blocking row that no automated check executes MUST have a named party responsible for running
> it before merge, recorded in that same contract; merging without that run is a gate regression,
> and "the check is not automated" is not a defence.

| | What it is | Who | Status |
| --- | --- | --- | --- |
| The enclave rows | `make conformance` in full, on a live enclave, before merge | **Dan McTeer** | Run 2026-08-01 |
| Principle V review | Security-maintainer review of the audit-schema change (one additive `AuditEventType` member) | **Dan McTeer** | **Discharged — see below** |

### Principle V review — 2026-08-01, Dan McTeer

The audit-schema change is **one additive member**, `AuditEventType.EFFECT_OBSERVED`. Reviewed as
the sealed-core change Principle V names, against an approved spec, and recorded here rather than
assumed:

- **Additive only.** No member renamed, removed, or given a new meaning. The digest pinned in
  `tests/unit/test_audit_chain.py` by 020 is unchanged, which is the assertion that adding a
  member rewrites no entry already in the chain.
- **No payload change to any existing event.** The new one carries `run_id`, `step_index`,
  `tool`, `idempotency_key`, `outcome`, and `detail` — the observer's own words about the basis,
  never a product value.
- **Written under a bounded identity.** The allocation observes, under the attested identity it
  already holds and bounded by the run's ceiling. This is the Principle IV property the
  Constitution Check failed on and this placement resolves; a report holds no credential and
  calls no observer, asserted by two rows.
- **Cannot change what it reports.** The observation is written *after* the terminal checkpoint,
  so it can add a finding and never alter the run's recorded ending.

**Approved.** The obligation the plan recorded as owed is discharged.

Run the **full** `make conformance`, not the individual lanes. 019's two defects on its last day
were both composition failures, visible only when everything ran together.

**Before running it, resync the container VM's clock** (`docker run --rm --privileged alpine
hwclock -s`). Drift makes dispatched runs die on `nbf` as a different random subset each time,
which reads as a flaky feature rather than an environment fault.

---

## The rows

Sketch until `/speckit-tasks` fixes them and implementation replaces this table with the rows as
shipped. **Labelled, because 019's contract carried a stale table through six analysis passes and
labelling it is cheaper than remembering.**

| Row | Asserts | Requirement |
| --- | --- | --- |
| every claim traces to a record | No claim without evidence behind it | FR-001, SC-001 |
| nothing is composed | 0 claims originate from a model | FR-001, SC-001 |
| a denial always appears | A run with a refusal produces a report mentioning it | FR-003, SC-002 |
| an unreconcilable claim is flagged | Emitted with a status, never omitted or softened | FR-005, SC-003 |
| one bad claim does not suppress the report | The rest is still emitted | FR-005 |
| the basis is stated | Chain and reconciliation status appear | FR-010 |
| the gate scores what a person reads | Same claim set to both consumers | FR-015a, SC-009 |
| a run observes before it ends | Each effect with an observer, under the allocation's identity | FR-006, FR-006b, SC-004 |
| a contradicted effect is legible | `did_not_happen` never reads as success | FR-006, data-model |
| an unreachable product is not success | `unverified_unreachable`, not asserted | FR-006a |
| a tool with no observer says so | `unverified_no_observer` | FR-016a |
| a killed run says so | `unverified_not_observed`, distinct from unreachable | FR-006c |
| observing changes no outcome | A late finding does not retroactively fail the run | FR-016c |
| the report performs no observation | 0 read-backs at report time | SC-004b |
| another tenant is indistinguishable | From a nonexistent run, including reason code | FR-008, SC-005 |
| a non-subject gets the report | And **no** result payload reaches them | FR-008a, SC-005a |
| no new access | Nothing visible that `read_evidence` would not return | FR-008b |
| the read is audited | Compiling writes the meta-audit record | FR-007 |
| surface parity | Same verdict, equivalent audit events, both transports | FR-015b, SC-010 |
| report fidelity is blocking | `report_fidelity` out of `OWED`, into `SUITES` | FR-013, SC-006 |
| fidelity measures precision and recall | Not a boolean | FR-013a, SC-007 |
| an unrunnable suite raises | Never skips, never empty-passes | FR-013a |
| nothing reads a report | 0 code paths consume one to decide anything | FR-014, SC-008 |
| nothing stopped running | Per-directory collection counts | SC-011 |

---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047.

- **Not that the report is present-tense.** Observations are facts about **run-end**. A product
  changed afterwards reads identically to one that never changed. **This is the limit most likely
  to be misread**, because the word "verified" invites a present tense the claim does not have —
  and it is the accepted cost of making read-back run under an authority bounded by the run
  rather than by the reader.
- **Not that the run was correct.** A faithful report of a run that did the wrong thing is a
  correct report.
- **Not that the records are complete.** The report is complete with respect to the records. If
  something happened and nothing recorded it, no row here can know — which is why FR-010 makes
  the report state whether its own basis verified.
- **Not that fidelity generalises.** The corpus is a set of recorded runs. A shape no case covers
  is a shape nothing checks.

---

## Known limits, recorded rather than closed

**The corpus is the soft spot, and ADR-0018 says so itself**: the labelled material events are
"the thing most likely to be skipped under schedule pressure, which would leave the decision
nominally in force and practically unenforced". A corpus of three easy runs passes exactly as
green as one of twenty hard ones. The mitigation available is a **floor** — `pack.toml`'s
`[evals.cases]` already declares a minimum per suite and the loader refuses below it — set from
runs containing the shapes that are hard: a denial, an unreconcilable step, a resumption, a
contradicted effect, a model that chose nothing.

**A truncated read is a confidently wrong report.** `EvidenceQueryRequest.limit` defaults to
1000; a 400-step dispatched run writes roughly seven entries per step. Compiling from a truncated
read would produce a report that is complete in form and missing most of the run. Handled as a
correctness requirement rather than a performance one — see the plan's Constraints.

---

## SC-011 baseline

`pytest --collect-only -q` per directory, taken on `main` at `bee9384` before any 021 code landed.

| Directory | Rows |
| --- | --- |
| `tests/conformance/adapter` | 12 |
| `tests/conformance/api` | 46 |
| `tests/conformance/authority` | 12 |
| `tests/conformance/choice` | 21 |
| `tests/conformance/deployment` | 22 |
| `tests/conformance/durability` | 50 |
| `tests/conformance/evidence` | 17 |
| `tests/conformance/identity` | 28 |
| `tests/conformance/mcp` | 56 |
| `tests/conformance/mcp_served` | 19 |
| `tests/conformance/packs` | 30 |
| `tests/conformance/portal` | 8 |
| `tests/conformance/reports` | 0 — created by this feature |

### The result (T059) — 2026-08-01

| Directory | On `main` | With 021 | Δ |
| --- | --- | --- | --- |
| `tests/conformance/adapter` | 12 | 12 | — |
| `tests/conformance/api` | 46 | **52** | +6 (`test_reports.py`) |
| `tests/conformance/authority` | 12 | 12 | — |
| `tests/conformance/choice` | 21 | 21 | — |
| `tests/conformance/deployment` | 22 | 22 | — |
| `tests/conformance/durability` | 50 | 50 | — |
| `tests/conformance/evidence` | 17 | 17 | — |
| `tests/conformance/identity` | 28 | 28 | — |
| `tests/conformance/mcp` | 56 | 56 | — |
| `tests/conformance/mcp_served` | 19 | 19 | — |
| `tests/conformance/packs` | 30 | 30 | — |
| `tests/conformance/portal` | 8 | 8 | — |
| `tests/conformance/reports` | 0 | **35** | +35 |

**SC-011 holds: no pre-existing directory lost a row.**

**Collection counts, not pass counts.** A row that stops being collected disappears silently; a
row that is collected and fails is loud. Only the first needs a baseline to be visible at all.
