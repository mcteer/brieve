# Phase 1 Data Model: Wire resume into the dispatched path

**Feature**: `specs/014-dispatched-resume` | **Date**: 2026-07-29

Three records — one new, two extended — and one payload. Nothing here is a new store: the
grant record joins the durability schema ADR-0026 always described it as living beside.

## Grant record *(new table: `grants`, durability schema)*

| Field | Type | Notes |
| --- | --- | --- |
| `grant_id` | text, primary key | What checkpoints have referenced since 005 — now it resolves |
| `subject_user_id` | text | Whose consent this is |
| `agent_definition_id` | text | What it consents to being done by |
| `requested_scope` | jsonb | Tool names and product actions, as `DelegationGrant` holds them |
| `issued_at` | timestamptz | |
| `expires_at` | timestamptz | The bound US4 checks. Duration was already ceilinged by the definition's maximum run duration at issuance |

**Properties**:

- **Consent metadata, zero credential material.** Subject, definition, scope, expiry — no
  token, no password, no lease. The existing no-secret conformance sweep extends to this
  table verbatim (FR-012), and that extension is a row, not a remark.
- **Written once at issuance, never updated.** A grant's terms do not change; a new consent
  is a new grant. Expiry is read from the record, not enforced by mutation.
- **Loaded by the checkpoint's `grant_id` at resume.** Absent → the resume refuses
  (`grant_missing`); a missing grant is not "no consent required". F1's latent bug — the
  credential id written where the grant id belongs — is fixed in the same change, or this
  table indexes garbage from day one.

## Checkpoint record *(extended: one column)*

| Field | Type | Notes |
| --- | --- | --- |
| `resume_count` | integer, not null, default 0 | How many times this run has been revived. **On the checkpoint because it must survive the disruption it counts** — memory resets, and the suspended-run index row is forgotten on dispatch, which is exactly when the count matters |

**Properties**:

- **Incremented after the ownership claim succeeds**, so a superseded instance cannot burn
  attempts it was never entitled to spend.
- **Compared against a platform constant** (`RESUME_ATTEMPT_CAP = 5`), set in core beside
  the other bounds. Never from workflow code, the definition, or dispatch metadata — a
  bound the bounded thing can raise is not a bound (FR-009c).
- **Exhaustion is terminal**: state STOPPED, `stop_reason = "resume_attempts_exhausted"`,
  the same posture as expired consent. It must not suspend again — a run past its cap
  waiting on a dependency would wait for a revival that can never come.

## Resume dispatch metadata *(extended: one flag)*

| Field | Carried as | Notes |
| --- | --- | --- |
| `resume` | dispatch meta → `RUN_RESUME` env | **Declared by the dispatcher, never inferred** (D1). Set only by the sweeper's resume dispatch. A fresh dispatch carrying a resume's identifiers stays a fresh dispatch — the id collision edge case resolves to "not a resume" because the flag, not the identifiers, is the discriminator |

## `RUN_RESUMED` audit event *(extended: one enum member)*

Payload:

| Field | Notes |
| --- | --- |
| `run_id` | |
| `attempt` | The `resume_count` this revival became — 1-based, so the trail reads "attempt 3 of 5" without arithmetic |
| `outcome` | `continued` \| `stopped` \| `suspended` — the three `ResumeDecision` states, one event (D4, the 013 `MODEL_GATE` pattern: one type, the distinction in the payload) |
| `reason` | The stop reason or awaited dependency; empty when continued |
| `completed_steps` / `pending_steps` | Counts, not contents — what an investigator needs to see "it skipped 3 and ran 2" without the trail carrying step payloads |

**Properties**:

- **Written by the entrypoint** — the caller that owns the sink and the tenant, on the same
  reasoning that put the `MATRIX_FALLBACK` emit there (013): the library returns, the
  caller records.
- **Written before any pending step executes**, so an investigator reading in order sees
  the revival before its consequences.
- A resumed run that also fell back to a different qualified cell records `MATRIX_FALLBACK`
  separately — two events, because "this run was revived" and "the model that ran was not
  the model pinned" are different questions (the D12/013 rule).

## State transitions *(no new states)*

`SUSPENDED → ACTIVE` (sweeper revival, under the cap) and `SUSPENDED → STOPPED`
(`resume_attempts_exhausted`, at the cap) are the only transitions this feature makes
reachable from production. Both states and both transitions already exist in the library;
what is new is that a dispatched run can actually traverse them.
