# Implementation Plan: Northbound API Operations

**Branch**: `spec/011-api-operations` | **Date**: 2026-07-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-api-operations/spec.md`

## Summary

Grow the northbound catalogue from four operations to ten, identically on both transports:
collect an authority change's disposition, list runs, retrieve a run's result, stop a run,
and enumerate agent definitions (two operations: list and get). Threads are deferred to the
portal per C1.

The approach follows from Phase 0's two structural findings. Nothing durable knows who
started a run — `checkpoints` carries no subject or tenant, because resume never needed
them — so listing requires a **run index** written at dispatch, on the `suspended_runs`
template. And the collect operation has nothing to look up — the accessor 008 returns is
stored nowhere — so submission gains a **change-request record**, which is what makes
collect a tenant-scoped read rather than an accessor-bearer capability. See
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: None new. Vault's `sys/control-group/request` endpoint is
reached through the existing authenticated-read shape; Postgres through the existing
credential path.

**Storage**: Two new Postgres tables (`run_index`, `authority_change_requests`), both
operational state beside the durability schema, neither read by resume. The trust fabric
is read-only to this feature — one `list` capability is added to an existing policy.

**Testing**: pytest. Parity and tenant-boundary rows in the enclave lanes 010 wired
(in-allocation and host); refusal shapes hermetic.

**Target Platform**: Linux containers under Nomad; macOS and Linux for development.

**Project Type**: Governed runtime library plus infrastructure module tree.

**Performance Goals**: List operations bounded (default page size, keyset cursor); no
per-caller server state between pages (FR-005). The stop is deliberately not instant —
C3 trades promptness for zero open intents, and nothing here tries to win that back.

**Constraints**: Every operation on both transports in the same change (FR-015); every
enumerable read tenant-scoped without disclosing withholding (FR-004); fail closed on
scope-resolution failure (FR-018); no static credentials (FR-016).

**Scale/Scope**: Six new operations, two new tables, one Terraform capability line,
~10 conformance rows.

### What this feature changes that is not its own

**Sealed core** (Principle V — approved spec plus security-maintainer review):

- `src/core/durability/checkpoint.py` — the step boundary learns to observe a durable
  STOPPED state (research F3). Additive; resume untouched.
- `src/core/run.py` is **not** changed. The stop is a durable-record write observed at
  checkpoint time, not a new run-state transition path.

**Surfaces**: `src/surfaces/api/` gains routes; `src/surfaces/mcp/` gains the same
operations as tools; the operations snapshot grows to ten.

**Dispatch seam** (008's, widened by 010): `dispatch()` gains the index write. The
signature does not change — the index consumes what dispatch already receives, which is
what makes this the *closure* of the recurring seam finding rather than a new instance.

**Infrastructure**: one `list` capability in `policies.tf`; two tables in a new
`src/core/runs/schema.sql` applied at bring-up beside the others (the 008/010 pattern —
schemas any role statement references are applied at bring-up, not on first use).

### The seams this feature consumes, and whether they accept what it needs

The check 009 wrote and 010 institutionalised, applied in advance:

| Seam | Built by | Accepts what this feature needs? |
| --- | --- | --- |
| `RunDispatcher.dispatch()` | 008/010 | **Yes for the signature** — subject, tenant, definition all flow through it already. The index write is a new consumer of existing arguments |
| `checkpoints` table | 005 | **No** — no subject/tenant, and deliberately not widened (research F1). The run index is the remedy |
| `BlockedPendingApprovalError.accessor` | 008 | **Partly** — the accessor reaches the caller and nothing else. The change-request record is the remedy (research F2) |
| `RunOutcome` / terminal checkpoint | 005 | **No** — `save` is last-write-wins, so a routine checkpoint (which carries `NULL` state) would erase a stop and resurrect the run. Remedied by terminal-once semantics on the upsert (research F3, corrected). The `payload` half is fine (research F4) |
| Sweeper `_is_suspended` | 009 | Yes — a STOPPED checkpoint is already unresumable; FR-009 is asserted, not built |
| `harness-authority-read` policy | 010 | **No** — `read` without `list` (research F5). One line |
| `VaultIdentityFabric` reads | 010 | Yes — registration and ceiling reads exist; enumeration composes them |
| Parity row / snapshot | 009 | Yes — grows by construction, fails on asymmetry in either direction |

Three "no"s, all found before implementation. Each has a one-table or one-line remedy
named in research rather than a discovery scheduled for mid-build.

### The delicate decision, restated where the plan commits to it

Stop must not become the pause ADR-0049 removed. The plan's mechanism *is* the argument:

- The stop writes a **terminal** state. Terminal states are unresumable by `is_terminal()`
  and invisible to the sweeper by `_is_suspended` — both existing, both asserted by rows.
- Nothing waits. The stopping caller returns immediately with the durable state; the run
  observes it at its next step boundary and ends after bracketing the in-flight step.
- The one race — stop lands as the run finishes — resolves in the store **only after
  `save` becomes terminal-once**: the shipped upsert was last-write-wins, and analyze
  pass 1 caught the research asserting the opposite of the SQL. With the COALESCE guard,
  the first terminal write wins, a routine checkpoint cannot clear a terminal state, and
  the record shows one outcome (edge case from the spec, asserted — including the
  resurrection fixture).

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (v1.2.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Operations over existing mechanisms; the only "new" storage is two index tables over facts the platform already produces |
| II — Total Interception; One Governed Tool Layer | **Pass** | No operation reaches a tool; all are reads plus one durable-state write. No second authorization path — MCP tools call the same functions the routes call, per 009's pattern |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-018; a scope-resolution failure refuses the read rather than shrinking it |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | No credential surface changes. Collect polls Vault with the caller's flow, never a stored token |
| V — Sealed Core, Versioned Seams | **Pass** | One additive change at the step boundary; reviewed as sealed core |
| VI — Lean by Default | **Pass** | No new dependencies; keyset pagination instead of stateful cursors |
| VII — Anti-Fragmentation | **Pass** | Schema and policy changes in the substrate-independent tree |
| VIII — Eval-Gated Promotion | **N/A** | No models, packs, or prompts |
| IX — Evidence Over Claims | **Pass** | Every operation audited (FR-017); FR-020's split — the trail records *not yours* distinctly while the caller sees *no such thing* — is the principle applied to refusals |
| X — The Decision Record Governs | **Pass** | ADR-0049 tension resolved by mechanism and recorded in spec assumptions; no ADR contradicted, none needed — no jurisdiction changes hands (contrast 010/FR-020, where the trust fabric's contents changed) |

**Gate result**: **PASS — proceed to Phase 0.**

### Who runs the blocking rows

Same-repo pull requests: the enclave CI lane. Fork pull requests, or a lane that could not
run: the agent harness per `AGENTS.md`. **Both runner lists must name any new conformance
directory** — 010 found the identity rows invisible to two lanes that each enumerate
directories, so this feature puts its rows in `tests/conformance/identity/`'s siblings'
existing paths (`tests/conformance/api/` for host rows, extending the identity directory
for in-allocation rows) rather than minting a new directory that both lanes would have to
learn about. Recorded in the conformance contract.

### Post-design Constitution Check

Re-evaluated after Phase 1. One entry sharpened.

**Principle IX gained a nuance worth naming.** Listing runs reads the run index, not the
audit trail — deliberately, per research F1. But that means the platform now has two
accounts of what ran: the index (product) and the trail (forensic). They are written at
the same moment by the same dispatch, and the conformance contract carries a row asserting
they cannot diverge silently — because two accounts that can disagree quietly is how an
investigator ends up trusting the wrong one.

**Gate result after design**: **PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/011-api-operations/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 — six findings, two structural
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── operations.md            # The ten-operation catalogue, both transports
│   ├── run-index.md             # The index, its writer, and what it is not
│   └── conformance-operations.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — NOT created by /speckit-plan
```

