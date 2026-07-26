# Research: Durable Execution

**Feature**: `specs/005-durable-execution`
**Date**: 2026-07-25

## Decision: Two-level authority — durable grant, ephemeral credential

- **Decision**: Add `DelegationGrant` as a durable object recording the requesting user's consent
  to a task, with an expiry ceilinged by the agent definition's maximum run duration. The
  existing `TaskCredentialRef` continues to be manufactured per step *under* a grant and keeps
  its short TTL. `manufacture_authority` gains a grant parameter; the grant never appears in a
  checkpoint.
- **Rationale**: FR-001/FR-002; ADR-0026. The grant is the human-meaningful unit ("I consented to
  this task") and the credential is the technically-meaningful one (valid for minutes). Merging
  them forces a choice between a token that outlives its safety margin and a run that dies when
  its token does.
- **Alternatives considered**: Extend credential TTL to cover the longest plausible run (inverts
  the security model to accommodate the slowest case; rejected by ADR-0026 explicitly). Store a
  refresh token in the checkpoint (a credential in a checkpoint, which FR-003 forbids and which
  hands an attacker with checkpoint-storage access exactly what they need).

## Decision: Resume re-attests because the allocation is new — not because we check

- **Decision**: `resume_run` re-manufactures authority under the surviving grant using the
  *current* allocation's workload identity. No code path accepts a credential recovered from a
  checkpoint, and there is nothing to recover because none is written.
- **Rationale**: ADR-0048. A resumed run is a new Nomad allocation with a new attested identity;
  the prior credential is unobtainable rather than forbidden. Demonstrated in
  [`infra/dev-enclave`](../../infra/dev-enclave/): a Nomad-scheduled container exchanged its
  workload identity for a ceiling-scoped 300-second token with no credential in the jobspec.
- **What this changes about the work**: the implementation's job is *not* to enforce
  no-replay — it is to avoid reintroducing a path that defeats what the substrate already
  guarantees, and to prove none exists. That is a review-and-assert task, not an enforcement one.
- **Alternatives considered**: Harness-enforced replay prevention with a credential blacklist
  (redundant given the substrate, and a blacklist is a thing that can be wrong; rejected).

## Decision: Fencing is an identity comparison, not a timing race

- **Decision**: `RunLease` records the holder's allocation identity. Writes and tool calls carry
  that identity; a superseded holder is rejected on comparison. Lease acquisition and fencing are
  a single conditional update in Postgres.
- **Rationale**: FR-009. ADR-0026 requires a partitioned instance's writes be *rejected, not
  merely raced*. Comparing identities gives that unconditionally; comparing timestamps or
  attempting mutual exclusion in the application does not.
- **Alternatives considered**: Advisory locks (release on connection loss, which is exactly the
  partition case). Lease renewal with expiry (introduces a window where both instances believe
  they hold it). A monotonic fencing token independent of identity (works, but duplicates
  information the allocation identity already carries).

## Decision: PostgreSQL as the durability provider, long-lived in the stack

- **Decision**: `PostgresDurabilityProvider` is the real implementation, backed by a **long-lived
  Postgres container** rather than one stood up per suite. `InMemoryDurabilityProvider` from 004
  survives as a test double for suites unrelated to durability. The durability conformance rows
  run against Postgres.
- **On who schedules it**: Nomad does today (see the jobspec in `infra/dev-enclave/jobs/`), and
  nothing in this feature depends on that. What the feature depends on is that the database
  **outlives any individual run** — a checkpoint written to storage that disappears with the
  process is not durability, it is a variable with extra steps.
- **Rationale**: The spec's corrected assumption, ADR-0024's Lean default, ADR-0048. Postgres is
  a component this project deploys; substituting a lighter datastore means the durability code
  ships untested against what it runs on. It also gives the transactional conditional update the
  lease needs, which an embedded store would give only under different semantics.
- **Correcting the record**: this spec originally assumed a hermetic provider on the grounds that
  no feature had introduced an operated service. That was wrong on the facts — `make dev-up` had
  been reserved since 001 and documented as bringing up Postgres, and the Integration test tier
  already named it a real backing service.
- **Alternatives considered**: SQLite (a different technology from what production runs — the
  substitution this project's principle rejects). A file-backed provider (same objection, plus it
  would have to reimplement the transactional guarantees Postgres provides).

## Decision: Database credentials come from Vault's dynamic database secrets engine

- **Decision**: The harness obtains its Postgres credentials from the control-plane Vault's
  **database secrets engine**, minted per workload and short-lived. No DSN with a password is
  handed to the process, and no shared standing database credential exists.
- **Rationale**: FR-017a and Principle IV. A static database password is a standing credential
  wherever it sits — jobspec, environment, secret file — and Principle IV admits no exception for
  "it's only the database." The licensed engine is available, so the compliant path is also the
  available one.
- **The consequence worth naming**: the harness must authenticate to Vault *before* it can reach
  the database, and under ADR-0048 its only route to doing so is its Nomad workload identity. The
  database path therefore runs **through** the attestation chain rather than beside it. A process
  with no attested identity cannot open a connection at all — a stronger and earlier failure than
  a policy check, and one that cannot be forgotten.
- **Alternatives considered**: A static role with a rotated password (still standing between
  rotations, and rotation is an operational promise rather than a structural property). A
  bootstrap DSN for tests with dynamic credentials proven separately (proves the mechanism in a
  place the product does not use it, which is the substitution this project's principle rejects).

## Decision: Database credential refresh is reactive — the rejection is the signal

- **Decision**: `src/core/durability/credentials.py` obtains a dynamic Postgres credential from
  the control-plane Vault under the workload's attested identity. When a connection attempt fails
  authentication, it fetches a fresh credential and retries **once**. The refresh is reactive —
  driven by the database's own rejection — rather than scheduled against the lease clock.
- **Named "credential refresh" on purpose**: "re-authenticate" is already spoken for by the run
  re-attesting to Vault on resume (US2), which is a Principle IV guarantee. A connection retry and
  a security property under one word is a collision that reads as familiar and hides a difference
  that matters.
- **Rationale**: FR-017a with FR-002. The Vault role's lease is on the order of an hour; a durable
  run is designed to outlive that. Treating expiry as fatal would mean a feature built for
  long-running execution cannot run longer than one credential lifetime — and the failure would
  surface only in the longest runs, which are precisely the ones this exists for.
- **Why reactive rather than a renewal timer**: a timer only handles the expiry it predicts. The
  authentication failure is the authoritative signal, and it also covers what a timer misses — a
  credential revoked early, a lease invalidated by a Vault operation, or a database restarted
  underneath the run. It needs no clock agreement between Vault, Postgres, and the harness.
- **The bound that keeps it honest**: retry once, only on an authentication failure, and surface
  the second one. An unbounded retry would spin against a genuine misconfiguration — and the
  enclave has one waiting: destroying the Postgres volume resets the database to its bootstrap
  password while Vault still holds the rotated one, so every credential fails auth. That must
  present as a clear failure rather than a hang.
- **The distinction that must not blur**: a *database credential* expiring is plumbing and
  reconnects silently; a *grant* expiring is withdrawn consent and parks the run (FR-005).
  Collapsing them in either direction is a real error — auto-renewing consent would defeat
  ADR-0026, and parking on a database lease would make the platform look like it lost permission
  when it only lost a socket.
- **Why its own module rather than a clause inside the provider**: the acquisition path is where
  the attestation chain is actually exercised — identity, exchange, lease, renewal — and it is
  worth being able to test and read it without a database attached. Folding it into
  `postgres.py` would also make it invisible to a second provider that needs the same thing.
- **Alternatives considered**: a renewal timer keyed to the lease duration (predicts one failure
  mode and misses the rest, and depends on clocks agreeing). A long-lived credential sized to the
  longest plausible run (a standing credential by another name, which is what Principle IV
  forbids). Fail the run and resume it (turns a socket problem into a durability event, and the
  resume would hit the same expiry). A static role with rotation (still standing between
  rotations).

## Decision: Non-repeatable tool calls are bracketed; repeatability is registry metadata

- **Decision**: `ToolRegistration` gains a repeatable flag and an optional `Observer`. Calls to
  non-repeatable tools are wrapped: an intent record is written before the effect and a result
  record after. On resume, an interrupted bracket is resolved by asking the tool's `Observer`
  what actually happened.
- **Rationale**: FR-006/FR-007. Only the tool author knows whether an effect is repeatable and
  how to observe it; putting both on the registration keeps that knowledge with the tool rather
  than in a central table that drifts.
- **Ongoing obligation, not a one-time task**: every future non-repeatable tool inherits this.
  ADR-0026 says this is where implementation difficulty concentrates and where getting it wrong
  produces exactly the duplicate side effects the bracket exists to prevent.
- **Alternatives considered**: Treat every tool as non-repeatable (correct but expensive — every
  call pays for observation). Infer repeatability from `product_mode` (conflates two orthogonal
  properties: a federated call can be non-repeatable and a brokered one idempotent).

## Decision: An unobservable interrupted step parks rather than guessing

- **Decision**: `ObservationOutcome` is a three-way result — happened, did-not-happen,
  cannot-tell. The third parks the run for human resolution; it never resolves to a guess.
- **Rationale**: FR-008 and the spec's edge cases. Guessing wrong in either direction is a
  duplicate infrastructure change or a silently incomplete run, and the whole point of
  re-observation is to make the decision on evidence.
- **Alternatives considered**: Default to not-repeating (silently incomplete runs, which is the
  quieter and therefore worse failure). Default to repeating (duplicate side effects, precisely
  what ADR-0026 forbids).

## Decision: Parking is a run state, not an error

- **Decision**: `RunState` gains `PARKED`. Parked runs are durable, queryable, and resumable once
  the blocking condition clears — expired consent renewed, or an unobservable step resolved.
- **Rationale**: FR-005/FR-008. A parked run is waiting, not failed; modelling it as an error
  loses the distinction an operator most needs.
- **Known gap, deliberate**: the surface a human uses to renew consent or resolve a step is
  Control Groups (ADR-0016) and northbound (ADR-0033), both out of scope. Parked runs are
  observable and resumable programmatically, which meets the conformance bar and is honestly less
  than a product.
- **Alternatives considered**: Terminate and require a new run (loses the checkpoint, so the work
  is lost along with the consent). A generic ERROR state with a reason code (conflates
  "needs a human" with "failed").

## Decision: Bounds are checked in the invoke path

- **Decision**: `bounds.py` holds maximum duration, step limit, and stuck-wait watchdog, checked
  where the run advances rather than by a background timer.
- **Rationale**: FR-011. A bound enforced by a separate timer is a bound that fails when the timer
  does; checking where work happens means the check cannot be skipped by the work proceeding.
- **Alternatives considered**: Background watchdog thread (an independent failure domain guarding
  a safety property). Enforcement in the adapter (leaves core-only runs unbounded).

## Decision: Disruption is simulated in-process, with one real process boundary

- **Decision**: Most scenarios tear a run down and rebuild it from its checkpoint in-process.
  Additionally, at least one Postgres-backed scenario crosses a genuine process boundary, so
  durability is demonstrated rather than asserted.
- **Rationale**: FR-016 and the fast lane's <5 min budget. In-process disruption is deterministic
  and fast; a purely in-process suite would prove the code reloads its own state, not that the
  state survived anything.
- **Alternatives considered**: Kill real infrastructure (non-deterministic, slow, and the spec
  forbids it). Purely in-process (cheaper, but proves the weaker claim).

## Decision: The durability suite runs as a Nomad job, and the workload fetches its own credential

- **Decision**: Durability tests execute inside a Nomad allocation. The test workload presents its
  own Nomad workload identity to Vault and fetches its own database credential; Nomad does not
  broker the secret into the task.
- **Rationale**: the decisions already taken leave one arrangement standing. The harness reaches
  Postgres with a Vault-issued credential (FR-017a); its only route to Vault is workload identity
  (ADR-0048); a host process has none. Handing it a DSN is what FR-017a forbids, and giving it a
  second Vault auth method is a standing credential on a developer's workstation.
- **Why not Nomad's `vault` stanza and `template`**, which is the other native path and the one
  most people reach for first: a brokered secret lands in the task's environment or filesystem and
  sits there for the life of the allocation, whereas a fetched one lives in process memory only as
  long as it works. More decisively, FR-017b refreshes on the *database's rejection*, and a
  templated secret renews on Nomad's schedule — the workload would have no way to re-fetch in
  response to the signal that matters, which makes the requirement unimplementable rather than
  merely awkward.
- **The identity that carries the database policy is the workload's, never the agent's per-step
  authority.** Backwards, this is serious: database access inside a definition's ceiling would let
  a model-chosen tool call reach the checkpoint store — the run's own record of what it has done.
- **Correcting the record**: this was carried as an open question through two planning passes. It
  was not open. `make dev-up` and the Integration test tier had already settled the Postgres
  question the same way, and the same lesson applies — search for prior intent before concluding
  something is undecided.
- **Alternatives considered**: run on the host with a bootstrap token (standing credential). Run on
  the host and pass credentials in from an allocation (a DSN by another route). Use Nomad's
  template stanza (above).

## Open — owned by the deployment-tree feature

One item, and it is mechanical rather than architectural: **what `make dev-up` guarantees on
exit** — services reachable, Vault unsealed with the database engine and dynamic role configured,
Postgres migrated, and how the suite is invoked in an allocation with its exit status returned.
That determines what test setup may assume versus must check.

It affects neither the seam, the entities, nor the conformance rows.
