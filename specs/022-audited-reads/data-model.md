# Data Model: 022 — the trail records who looked

**Phase 1.** Three entities, one of which is an existing enum gaining members. Nothing here is a
new table.

---

## 1. Read record — an entry in the record-access stream

**What it represents**: evidence that someone was shown something about a run or a thread.

**Where it lives**: `record-access:{tenant_id}` — one hash-chained stream per tenant, stable
across reads. Never the chain of the thing read (FR-005a).

**It is an ordinary `AuditEntry`.** No new type, no new table; the stream is a `correlation_id`
value. That is what makes it queryable by the existing governed evidence path (FR-005b) with no
new read surface.

### Payload fields

| Field | Type | Why |
| --- | --- | --- |
| `subject_user_id` | string | Who looked. The question the feature exists to answer. |
| `operation` | string | Which of the six, by tool name — so a query can separate "read one run's payload" from "listed runs". |
| `target_correlation_id` | string \| null | **The correlation id of the thing read** (FR-005). Null for a listing, which has no single target. This is what makes holding a run id enough to find its readers. |
| `target_id` | string \| null | The run id or thread id where one exists. |
| `disposition` | string | Permitted or refused, and on refusal the reason code — carrying the distinction the caller cannot see (FR-007). |
| `result_count` | integer | How many records were returned. Zero is meaningful: an empty listing still discloses that the caller asked (FR-007b), and a run of large counts is someone enumerating a tenant. |

### Validation rules

- **`target_correlation_id` is null only for listings.** A single-record read that recorded no
  target would satisfy FR-004 and defeat FR-005.
- **No field may carry content.** Not the result payload, not thread turn text, not a run's
  output. FR-006, and it is asserted by planting a credential-shaped value in a payload the reader
  is not asked for and checking it reaches no entry (SC-006).
- **`result_count` counts; it does not sample.** It is a number, never a subset of rows.

### Relationships

- **Refers to** a run or thread stream by `target_correlation_id`. **Never appended to it**
  (FR-005a) — that is the constraint 021's `RunReport` makes load-bearing, since a report compiles
  from a run's chain and would otherwise grow claims about its own readers.
- **Read through** the same governed, tenant-scoped evidence path as any other entry. No new
  entitlement (spec Assumptions).

---

## 2. Audit disposition — a property of an operation

**What it represents**: whether an operation records, decided when the operation is written.

**Where it lives**: a required field on `McpOperation` (`src/surfaces/mcp/operations.py`).

| Value | Meaning | Operations |
| --- | --- | --- |
| `records` | Touches a run or thread; writes its own entry | `list_runs`, `get_run`, `get_run_result`, `list_threads`, `get_thread`, `create_thread`, **`stop_run`** |
| `records_elsewhere` | The act is recorded, but by the machinery it starts rather than by the operation | `start_run` (`authority_issued` / `run_start`), and the seven that already audit |
| `no_record` | Touches neither a run nor a thread; configuration rather than activity | `list_agent_definitions`, `get_agent_definition` |

### Validation rules

- **Required, with no default.** Adding an operation without deciding is a construction error, not
  a missed edit to a list someone must remember (FR-009). This is the distinction from the
  existing hand-kept guard, which requires a human to notice.
- **`records_elsewhere` must name where.** A disposition that says "recorded somewhere" without
  saying where is indistinguishable from a wrong one, and is how `start_run` would quietly become
  unrecorded if its run path changed. **This rule earned itself before implementation began**: an
  earlier draft classified `stop_run` as `records_elsewhere`, and applying the rule — name where —
  revealed there was no where. It writes nothing.
- **Every value is checkable against measured behavior** (FR-002). `records` and `no_record` are
  both asserted — the second is why SC-011 exists, so widening coverage later is a decision rather
  than a drift.

---

## 3. `AuditEventType` — four additive members

**Sealed core** (Principle V). Additive only; no member removed, renamed, or repurposed.

| Member | Value | Stream | Why it is not an existing member |
| --- | --- | --- | --- |
| `RECORD_READ` | `record_read` | `record-access:{tenant}` | `EVIDENCE_READ` means *someone read the audit plane*. Reusing it would make an operator asking who read the trail receive run listings, and would silently change what already-written entries appear to mean. |
| `RECORD_READ_REFUSED` | `record_read_refused` | `record-access:{tenant}` | Mirrors the existing `EVIDENCE_READ_REFUSED`. A separate member rather than a payload flag, so FR-007's distinction is queryable rather than filterable. |
| `THREAD_CREATED` | `thread_created` | the thread's own stream | **Not a read.** `THREAD_DELETED` already exists and writes to `record.correlation_id`; this is its missing counterpart. Today the trail can prove a thread ended and what was said in it, and cannot prove it began. |
| `RUN_STOPPED` | `run_stopped` | the run's own stream | **Not a read either — the only write this feature covers.** Added by analysis pass 8: `stop_run_for` writes a durability blob carrying `written_by="stop:{user}"` and no audit entry at all, so a person withdrawing consent and ending a run leaves nothing hash-chained. On the run's own stream for the same reason `THREAD_DELETED` is on the thread's. |

### Invariants

- The pinned digest in `tests/unit/test_audit_chain.py` **must not move**. The hash covers an
  entry's own `event_type` value, not the set of possible values, so additive members change no
  written entry — and the pinned literal is what proves it rather than the argument.
- The row's assertion list grows by these three, matching how 020 and 021 recorded theirs.

---

## State transitions

None. A read record is written once and never updated — the trail is append-only. There is no
lifecycle and no field that changes after the append.

**The record carries no reconciliation state**, which is not the same as being exempt from
reconciliation. The record-access stream is swept like any other, and must be: a record of who
looked, excused from the check that its two copies agree, would be the one stream nobody verifies.
Reconciliation writes its summary to `audit-reconcile-{basis}` under `__platform__`, so sweeping
this stream does not grow it (research F9a).

The only ordering constraint: **the record is written before the records are returned.** A read
that answered first and recorded second would, on a failure between the two, be exactly the
unrecorded-answer state this feature exists to end (FR-007a).
