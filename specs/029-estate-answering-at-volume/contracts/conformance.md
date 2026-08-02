<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 029 — estate answering at real volume

---

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Routing: SC-007's five questions reach the estate; the guidance regression set stays guidance | `tests/component/test_answering_routing.py` (or the routing rows' home) | Nothing | Planned |
| Focus: term→types mapping, intersection-only, empty-focus fallback | `tests/component/test_estate_focus.py` | Nothing | Planned |
| Per-type window: rare types not crowded out, newest-first selection, oldest-first return, `None` = today | `tests/component/test_evidence_read_window.py`, parametrized over implementations | Nothing (in-memory) | Planned |
| The same property rows against Postgres, seeded volume | the enclave lane | `make conformance` | Planned |
| SQL shape: `PARTITION BY` present exactly when `limit_per_type` is set | hermetic row beside the Postgres implementation | Nothing | Planned |
| Window note: present when truncated, absent when not, rendered by both surfaces | component rows + `tests/component/test_portal_asks.py` | Nothing | Planned |
| Scope untouched: focus never widens, tenant bound intact, access record unchanged | extended window rows | Nothing | Planned |
| **SC-007 against the live tenant**: the five failed questions answer at 236k entries | The deployed portal | The enclave; **named runner: Dan McTeer** | **Owed** |

**No sealed core is touched** — `ASK_ANSWERED`'s payload is unchanged because FR-006 lands on the
answer, not the record. No Principle V review arises; third feature running.

---

## What these rows assert

**The five questions that failed on 2026-08-02 route to the estate** — *"Which tools were
used?"*, *"What did the planner agent do?"*, *"Were any secrets read?"*, *"Which agents are
active?"*, *"What ran today?"* — and a guidance regression set (including *"How do I read a
secret?"*, the eager-routing shape F1 names) keeps routing to guidance. A term that cannot survive
both sets is a wrong term, not a reason to bend the tie-break.

**At volume with the measured skew, a question's types win.** The hermetic volume row rebuilds the
live composition — hundreds of `effect_observed`/`pre_decision` against tens of `run_start` — and
asserts a runs question receives predominantly run records. This is SC-002 in the exact shape that
failed.

**Focus only narrows.** The types passed to the read are always a subset of the visible set; an
empty intersection falls back to visible rather than refusing; and a caller with an empty
*visible* set still refuses before any read, exactly as 025 built it.

**The per-type bound is honest at its edges.** `limit_per_type=None` reproduces today's read
byte-for-byte; zero returns nothing (the `[-0:]` trap the window rows already pin); selection is
newest-per-type while the return stays oldest-first overall.

**Both implementations, one behaviour — with teeth.** The property rows run against both; the
enclave half runs the Postgres implementation against seeded thousands; and a mutation check (the
same discipline the window fix used: flip one implementation, watch the rows fail) is performed at
implement and recorded in this contract's status.

**The window note tells the asker, and only when true.** Present with counts when a requested type
truncated; absent otherwise, so a small estate renders exactly as before. Both surfaces render it;
the portal's a11y lane audits the state.

---

## What these rows refuse to assert

**They do not assert answer quality** — the model's claims are the eval lane's business. These
rows end at "the evidence handed to the model is about the question, current, and honestly
labelled".

**They do not assert role visibility** (FR-009). Whether `operator` should see authority records
is recorded for decision, and the fourth finding — *"which runs were denied?"* declining for an
operator — remains correct behaviour under this contract.

**They do not resolve the eval-suite/role mismatch.** 025's `estate_state` suite scores a question
no operator can ask; that is recorded as an owed decision (re-aim the suite, or score it as
`compliance-analyst`), not patched here.

**They do not claim a hermetic behavioural differential between the implementations.** That would
require a fake Postgres — a new dependency asserting fidelity to a database it is not. The split
(hermetic property rows + enclave behaviour + SQL-shape assertion) is stated rather than papered
over, because finding three survived on exactly that kind of unstated gap.

---

## The row that would have caught each finding

- **Routing**: SC-007's questions as a fixture — the set the first user actually asked.
- **Starvation**: the volume row with the measured skew. Every prior row used tens of records,
  where no bound truncates and no type competes.
- **Stale window**: already written (`test_evidence_read_window.py`), verified to fail against the
  old behaviour before being trusted.
