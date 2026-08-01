<!-- SPDX-License-Identifier: Apache-2.0 -->
# Contract: what a report says, and what it refuses to say

---

## What a request needs, and what it may not supply

A run id. **Nothing else** — and in particular no tenant, on the rule
`EvidenceQueryRequest` already enforces: the bounding dimension comes from the authenticated
subject and is never accepted from the caller, because a caller-supplied tenant is a request to
widen scope.

| Who asks | What they get |
| --- | --- |
| Anyone authenticated in the run's tenant | The report. **Including people who did not start the run** — auditors, compliance, operators, change reviewers |
| Someone in another tenant | Exactly what a nonexistent run returns. No discriminating signal, including reason code and message text |
| Anyone at all | **Never** the run's result payload — that is `get_run_result`'s, and it is subject-restricted |

**A report grants no access the caller does not already have.** Every claim compiles from entries
`read_evidence` would have returned to the same caller. If a report can show something the
evidence path cannot, that is a widening and a defect (FR-008b).

---

## What every claim carries

A statement, the evidence behind it, and a status from the closed vocabulary in
[data-model.md](../data-model.md). **No claim is ever emitted bare.**

The four unsupported statuses are kept apart because each sends a reader somewhere different:

- `unverified_unreachable` → go look at the product.
- `unverified_no_observer` → go look at the tool's registration.
- `unverified_not_observed` → go look at why the run never finished.
- `unreconciled` → go look at the records; they disagree with each other.

Collapsing them into one honest "unknown" would be defensible and useless.

---

## What the platform guarantees

**Every claim traces to a record.** Nothing is composed, inferred, or summarised by a model.
The compiler receives entries and returns a report; it holds no query and no credential, so it
*cannot* reach anything the governed read did not already return.

**Nothing is softened.** A claim that cannot be reconciled is emitted with the status that says
so. The report is still emitted — one unreconcilable claim does not suppress the rest.

**The gate scores what a person reads.** There is one compiled object. No projection, no
gate-only variant, no field visible to one consumer and not the other (FR-015a).

**Observations are the run's, not the report's.** They are made inside the allocation, under an
attested identity bounded by the run's ceiling, before the run reaches a terminal state. A report
performs no read-back and holds nothing that would let it.

---

## What it does NOT guarantee

**That the report is complete in the sense a reader might assume.** It is complete with respect
to the *records*. If something happened and nothing recorded it, the report cannot know — which
is why FR-010 makes the report state whether its basis verified, and why the scope field exists.

**That the product still looks the way the report says.** Observations are facts about run-end.
A product changed afterwards reads identically to one that never changed. **This is the deliberate
cost of the Principle IV redesign** and it is the single most likely thing for a reader to
misread, because "verified" invites a present tense the claim does not have.

**That the run was correct.** A report faithfully describing a run that did the wrong thing is a
correct report.

**That fidelity is continuously proven.** The gate scores a corpus of recorded runs. A shape no
case covers is a shape nothing checks — see the conformance contract's known limits.
