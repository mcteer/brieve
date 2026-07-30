# Phase 0 Research: Audit egress for tamper-evidence

**Feature**: `specs/015-audit-egress` | **Date**: 2026-07-30

Four findings and seven decisions. The findings came from reading the shipped audit plane
before designing anything on top of it — the habit that has paid every time — and two of them
delete work the spec assumed would be needed.

---

## Findings

### F1 — There is no collector, and the OTel path cannot carry this anyway

The spec's assumption reads "the collector ADR-0020 already describes is the natural
destination, so the transport is a configuration surface the platform has rather than a new
one." Checked against the tree, both halves are optimistic:

- The dependency is `opentelemetry-api` **only** — no SDK, no OTLP exporter. Every span in
  `core/telemetry` is a no-op API call unless someone installs an SDK nothing installs.
- No collector is deployed anywhere in `infra/`. The "configuration surface" is a described
  posture, not an existing component.

And the deeper problem is structural, not a missing package: **reconciliation must read the
second copy back** — entry-for-entry, chain fields intact, verifiable in isolation (SC-001/
002/003). An OTel log pipeline is fire-and-forget into whatever backend the collector routes
to; reading it back would need a query adapter per backend, which fragments the one comparison
this feature exists to make exact. The transport question is settled by the read-back
requirement, not by transport preference. See D2.

### F2 — The capture-refusal path already exists, so FR-014 is inherited rather than built

Clarify Q1 drew the line at *capture*: a step is refused only when the entry cannot be durably
captured for shipping. The tree already enforces exactly this, in two places:

- `core/hooks/engine.py` denies with `evidential_gap=True` when the audit append around a tool
  call fails — the step is refused because it cannot be accounted for.
- `start_governed_run` refuses a run whose `AUTHORITY_ISSUED` cannot be appended.

Under D1 (the outbox), "durably captured for shipping" **is** the local append. So the
fail-closed half of the clarified FR-014 is the existing behaviour, asserted rather than
implemented. The new work is confined to delivery, which by FR-014a never refuses anything.

### F3 — Per-stream `seq` is gapless under a row lock, so the head table is the worklist

`PostgresAuditSink.append_event` assigns positions inside one transaction under `SELECT ...
FOR UPDATE` on the stream head. Consequence: per-stream sequences have **no gaps and no
commit-order races** — unlike any global cursor over the table, where a serial column's
N+1 can commit before N and a watermark silently skips rows (the classic outbox defect).

So the shipper needs no new ordering machinery: `audit_stream_heads ⋈ audit_egress_watermarks`
yields exactly the streams with unshipped work, and `seq ∈ (watermark, head]` is exact. The
table that exists to detect truncation doubles as the queue, for free.

### F4 — The residual exposure window is the shipping lag, and it must be stated

An entry is protected once delivered. Between local append and confirmed delivery, an actor
with local write access can destroy the entry, lower the head, and advance the watermark
consistently — and that entry then never existed anywhere. This is not a defect of the design;
it is the direct consequence of clarify Q1's decision that delivery may lag (the alternative
hands the collector's administrator a platform-wide halt switch). What the platform owes is
honesty and pressure: the backlog is observable (FR-016) as a *security* signal rather than an
ops nicety, the ship pass runs on the service's 30s interval so honest lag is seconds, and the
contract records the window in "what these rows do not prove."

---

## Decisions

### D1 — The local trail is the spool: transactional outbox with per-stream watermarks

**Decision**: no spool file, no queue, no fan-out sink. The shipper reads `audit_entries` —
already durable, already ordered, already written transactionally — and tracks confirmed
delivery in a new `audit_egress_watermarks` table (one row per stream, advanced only after the
destination confirms). Capture is the existing append; the `AuditSink` seam does not change.

