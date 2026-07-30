# Implementation Plan: Wire resume into the dispatched path

**Branch**: `spec/014-dispatched-resume` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-dispatched-resume/spec.md`

## Summary

One integration and one repair. The integration: the dispatched entrypoint takes
`resume_run` when the dispatch declares itself a resume, honours all three decision
outcomes, and skips work the brackets show already happened — consuming the three pieces
013 left orphaned (the tool→product mapping, the registered observers, the resume refusal
handling). The repair: **the dispatched path has no durable grant** (research F1), so a
grants record joins the durability schema, the entrypoint starts issuing real grants, and
its latent bug — writing the 15-minute credential id into the checkpoint's `grant_id`
column — is fixed in the same change, because the store would otherwise index garbage.

Everything is asserted **through a dispatch**, merge-blocking, in the existing enclave lane
(clarify Q2), with re-observation against live Vault in both directions (clarify Q3) and a
resume-attempt cap of five (clarify Q1, D3).

## Technical Context

**Language/Version**: Python 3.12 (existing toolchain; `uv`)

**Primary Dependencies**: none new. The feature consumes what exists: the 005 durability
library, the 009 sweeper and dependency store, the 013 observers and product mapping.

**Storage**: one new table — `grants` — in the existing durability schema, applied at
bring-up in the same statement block as everything else (the rule that has bitten four
times). One additive column: `resume_count` on checkpoints. No new store, no new operated
component.

**Testing**: pytest. Hermetic rows for the entrypoint's resume branch, the grant store, the
cap arithmetic, and the discriminator; **dispatch-level rows in the merge-blocking enclave
lane** for the five 005 properties plus the cap — driving the scheduler, killing
allocations, flapping the terraform fixture product (research D5).

**Target Platform**: the dev enclave. No new operated component.

**Project Type**: an integration (entrypoint ⇄ durability library) + one schema addition +
a conformance discipline (dispatch-level assertions replacing function-level scope).

**Performance Goals**: none newly binding. The enclave lane gets slower by design — the
spec's own Assumption accepts minutes per row, because waiting is what the flapping row
tests.

**Constraints**: no path carries authority across the disruption (FR-011 — `resume_run`
has no credential parameter and none may be added); the grants table holds consent
metadata and zero credential material (FR-012); the cap is platform-set and durable
(FR-009a/c); an unhandled `ResumeDecision` outcome must not default to proceeding (FR-003).

**Scale/Scope**: one entrypoint branch, one table, one column, one audit event, one
dispatcher flag, ~six dispatch-level conformance rows.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Nothing new is built that exists upstream; the feature connects two halves of this platform's own code. The scheduler's stop/dispatch is the disruption mechanism rather than any new chaos tooling. |
| II — Total Interception | **Pass** | Resumed runs invoke tools through the same `invoke_tool` pipeline; the resume path adds no invocation surface. The pending-step skip happens *before* invocation, so no call bypasses hooks — asserted by the exactly-once row, which would fail on a double-invoke and on a skipped-hook invoke alike. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-003 is this principle applied to the decision seam: every `ResumeDecision` outcome is handled, and an unhandled one refuses rather than proceeds. Grant absent → refuse (a missing grant is not "no consent required" — F1's bug made this reachable, and the fix makes it refuse). Cap exhausted → terminal stop, never a fifth-plus revival. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The core of the feature. Fresh authority from the resuming allocation's own attested identity (ADR-0048 makes replay structurally unavailable); the grants table holds consent metadata — subject, scope, expiry — and **no credential material**, extending the existing no-secret sweep to the new table. The checkpoint's `grant_id` finally references durable consent, as ADR-0026 always said it did. |
| V — Sealed Core, Versioned Seams | **Pass, four recorded additions — none a signature break** | `CheckpointBlob` gains `resume_count` (additive, defaulted); `AuditEventType` gains `RUN_RESUMED`; `DurabilityProvider` gains grant save/load (additive protocol methods, both implementations updated in the same change — pre-1.0, in-repo consumers only, the same posture 005's own seam note declared); the dispatcher gains a `resume` flag (optional, defaulted). `resume_run`'s signature does not move. |
| VI — Lean by Default | **Pass** | One table in the Postgres that already runs. The cap is a constant, not a service. No queue, no scheduler beyond the one that exists. |
| VII — Anti-Fragmentation | **Pass** | The resume path is identical across substrates; the jobspec flag is metadata the parameterized job already carries a mechanism for. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No model promotion here. The one touchpoint: a resumed run re-validates its binding map (built in 013), and a fallback on resume records `MATRIX_FALLBACK` via the field `ResumeDecision` already carries — this feature wires the emit at the caller that owns the sink, closing the loop 013's plan documented. |
| IX — Evidence Over Claims | **Pass — and this is the feature** | The whole feature exists because a claim outran its evidence. `RUN_RESUMED` puts every revival and its outcome in the trail (D4); FR-020 re-scopes 005's contract the moment the dispatch-level rows exist; and the rows themselves are the evidence discipline — SC-009a: a property nobody is obliged to run is not evidence. |
| X — The Decision Record Governs | **Pass** | ADR-0049 implemented as amended (stop, not park); ADR-0026 implemented as written (the durable half that was never built); ADR-0047 honoured by FR-020's re-scoping. No new ADR needed — every decision here lands inside existing records' text. |

**Named-runner obligation** (constitution v1.1.0): **none owed.** Every blocking row this
feature adds runs in CI's enclave lane on same-repo pull requests, per clarify Q2. Fork
pull requests fall to the agent harness per `AGENTS.md`, as with 005's existing rows.

**Gate result**: **PASS — proceed to Phase 0.** (Phase 0 complete; re-checked post-design:
still PASS. The grants table was the one addition that could have moved a verdict — it is
consent metadata in the existing store, so IV and VI hold.)

## Project Structure

### Documentation (this feature)

```text
specs/014-dispatched-resume/
├── plan.md              # This file
├── research.md          # Phase 0 — findings F1–F3, decisions D1–D5
├── data-model.md        # Phase 1 — grant record, resume metadata, decision payload
├── quickstart.md        # Phase 1 — end-to-end validation
├── contracts/
│   └── conformance-resume.md   # The five 005 properties, asserted through dispatch
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/core/durability/
├── schema.sql           # + grants table (consent metadata, zero credential material);
│                        #   + resume_count column on checkpoints
├── types.py             # CheckpointBlob gains resume_count (additive, defaulted);
│                        #   DurabilityProvider gains save_grant / load_grant
├── postgres.py          # both grant methods; schema applies at bring-up via enclave-up's
│                        #   existing statement block
├── memory.py            # the in-memory provider keeps parity for hermetic rows
└── resume.py            # increments resume_count after the lease claim; refuses past
                         #   the cap with a terminal stop (D3). The ONLY behavioural
                         #   change to the library — everything else is consumption.

