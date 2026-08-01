<!-- SPDX-License-Identifier: Apache-2.0 -->
# Data model: 021 — a report compiles from records

Three new entities, one new audit event, and nothing stored beyond the trail.

---

## RunReport

A typed account of one run. **Compiled on demand and never persisted** (FR-014a): it has no
identity, no lifecycle, and does not exist between requests.

| Field | What it is | Rules |
| --- | --- | --- |
| `run_id` | Which run | From the caller; the governed read bounds it by tenant |
| `disposition` | Running, or how it ended | A report of an unfinished run must not read as an account of a finished one (FR-002) |
| `claims` | Every statement, in order | Each carries its own status — see `Claim` |
| `basis` | Whether the evidence verified | Chain, and reconciliation where a second copy exists (FR-010) |
| `scope` | What this report can and cannot evidence | ADR-0032 — stated, never left to inference (FR-012) |

**What it does NOT carry**: the run's **result payload**. That is subject-restricted by
`get_run_result`, and a report is tenant-scoped — so carrying it would route around the
restriction (FR-008a). This is the one field whose absence is a security property rather than a
scoping choice.

---

## Claim

One statement, together with what it was checked against.

| Field | What it is | Rules |
| --- | --- | --- |
| `subject` | What the claim is about — a step, a tool, the run | From the records, never invented |
| `statement` | What is being asserted | Populated from evidence (FR-001) |
| `status` | How well it is supported | Closed vocabulary — see below |
| `evidence` | Which record(s) support it | Every claim traces to one (SC-001) |

**A claim is never dropped for being unsupportable.** It is emitted with a status that says so
(FR-005), because a report that silently omits what it could not verify is more dangerous than
one that never claimed to verify anything — it terminates the investigation.

### `ClaimStatus` — the closed vocabulary

| Value | Means | Why it is its own value |
| --- | --- | --- |
| `from_record` | The records say this, and nothing more was required | The ordinary case |
| `observed` | The product was asked at run end and confirmed it | The strongest claim available |
| `contradicted` | The product was asked and said the effect did **not** land | The failure ADR-0018 opens with. Must be impossible to read as success |
| `unverified_unreachable` | The product could not be reached at run end | An unreachable product is not evidence of success, and not of failure either (FR-006a) |
| `unverified_no_observer` | The tool has no observer, so nothing could ask | A fact about the *tool's registration*, and it sends a reader somewhere different from the value above (FR-016a) |
| `unverified_not_observed` | The run never reached a terminal state, so it never observed | A killed run and an unreachable product are different facts (FR-006c) |
| `unreconciled` | The records disagree, or a bracket opened and never closed | Flagged in place, never softened (FR-005) |

**Four `unverified`/`unreconciled` values rather than one**, on the reasoning 020 applied to
choice outcomes: each sends a reader to a different place — the product, the tool's registration,
the run's ending, or the records themselves. A single "unknown" would be honest and useless.

---

## Observation *(recorded, new to the trail)*

What the run learned by asking a product at the end, carried as an audit event.

| Field | What it is |
| --- | --- |
| `run_id`, `step_index`, `tool` | Which effect |
| `idempotency_key` | The bracket key the observer was asked about |
| `outcome` | `happened` / `did_not_happen` / `cannot_determine` — `ObservationOutcome`, unchanged |
| `detail` | The observer's own words about the basis |

**The type already exists.** `core.observation.types.Observation` is three-way and its docstring
already argues for the third value: *"A two-way outcome would force a guess in exactly the case
where guessing is the failure."* This feature records it rather than defining it.

**Made by the allocation, under its own attested identity** (FR-006b). No process acting on a
reader's behalf ever calls an observer — that was the Principle IV failure, and the placement is
the fix.

### The state transition that matters

```
   effect executed ──▶ run reaches a terminal state
                              │
                              ├── observer exists ──▶ observe() ──▶ recorded
                              │                          │
                              │                          ├── happened          ──▶ observed
                              │                          ├── did_not_happen    ──▶ contradicted
                              │                          └── cannot_determine  ──▶ unverified_unreachable
                              │
                              └── no observer ──────────────────────▶ unverified_no_observer

   effect executed ──▶ run killed, never terminal ─────▶ unverified_not_observed
```

**Recording an observation never changes the run's outcome** (FR-016c). A run that did its work
and then found an effect missing completed and produced a finding; letting the observation fail
the run retroactively would give a reporting mechanism power over what it reports.

---

## What is NOT modelled

- **A report store.** There is none, deliberately (FR-014a).
- **A report identity.** Nothing cites "report #47"; a citation names the run.
- **Prose.** A model may one day write over a compiled report; that is a separate feature with
  its own eval, and ADR-0018 draws the line here.
- **Drift after run end.** Accepted cost of the Principle IV redesign, recorded in the spec's
  fourth clarification rather than left to be discovered as a missing feature.
