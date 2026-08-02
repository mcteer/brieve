# Implementation Plan: Estate answering at real volume

**Branch**: `spec/029-estate-answering-at-volume` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-estate-answering-at-volume/spec.md`

## Summary

Three measured defects, one design: the router's estate vocabulary grows to the trail's own nouns
(US1); the read gains a **per-type bound** so a question's types stop competing with the estate's
noisiest ones (US2); and the held newest-window fix merges as US3. The question→types mapping —
the one new thing that could go wrong — is deterministic, derived from the same vocabulary the
router uses, and guarded by SC-007's five named questions plus a guidance regression set. FR-006's
"the answer says it was bounded" lands as a field on the **answer**, deliberately not on the
`ASK_ANSWERED` record — which is what keeps this feature out of sealed core entirely.

## Technical Context

**Language/Version**: Python 3.12 (the repository's)

**Primary Dependencies**: none new. The Postgres per-type bound uses a window function the
existing pg8000 path already speaks; the in-memory twin is a groupby.

**Storage**: the existing `audit_entries` table, read-only, through the existing evidence role.
No migration, no new table, no index change proposed without measurement.

**Testing**: hermetic property rows parametrized over **both** `EvidenceQuery` implementations
(the in-memory one directly; the Postgres one in the enclave lane against seeded volume), because
FR-008's lesson is that agreement between implementations that cannot disagree proves nothing.
Volume fixtures in the thousands — the InMemory sink handles that in milliseconds.

**Target Platform**: the deployed API and MCP surfaces, unchanged in assembly; the live tenant
holds 236,581 readable entries and is the final validation target (SC-007).

**Project Type**: core + read-path change, consumed by both answering surfaces.

**Performance Goals**: SC-002 at 63,947-entry volume; the per-type SQL must not regress the read
(one query, not one per type).

**Constraints**: the tenant bound and role-derived type narrowing are untouched (FR-005) — the
focus **intersects** with the visible set and can only narrow; the read path composes nothing
(ADR-0018); access records unchanged (ADR-0035); **no sealed-core touch** — `ASK_ANSWERED`'s
payload does not change, and `EvidenceQueryRequest` is a versioned seam, not audit schema.

**Scale/Scope**: one new module (`core/answering/focus.py`), one field on the query request, one
window-selection change per implementation, vocabulary growth in `routing.py`, one answer field,
two renderers.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No new dependency; a SQL window function and a groupby. |
| II — Total Interception | Pass | The read stays behind the same governed entry. |
| III — Fail-Closed | Pass | Focus **intersects** visible types — no focus falls back to visible, empty *visible* still refuses; no path widens on error. |
| IV — Zero Standing Credentials | Pass | Untouched. |
| V — Sealed Core, Versioned Seams | **Pass — no touch** | `ASK_ANSWERED` payload unchanged (FR-006 lands on the answer, not the record); audit schema, sinks and chain untouched. `EvidenceQueryRequest` gains one defaulted field — a versioned seam changing additively, the same shape 025 used for `event_types`. |
| VI — Lean by Default | Pass | The rejected alternatives (summarising, two-pass) were rejected partly on this ground. |
| VII — Anti-Fragmentation | Pass | One focus mechanism, one bound, both implementations changing together with rows that can see them disagree. |
| VIII — Eval-Gated Promotion | Pass | No model change. The eval-suite/role mismatch is recorded for decision (FR-009), not resolved. |
| IX — Evidence Over Claims | Pass | Every finding in the spec is a measurement; SC-007 closes against the live tenant. |
| X — The Decision Record Governs | Pass | ADR-0035/0018/0039 consumed unchanged; no amendment needed — the read's *bound* changes, not its governance. |

**Gate result**: PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/029-estate-answering-at-volume/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── conformance.md
└── tasks.md              (/speckit-tasks)
```

### Source Code (repository root)

```text
src/core/answering/
├── routing.py            # ESTATE_TERMS grows to the trail's vocabulary (US1)
├── focus.py              # NEW — question → the AuditEventTypes it concerns (US2)
└── estate.py             # the answer carries the window note (FR-006)

src/core/audit/
├── query.py              # EvidenceQueryRequest gains limit_per_type (defaulted, additive)
└── postgres_query.py     # newest-window fix (US3, cherry-picked) + per-type window SQL

tests/harness/memory_evidence.py        # the twin, changed together (FR-008)
src/surfaces/api/ask.py                 # passes focus ∩ visible; threads the window note
src/surfaces/portal/templates/ask.html  # shows "based on the N most recent …"

tests/
├── component/test_evidence_read_window.py   # extended: per-type rows, both-impl parametrization
├── component/test_estate_focus.py           # NEW — the mapping, incl. guidance regressions
└── conformance/answering/                   # volume row; SC-007's named questions
```

**Structure Decision**: focus lives in `core/answering` beside routing — it is the same kind of
decision about a question — and NOT in `core/audit`: the query layer stays ignorant of questions
and gains only a bound. The ordering fix on `fix/evidence-read-returns-the-newest-window` is
cherry-picked into the implementation branch as its first commit.

## Complexity Tracking

No violations. One narrowing to record: FR-008's "a row that can observe them disagreeing" is
delivered as property rows parametrized over both implementations — the in-memory one hermetically,
the Postgres one in the enclave lane against seeded volume — plus a hermetic SQL-shape assertion.
A fully hermetic behavioural differential would require a fake Postgres, which is a new dependency
(Principle VI) asserting fidelity to a database it is not. The contract states the split.
