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

002 shipped `ACTIVE` and `REFUSED` only, which was sufficient while nothing had to survive a
restart. It is not sufficient now: a resumed run must be able to tell a run that *finished* from
one that was interrupted, and a run stopped by a bound is neither refused nor waiting.

| State | Meaning | New? |
| --- | --- | --- |
| `ACTIVE` | Running | 002 |
| `REFUSED` | Refused at start — authority insufficient | 002 |
| `COMPLETED` | Finished its work | **new** |
| `STOPPED` | Halted by an execution bound; `stop_reason` records which | **new** |
| `PARKED` | Waiting for something only a human can supply | **new** |

`GovernedRun` gains `stop_reason: str | None`, set on the transition to `STOPPED` so FR-011's
"with the reason recorded" is satisfied by data rather than by a log line.

Three distinctions worth keeping apart, because collapsing any of them loses something an
operator needs:

- **`PARKED` is waiting, not failed.** Durable, queryable, and resumable once the blocking
  condition clears. Modelling it as an error would lose exactly the signal that matters.
- **`STOPPED` is not `PARKED`.** A bounded run is not waiting for consent or for a human to
  resolve a step; nothing will unblock it. Resuming it would defeat the bound.
- **`COMPLETED` is not `ACTIVE`.** Without it, a resume attempt against a finished run has no way
  to recognise that there is nothing to resume, and would re-enter the loop.

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

### DatabaseCredential

The Postgres provider's connection credential, obtained from the control-plane Vault's dynamic
database secrets engine under the workload's attested identity. Distinct from `TaskCredentialRef`:
that one bounds what the *agent* may do, this one is how the *platform* reaches its own store.

| Field | Rules |
| --- | --- |
| `username` / `password` | Vault-minted, per workload. Never checkpointed, never logged |
| `lease_id` | Vault's handle for renewal and revocation |
| `expires_at` | Wall-clock expiry, from the lease duration |

**Validation**: obtaining one requires an attested identity — there is no path that accepts a DSN
with a password (FR-017a).

**Expiry is expected, not exceptional.** The lease is on the order of an hour and a durable run is
designed to outlive that, so a credential ending mid-run MUST NOT fail the run.

Re-authentication is **reactive**: the provider attempts the operation, and on an authentication
failure obtains a fresh credential from Vault and retries **once**. The database's rejection is
the authoritative signal — a renewal timer would predict only ordinary expiry and miss a
credential revoked early, a lease invalidated by a Vault operation, or a database restarted
underneath the run, and it would require Vault, Postgres, and the harness to agree on a clock.

The retry is bounded on purpose: once per operation, only on authentication failure — not on
connection-refused or permission-denied-on-object — and the second failure surfaces. An unbounded
retry would spin against a real misconfiguration, and one is reachable in the enclave today:
destroying the Postgres volume resets the database to its bootstrap password while Vault holds the
rotated one, so every credential fails auth. That must read as a failure, not as a hang.

Reconnection is a provider-internal concern and changes no guarantee above the seam: it does not
touch the grant, the lease, or per-step authority. A run whose *grant* expires still parks
(FR-005) — that is consent, not plumbing, and the two must not be conflated.

## State transitions

```text
[grant issued] ──► ACTIVE ──► (steps, each under a fresh per-step credential)
                     │
                     ├─ work finished ─────────────► COMPLETED
                     ├─ bound reached ─────────────► STOPPED (stop_reason recorded)
                     ├─ lease superseded ──────────► writes rejected (this instance is done)
                     │
                     └─ disruption
                            │
                            ▼
                     resume attempt (NEW allocation, NEW attested identity)
                            │
                            ├─ run already COMPLETED ► nothing to resume
                            ├─ run STOPPED ─────────► not resumable; the bound stands
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
5. Reaching any execution bound moves the run to `STOPPED` with `stop_reason` recorded.
6. Correlation ID and hash chain survive the disruption boundary.
7. Postgres access uses short-lived per-workload credentials — no shared standing credential.
8. An authentication failure against the database triggers one fresh-credential retry, never run
   failure; a second failure surfaces. Grant expiry, by contrast, parks — plumbing and consent are
   not the same thing.
9. A resume attempt against a `COMPLETED` or `STOPPED` run does not re-enter the run loop.
