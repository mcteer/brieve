# Phase 1 Data Model: Audit egress for tamper-evidence

**Feature**: `specs/015-audit-egress` | **Date**: 2026-07-30

Two destination tables, one local table, one report, one event. Nothing here changes an
existing row shape: the shipped entry is the local entry, byte-for-byte in every chain field,
because a copy that differs from the original cannot be compared entry-for-entry (FR-002).

## Shipped entry *(destination table: `shipped_entries`)*

| Field | Type | Notes |
| --- | --- | --- |
| `tenant_id` | text | As local — inside the hash, so it ships |
| `correlation_id` | text | Stream identity |
| `seq` | integer | Gapless per stream, assigned by the local sink under its row lock |
| `event_type` | text | |
| `timestamp` | timestamptz | As recorded locally — part of the hash input |
| `payload` | jsonb | Full payload, not a digest: a digest detects *that* something changed and cannot say *what* (ADR-0055) |
| `prev_hash` | text | What makes the copy independently chain-verifiable |
| `entry_hash` | text | |
| `received_at` | timestamptz | Destination-assigned; the one field with no local counterpart |

**Properties**:

- **PK `(correlation_id, seq)`, first write wins.** The shipper inserts `ON CONFLICT DO
  NOTHING`, so a crash-driven re-ship is a no-op and a tamper-driven re-ship collides with the
  honest original and changes nothing (research D4). The reconciler, not the shipper, reports
  content mismatches.
- **Append is the platform's entire capability here.** The shipping credential holds
  INSERT+SELECT; UPDATE and DELETE are refused by grant, and the probe demonstrates the
  refusal rather than trusting it (D7).

## Shipped head observation *(destination table: `shipped_head_observations`)*

| Field | Type | Notes |
| --- | --- | --- |
| `correlation_id` | text | |
| `highest_seq` | integer | The local head's claim at observation time |
| `head_hash` | text | |
| `observed_at` | timestamptz | Destination-assigned |

**Properties**:

- **Append-only observations, never an updated row** — an updatable head would require the
  UPDATE capability FR-008 forbids, and the history is itself evidence: each row is the
  platform's own claim "stream X had N entries" (D5). PK `(correlation_id, highest_seq)`,
  first write wins, so a rewrite at constant length collides with the honest hash.
- **A local head below any shipped observation is truncation proven by the platform's own
  prior statement** — the decisive input for SC-004, requiring no lag inference.

## Egress watermark *(local table: `audit_egress_watermarks`, evidence schema)*

| Field | Type | Notes |
| --- | --- | --- |
| `correlation_id` | text, primary key | |
| `shipped_seq` | integer | Highest seq **confirmed** at the destination. Advanced only after delivery, so a crash re-ships (idempotent by D4) rather than skips |
| `updated_at` | timestamptz | |

**Properties**:

- **Operational state, not evidence.** The run role writes it; the evidence role holds no
  grant. It lives in the evidence schema file because it is applied by the same bring-up
  block, not because it shares the evidence tables' posture.
- **The worklist is `audit_stream_heads ⋈ audit_egress_watermarks`** where
  `highest_seq > coalesce(shipped_seq, -1)` — exact because per-stream seq is gapless
  (research F3). The backlog observable (FR-016) is the sum of those gaps.

## Reconciliation report *(returned by the operation; summarized into the event)*

| Field | Notes |
| --- | --- |
| `streams_checked` | |
| `findings[]` | Each: `correlation_id`, `kind`, `seq` range where applicable, detail. **Never payload content** — a report that quoted entries would be an ungoverned read path (FR-019) |
| `backlog` | Total unshipped entries at report time (FR-016 / SC-009) |
| `coverage` | **The range over which tamper-evidence holds** (FR-017): attested-since, derived from the earliest destination `received_at`. Entries written before egress was configured DO ship on the first drain — the watermark starts below every stream — but the destination then attests the local store's state *at import time*, not its history before it. A report that implied coverage of the pre-import past would be the overstated claim FR-018 forbids, one field over |
| `destination_verified` | `verified` \| `non_compliant` \| `unverified` — the probe's result (D7). Only `verified` permits the posture "tamper-evidence in force" |
| `posture` | `in_force` \| `absent` (no destination configured — FR-009) \| `unverified` \| `non_compliant` |
| `basis` | `scheduled` \| `on_demand`, with caller |

**Finding kinds** (extending the integrity checker's local vocabulary):

- `entry_mismatch` — same `(stream, seq)`, different `entry_hash`: rewrite of one copy (SC-003)
- `missing_at_destination` — local entry at or below the watermark absent at the destination:
  shipped work lost or destroyed there
- `local_truncated` — local head below a shipped head observation, or destination entries
  above the local head: the consistent local rewrite (SC-004)
- `destination_chain_broken` — the second copy fails verification on its own contents (SC-002's
  negative)
- `pending` is **not** a finding: entries above the last shipped observation and within the
  active worklist are lag, reported in `backlog` (FR-013 / SC-008)

## `AUDIT_RECONCILED` audit event *(one new enum member)*

Payload: the report's summary — basis, caller, streams checked, finding count by kind,
backlog, posture. One event with the distinction in the payload (the 013 `MODEL_GATE`
pattern); written through the governed path so reconciliation itself satisfies "reading
evidence is audited" (ADR-0035, SC-007). An unauthorized attempt records its refusal through
the operation layer's existing refusal event.

## State transitions *(posture only — no run states change)*

`absent → unverified → in_force` on configure-then-probe; `in_force → non_compliant` when a
probe's tamper attempt succeeds; `in_force → unverified` when the destination cannot be
probed. Posture never moves toward `in_force` except by a passing probe (FR-020b).
