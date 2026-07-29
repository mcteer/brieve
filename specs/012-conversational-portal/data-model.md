# Phase 1 Data Model: The Conversational Portal

**Feature**: `specs/012-conversational-portal` | **Date**: 2026-07-29

Two tables, one input record, two trail events, and a session that is deliberately not a
record. The organizing rule comes from ADR-0051 (drafted in this feature): **the trail is
the record; the thread tables are a view.** Everything below is shaped by which side of
that line it sits on.

---

## Thread *(new table: `threads`)*

The view's spine. Created empty by `create_thread`, hard-deleted by `delete_thread`.

| Field | Type | Notes |
| --- | --- | --- |
| `thread_id` | TEXT, primary key | Minted at creation; opaque |
| `correlation_id` | TEXT, unique | **The join to the trail.** One correlation ID per thread — every turn event, and every run the thread starts, chains under it or references it |
| `subject_user_id` | TEXT | The owner. Only this subject sees or continues the thread |
| `tenant_id` | TEXT | Filtered **first** in every query, as 011's tables do |
| `title` | TEXT, nullable | Display only. Null at creation (the thread is empty); set **once** at the first accepted turn from the message's leading fragment; never updated after — the contract's no-rename rule, held by there being no operation that could |
| `created_at` | TIMESTAMPTZ | Keyset cursor component for listing |

**Properties**:

- Tenant-scoped and subject-owned: every read filters `tenant_id` then
  `subject_user_id`; another tenant's thread answers as absent (FR-007) — the same
  collapse, in the same place, as `run_index.get`.
- **Hard-deleted.** After D4, deletion loses nothing the trail lacks; a soft-delete
  shadow copy would retain every message in a table whose deletability is justified by
  the trail being the record.
- Never on the resume path; droppable, like everything in `core/runs` and for the same
  reason.

## Turn *(new table: `thread_turns`)*

One exchange. Insert-only; rows die only with their thread.

| Field | Type | Notes |
| --- | --- | --- |
| `turn_id` | TEXT, primary key | Minted at acceptance |
| `thread_id` | TEXT, FK → threads | Cascade-deleted with the thread |
| `tenant_id` | TEXT | **Denormalized from the thread, deliberately.** The rate window is per-*person across threads* — a join through one thread answers the wrong question — and the index that serves it needs these columns on this table |
| `subject_user_id` | TEXT | With `tenant_id`: the `(tenant_id, subject_user_id, created_at)` index is the rate window's whole cost |
| `seq` | INTEGER | Dense per-thread ordering, assigned under the thread's row lock — two tabs cannot interleave into ambiguity (edge case: two tabs, one thread) |
| `message` | TEXT | What the person typed, ≤ 8 KiB, verbatim |
| `disposition` | TEXT | `dispatched` / `declined` / `refused` |
| `reason` | TEXT | For declined/refused: `nothing_to_dispatch`, `not_permitted`, `rate_limited`, … — the same reason vocabulary 011's refusals use where they overlap |
| `run_id` | TEXT, nullable | Set iff `disposition = 'dispatched'` |
| `agent_definition_id` | TEXT, nullable | What was selected, when anything was |
| `context_run_ids` | TEXT | The runs whose results this turn carried forward (comma-joined, ordered) |
| `context_dropped` | TEXT | The runs that fell outside the bound (FR-009b — rendered, not just stored) |
| `created_at` | TIMESTAMPTZ | |

**Properties**:

- **The trail event is written first.** A turn row without a matching `TURN_RECORDED`
  event is a bug; a `TURN_RECORDED` event without a turn row is a deleted thread —
  expected, and exactly what SC-004 reconstructs from.
- `seq` is assigned under `SELECT ... FOR UPDATE` on the thread row — the same
  first-writer-wins discipline the audit stream heads use, for the same reason.

## Run input *(new table: `run_inputs`)*