### Source (repository root)

```text
src/core/runs/
├── __init__.py           # NEW
├── index.py              # NEW — run index: written at dispatch, read by list/result/stop
├── changes.py            # NEW — authority change-request record + Vault status poll
└── schema.sql            # NEW — run_index, authority_change_requests

src/core/durability/
└── checkpoint.py         # CHANGED — step boundary observes a durable STOPPED state

src/surfaces/api/
├── runs.py               # CHANGED — list, result, stop routes
├── definitions.py        # NEW — enumerate/get agent definitions
└── mappings.py           # CHANGED — collect route

src/surfaces/mcp/
├── operations.py         # CHANGED — six new tools
└── transport.py          # CHANGED — same functions the routes call

specs/008-northbound-api/contracts/operations.snapshot.json   # GROWS to ten

infra/modules/trust-fabric/policies.tf   # CHANGED — list capability, one line
infra/bin/enclave-up                     # CHANGED — apply the runs schema at bring-up

tests/
├── unit/ component/                     # refusal shapes, three-way result disposition
└── conformance/{api,identity}/          # parity, tenant boundary, stop/sweeper rows
```

**Structure Decision**: `src/core/runs/` is a new package rather than additions to
`durability/`, because the index is deliberately *not* durability — resume never reads it,
and placing it beside checkpoints would invite the widening research F1 rejected. The open
question from research (whether `suspended_runs` eventually moves in) is recorded in the
package docstring, not resolved.

## Phases

**Phase 0 — Research.** Complete: [research.md](research.md).

**Phase 1 — Design & contracts.** Complete: [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md).

**Phase 2 — Tasks.** `/speckit-tasks`. Not created here.

### Sequencing notes for whoever writes tasks

1. **The two records go first** (run index, change-request record) — every story except
   enumeration reads one of them, and dispatch must write the index before anything can
   list it.
2. **Snapshot-first per operation** (research F6): grow the snapshot, watch the parity row
   fail, add both surfaces, watch it pass. The row becomes the loop.
3. **The stop's conformance row needs a long run** — the existing fixture pair completes
   immediately. A deliberately multi-step fixture is a prerequisite, the same shape as
   010's T009: a row against a fixture that cannot exhibit the behaviour passes vacuously.
4. **Backfill is not needed and should be said**: the run index starts empty and lists
   runs dispatched after this feature lands. A backfill from audit would launder the
   forensic path through a migration script. One line in the contract, so nobody "fixes"
   the empty list.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Two accounts of what ran (index + audit trail) | Listing from audit makes the forensic path a product dependency and audits every page view as evidence access | A divergence row in the conformance contract makes silent disagreement impossible, which is the actual risk of duplication |
| A change-request record for data Vault already holds | Vault's status endpoint takes only an accessor; without a tenant-scoped record the accessor is a cross-tenant capability | Storing nothing was 008's choice, and it is the defect US1 exists to fix |
