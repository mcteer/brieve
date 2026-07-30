# Tasks: Audit egress for tamper-evidence

**Input**: Design documents from `/specs/015-audit-egress/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. SC-010 makes them decisive: the whole feature is a claim about a
credential boundary, and a version without rows against a *live second store* would assert
the comparator compares while proving nothing about the separation ADR-0055 exists to
establish.

**Organization**: Setup (the second store and its seam) → Foundational (schema, watermark,
destination impl + probe) → US1–US5 in priority order → Polish. The two omissions the plan
flagged — the Makefile lane and the `enclave-up` collector bring-up — are **T004** and
**T003**, not afterthoughts, because "named by a lane that will run it" is a separate question
from "written" (014's lesson).

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | Capture failure refuses the step (inherited, asserted); an unprobeable destination reports `unverified`, never protected |
| **Conformance** | The eleven rows in `contracts/conformance-egress.md`, host_enclave, against the live second store |
| **No-secret / separation** | The shipping credential holds INSERT+SELECT only; the probe proves UPDATE/DELETE refused; the platform's Vault never mints the destination credential |
| **Correlation / evidence** | `AUDIT_RECONCILED` with basis and caller; reconciliation itself in the trail; refusal recorded |

## Path Conventions

Single project: `src/`, `tests/`, `infra/` at repository root. The conformance rows join a
**new** `tests/conformance/evidence/` directory, wired into the Makefile host lane in the same
change that creates it (T004).

---

## Phase 1: Setup — the second store exists and the enclave stands it up

- [ ] T001 Create `infra/jobs/collector-postgres.nomad.hcl`: a second Postgres (`postgres:17-alpine`), its own named volume, its own static port, `cores`-based reservation (the ~24 MHz fingerprint trap 008 paid for — copy the pattern from `infra/jobs/postgres.nomad.hcl`). **It is NOT registered in the platform Vault's database secrets engine** — that registration is the administrative capture the feature forecloses, and its absence is the property. Comment says so.
- [ ] T002 Create `infra/collector/roles.sql`: the collector store's **append-only role** — `INSERT, SELECT` on the destination tables and **no** `UPDATE`/`DELETE`/`TRUNCATE`. **On the collector's side of the line, not in the trust-fabric module** (analyze I2): platform Terraform defining destination roles would blur the administrative boundary the feature draws, so this file is applied by whoever administers the collector — enclave-up wearing that hat in dev. The credential is deliberately not Vault-minted (research D2, Complexity Tracking): a credential the platform's Vault issues is one the platform's administrators govern, which re-captures the destination. Record both reasons inline.
- [ ] T003 Extend `infra/bin/enclave-up` to bring up the collector store: start the container; **as the collector admin** create the role (`infra/collector/roles.sql`) and apply `destination_schema.sql` — never under the platform's `brieve` owner role; then write the ship credential to a dedicated platform Vault KV path and extend the **mcp role's policy** in `infra/modules/trust-fabric/policies.tf` with read on exactly that path. **Never jobspec env** (analyze N1): the credential's SELECT half reads the entire evidence copy, and a jobspec is readable by anyone with scheduler access — the same rule that keeps run input out of jobspecs, applied to the same class of exposure. Storing it in the platform's Vault is storage, not lifecycle control: the collector admin can rotate it at the destination unilaterally. The ADMIN credential stays operator-held, outside `.env`-adjacent platform machinery. Update the block's `ok` message; the destination schema rides bring-up like every other (the rule that has bitten five times).
- [ ] T004 Add `tests/conformance/evidence` to the `host_enclave` line in `Makefile` **in this task, creating the directory's `__init__.py` and `conftest.py` in the same change** — a conftest that yields two connections, the platform's shipping credential and the collector admin credential, the second being what the platform must never hold, and that documents the marker discipline every row file in this directory carries: `pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]`, both, the 013/014 lesson (analyze U4). "Already named by a lane" and "named by a lane that will run this row" are different questions (014). Correct nothing later; wire it at birth.

**Checkpoint**: `make dev-up` brings up two stores; the collector store rejects `UPDATE` from the append-only role by hand; `make check` green.

---

## Phase 2: Foundational (blocking all user stories)

**Purpose**: the schema both copies need, the watermark the shipper tracks against, the
destination implementation, and the probe. No story ships an entry until these exist.

### Schema and the local worklist

- [ ] T005 Create `src/core/audit/destination_schema.sql`: `shipped_entries` (all chain fields as `evidence_schema.sql`'s `audit_entries`, plus `received_at`, PK `(correlation_id, seq)`) and `shipped_head_observations` (`correlation_id, highest_seq, head_hash, observed_at`, PK `(correlation_id, highest_seq)`). Comment records D4/D5: first-write-wins PK is the evidence posture, and observations are append-only because an updatable head needs the UPDATE the probe disproves.
- [ ] T006 Add `audit_egress_watermarks` (`correlation_id` PK, `shipped_seq`, `updated_at`) to `src/core/audit/evidence_schema.sql`. Comment: operational state, run-role writes, evidence role holds no grant — same posture the file's other tables' comments state. This one lives here because it applies at the same bring-up block, not because it shares the evidence tables' read protection.

### The destination seam and its implementation

- [ ] T007 Define the `AuditDestination` protocol in `src/core/audit/egress.py`: `ship_entries(entries)`, `ship_head_observation(correlation_id, highest_seq, head_hash)`, `read_entries(correlation_id)`, `read_head_observations(correlation_id)`, `probe() -> Literal["verified","non_compliant","unverified"]`. Additive seam; no change to `AuditSink` (research D1 — the shipper reads the store the sink already writes). Docstring: the platform holds append+read only, and `probe` is the mechanism that turns FR-020's requirement into an observation rather than an assertion.
- [ ] T008 Implement `PostgresAuditDestination` in `src/core/audit/destination_postgres.py`: `ship_*` are `INSERT ... ON CONFLICT DO NOTHING` (idempotent re-ship, first write wins — D4); `read_*` select back for reconciliation; **the credential is the append-only role's, never `VaultDatabaseCredentials`** — fetched from the platform Vault KV path T003 writes, under the service's own attested identity, and the type difference is the point: this class must be *unable* to reach the destination with anything the platform's secrets engine can mint. Never read from env (analyze N1). Migrate applies `destination_schema.sql` under the admin role at bring-up (T003), not here.
- [ ] T009 [GATE:separation] Implement `probe()` in `src/core/audit/destination_postgres.py`: against a reserved probe stream the shipper seeds (a fixed correlation id), attempt `UPDATE` and `DELETE` with the platform's own credential; **both refused → `verified`**; either succeeds → `non_compliant`; cannot reach/execute → `unverified`. **Must leave the destination unaltered** (FR-020c): success would mean it damaged a row to prove it could not, so the probe rows are sacrificial and the assertion is on the refusal, not on a mutation landing.
- [ ] T010 [P] Component rows in `tests/component/test_audit_destination.py`: an entry round-trips with every chain field intact; a re-ship of the same `(stream, seq)` is a no-op (D4); a head observation is append-only; `read_entries` returns what `ship_entries` wrote. Hermetic against an in-memory `AuditDestination` double **for the arithmetic only** — the separation itself is a conformance row, never a hermetic one (SC-010).

### The event

- [ ] T011 [P] Add `AUDIT_RECONCILED` to `AuditEventType` in `src/core/audit/schema.py` — one event, the distinction in the payload (basis `scheduled|on_demand`, caller, streams checked, findings-by-kind, backlog, posture), on the 013 `MODEL_GATE` pattern. Docstring: findings carry stream and seq and **never payload content** (FR-019), so the record of a read cannot itself become an ungoverned read.

**Checkpoint**: `make check` green; destination round-trips; the probe returns `verified` against the append-only store and `non_compliant` against a writable one.

---

## Phase 3: User Story 1 — An investigator has a second copy to reconcile against (P1) 🎯 MVP

**Goal**: every entry a run writes appears at the destination, chain-verifiable on its own,
and a local rewrite is nameable.

**Independent test**: run real work; read the destination under the collector admin
credential; verify its chain with no local read; rewrite one local entry and see it named.

- [ ] T012 [US1] The ship pass in `src/core/audit/egress.py`: worklist = `audit_stream_heads ⋈ audit_egress_watermarks` where `highest_seq > coalesce(shipped_seq, -1)` (exact because per-stream seq is gapless — research F3); for each stream drain `(shipped_seq, highest_seq]` in order, `ship_entries` then `ship_head_observation`, and **advance the watermark last, only on confirmed delivery** (D3 — a crash re-ships, which D4 makes idempotent). Return the backlog it could not drain. **Seed the reserved probe stream on the first pass** (analyze U3), so T009's probe always has sacrificial rows to attempt tampering against.
- [ ] T013 [US1] Wire a `ship` pass into the mcp supervisory loop in `src/surfaces/mcp/server.py`, beside health/sweep/integrity; construct the `PostgresAuditDestination` from egress config in env (**coordinates only** — host, port, database, KV path; the credential itself comes through T008's KV fetch, never env); **when no destination is configured, the pass is inert and posture is `absent`** (FR-009) — not a silent default that reads as protected.
- [ ] T014 [US1] The reconciler in `src/core/audit/reconcile.py`: for each stream, compare local entries to shipped by `(seq, entry_hash)` → `entry_mismatch`; local entries at/below the watermark missing at the destination → `missing_at_destination`; verify the destination's chain on its own contents → `destination_chain_broken`; entries above the last shipped observation and within the worklist are **`pending`, not a finding** (backlog, not divergence — FR-013). Extends `verify_stream_integrity`'s walk rather than duplicating it (D6).
- [ ] T015 [P] [US1] Hermetic rows in `tests/component/test_reconcile.py`: agreeing copies → no findings; one altered local entry → `entry_mismatch` naming stream and seq; a destination entry with a broken chain → `destination_chain_broken`; entries within the active worklist → reported as backlog, never divergence; **and the report's `coverage` field states attested-since** (FR-017, analyze C1) — coverage runs from first delivery, and a report never implies the destination attests history from before its import.
- [ ] T016 [US1] [GATE:conformance] Row in `tests/conformance/evidence/test_ships_and_reconciles.py` (`enclave` + `host_enclave`): run real work through the sink, run the ship pass, read `shipped_entries` under the **collector admin** credential, assert every chain field byte-identical (SC-001) **and head observations present for every shipped stream** (contract row 1, analyze U1), and the destination chain verifies alone (SC-002); **assert the local `audit_entries` rows are byte-identical before and after the ship pass** (FR-004, analyze U2 — structural under D1, and asserted so the structure is a row rather than a belief); then rewrite one local entry as the platform DB admin and assert reconciliation names it (SC-003). Read through the evidence path, not the shipper's return value.

**Checkpoint**: US1 demonstrable — a second copy exists, stands alone, and a rewrite is named. The MVP of ROADMAP gap 0.

---

## Phase 4: User Story 2 — Truncation is detectable, not just alteration (P1)

**Goal**: the consistent local rewrite — delete newest entries AND lower the head — is caught.

**Independent test**: truncate local entries, lower the local head to match, compare against
the shipped head observations.

- [ ] T017 [US2] Add the `local_truncated` verdict to `src/core/audit/reconcile.py`: a local head below the highest shipped head observation, OR destination entries above the local head, is truncation proven by the platform's own prior claim (D5) — no lag inference. Distinguish from `pending` (which is *above* the last observation, not below it).
- [ ] T018 [P] [US2] Hermetic row in `tests/component/test_reconcile.py`: shipped observation records seq N; local head lowered to N-3 with entries to match; reconciler reports `local_truncated`, not silence.
- [ ] T019 [US2] [GATE:conformance] Row in `tests/conformance/evidence/test_truncation_is_caught.py`: ship a stream, then as the platform DB admin delete the newest local entries AND lower `audit_stream_heads` to match — the rewrite that defeats chain, grant, and head together — and assert reconciliation reports `local_truncated` (SC-004). This is the row the whole head-shipping design exists for.

**Checkpoint**: the attack that was invisible is visible, witnessed by the platform's own shipped claims.

---

## Phase 5: User Story 3 — Divergence is reported by a named, audited operation (P1)

**Goal**: reconciliation is invokable and scheduled, itself in the trail, refused without authority.

**Independent test**: invoke reconcile on agreeing and differing copies; read
`AUDIT_RECONCILED` back; attempt it unauthorized and see the refusal recorded.

- [ ] T020 [US3] The on-demand operation in `src/surfaces/mcp/operations.py`: a reconcile operation through the **existing authorization path**, returning the report; refusal for a caller without evidence-read authority goes through the operation layer's existing refusal event (SC-007). No new authorization surface (Principle II).
- [ ] T021 [US3] [GATE:correlation] Emit `AUDIT_RECONCILED` from both the scheduled pass and the on-demand operation, through the governed sink, with basis (`scheduled`|`on_demand`), caller, findings-by-kind, backlog, posture, **and coverage (attested-since — FR-017, analyze C1)** — findings carrying stream/seq only, never content (FR-019). Reconciliation reading evidence is itself audited (ADR-0035).
- [ ] T022 [US3] Wire a `reconcile` pass into the mcp supervisory loop beside `ship` (D6): scheduled, so divergence surfaces without anyone asking (clarify Q3). It runs the probe (T009) each pass and folds `destination_verified` into the posture (FR-020a — periodic, because control drifts).
- [ ] T023 [P] [US3] Hermetic rows in `tests/component/test_reconcile_operation.py`: the operation returns a report; an unauthorized caller is refused; the emitted event carries basis and caller and no payload content.
- [ ] T024 [US3] [GATE:conformance] Row in `tests/conformance/evidence/test_reconcile_is_audited.py`: run reconcile; assert `AUDIT_RECONCILED` in the trail naming basis and caller (SC-007); attempt an unauthorized on-demand reconcile and assert it is refused and the refusal recorded. **And the SC-008 case in the same file** (analyze C3): reconcile while a run is actively writing — live, not only T015's hermetic version — and assert zero false findings, with the in-flight tail reported as backlog (FR-013). Read through the evidence path.

**Checkpoint**: the comparison is a named operation an investigator can point at, and it leaves its own evidence.

---

## Phase 6: User Story 4 — A destination the platform can rewrite is refused (P2)

**Goal**: the non-solution ADR-0055 named is visibly non-compliant.

**Independent test**: point egress at a writable store; posture reports `non_compliant`.
Point it at one that cannot be probed; posture reports `unverified`.

- [ ] T025 [US4] Fold the probe result into posture reporting in `src/surfaces/mcp/server.py`: only `verified` permits posture `in_force`; `non_compliant` and `unverified` each report as themselves and neither claims tamper-evidence (FR-020b). Report names the reason.
- [ ] T026 [P] [US4] Hermetic row in `tests/component/test_posture.py`: a `non_compliant` probe → posture not `in_force`, reason named; an `unverified` probe → posture `unverified`; a `verified` probe → `in_force`; **no destination configured → posture `absent`** (FR-009, analyze C2) — four postures, and only one of them claims protection.
- [ ] T027 [US4] [GATE:conformance] [GATE:fail-closed] Row in `tests/conformance/evidence/test_probe_gates_posture.py`: run the probe against the append-only store (→ `verified`, both tamper attempts refused, SC-005) and against a deliberately writable store (→ `non_compliant`, naming why); then against a store that refuses the probe entirely (→ `unverified`, posture does not claim protection, SC-005a). The probe leaves every store unaltered (FR-020c).

**Checkpoint**: separation is proven by attempting to break it, not by a config flag.

---

## Phase 7: User Story 5 — The air-gapped shape, the absent posture, and outage honesty (P2)

**Goal**: an estate with no outbound connectivity still has a second copy; one with no
destination says so; and an unreachable destination loses nothing and lies about nothing.

**On the spec mapping** (analyze I1): the spec's US5 has two scenarios. Scenario 1 — the
air-gapped estate — is **the suite's own shape**: the dev collector binds to the local network
and every row in this contract runs against it with zero external egress, so the demonstration
is by construction, stated in the contract (T030a) rather than implied. Scenario 2 — the
absent posture — is T026 (hermetic) and T030a (conformance). The outage tasks demonstrate the
FR-014a/015/016 guarantees holding *in* that shape.

**Independent test**: stop the collector mid-run; runs finish; backlog rises; on restart every
entry arrives. Break local capture; the step is refused. Unset the egress config; posture
reads `absent`.

- [ ] T028 [US5] Expose the backlog observable in `src/core/audit/egress.py` and surface it in the mcp service's readiness/status line (FR-016): the sum of `(shipped_seq, highest_seq]` gaps, reported as a **security** signal — the second copy falling behind is the exposure window, not an ops nicety.
- [ ] T029 [P] [US5] Hermetic row in `tests/component/test_egress_backlog.py`: with the destination raising on `ship_entries`, the ship pass records no watermark advance and the backlog reflects the undelivered entries; when it recovers, the next pass drains them and the backlog returns to zero — none skipped (the watermark-advances-last property, D3).
- [ ] T030 [US5] [GATE:conformance] Row in `tests/conformance/evidence/test_outage_loses_nothing.py`: stop the collector container mid-run; assert runs complete (FR-014a — delivery never gates availability) and the backlog rises and is observable; restart it; assert every entry written during the outage arrives, none lost (SC-009/009a).
- [ ] T030a [US5] [GATE:conformance] Row in `tests/conformance/evidence/test_posture_absent.py`: with egress unconfigured, posture reads `absent` — stated, never defaulted to something that looks protected (SC-006, FR-009, analyze C2). The same task confirms the air-gapped by-construction claim already stated in `contracts/conformance-egress.md` still holds — the collector local-network-only, the whole suite exercising US5 scenario 1 by running against it (analyze I1).
- [ ] T031 [US5] [GATE:fail-closed] Hermetic row in `tests/component/test_capture_refuses.py`: with the **local** append raising, the step that produced the entry is refused — asserting the inherited `evidential_gap` path (research F2) so FR-014's capture-failure line is a row rather than a belief (SC-009b). The seam between capture (refuses) and delivery (never refuses) is the clarified decision, demonstrated from both sides.

**Checkpoint**: the guarantee is "no entry is ever lost," not "every entry has already arrived," and both halves are demonstrated.

---

## Phase 8: Polish, the honest limits, and the gate run

- [ ] T032 [P] Update `docs/glossary.md`: `audit egress`, `second copy / destination`, `reconciliation`, `separation probe`, `shipping lag window` — where the audit and evidence terms live, cross-referenced to `[[tamper-evidence]]`.
- [ ] T033 [P] Record the standing append-only credential in the security posture doc alongside ADR-0044's TFE management token: a named, bounded standing credential, argued not smuggled (Principle IV, plan Complexity Tracking).
- [ ] T034 Apply the contract's four break fixtures (watermark-before-delivery, head-as-upsert, probe-as-config-check, tail-gaps-all-pending), watch each named row fail, revert, and record outcomes **In force** in `specs/015-audit-egress/contracts/conformance-egress.md`.
- [ ] T035 Close ROADMAP gap 0 naming this feature, and confirm the three "what these rows do not prove" limits (lag window, organizational separation, which-copy-is-right) are stated in the contract and not overclaimed anywhere in the spec or plan — evidence not outrunning the claim is this feature's own subject (FR-018).
- [ ] T036 Run `make check`, `make conformance` (full, against a live enclave with the collector store up, on a clean tree — including the existing durability and evidence rows), and walk `specs/015-audit-egress/quickstart.md` sections 2–6. Record rows **In force** in the contract.

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─→ Phase 2 Foundational ─→ Phase 3 US1 (MVP)
                                          ─→ Phase 4 US2 (needs US1's reconciler)
                                          ─→ Phase 5 US3 (needs US1's reconciler + T009 probe)
                                          ─→ Phase 6 US4 (needs T009 probe)
                                          ─→ Phase 7 US5 (needs US1's ship pass)
                                                     ─→ Phase 8 Polish & the gate run
```

