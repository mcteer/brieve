# Phase 1 Data Model: MCP Surface

**Feature**: `specs/009-mcp-surface` | **Date**: 2026-07-27

Five entities and one sealed-core change that is **not** additive. The non-additive one is
first, because it is the change a reviewer should look at hardest.

---

## `RunState` — `PARKED` removed, `SUSPENDED` added

```python
ACTIVE, REFUSED, COMPLETED, STOPPED, SUSPENDED   # PARKED is gone
```

`PARKED` meant *"stopped for a human to resolve"*. ADR-0049 removes the category, so the
state goes with it rather than being renamed — keeping the name would carry the
human-in-the-loop connotation into the one state that most needs it gone.

What it was conflating splits in two:

| Was | Becomes | Why |
| --- | --- | --- |
| Grant expiry | `STOPPED`, reason recorded | An execution bound, the same as any other. Nothing resumes it |
| Unreachable dependency | `SUSPENDED`, naming the dependency | Resumable — by the sweeper, never by a person |

**This changes what a constitutionally-named gate row asserts.** The Quality Gates name
*"grant-expiry parking"* among seven merge-blocking durability rows. It becomes grant-expiry
**stop**, which requires a constitution amendment with a Sync Impact Report citing ADR-0049
— MINOR, since a gate row is redefined and no principle is. Not a rename in a test file.

**Blast radius**: `src/core/run.py`, `durability/checkpoint.py`, `durability/resume.py`, and
five test modules including `tests/conformance/durability/rows.py`.

---

## DependencyHealth

What the platform believes about a product's reachability. **The single owner of "healthy"**
— everything else reads what this records (FR-006a).

| Field | Type | Notes |
| --- | --- | --- |
| `product` | `str` | Named as the tool registry names it. Not per-workspace: that would mean enumerating a customer's estate |
| `state` | `HealthState` | `HEALTHY`, `UNHEALTHY`, `UNKNOWN` |
| `checked_at` | `datetime` | When, so staleness is visible rather than inferred |
| `consecutive_successes` | `int` | Drives recovery hysteresis (D9) |
| `detail` | `str` | What failed, for an operator. Never a credential |

**`UNKNOWN` is treated as `UNHEALTHY`.** Guessing reachable is how a dead dependency gets
called anyway, and the whole mechanism exists to stop that.

**Stored in Postgres, not memory** (D3). A restart must not silently mean "everything is
reachable again", and a stale record must read as unknown rather than as either extreme.

**Asymmetric transitions** (D9): one failure marks unhealthy; several consecutive successes
mark healthy. Marking unhealthy fast costs a suspension the sweeper resolves. Marking
healthy fast resumes every waiting run into a product that fails again, and each cycle burns
real budget against the run's maximum duration.

---

## SuspendedRun

A record, **not a process**. The container ended when its work ended, including when that
work ended in suspension (FR-011).

**And an *index*, not a second source of truth.** 005's checkpoint already records
`run_state`, and it will say `SUSPENDED` — so this table repeating that fact creates two
places that can disagree, silently and asymmetrically: a run SUSPENDED in its checkpoint but
absent here is **invisible to the sweeper forever**, which presents exactly like the hang
ADR-0049 exists to prevent; a row here whose checkpoint has since reached `COMPLETED` has
the sweeper resuming a finished run. So:

- **The checkpoint is authoritative.** It survives 005's whole lifecycle already.
- **Both writes happen in one transaction.** A suspension that recorded one and not the
  other is the failure mode, and splitting the writes is how it happens.
- **The sweeper re-reads the checkpoint before resuming**, and treats this table as a
  candidate list. Same shape as `audit_stream_heads`: a head over a chain, never a second
  chain.

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | `str` | 005's run id, stable across resumption |
| `correlation_id` | `str` | Joins the whole chain |
| `awaiting` | `str` | The product it could not reach. **Named**, so the sweeper knows what to watch |
| `suspended_at` | `datetime` | Against which the existing maximum duration is measured |
| `step_index` | `int` | Where to resume |

**No `resume_after`, no retry counter, no escalation field.** Each would be a way for a run
to wait on a clock or a person rather than on a named machine condition, which is the
distinction ADR-0049 is entirely about.

**Suspension expires against the run's existing maximum duration** (FR-013) — not a new
ceiling. A dependency down long enough to exhaust it indicates a failure well beyond this
platform's concern.

---

## DenialClass

Two kinds of "no", and they must not blur.

| Class | Audit | Model-visible? | Why |
| --- | --- | --- | --- |
| `POLICY` | Yes | **No** | The governance boundary holding. An agent that treats it as an obstacle to route around inverts Principles II and III |
| `AVAILABILITY` | Yes | **Yes** | Invites a legitimate alternative — write the Terraform, hand it back, say the workspace was unreachable |

This is the subtlest thing in the feature, and getting it **backwards** would actively train
the wrong behaviour: an agent told that a scope refusal is adaptable will look for another
route. The asymmetry is deliberate and is ADR-0049 being more specific than the spec was.

---

## ParityComparison

What the parity row compares (D8). Not a stored entity — the shape of an assertion, recorded
here because leaving it vague is how this row passes dishonestly.

| Compared | Not compared | Why not |
| --- | --- | --- |
| Verdict | Timestamps | Legitimately differ |
| Audit event **types** | Correlation IDs | Different runs |
| Their **order** | Entry hashes | Follow from the above |
| Subject | Transport field | The one thing that *should* differ |
| Decision fields | | |

Driven from `specs/008-northbound-api/contracts/operations.snapshot.json`. If that snapshot
has drifted from the API, parity is measuring the wrong thing — so this row implicitly
re-verifies 008's snapshot check, and drift surfaces here as the first failure rather than
as a mystery later.

---

## Schema additions

New tables, in the evidence store's database but owned by the dependency subsystem.

```sql
CREATE TABLE IF NOT EXISTS dependency_health (
    product               TEXT PRIMARY KEY,
    state                 TEXT        NOT NULL,
    checked_at            TIMESTAMPTZ NOT NULL,
    consecutive_successes INTEGER     NOT NULL DEFAULT 0,
    detail                TEXT        NOT NULL DEFAULT ''
);

-- One row per suspended run. Deliberately NOT a column on a runs table: a suspended run
-- is a record of something waiting, and the sweeper's query is "what is waiting on this
-- product", which wants an index on the dependency rather than a scan of every run.
--
-- An INDEX over the checkpoint, not a second record of state. The checkpoint's run_state
-- is authoritative; this table is the sweeper's candidate list, written in the same
-- transaction as the suspension checkpoint, and re-verified against the checkpoint before
-- any resume. Two stores that can disagree about whether a run is suspended would fail
-- silently in both directions.
CREATE TABLE IF NOT EXISTS suspended_runs (
    run_id         TEXT PRIMARY KEY,
    correlation_id TEXT        NOT NULL,
    awaiting       TEXT        NOT NULL,
    suspended_at   TIMESTAMPTZ NOT NULL,
    step_index     INTEGER     NOT NULL
);

CREATE INDEX IF NOT EXISTS suspended_by_dependency ON suspended_runs (awaiting);
```

**The evidence role gets no grant on either.** Neither is evidence; both are operational
state, and widening that role to cover "things in the same database" is how a SELECT-only
credential quietly becomes a general reader.