src/core/audit/schema.py # + RUN_RESUMED (D4): one event, the outcome in the payload —
                         #   continued/stopped/suspended, reason, attempt, step counts

src/core/run.py          # RESUME_ATTEMPT_CAP constant beside the other bounds (D3);
                         #   platform-set, never from workflow code or dispatch meta

src/surfaces/dispatch/nomad.py        # dispatch() gains resume: bool = False → meta (D1)
infra/jobs/agent-run.nomad.hcl        # meta_optional + "resume"; env RUN_RESUME
src/surfaces/mcp/server.py            # _resume_dispatcher sets resume=True — the one caller
src/surfaces/dispatch/entrypoint.py   # THE integration:
                                      #   RUN_RESUME=1 → load grant by the checkpoint's
                                      #   grant_id; resume_run(...) with
                                      #   observers=registry.observers() and
                                      #   depends_on=dependency_products(loaded_packs);
                                      #   honour all three outcomes; skip completed steps;
                                      #   emit RUN_RESUMED and MATRIX_FALLBACK
                                      #   fresh path → issue_grant + save_grant; write the
                                      #   GRANT id into checkpoints (F1's bug, fixed)

tests/conformance/durability/         # the dispatch-level rows join 005's lane:
                                      #   disrupt/complete exactly-once; re-observe both
                                      #   directions against live Vault; suspend-names-
                                      #   product + sweeper revival; cap exhaustion under
                                      #   flapping; expired-grant terminal stop; fencing
```

**Structure Decision**: no new packages. The grant store is durability's (ADR-0026 put it
there in prose six features ago); the cap constant is core's; the discriminator is the
dispatcher's. The entrypoint grows one branch rather than a second entrypoint — a resume
*is* a dispatch, differing in what it loads, and two entrypoints would be the two-jobspec
drift D1 rejected in miniature.

## Complexity Tracking

No violations to justify. The four seam additions are recorded in the Constitution Check;
the one behavioural change to the 005 library (the cap, in `resume.py`) implements a
clarify decision and is covered by its own dispatch-level row.