The bridge from a turn to its run. Written by the turn operation **before** dispatch;
read by the run's entrypoint under its own workload credentials. Never travels through
the scheduler (research D6: a person's text must not enter a jobspec).

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | TEXT, primary key | The dispatched run |
| `message` | TEXT | Verbatim, ≤ 8 KiB |
| `context_run_ids` | TEXT | Ordered references; the entrypoint resolves each to its **recorded result, verbatim** at run start — byte-identical is SC-002's word, and reading the record is how it is guaranteed |
| `created_at` | TIMESTAMPTZ | |

**Properties**:

- **References, not copies.** Carrying five results verbatim could exceed a megabyte;
  carrying five run ids is nothing, and resolving at run start reads the recorded bytes
  rather than a copy that traveled.
- Not deleted with the thread (FR-010d — the run outlives the view). Insert-only,
  `ON CONFLICT DO NOTHING`, like the run index.
- **Not secret-bearing**: results are the same records the person can already read
  through `get_run_result`; the tenant boundary was enforced when the turn was accepted
  (context may only reference runs from the same thread).

## Trail events *(three new `AuditEventType` members — the sealed-core change)*

### `TURN_RECORDED`

Written under the thread's `correlation_id` for every **accepted** message — dispatched,
declined, or scope-refused — before the turn does anything else. **Pre-acceptance
refusals (`rate_limited`, `message_too_large`) get a small fixed-size refusal record
without the message instead**: the attempt is in the trail, but a subject cannot grow the
append-only evidence store at HTTP rate by being refused (analyze pass 2, I4).

Payload: `thread_id`, `turn_id`, `seq`, `subject_user_id`, `tenant_id`, `message`
(verbatim), `disposition`, `reason` (when not dispatched), `agent_definition_id` (when
selected), `run_id` (when dispatched), `run_correlation_id` (when dispatched — the join
that lets an investigator walk from the thread's chain into the run's), `context_run_ids`,
`context_dropped`.

- A **dispatched** turn's event is the run's rationale (FR-010a) — the consent record.
- A **declined or refused** turn's event is the only durable copy of that message once
  its thread is deleted, and that is the point (D4): the asks that started nothing are
  the ones an investigator most wants.

### `TURN_REFUSED`

The pre-acceptance record. Fixed-size payload: `thread_id`, `subject_user_id`,
`tenant_id`, `reason` (`rate_limited` / `message_too_large`), `message_bytes` (the size,
never the content). Exists because a refusal that leaves no record makes flooding
invisible, and a refusal that records the message makes flooding effective — the size
field lets an investigator see the shape of an abuse attempt without the trail carrying
its payload.

### `THREAD_DELETED`

Payload: `thread_id`, `subject_user_id`, `tenant_id`, `turn_count`, `run_ids` (started by
this thread). The deletion is in the chain, so SC-009a's "the deletion itself appears in
the trail" is a row, not a claim.

## Thread context *(a computation, not a table)*

The bounded set a new turn carries forward: the runs of the **5 most recent turns with
`disposition = 'dispatched'` whose runs produced results**, newest first. Computed by the
turn operation from `thread_turns` + the durable record at acceptance time; recorded on
the turn (`context_run_ids` / `context_dropped`) so the bound's effect is inspectable
after the fact. The bound is a named constant (`CONTEXT_TURNS = 5`, `MAX_MESSAGE_BYTES =
8192`) — stated, not emergent (FR-009a).

## Portal session *(deliberately not a record)*

In-memory only: opaque id → (subject, access token, expiry). Holds the person's token for
relay; dies with the process or the token's own expiry, whichever is first. **Not in
Postgres by design** — FR-020b wants nothing persisted that could act for the person
later, and a session table would be exactly that. Losing sessions on restart costs a
re-login and loses nothing else (threads are in Postgres; SC-003 is about threads, not
sessions).

## Rate window *(a query, not a table)*

`COUNT(*) FROM thread_turns WHERE tenant_id = ? AND subject_user_id = ? AND created_at >
now() - 5min` ≥ 30 → refuse `rate_limited`. Stateless, restart-safe, one indexed query —
served by `thread_turns`'s own `(tenant_id, subject_user_id, created_at)` index, which is
why those two columns are denormalized onto the turns table: the window counts a
*person's* turns across every thread they have, and a query that joined through a single
thread would bound each thread separately, which is thirty threads times thirty turns.

---

## Refusal shapes (unchanged vocabulary, two additions)

**A wording honesty note (analyze pass 2, C2)**: for not-found and pre-acceptance rows,
the "trail" column names the *reason code the response carries and a refusal record where
stated* — run-operation refusals today are response codes, not audited events (only
evidence reads have a refusal event), and this feature follows that posture rather than
quietly inventing a new mechanism. The turn operation's own events (`TURN_RECORDED`,
`THREAD_DELETED`) are where this feature's trail writing lives.

| Situation | Caller sees | Reason / record |
| --- | --- | --- |
| No such thread / other tenant's | not found — identically | `no_such_record` / `outside_tenant` |
| Someone else's thread, same tenant | refused | `not_permitted` |
| No agent selected / none available | **declined** | `nothing_to_dispatch` |
| Agent selected, not startable by this person | refused | `not_permitted` |
| Turn limit exceeded | refused | `rate_limited` — fixed-size refusal record, no message *(new reason, same frozen-mapping discipline as 011's `OPERATION_REASONS`)* |
| Message over `MAX_MESSAGE_BYTES` | refused | `message_too_large` — refused whole, **never truncated**; fixed-size refusal record, no message |

The decline/refusal distinction is FR-017's: the first says the platform does not do
this, the second says this person may not — conflated, they tell someone their access is
fine when it is not.
