# Phase 1 Data Model: Northbound API Operations

**Feature**: `specs/011-api-operations` | **Date**: 2026-07-28

Two new records, three response shapes, and one reserved key. Everything else this feature
touches already exists and is deliberately unchanged.

---

## Run index record *(new)*

Written by `dispatch()` in the same motion as the dispatch itself, from arguments dispatch
already receives. Read by list, result, and stop. **Never read by resume** — the checkpoint
stays authoritative for run state, and this is a candidate list for enumeration exactly as
`suspended_runs` is a candidate list for the sweeper.

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | TEXT, primary key | As dispatch assigns it |
| `correlation_id` | TEXT | The join to everything else |
| `subject_user_id` | TEXT | Who started it — the field `checkpoints` never had |
| `tenant_id` | TEXT | The boundary every read filters on **first** |
| `agent_definition_id` | TEXT | So a listing can say what an entry *is* |
| `created_at` | TIMESTAMPTZ | Keyset cursor component |

**Validation / properties**:

- Insert-only from the dispatch path. Nothing updates it; state lives on the checkpoint.
- Every query filters `tenant_id` first and `subject_user_id` second; there is no
  cross-subject query on this surface at all.
- **Starts empty, stays honest**: no backfill. A backfill from audit would launder the
  forensic path through a migration script.

## Authority change-request record *(new)*

Written when submission returns a wrap accessor (the 202 path). Read by collect.

| Field | Type | Notes |
| --- | --- | --- |
| `accessor` | TEXT, primary key | What Vault's status endpoint takes |
| `requester` | TEXT | Only this subject may collect |
| `tenant_id` | TEXT | Another tenant's request answers as not-exists |
| `claim_name` / `claim_value` / `role` | TEXT | What was asked, so collect can say |
| `submitted_at` | TIMESTAMPTZ | |

**The record is the authorization, not a cache.** Vault's `sys/control-group/request`
takes an accessor and answers anyone who presents one — so without this record the
accessor is a bearer capability that crosses tenants. Collect resolves the record first,
refuses unless the caller is its requester in its tenant, and only then polls Vault.
Vault stays authoritative for the *disposition*; this record is authoritative for *who
may ask*.

## Run result *(reserved key, not a table)*

The terminal checkpoint's `payload` carries the result under `"__run_result__"`. No new
column, no new table: the terminal checkpoint is the one place a run's ending is already
recorded, and two records of one ending will eventually disagree.

**The three-way disposition (FR-007)**, computed from what already exists:

| Checkpoint state | Result key | Answer |
| --- | --- | --- |
| No terminal state | — | *Not finished* |
| Terminal | Present | *The result* |
| Terminal | Absent | *Ended without one* — with `stop_reason` as the why |

A single empty response would conflate all three, which is the defect FR-007 names.

## Agent definition — public view *(response shape)*

Built from the **harness-authority record and the registration's display fields only**.
The credential-issuance jurisdiction (`ceiling_policies`, `allowed_paths`) never appears —
FR-014, and ADR-0050's disjointness surfacing as a response-shape rule.

| Field | Source | Notes |
| --- | --- | --- |
| `agent_definition_id` | registration | |
| `description`, `owner` | registration | Display fields |
| `may_start` | computed | `subject scope ∩ ceiling ≠ ∅` — see below |

**`may_start` is intersection-non-empty, not subset.** 002 refuses only requests that
*exceed* scope, so a subject covering part of a ceiling can start that agent with a
narrower request. Subset would mark startable agents unavailable — the inverse of C2.

**The C2 asymmetry, stated where the shape is defined**: within a tenant, every
registered definition appears (marked); across tenants, nothing does. Discoverability
stops at the tenant boundary.

## Run summary *(response shape)*

What a listing returns per run — enough to identify and choose, deliberately less than
run detail: `run_id`, `correlation_id`, `agent_definition_id`, `state`, `created_at`.
State comes from the checkpoint at read time; the index supplies everything else.

## Pagination cursor *(response shape)*

Keyset: `(created_at, run_id)` of the last returned row, opaque to the caller, stateless
for the platform (FR-005). **The cursor must not encode the total** — a count is exactly
the withholding disclosure FR-004 forbids.

---

## Refusal shapes (FR-020)

The trail and the response answer different questions:

| Situation | Caller sees | Trail records |
| --- | --- | --- |
| No such run / change / definition | not found | `no_such_record` |
| Exists, another tenant | **not found** — identically | `outside_tenant` |
| Yours, but not permitted (e.g. stop by non-starter) | refused | `not_permitted` |
| Scope unresolvable | refused | the 010 reason code, unchanged |

The caller-facing collapse of the first two is the tenant boundary; the trail's
distinction is what lets an investigator see probing.
