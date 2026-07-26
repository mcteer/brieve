# Implementation Plan: Durable Execution

**Branch**: `spec/005-durable-execution` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-durable-execution/spec.md`

## Summary

Split authority into a durable `DelegationGrant` — the human's consent, ceilinged by the agent
definition's maximum duration — and the short-lived per-step credential 003 already manufactures
under it. Add a fenced single-writer run lease, an intent/result bracket around non-repeatable
tool calls, an `Observer` seam that resolves an interrupted step by re-reading external state,
execution bounds, and terminal run states — including `PARKED` for anything only a human can
settle. Extend
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

**Storage**: PostgreSQL for checkpoints, leases, and intent/result records — a **long-lived
container in the stack**, not stood up per suite. The harness obtains its database credentials
from the **control-plane Vault's dynamic database secrets engine**, under its own attested
identity; the connection is opened with a credential Vault minted moments earlier and that expires
on its own (FR-017a). Credential expiry mid-run is expected rather than exceptional — the provider
refreshes on the database's rejection; only *grant* expiry parks a run. The 004
`InMemoryDurabilityProvider` survives as a test double for suites that are not about durability

**Testing**: `pytest` unit + component; new `tests/conformance/durability/` lane carrying the
seven in-force rows. Disruption is simulated **in-process** — a run is torn down and rebuilt from
its checkpoint — with the Postgres-backed provider additionally exercised across a real process
boundary so durability is demonstrated rather than asserted. No live models, no live
managed-product APIs

**Target Platform**: The local enclave (Terraform → Vault → Nomad → harness). The durability suite
runs **as a Nomad job**, so the test process has a workload identity of its own and the attestation
path is exercised by the tests rather than adjacent to them; suites that do not touch identity or
durability continue to run on the host without it

**Project Type**: Sealed-core feature. Extends `src/core/durability/` and `src/core/authority/`;
adds `src/core/observation/`, lease, credential, and bounds modules. `RunState` gains three
terminal states — `COMPLETED`, `STOPPED`, `PARKED` — because 002's `ACTIVE`/`REFUSED` pair cannot
express a run that finished, one a bound halted, or one waiting on a human. No adapter changes
beyond surfacing the new run states

**Performance Goals**: N/A — success is `make check` + `make conformance` green. The durability
lane's runtime is a real constraint on the fast lane's <5 min budget and is a design input for
how disruption is simulated

**Constraints**: Semantics defined **above** the provider interface (FR-012); fail-closed on
every resume path; sealed-core changes capped by FR-018; security-maintainer review on `feat/005`

**Scale/Scope**: Single-node enclave. Per the spec's stated caveat, fencing and parking are
proven against single-node behaviour; multi-node partition is not exercised

### Settled — Postgres lifetime and credential path

Postgres is a **long-lived container in the stack**. Whether Nomad schedules it or something else
does is not a property this feature depends on; what it depends on is that the database outlives
any individual run, which is what makes a checkpoint worth writing.

The harness obtains its credentials from the **control-plane Vault's dynamic database secrets
engine** — a Vault-minted, short-lived, per-workload credential, not a DSN handed to the process.
This closes FR-017a's plumbing question in the shape the requirement always implied, and removes
the last standing credential in the enclave.

It also has a consequence worth stating rather than discovering: **the harness must authenticate
to Vault before it can reach the database.** Under ADR-0048 the only supported way it does that is
its Nomad workload identity. So the database path is not merely adjacent to the attestation
chain — it runs *through* it. A harness with no attested identity cannot open a connection at all,
which is the correct failure and a stronger one than a policy check.

### Settled — the suite runs as a Nomad job, and the workload does its own exchange

Durability tests execute **inside a Nomad allocation**, not on the host. This is not a preference;
it is the only arrangement the decisions already taken permit. The harness reaches Postgres with a
Vault-issued credential (FR-017a), its only route to Vault is Nomad workload identity (ADR-0048),
and a host process has no such identity. The alternatives are the ones this project has already
rejected: hand the process a DSN (forbidden by FR-017a), or give it a second Vault auth method —
approle, userpass, a token — which is a standing credential on a developer's machine.

`infra/dev-enclave/jobs/harness-probe.nomad.hcl` is already the shape: a job whose ID is bound in
the Vault JWT role, authenticating as itself. Running the suite is that job with a different
command.

**The workload performs the exchange itself.** Nomad *is* a Vault client — that is why Vault
cannot be a Nomad job (ADR-0048's circularity argument) — and it can broker secrets into a task
through a `vault` stanza and `template`. This design deliberately does not use that path. The
workload presents its own identity and fetches its own credential, for two reasons:

1. A brokered secret lands in the task's environment or filesystem, where it is a credential at
   rest for the life of the allocation. A fetched one lives in process memory for as long as it
   works.
2. FR-017b refreshes **on the database's rejection**. A Nomad-templated secret is renewed on
   Nomad's schedule, so the workload cannot re-fetch in response to the signal that actually
   matters. Brokering would make the requirement unimplementable.

**Which identity carries the database policy** is worth stating precisely, because getting it
backwards would be serious: the policy sits on the **workload identity**, never on the per-step
authority manufactured for the agent. The harness process may reach its own state store; the
agent's tool calls may not. If database access ever appeared in a definition's ceiling, a
model-chosen call could reach the checkpoint store — which is the run's own memory of what it has
done.

**What remains for the deployment-tree feature** is mechanical, not architectural: how it invokes
the suite in an allocation and returns exit status and output. That is a build detail, and it
changes nothing below.

### How run state is recorded and retrieved

Written out because the design was not legible from the artifacts without it, and because the
layers are easy to collapse — with real consequences, since collapsing them is how one concludes
the agent can reach its own state store.

**One process, three layers.** "Harness" means this product, not the agent framework and not
`tests/harness/` (see [docs/glossary.md](../../docs/glossary.md)):

```text
Nomad allocation
└── container
    └── ONE process — the Harness
        ├── harness core      ← authenticates to Vault, records run state
        ├── adapter           ← maps Pydantic AI's concepts onto core
        └── agent (framework) ← chooses tools; holds no credential, touches no store