**Rationale**: ADR-0055 guessed "a local durable spool the shipper drains" and labelled it a
guess. The guess is right about the shape and redundant about the storage: a separate spool
would duplicate rows that are already durable in the same database, and a spool on allocation
disk would *die with the allocation* — dispatched runs are ephemeral by design (014), so any
allocation-local buffer converts a scheduler kill into silent evidence loss, which is the
exact failure this feature exists to close. The outbox also collapses FR-014 onto existing
behaviour (F2).

**Alternatives**: synchronous ship (rejected by clarify Q1 — hands a third party the ability
to halt the platform); allocation-disk spool (rejected above — ephemeral disk is where
evidence goes to die); a dedicated spool table (rejected — a copy of a durable table in the
same database is bytes, not safety); a fan-out `AuditSink` wrapper (rejected — it couples
delivery into the write path that must never block, and the seam's docstring argues hard
against second write paths).

### D2 — The destination is a store behind an `AuditDestination` seam; the enclave implementation is a second Postgres

**Decision**: a small protocol — append entries, append head observation, read back for
reconciliation, probe — with one shipped implementation: a second Postgres instance owned by
the collector administrator, reached with a static INSERT+SELECT credential. Direct `pg8000`
inserts; no OTel pipeline in the shipping path.

**Rationale**: the *decision* bullets of ADR-0055 require administrative separation, full
chain entries, heads, and reconciliation — none of which names a transport. The Consequences
section's "the collector is the natural destination" is a guess that fails F1's read-back
requirement. A second Postgres satisfies every decision bullet with a technology class the
enclave already operates (Principles I, VI, VII), makes the probe trivial and exact
(`UPDATE`/`DELETE` → `permission denied` by grant), and makes reconciliation a query rather
than a per-backend adapter. ADR-0020 is honoured, not dodged: no vendor SDK enters core, and
nothing new crosses the organization's boundary — an estate that wants the copy in its SIEM
exports *from its own store*, outside the platform, under ADR-0020's existing explicit-export
rule.

**Alternatives**: OTLP → collector → backend (rejected — F1: nothing exists, and read-back
fragments per backend); object storage with versioning/WORM (defensible for production
hardening, rejected here — the enclave gains a new technology class, probe semantics vary by
provider, and ADR-0055 already burned "a bucket the enclave's role can write" as the canonical
non-solution; the seam leaves room for a WORM implementation later); same-server second
database (rejected — the server administrator is one person; that is the blast radius,
unchanged).

### D3 — The shipper is a supervisory pass in the mcp service

**Decision**: a "ship" pass beside health/sweep/integrity in the existing supervisory loop:
compute the worklist (F3), drain each stream's `(watermark, head]` range in order, ship a head
observation after its entries, advance the watermark only on confirmed delivery.

**Rationale**: the mcp service is the platform's one persistent process and already owns
periodic duties; a dedicated shipper service would be a new operated component for a loop that
runs in milliseconds (Principle VI). Crash-safety comes from ordering, not coordination:
watermark advances last, so a crash anywhere re-ships, and re-shipping is idempotent by D4.

**Alternatives**: ship-on-write from every writer (rejected — puts destination latency and
failure into every process's hot path, exactly what FR-014a forbids); LISTEN/NOTIFY (rejected
— machinery for latency nobody asked for; the 30s interval already bounds lag); a dedicated
service (rejected above).

### D4 — First write wins at the destination: idempotent by primary key, mismatch left for the reconciler

**Decision**: `shipped_entries` carries PK `(correlation_id, seq)`; the shipper inserts with
`ON CONFLICT DO NOTHING`. Same for head observations on `(correlation_id, highest_seq)`.

**Rationale**: re-shipping after a crash between insert and watermark advance must be a no-op,
and first-write-wins is precisely the evidence posture — the earliest claim is the one a
rewrite cannot retroactively replace. An attacker who rewrites a local entry and re-ships it
collides with the original row and changes nothing; the reconciler then reports the content
mismatch. The conflict clause makes tampering *quiet at ship time and loud at reconcile time*,
which is the right split: the shipper is not a judge.

