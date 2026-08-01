<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 022 — the trail records who looked

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Most of this feature is hermetic.** Recording happens inside the shared functions both
transports call, so "does a read write a record", "does the record exclude content", "does a
refused read record", and "does an unrecordable read fail" all need is an in-memory sink and a
fake subject. That is deliberate: a gate needing infrastructure is a gate that eventually stops
running.

Three groups, and only the second needs a served surface:

| Group | Where | Needs |
| --- | --- | --- |
| Recording, exclusion, refusal, fail-closed | `tests/component/test_record_access.py` | Nothing |
| **The reader stream is reachable through the governed path** | `tests/component/test_record_access.py` (T023a) | Nothing |
| **Authorization unchanged by recording** | `tests/component/test_record_access.py` (T023b) | Nothing |
| Both surfaces answering identically, including the failure path | `tests/conformance/mcp`, `tests/conformance/api` | The enclave — both transports served |
| The claim matches behavior | `tests/component/`, derived from the catalogue | Nothing |
| Sealed-core digest unmoved | `tests/unit/test_audit_chain.py` | Nothing |

**SC-002 is the exception and cannot be made hermetic**, because it is written not to be: *"a trail
entry naming the reader, discoverable through the governed read path by the run's correlation id —
demonstrated against a served surface, not a test double."* That wording is deliberate. This
feature exists because a defect survived a full green suite and was found only by connecting a
real editor to a running service; a spec closing it against a test double would be repeating the
mistake it was written about.

**The enclave lane is `workflow_dispatch` only** — it has not run on pull requests since #95. So
the second group is executed by **no automated check**, and the constitution is explicit:

> A blocking row that no automated check executes MUST have a named party responsible for running
> it before merge, recorded in that same contract; merging without that run is a gate regression,
> and "the check is not automated" is not a defence.

| | What it is | Who | Status |
| --- | --- | --- | --- |
| The enclave rows | `make conformance` in full, on a live enclave, before merge | **Dan McTeer** | **Owed** |
| SC-002 served demonstration | Read a run's result through a served surface; find the reader in the trail | **Dan McTeer** | **Owed** |
| Principle V review | Security-maintainer review of four additive `AuditEventType` members | **Dan McTeer** | **Owed — requested on the PR** |
| Principle X amendment | ADR-0035 amended in **this** change, not a follow-up (FR-012, T037–T039) | **Dan McTeer** | **Owed** |

*The last row is not a conformance row and no check executes it — which is exactly why it belongs
here. `plan.md` names it as a gate obligation and `quickstart.md` points at this table for it;
before analysis pass 6 it was named in both of those and in neither of the places that would stop a
merge.*

**None of the three is discharged by this plan.** They are recorded here so that merging without
them is visibly a gate regression rather than an oversight.

---

## What these rows assert

**A covered read leaves a record.** For each of the six — `list_runs`, `get_run`,
`get_run_result`, `list_threads`, `get_thread`, `create_thread` — a successful call appends to
`record-access:{tenant}` naming the caller, the operation, and the target's correlation id where
one exists.

**A stop leaves a record naming who stopped it.** `stop_run` appends `RUN_STOPPED` to the **run's
own stream**, not the reader stream — it is an act performed on the run rather than a read of it,
so FR-005a does not apply and the symmetry with `THREAD_DELETED` holds. This is the seventh covered
operation and the only write among them.

**The record is reachable.** A `record_read` entry is returned by the governed evidence read for
its own tenant and refused for another. FR-005b ends *"a record nobody can query is not a record"*,
and this row is what makes that checkable rather than assumed — it was missing from the first draft
of this contract, and the served demonstration that should have exposed the gap was querying
Postgres directly and skipping the governed path entirely.

**A record carries no content.** A credential-shaped value planted in a payload the reader is not
asked for reaches no entry (SC-006). This is asserted by planting, not by reading the code.

**A refused read is recorded, and the trail keeps what the caller cannot see.** `no_such_record`
and `outside_tenant` remain indistinguishable in the response and distinct in the entry (SC-007).

**An unrecordable act fails.** With the sink made to fail, all six reads refuse and return nothing, and `stop_run` refuses and leaves the run running
(SC-009) — including listings, which is the case with no precedent and the one most likely to be
softened later for convenience.

**A read never touches the chain it read.** After reading a run, that run's chain is
byte-identical, and a report compiled for it afterward carries no claim about who read it
(SC-010). This is the row that protects 021.

**The two catalogue operations stay unrecorded** (SC-011) — pinned deliberately, so widening is a
decision someone makes rather than a drift nobody notices.

**The claim matches behavior.** The surface's governance sentence is derived from the catalogue's
dispositions, so it cannot assert coverage the catalogue does not declare (SC-003).

**No prior entry's hash moves.** The pinned digest is unchanged and the four new members are
present (SC-005).

---

## What these rows refuse to assert

**They do not assert that reads are authorized correctly.** A row here passing says a read was
*recorded*, not that it was *permitted rightly* — and conflating the two would let a scoping
regression hide behind a green audit row.

**They do assert that authorization did not change** (T023b, SC-004a): the seven operations answer
identically to before this feature for the same caller — same records, same refusals, same status.
That is a narrower claim than "authorized correctly", and the distinction is the point.

*An earlier draft of this section said FR-015 "is covered by the rows that already exist" and left
it there. Analysis rejected that: existing rows covering something incidentally is not the same as
covering it, and a negative requirement with no check is a hope. The disclaimer is kept because it
is still true of correctness; the added paragraph is what the feature actually proves.*

**They do not assert that the trail is complete for anything outside the seven.** Seven operations
already audited before this feature and are not re-proved here; `start_run` is covered downstream
and is not re-proved either; two are pinned as recording nothing. A reader of these rows learns
about nine operations' coverage and must not infer the rest.

**They do not assert present-tense truth about a reader.** A record says someone read something at
a time. It does not say they still hold it, still have access, or have not shared it. That limit
is the same one 021 stated about observations, and it is worth stating again because "who read
this" invites a durability the record does not have.

**They do not assert that recording deters anything.** A trail that records reads is evidence
after the fact. It prevents nothing at the moment of reading, and a control that were required to
*prevent* an improper read would be an authorization change — explicitly out of scope (FR-015).

---

## The one row that would have caught the original defect

Every row above is new. It is worth naming which of them would have failed on 2026-08-01, before
this feature, because a suite that grows without answering that question grows without learning:

**The claim-versus-behavior row (SC-003).** It compares the surfaces' governance sentence against
measured dispositions. On the pre-022 codebase the sentence claimed every operation was recorded
and nine were not, so it fails immediately. Nothing else in the existing 857-test suite (collected
2026-08-01) compares
what the platform *says* to what it *does* — including
`tests/component/test_operations_audited.py`, whose name promises exactly that and whose rows
assert unauthenticated refusal instead.