```

**Two credential paths that never cross.** The core reaches Postgres as *itself*; the agent
reaches tools under the user's grant. An agent's per-step authority cannot reach the database —
if it could, a model-chosen tool call could rewrite the run's own record of what it has done.

| Path | Identity | Yields | Used for |
| --- | --- | --- | --- |
| core → Postgres | Nomad workload identity | Dynamic database credential | Recording and retrieving run state |
| agent → tools | `DelegationGrant` | Short-lived `TaskCredentialRef` | Tool calls only |

**Recording:**

```text
Nomad schedules allocation, issues a workload identity JWT to the task
       │
       ▼
core → POST /v1/auth/nomad/login        (presents the JWT; no secret anywhere)
       └─ Vault returns a token carrying the database policy
            │
            ▼
core → GET /v1/database/creds/harness   → fresh Postgres user, short lease
            │
            ▼
       connect; acquire the run lease
            │
     ┌──── per step ───────────────────────────────────────┐
     │  agent chooses a tool                               │
     │  core manufactures per-step authority under the     │
     │    grant and invokes through invoke_tool            │
     │  non-repeatable? intent record → effect → result    │
     │  core writes CheckpointBlob: step_index, grant_id,  │
     │    written_by, run_state, stop_reason               │
     └─────────────────────────────────────────────────────┘
            │
            ▼
       work finishes → run_state = COMPLETED
```

**Retrieving.** Disruption kills the allocation; Nomad schedules a new one, so nothing carries
over — which is what makes replay unavailable rather than forbidden:

```text
new allocation → new workload identity → Vault → NEW database credential
       │
       ▼
load checkpoint by run id
       ├─ COMPLETED or STOPPED?    → nothing to resume
       ├─ grant expired?           → PARKED
       ├─ checkpoint unreadable?   → PARKED / refuse
       │
       ▼
acquire lease → supersedes the prior holder; its writes are now rejected
       │
       ▼
re-manufacture per-step authority under the surviving grant
       │
       ▼
resolve open intents by observation
       ├─ happened          → skip, continue
       ├─ did_not_happen    → redo, continue
       └─ cannot_determine  → PARKED
```

**The two similar-sounding events are not the same event.** The *run* re-authenticates — new
allocation, new identity, fresh per-step authority under the surviving grant; that is the
Principle IV guarantee. The *provider* refreshes a credential when Postgres rejects an expired
one; that is plumbing, and it touches neither the grant nor the lease nor the run.

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
│   ├── credentials.py              # dynamic Postgres credential from Vault; reconnect on expiry
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
