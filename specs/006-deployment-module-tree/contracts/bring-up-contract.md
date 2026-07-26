# Contract: Bring-up

**Feature**: `specs/006-deployment-module-tree`
**Status**: Planned
**Depends on**: FR-008, FR-009

## Purpose

State what is true when bring-up succeeds, so that test setup can assume it rather than guess. A
suite that guesses reports environment problems as test failures, which is how a confusing hour
starts.

## Guarantees when bring-up reports success

| # | Guarantee |
| --- | --- |
| 1 | The scheduler is reachable and has a leader |
| 2 | The trust store is reachable, **unsealed**, and active |
| 3 | The trust fabric is configured: auth mount, ceiling policies, registry entries, database engine |
| 4 | A dynamic state-store credential can be minted and it authenticates |
| 5 | The state store is reachable and its schema is applied |
| 6 | Persistent state from previous runs is intact |

## Invariants

1. **Every guarantee is machine-checkable**, and `enclave-verify` checks it. A guarantee confirmed
   by reading something is not a guarantee.
2. **Bring-up runs the verification before reporting success.** Otherwise the contract is a
   description of intent rather than of state.
3. **Failure names the missing prerequisite** (FR-008). "Bring-up failed" costs the reader the
   diagnosis the tool had already done.
4. **Bring-up is repeatable and destroys nothing** (FR-009). Against a configured environment it
   unseals; it never re-initialises. Re-initialising discards the trust store and invalidates every
   credential derived from it, which is the most expensive mistake available here.
5. **The bootstrap order is asserted, not assumed** (FR-003). Trust store before scheduler,
   scheduler before any agent workload. It is the only ordering that terminates, and an inverted
   one fails at cold start — the worst time to discover it.
6. **Detection reports causes, not symptoms.** For each entry in the failure catalogue, the message
   names the cause — the catalogue exists because these symptoms point elsewhere.

## What bring-up does NOT guarantee

Stated so nobody infers it:

- **No high availability.** Single-node trust store, single scheduler server. 005's conformance
  caveat persists: fencing and parking are proven against single-node behaviour only.
- **No production seal.** The development default is a 1-of-1 shamir with the key beside the
  server.
- **No bootstrap-credential revocation in development.** The root token persists, deliberately, so
  the re-apply loop stays usable.

## Related

- [module-interface.md](./module-interface.md)
- [substrate-requirements.md](./substrate-requirements.md)
