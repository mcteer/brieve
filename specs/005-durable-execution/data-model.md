# Data Model: Durable Execution

**Feature**: `specs/005-durable-execution`
**Date**: 2026-07-25

## Entities

### DelegationGrant

The requesting user's durable consent to a task. The human-meaningful unit.

| Field | Type | Rules |
| --- | --- | --- |
| `grant_id` | `str` | Opaque, non-secret |
| `subject_user_id` | `str` | The consenting human; non-empty |
| `agent_definition_id` | `str` | Non-empty; supplies the ceiling that bounds this grant |
| `requested_scope` | `AuthorityScope` | What the user consented to; never widened afterwards |
| `issued_at` / `expires_at` | `datetime` | Lifetime ceilinged by the definition's maximum run duration |

**Validation**: Blank subject, blank definition, or an expiry beyond the definition's maximum
refuses issue. **Holds no credential material** — a grant is a record of consent, not authority.

**Relationships**: One grant to many `TaskCredentialRef`. Referenced by a checkpoint via
`grant_id` only.

### TaskCredentialRef *(unchanged from 003)*

Short-lived per-step authority, now manufactured **under** a grant. Never checkpointed. Its
absence from durable state is what makes resume-re-authenticates trivially true.

### CheckpointBlob *(extended from 004)*

| Field | Type | Rules |
| --- | --- | --- |
| `blob_id` | `str` | Opaque |
| `payload` | mapping | Framework/run state only |
| `correlation_id` | `str` | Join metadata; not authority |
| `grant_id` | `str` | **New** — which consent this run proceeds under |
| `step_index` | `int` | **New** — resume point |
| `written_by` | `str` | **New** — allocation identity that wrote it; fencing input |

**Validation**: MUST NOT contain credential, token, or secret material — enforced structurally as
in 004, not by convention, and asserted for every provider (FR-003).

### RunLease

The single-writer claim on a run.

| Field | Type | Rules |
| --- | --- | --- |
| `run_id` | `str` | One live lease per run |
| `holder_identity` | `str` | Allocation identity of the current holder |
| `acquired_at` | `datetime` | |

**Validation**: Acquisition is a conditional update — a new holder supersedes the old atomically.
A write or tool call whose `holder_identity` is not current is **rejected on comparison**, not
raced (FR-009).

### IntentRecord / ResultRecord

The bracket around a step whose effect is not naturally repeatable.

| Field | Type | Rules |
| --- | --- | --- |
| `run_id`, `step_index` | | Identify the bracketed step |
| `tool_name` | `str` | Must be a registered tool |
| `idempotency_key` | `str` | **Stable across retries of the same step** (FR-010) |
| `recorded_at` | `datetime` | Intent before the effect; result after |

**Validation**: An intent with no result is exactly the interrupted case resume must resolve by
observation. Neither record holds arguments that could carry secret values.

### ObservationOutcome

The result of re-reading external state for an interrupted step. **Three-way, deliberately.**

| Value | Meaning | Resume behaviour |
| --- | --- | --- |
| `happened` | The effect is present | Do not repeat; record resolution |
| `did_not_happen` | The effect is absent | The step may proceed |
| `cannot_determine` | The system cannot answer conclusively | **Park** for human resolution (FR-008) |

A two-way outcome would force a guess in exactly the case where guessing is the failure.

### ExecutionBounds

| Field | Rules |
| --- | --- |
| `max_duration` | Wall-clock ceiling for the run |
| `max_steps` | Loop limit |
| `stuck_wait_timeout` | No-progress watchdog |

**Validation**: Reaching any bound stops the run with the reason recorded (FR-011). Checked where
the run advances, not by a background timer.

### RunState *(extended from 002)*

`ACTIVE` → `REFUSED` (002) → **`PARKED`** (new).

Parked is *waiting*, not failed: durable, queryable, and resumable once the blocking condition
clears. Modelling it as an error would lose the distinction an operator most needs.

### DurabilityProvider *(extended from 004 — breaking)*

| Method | Behaviour |
| --- | --- |
| `save` / `load` | Unchanged from 004 |
| `acquire_lease(run_id, holder_identity)` | Conditional; supersedes atomically |
| `check_lease(run_id, holder_identity)` | Rejects a superseded holder |
| `record_intent` / `record_result` | Bracket persistence |
| `open_intents(run_id)` | Brackets awaiting resolution on resume |

004's protocol cannot satisfy the new guarantees, so this is a genuine break. Pre-1.0, one
in-repo implementation, no external consumers — the exemption 004 recorded applies, declared
rather than assumed.

## State transitions

```text
[grant issued] ──► ACTIVE ──► (steps, each under a fresh per-step credential)
                     │
                     ├─ bound reached ─────────────► stopped, reason recorded
                     ├─ lease superseded ──────────► writes rejected (this instance is done)
                     │
                     └─ disruption
                            │
                            ▼
                     resume attempt (NEW allocation, NEW attested identity)
                            │
                            ├─ grant expired ──────► PARKED (await fresh consent)
                            ├─ checkpoint unreadable ► PARKED / refuse
                            │
                            ▼
                     re-observe open intents
                            ├─ happened ───────────► skip step, continue
                            ├─ did_not_happen ─────► redo step, continue
                            └─ cannot_determine ───► PARKED (await human)
```

## Validation summary (normative)

1. No checkpoint written by any provider contains credential material.
2. Resume manufactures authority under the surviving grant; no path accepts a checkpointed
   credential — and none is written for a path to accept.
3. A superseded lease holder's writes and tool calls are rejected by identity comparison.
4. An interrupted non-repeatable step is resolved by observation; `cannot_determine` parks.
5. Reaching any execution bound stops the run with the reason recorded.
6. Correlation ID and hash chain survive the disruption boundary.
7. Postgres access uses short-lived per-workload credentials — no shared standing credential.
