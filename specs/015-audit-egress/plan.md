# Implementation Plan: Audit egress for tamper-evidence

**Branch**: `spec/015-audit-egress` | **Date**: 2026-07-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-audit-egress/spec.md`

## Summary

Ship every audit entry and every stream head to a destination the platform's own credentials
cannot alter, and make comparing the two copies a named, scheduled, audited operation. The
design leans on two findings that make this smaller than it sounds: **the local trail is
already the spool** (the transactional append 008 built is the durable capture FR-014
requires, so the outbox pattern needs no new capture path), and **the head table is already
the shipping worklist** (per-stream `seq` is gapless by construction, so a per-stream
watermark is exact where a global cursor would race). The one genuinely new operated piece is
the destination itself: a second Postgres under collector-administrator credentials the
platform never holds, whose append-only posture the platform *probes* rather than trusts.

## Technical Context

**Language/Version**: Python 3.12 (existing toolchain; `uv`)

**Primary Dependencies**: none new. `pg8000` (already a dependency) reaches the destination;
the OTel pipeline is deliberately *not* the transport — research F1/D2, and the reasoning is
recorded there because it corrects a guess ADR-0055's Consequences section made.

**Storage**: one new local table (`audit_egress_watermarks`, evidence schema — operational
state, no evidence-role grant) and a new **destination schema** (`shipped_entries`,
`shipped_head_observations`) applied to a second Postgres the collector administrator owns.
The dev enclave stands that store up at bring-up; its DDL rides `enclave-up` like every other
schema, per the rule that has now bitten five times.

**Testing**: pytest. Hermetic rows for the watermark arithmetic, ship idempotency, reconciler
verdicts, and the capture-refusal path; **host_enclave rows in
`tests/conformance/evidence/`** against the live second store — a NEW directory, wired into
the Makefile's host lane **in the same change that creates it** (the 014 lesson, stated as a
task rather than remembered).

**Target Platform**: the dev enclave, plus one new container (the collector store).

**Project Type**: an integration (audit plane ⇄ second store) + one seam (`AuditDestination`)
+ a named operation (reconcile) + a conformance discipline against a genuinely separate
credential domain.

**Performance Goals**: none newly binding. Shipping is asynchronous by clarified decision
(FR-014a); the write path gains zero latency. The ship pass drains on the mcp service's
existing 30s interval, which bounds honest lag — and lag is surfaced, not hidden (FR-016).

**Constraints**: the platform holds **append+read only** at the destination and must be unable
to hold more (FR-008); the probe must demonstrate refusal without altering anything
(FR-020c); no destination configured means posture reports *absent*, never a silent default
(FR-009); ADR-0020's boundary default is untouched — the near destination is inside the
organization, and nothing new egresses beyond it.

**Scale/Scope**: one shipper pass, one reconciler extension, one probe, one MCP operation, one
audit event type, two destination tables, one watermark table, one container, ~10 conformance
rows.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The destination is a stock Postgres under someone else's administration; the platform adds a shipper, a probe, and a comparator. No new technology class, no bespoke store. |
| II — Total Interception | **Pass** | No new tool-call surface. The on-demand reconcile is a northbound operation through the existing MCP authorization path; the scheduled pass runs in the service that already runs the integrity pass. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Capture failure refuses the step — and this is the *existing* fail-closed path (research F2): the hook engine already denies with `evidential_gap` when an audit append fails, and `start_governed_run` already refuses an unauditable issuance. The outbox design means "captured for shipping" *is* the local append, so FR-014 is inherited rather than built. A destination that cannot be probed is **unverified**, and unverified never reports as protected (FR-020b). |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, with one recorded standing credential — see Complexity Tracking** | The shipping credential to the destination is static and org-issued, and that is the *point*: if the platform's Vault minted destination credentials, the platform's administrators would control the destination's credential lifecycle, which is precisely the administrative capture ADR-0055 exists to prevent. The credential grants INSERT+SELECT and nothing else, the probe proves it, and holding it confers no tampering ability. This is the same posture ADR-0044 took for the TFE management token: a standing credential, named, bounded, and argued rather than smuggled. |
| V — Sealed Core, Versioned Seams | **Pass** | `AuditSink` does not change — the shipper reads the store the sink already writes, so no fan-out sink is needed and the write seam stays sealed (a simplification over the spec's own assumption; research D1). New additive seam: `AuditDestination` protocol with the Postgres implementation, so an organization can implement collector-side delivery without touching core. |
| VI — Lean by Default | **Pass, one addition argued** | One new container in the enclave. Irreducible: a copy in the same store is the non-solution ADR-0055 forecloses by name, so the leanest compliant shape is exactly one separate store. No queue, no broker, no new service — the shipper rides the mcp service's existing loop. |
| VII — Anti-Fragmentation | **Pass** | One shipping path behind one protocol. An estate that wants the copy in its SIEM routes onward from its own collector store, outside the platform, under ADR-0020's existing explicit-export rule. |
| VIII — Eval-Gated Promotion | **N/A** | No model involvement. |
| IX — Evidence Over Claims | **Pass — the feature is this principle applied to the evidence plane itself** | Separation is *probed*, not asserted (clarify Q2). Divergence is *scheduled*, not awaited (clarify Q3). Reconciliation is itself audited (ADR-0035). The honest limits are in the contract: detection not prevention, and a residual window bounded by shipping lag (research F4). |
| X — The Decision Record Governs | **Pass, with one correction to a non-decision** | ADR-0055's decision bullets are implemented as written. Its Consequences section *guessed* the OTel collector as the transport; research D2 records why that guess fails reconciliation's read-back requirement and what satisfies the actual decision (administrative separation) instead. A guess in Consequences is not a rule — ADR-0020's actual rules (no vendor SDK in core, no default egress past the boundary) are both honoured. No new ADR needed; ADR-0055 anticipated exactly this by deferring the shape to the implementing feature. |

**Named-runner obligation** (constitution v1.1.0): **none owed.** The evidence rows run in
CI's enclave lane on same-repo pull requests (the lane runs `make conformance`, which will
collect the new directory because wiring it is its own task). Fork pull requests fall to the
agent harness per `AGENTS.md`.

**Gate result**: **PASS — proceed to Phase 0.** (Phase 0 and 1 complete; re-checked
post-design: still PASS. The standing credential and the second container are the two
additions that could have moved a verdict, and both are argued in Complexity Tracking.)

## Project Structure

### Documentation (this feature)

```text
specs/015-audit-egress/
├── plan.md              # This file
├── research.md          # Phase 0 — findings F1–F4, decisions D1–D7
├── data-model.md        # Phase 1 — watermarks, destination tables, report, event
├── quickstart.md        # Phase 1 — end-to-end validation
├── contracts/
│   └── conformance-egress.md   # The rows, against a live second store
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/core/audit/
├── evidence_schema.sql        # + audit_egress_watermarks (local operational state;
│                              #   run-role writes, evidence role holds no grant)
├── destination_schema.sql     # NEW — shipped_entries + shipped_head_observations,
│                              #   applied to the COLLECTOR store by its administrator
│                              #   (enclave-up plays that role in dev)
├── egress.py                  # NEW — AuditDestination protocol; the ship pass:
│                              #   worklist from heads ⋈ watermarks, per-stream drain,
│                              #   watermark advance only on confirmed delivery
├── destination_postgres.py    # NEW — the destination impl (INSERT ... ON CONFLICT
│                              #   DO NOTHING; first write wins) + the separation PROBE
│                              #   (attempt UPDATE and DELETE, require both refused)
├── reconcile.py               # NEW — compare local vs destination per stream; verdicts
│                              #   distinguish pending (within lag) from missing;
│                              #   destination chain verified on its own contents
└── schema.py                  # + AUDIT_RECONCILED event type (one type, the
                               #   basis/caller/findings in the payload — the 013 pattern)