**Alternatives**: upsert (rejected — a re-ship could overwrite the honest copy, which is the
whole attack); insert-and-compare in the shipper (rejected — duplicates the reconciler's job
in a second place with worse reporting).

### D5 — Heads ship as append-only observations, never as an updated row

**Decision**: each pass appends the current local head as a new observation row; nothing at
the destination is ever updated in place.

**Rationale**: FR-008 caps the platform at append — an updatable head row would require
UPDATE, the very capability the probe exists to prove absent. And the observation *history* is
itself evidence: every row is the platform's own signed-by-hash claim "stream X had N entries
at time T." A local head later found *below* a shipped observation is truncation proven by the
platform's own prior statement — no inference about lag required. This is what makes FR-013's
tail case decidable: entries above the last shipped observation are *pending*; entries below
it that are missing are *gone*.

**Alternatives**: mutable head row at the destination (rejected — needs UPDATE); deriving the
head from `max(seq)` of shipped entries (rejected as the only mechanism — it cannot distinguish
"never shipped" from "shipped and locally truncated", which is exactly the distinction the
observation history provides; the derived head remains a useful cross-check inside the
reconciler).

### D6 — Reconciliation extends the integrity pass, and on-demand goes through the operations catalogue

**Decision**: the scheduled half runs in the mcp supervisory loop beside (and building on) the
existing `verify_stream_integrity` pass; the on-demand half is a new operation in
`src/surfaces/mcp/operations.py`, through the existing authorization path. Both emit one new
audit event, `AUDIT_RECONCILED` — one type, with basis (`scheduled` | `on_demand`), caller,
range, findings, backlog, and destination-verification result in the payload (the 013
`MODEL_GATE` pattern). Findings carry stream and sequence, **never payload content**, so the
report itself cannot become an ungoverned read of tenant data (FR-019).

**Rationale**: clarify Q3 requires proactive + on-demand; both homes already exist, and the
integrity checker already walks streams and classifies findings — the reconciler adds the
cross-copy comparisons (local-vs-shipped entry hashes, local head vs shipped observations,
destination-only chain verify) to a walk that already happens. The event satisfies ADR-0035's
"reading evidence is audited" with the caller named (SC-007).

**Alternatives**: a separate reconciler service (rejected — Principle VI, again); divergence
alerting beyond the event (deferred — clarify Q3 explicitly chose the report-and-event shape
over pulling an alerting surface into scope).

### D7 — The probe attempts real tampering against a sacrificial stream and requires refusal

**Decision**: at configuration and on every reconcile pass, the platform attempts `UPDATE` and
`DELETE` against a dedicated probe stream's rows at the destination (a reserved correlation id
the shipper seeds), using its own shipping credential, and requires **both to be refused**.
Refused → separation verified. Either succeeds → the destination is reported non-compliant —
and the probe stream, not tenant evidence, is what got altered. Unprobeable → **unverified**,
and unverified never reports as protected (FR-020b).

**Rationale**: FR-020c forbids a probe that leaves the destination altered; attempting
mutation on a sacrificial stream and *requiring refusal* means success alters nothing and
failure alters only probe rows while downgrading the posture. Probing per pass rather than
once implements FR-020a's drift argument at zero extra cost — the pass is already connected.

**Alternatives**: credential introspection (rejected — verifies what the grant says, not what
the store enforces); probing tenant rows (rejected — a probe that *could* damage evidence to
prove it cannot is self-refuting, which is FR-020c verbatim).

---

## Resolved unknowns

The spec deferred three questions to planning; all are resolved above — synchronous vs
spooled (D1, F2), transport and wire format (D2, F1), and where reconciliation runs plus what
each pass compares (D3, D6). The clarified requirements map cleanly: FR-014/014a → F2 + D1;
FR-020a–c → D7; FR-010a → D6. No NEEDS CLARIFICATION remains.
