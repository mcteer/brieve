# ADR-0072: Identity is per definition, never per invocation

- **Status**: Accepted (2026-08-28, decided by `specs/054-run-scoped-write-grant`)
- **Date**: 2026-08-27
- **Relates to**: [ADR-0056](0056-task-scope-needs-an-authorization-server-vault-is-not-one.md) (the distinction this applies), [ADR-0057](0057-context-hungry-agents-want-breadth-not-narrower-reads.md) (whose trigger 1 produced the feature that found this), [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0025](0025-enclave-is-the-default-topology.md)
- **Requirements**: R2, R3, R12

## Context

054 needed a run's write authority bounded to that run's own workspace. The mechanism that
delivered it pointed the JWT role's `user_claim` at the allocation id, giving every dispatched
run its own identity alias and therefore its own Vault identity entity. The bound worked: a run
attempting another run's workspace was refused on read, write and delete, demonstrated against
the live control plane.

**The cost was found after it was built, which is why this record exists.** Measured on a
running enclave: one dispatched Build costs 73 raft writes and **one permanent identity
entity**. Entities carry no TTL and no expiry field. Vault's documented ceiling on integrated
storage is a hard **256 MiB across 256 shards** — roughly 480,000 entities conservatively — and
entity writes occur on **every login**. At 10,000 users running 20 Builds a month the
conservative ceiling arrives in about 2.4 months, after which logins fail and every Build fails
with them.

The intermediate state is worse than the wall. HashiCorp records that *"the cost of entity and
group updates grows as the number of objects in each shard increases"*, and every login pays
it, so Build-start latency rises with the cumulative number of Builds ever run. There is no
steady state and no recovery, and it looks correct in every test.

**This platform is intended to be tier-0.** A control that is correct, gets slower forever, and
eventually stops all authentication is not a control that can ship.

## Decision

**An identity is per definition — or per definition and tenant. Never per invocation.**

- **Identity answers *who you are*.** A task boundary answers *what this task may do*. These are
  different questions and Vault answers them with different machinery. ADR-0056 already drew
  this line when it established that Vault is the **resource server** and not the authorization
  server; carrying a task scope in the identity system is the same category error, arriving
  from the other direction.
- **The identity store is a durable, capped, replicated resource, and must be treated as one.**
  It has a hard ceiling, no expiry, and its write cost grows with its size. Anything whose
  cardinality tracks *runs* does not belong in it.
- **Where a run must not hold authority, the authority moves to something long-lived** — not to
  a per-run identity that can be granted it narrowly. The estate already does this: the scratch
  sweep lives on the MCP surface because it needs enumeration a run must never have, on the
  reasoning that *"something a dead run left"* is work *"only a living process can clear"*. A
  measurement needing authority a run should not hold has the same shape and the same home.
- **A mechanism's cost must be bounded by things that grow slowly** — definitions, tenants,
  services. This is now a requirement on any authority mechanism (054 FR-018), not a review
  note, because 054 passed every correctness gate it had while carrying an unbounded cost.

## Consequences

**054's first implementation is withdrawn and its property is kept.** `user_claim` returns to
the job, so runs share one identity that already exists and nothing accumulates. The isolation
is preserved by moving the measurement rather than by narrowing a per-run grant — which also
satisfies 054's FR-012 in full, since a run then holds no policy-write authority at all rather
than a self-scoped one it may not need.

**Non-entity tokens become the cheaper path where one is needed.** Since Vault 1.9, *"all
non-entity tokens with the same namespace and policy assignments are treated as the same client
entity"*, so identical-policy tokens do not multiply identities. That is a property to reach
for deliberately rather than discover.

**Telemetry stops being optional.** `vault.identity.upsert_entity_txn` is the metric HashiCorp
names for exactly this degradation, and telemetry is currently disabled in the dev enclave —
`sys/metrics` answers 400. Nothing would have reported the problem this record exists to
prevent, and for a tier-0 service that absence is its own defect.

**What this does not decide.** Whether a *tenant* deserves its own entity, and whether the
per-definition entities `registry.tf` already creates should become per-definition-per-tenant
when multi-tenancy lands. Both are bounded by things that grow slowly, so both are admissible
under this record; which is right is 046's question, not this one.

## Notes

**Found by measurement after the fact, which is the honest characterisation.** 054 was
specified, planned, tasked, analysed twice, implemented and demonstrated — and every gate it
had was green, because every gate asked whether the bound *held* and none asked what the bound
*cost to maintain*. The requirement that would have caught it did not exist until the
implementation was already merged into a pull request.

The limit itself is documented and was not hard to find. Nobody looked, because nothing in the
process prompted the question.
