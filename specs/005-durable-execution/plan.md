# Implementation Plan: Durable Execution

**Branch**: `spec/005-durable-execution` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-durable-execution/spec.md`

## Summary

Split authority into a durable `DelegationGrant` — the human's consent, ceilinged by the agent
definition's maximum duration — and the short-lived per-step credential 003 already manufactures
under it. Add a fenced single-writer run lease, an intent/result bracket around non-repeatable
tool calls, an `Observer` seam that resolves an interrupted step by re-reading external state,
execution bounds, and a `PARKED` run state for anything only a human can settle. Extend
`DurabilityProvider` so a checkpoint can actually be resumed, and back it with Postgres scheduled
by Nomad. Attach the seven durability conformance rows.

The load-bearing insight from ADR-0048 shapes the whole design: **resume-re-authenticates and
single-writer fencing are properties of the substrate, not rules this code enforces.** A resumed
run is a new Nomad allocation with a new attested identity, so the prior credential is
unobtainable rather than forbidden. The implementation's job is to avoid reintroducing what the
substrate already prevents, and to prove that it did not.

## Technical Context

**Language/Version**: Python 3.12+ (existing floor); fully typed; Pydantic models at boundaries;
`src/core` remains free of agent-framework imports

**Primary Dependencies**: Existing (`pydantic`, `opentelemetry-api`; `pydantic-ai-slim` behind the
`adapters` extra). **New**: a PostgreSQL driver for the durability provider — `psycopg` (v3) is
the current default choice, pinned and justified at implement time per the regulated
dependency-tree bar. No other addition; the lease, bracket, and bounds are library code

**Storage**: PostgreSQL, scheduled by Nomad, for checkpoints, leases, and intent/result records.
Vault issues per-workload database credentials (FR-017a). The 004 `InMemoryDurabilityProvider`
survives as a test double for suites that are not about durability

**Testing**: `pytest` unit + component; new `tests/conformance/durability/` lane carrying the
seven in-force rows. Disruption is simulated **in-process** — a run is torn down and rebuilt from
its checkpoint — with the Postgres-backed provider additionally exercised across a real process
boundary so durability is demonstrated rather than asserted. No live models, no live
managed-product APIs

**Target Platform**: The local enclave (Terraform → Vault → Nomad → harness). Durability tests
require it; suites that do not touch identity or durability continue to run without it

**Project Type**: Sealed-core feature. Extends `src/core/durability/` and `src/core/authority/`;
adds `src/core/observation/`, lease, and bounds modules. No adapter changes beyond surfacing the
new run state

**Performance Goals**: N/A — success is `make check` + `make conformance` green. The durability
lane's runtime is a real constraint on the fast lane's <5 min budget and is a design input for
how disruption is simulated

**Constraints**: Semantics defined **above** the provider interface (FR-012); fail-closed on
every resume path; sealed-core changes capped by FR-018; security-maintainer review on `feat/005`

**Scale/Scope**: Single-node enclave. Per the spec's stated caveat, fencing and parking are
proven against single-node behaviour; multi-node partition is not exercised

### NEEDS CLARIFICATION — owned by the deployment-tree feature, not by this plan

These are interface questions about infrastructure this feature consumes. They are recorded
rather than answered because answering them here would define another feature's surface from
inside this one. Each has a working reference in [`infra/dev-enclave`](../../infra/dev-enclave/),
which constrains the answer without settling it.

1. **Where do durability tests execute** — inside a Nomad allocation, or on the host against
   scheduled services? This determines whether the test process has a workload identity of its
   own, and therefore whether the attestation path is exercised by the tests or merely adjacent
   to them. It is the highest-impact unknown here.
2. **How does the test harness obtain a Postgres connection** — dynamic Vault-issued credentials
   under the workload's identity (the FR-017a shape), or a bootstrap DSN with dynamic credentials
   proven separately? The requirement is settled; the plumbing is not.
3. **What does `make dev-up` guarantee on exit** — services reachable, Vault unsealed and
   configured, Postgres migrated? Determines what test setup may assume versus must check.

None blocks writing the design below: the seam, the entities, and the conformance rows are
unaffected by how the environment is reached.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.0.1**; re-check if the version advances.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Durable execution as a library over the seam 004 defined; no workflow-engine product. Postgres is scheduled, not operated by us |
| II — Total Interception; One Governed Tool Layer | Pass | Resumed runs invoke through the same `invoke_tool`; the intent/result bracket wraps that path rather than creating a second one |
| III — Fail-Closed, In-Process Enforcement | Pass | Unwritable checkpoint, unreadable checkpoint, unobservable step, expired grant, and lost lease all refuse or park |
| IV — Zero Standing Credentials; Authority Per Task | Pass | Grant is durable, credential is not. Resume re-attests as a new allocation. Checkpoints hold state only. FR-017a removes the last standing credential — the database password |
| V — Sealed Core, Versioned Seams | Pass | Durability is sealed core; guarantees sit above the provider interface. `DurabilityProvider` gains methods — a **breaking seam change**, assessed below |
| VI — Lean by Default | Pass | One new library dependency (a Postgres driver). Postgres itself is not a new operated component — it is part of the enclave ADR-0025 already defines |
| VII — Anti-Fragmentation | Pass | One durability lane over one core |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs, prompts, models, or policies promoted |
| IX — Evidence Over Claims | Pass | Correlation and hash chain survive the disruption boundary (FR-015); intent, observation, and resolution are recorded. Re-observation consumes ADR-0018 receipts rather than re-owning them |
| X — The Decision Record Governs | Pass | Binds ADR-0048, 0024, 0026, 0018, 0047. Defers workflow-engine providers under ADR-0028's named-trigger rule, recorded rather than silent |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1: still **PASS**. Three notes worth carrying into review rather than
burying:

- **Principle V — breaking seam change.** `DurabilityProvider` gains lease and intent-record
  operations and `CheckpointBlob` gains resume metadata; 004's protocol cannot satisfy the new
  guarantees. Pre-1.0 with one in-repo implementation and no external consumers, so the same
  exemption 004 recorded applies — declared in the contract and the feat PR rather than assumed.
- **Principle IV — the grant is new durable state about a human's consent.** It holds no
  credential, but it is the first object whose lifetime encodes "the user said yes." Expiry is
  enforced fail-closed (park, never resume), and it is deliberately not renewable from inside a
  run — only by a human, through a surface this feature does not build.
- **Principle VI — one new dependency.** A Postgres driver is a library, not an operated
  component, and Postgres was already in the enclave baseline. Pin and justification are an
  implement-time duty.

## Project Structure

### Documentation (this feature)

```text
specs/005-durable-execution/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── durability-seam.md
│   ├── grant-and-resume.md
│   └── conformance-durability.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
src/core/
├── authority/
│   ├── grant.py                    # DelegationGrant: issue, validate, expiry, park semantics
│   ├── manufacture.py              # per-step credential now issued under a grant
│   └── types.py                    # GrantRef; TaskCredentialRef unchanged
├── durability/
│   ├── types.py                    # CheckpointBlob + resume metadata; extended provider protocol
│   ├── memory.py                   # InMemoryDurabilityProvider — test double, extended to match
│   ├── postgres.py                 # PostgresDurabilityProvider — the real one
│   ├── schema.sql                  # checkpoints, leases, intent records
│   ├── lease.py                    # RunLease: acquire, fence, reject superseded writers
│   └── resume.py                   # resume_run: re-attest, re-observe, continue or park
├── observation/
│   ├── types.py                    # Observer protocol; ObservationOutcome
│   └── bracket.py                  # intent/result bracket around non-repeatable calls
├── bounds.py                       # max duration, step limit, stuck-wait watchdog
├── run.py                          # RunState gains PARKED; lease + bounds on GovernedRun
└── registry/memory.py              # ToolRegistration gains repeatable flag + observer

tests/harness/
└── durability_fixtures.py          # disruption simulation, fake Observer, grant helpers

tests/conformance/durability/       # the seven in-force gate rows
tests/component/                    # resume, park, fencing through the governed path
tests/unit/                         # grant expiry, bounds, bracket, checkpoint purity
```

**Structure Decision**: Durability and authority changes stay in `src/core`; the adapter is
untouched except where the new run state surfaces. `observation/` is a **new core package rather
than part of the durability seam** because re-observation is a harness guarantee (FR-006, FR-012)
— putting it behind the provider interface would let a provider decide whether resume re-observes,
which FR-012 forbids. `postgres.py` sits beside `memory.py` under the same protocol; a
`providers/` tree waits until there is a second real provider.

**Explicitly not in this plan**: the deployment module tree's layout. That belongs to the
deployment-tree feature (see [ROADMAP.md](../../ROADMAP.md)), and defining it here would be this
feature deciding another's surface.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