src/surfaces/mcp/
├── server.py                  # + "ship" and "reconcile" supervisory passes beside
│                              #   health/sweep/integrity; egress config from env;
│                              #   posture ABSENT when unconfigured (FR-009)
└── operations.py              # + on-demand reconcile operation through the existing
                               #   authorization path; refusal recorded (SC-007)

infra/
├── jobs/collector-postgres.nomad.hcl   # NEW — the second store, its own volume,
│                                       #   NOT registered in the platform Vault's
│                                       #   database secrets engine
└── bin/enclave-up             # + collector bring-up: create store, create the
                               #   append-only role, apply destination_schema.sql,
                               #   hold the admin credential OUTSIDE the platform's
                               #   credential machinery (operator-held in dev)

Makefile                       # + tests/conformance/evidence on the host_enclave line,
                               #   IN THE SAME CHANGE that creates the directory

tests/conformance/evidence/    # NEW — the rows in contracts/conformance-egress.md
tests/component/               # hermetic halves: watermark arithmetic, ship idempotency,
                               #   reconciler verdicts, capture-refusal inheritance
```

**Structure Decision**: everything ships in `core/audit` beside the plane it extends — the
shipper reads what the sink writes, so no new package and **no change to the sink seam**. The
mcp service hosts both passes because it is the platform's one persistent process and already
owns the integrity pass this extends. The destination schema is its own file because it is
applied by a different administrator to a different store: bundling it into
`evidence_schema.sql` would invite exactly the same-store shortcut the feature forecloses.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A standing (static, org-issued) credential for the destination | The platform must be *unable* to control the destination's credential lifecycle; a credential the platform's Vault mints is a credential the platform's administrators govern, which re-captures the destination administratively | Vault-minted dynamic credentials — rejected because they invert the trust requirement: rotation convenience is not worth handing the guarded system's keys back to the party being guarded against. Bounded instead: INSERT+SELECT only, probe-verified every reconcile pass |
| A second Postgres container in the dev enclave | Tamper-evidence requires a copy outside the writer's blast radius; same-store and same-server copies share the administrator whose compromise is the threat | Reusing the existing Postgres (second database/schema) — rejected as the non-solution ADR-0055 names: one server administrator can rewrite both copies consistently |