**Orderings that are not obvious from the phases:**

- **T001 → T002 → T003.** The store, then the role that cannot tamper, then the bring-up that
  applies the schema under that role. Applying the destination schema under the platform's own
  owner role would make the platform the destination's administrator — the capture the feature
  forecloses, reintroduced in a shell script.
- **T004 before any conformance row.** The directory must be on the host lane before a row in
  it can be collected — the 014 defect, pre-empted rather than repaired.
- **T007 → T008 → T009.** Protocol, implementation, probe: the probe is a method on the
  implementation, and it needs the destination reachable to attempt refusal against it.
- **T009 → T022, T025, T027.** The probe result feeds the scheduled pass, the posture, and the
  gate — build it once, in Foundational, consume it three places.
- **T012 (ship) → T014 (reconcile).** Reconciliation compares against what shipping delivered;
  a reconciler with nothing shipped reports everything missing.
- **T005/T006 → everything.** Both schemas exist and apply at bring-up before any pass runs, or
  the first ship dies on a missing relation (the defect that has bitten five times).
- **T017 → T019.** The `local_truncated` verdict before the row that engineers a truncation to
  catch.
- **T034 → T036.** Break fixtures before the final gate run, so the run certifies rows someone
  has watched fail.

**US2, US3, US4, US5 are mutually independent** once US1's ship pass and reconciler land; US3
and US4 additionally need the T009 probe from Foundational; T030a needs only T013's posture
wiring and can land with either US4 or US5.

## Parallel opportunities

- **Setup**: T001 ∥ T002 (different files); T003 needs both.
- **Foundational**: T010 ∥ T011 after their implementations; T005 ∥ T006.
- **After US1**: Phases 4, 6, 7 in parallel; Phase 5 after the reconciler.
- **Polish**: T032 ∥ T033.

**Not parallel, despite looking it**: T008 and T009 (same file, and the probe calls the
destination the impl configures); T012 and T014 (the reconciler reads what the ship pass
wrote).

## Implementation strategy

**MVP = Phase 3 (US1)**: a second copy exists, verifies alone, and a local rewrite is named.
That alone closes the headline of ROADMAP gap 0 — the platform's central claim stops being
enforced by a permission sitting next to the data it protects. Everything after it hardens the
claim: US2 catches the strongest attack, US3 makes the check a named operation, US4 proves the
separation is real rather than asserted, US5 makes the failure modes honest.

The conformance rows are one-per-file in a new `tests/conformance/evidence/` directory wired at
its creation (T004) — the 014 lesson applied at birth rather than after a gate runs green
against rows no lane collected.
