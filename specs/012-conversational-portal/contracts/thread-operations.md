# Contract: Thread Operations

**Feature**: `specs/012-conversational-portal` | **Date**: 2026-07-29

Five operations, landing on **both** implemented transports; the catalogue grows from ten
to fifteen and `specs/008-northbound-api/contracts/operations.snapshot.json` grows with
it, snapshot-first, one operation at a time — the development loop 011 proved.

The portal is a **consumer** of these operations, never an implementation of them
(spec clarification, 2026-07-29). Its own contract is
[conformance-portal.md](conformance-portal.md).

---

## The operations

### `POST /threads` / `create_thread`

Creates an empty thread owned by the authenticated subject in their tenant. Returns
`thread_id`, `correlation_id`, `created_at`. Explicit creation rather than
create-on-first-message: orthogonal operations hold parity more simply, and the client
needs an id to subscribe to before the first turn resolves.

### `POST /threads/{thread_id}/turns` / `send_turn`

The consequential one. Request: `message` (≤ 8 KiB), `agent_definition_id` (optional —
absent means nothing was selected), `requested_tools` (optional, as `start_run` takes).

Ordered semantics, and the order is the contract. The load-bearing distinction is
**pre-acceptance versus accepted** (analyze pass 2, I4): a message the platform never
accepted gets a small fixed-size refusal record; a message it accepted gets a
`TURN_RECORDED` event carrying the message itself. Without that split, either rate-limited
messages vanish from the record, or the append-only trail is floodable at whatever HTTP
rate a subject can achieve — the rate limit would protect dispatch while leaving evidence
unbounded.

1. **Resolve the thread** — absent or another tenant's → not found; another subject's in
   the same tenant → refused `not_permitted`. Response reason codes, per the platform's
   existing refusal posture — there is no thread to chain an event under.
2. **Pre-acceptance checks** — over the rate window → refused `rate_limited`; message
   over `MAX_MESSAGE_BYTES` → refused `message_too_large`. Each writes a **`TURN_REFUSED` event — small, fixed-size, without the message** under the thread's correlation ID, so
   the attempt is visible in the trail while per-attempt trail growth stays bounded.
3. **Compute context** — the 5 most recent dispatched turns with results; record what
   fell outside the bound.
4. **Write the `TURN_RECORDED` trail event** — the message verbatim, before dispatch,
   before the turn row. Evidence first: a turn that reaches step 5 without a trail event
   cannot exist. This covers all three **accepted** dispositions — `dispatched`,
   `declined`, and scope-`refused` — and the scope refusals are deliberate: the asks a
   person made *beyond their authority* are the ones an investigator most wants.
5. **Decide**: no agent selected / none available → `declined: nothing_to_dispatch`;
   agent not startable by this subject (011's `may_start` intersection) → `refused:
   not_permitted`; otherwise write `run_inputs`, dispatch through the **same core path
   `start_run` uses** (same subject, same authorization, same events — SC-007), link
   `run_id` to the turn.

Response: the turn — `turn_id`, `seq`, `disposition`, `reason?`, `run_id?`,
`context_run_ids`, `context_dropped`. A decline is a 200 with a disposition, not an
error: the platform answered; the answer is no.

### `GET /threads` / `list_threads`

The subject's own threads in their tenant, newest first, keyset cursor, bounded page,
**no totals** — 011's listing discipline verbatim.

### `GET /threads/{thread_id}` / `get_thread`

One thread with its turns in `seq` order. Tenant-scoped with the standard collapse.
Turn rows carry dispositions; run state is joined from the durable record at read time,
never stored on the turn (the checkpoint stays the one writer of run state — 011's rule).

### `DELETE /threads/{thread_id}` / `delete_thread`

Writes `THREAD_DELETED` to the trail, then hard-deletes the thread and its turns.
`run_inputs` rows and runs are untouched (FR-010d). Idempotent from the caller's view:
deleting an absent thread answers not-found, the same as any other absent thread.

---

## Parity obligation

Every row in this table exists on both transports and the parity row compares them via
`operation_pairs()` against the snapshot. Verdict parity rows (the 009 set) grow to
cover: turn dispositions identical on both transports for the same inputs, including
declines, refusals, and the rate limit — a surface that declines on one transport and
dispatches on the other has two authorization paths wearing one name.

## What is deliberately absent

- **No stop/result thread operations** — a turn's run is stopped and read through the
  existing `/runs` operations. Two paths to one action is the thing parity exists to
  prevent.
- **No watch/subscribe operation** — cadence is not capability (research D8). Recorded
  here so its absence reads as decided, not missed; if MCP clients someday need push,
  that is a catalogue decision taken then, binding parity when taken.
- **No thread rename/edit** — a thread is a view of evidence; the only mutation it
  supports is ceasing to exist.
