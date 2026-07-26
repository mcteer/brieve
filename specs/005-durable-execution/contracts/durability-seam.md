# Contract: Durability provider seam

**Feature**: `specs/005-durable-execution`
**Status**: Planned
**Depends on**: `specs/004-primary-adapter` (`DurabilityProvider`, `CheckpointBlob`)

## Purpose

Define what a durability provider must supply, and — more importantly — what it may **not**
influence. ADR-0024's claim is that swapping providers changes performance, never whether resume
re-authenticates or whether a checkpoint may hold a credential. That claim is only true if the
seam is drawn so a provider *cannot* affect it.

## Surface (normative)

| Operation | Contract |
| --- | --- |
| `save(blob)` | Persist checkpoint. Failure MUST propagate — a step MUST NOT proceed as though recorded |
| `load(blob_id)` | Return blob or miss. A partial or corrupt blob MUST NOT be returned as valid |
| `acquire_lease(run_id, holder)` | Atomically supersede any prior holder. Returns the fencing state |
| `check_lease(run_id, holder)` | False for a superseded holder. MUST NOT be advisory |
| `record_intent` / `record_result` | Persist the bracket around a non-repeatable step |
| `open_intents(run_id)` | Intents with no result — the set resume must resolve |

## Invariants

1. **A provider cannot decide whether resume re-authenticates.** Authority manufacture happens
   above this seam. A provider that returned credential material would be violating (2), not
   exercising a permitted option.
2. **Checkpoints hold state, never credentials** — for every provider, asserted rather than
   documented.
3. **Lease rejection is a comparison, not a race.** A provider whose lease check can return true
   for two holders is non-conforming.
4. **Failures are visible.** A silently dropped checkpoint write is indistinguishable on resume
   from a step that never ran, which is the failure re-observation exists to prevent.
5. The conformance rows in [conformance-durability.md](./conformance-durability.md) run against
   any provider and MUST pass identically.

## Breaking change

004's `DurabilityProvider` is `save`/`load` only and cannot satisfy the lease or bracket
guarantees. This is a genuine break to a seam shipped one feature ago. Exempt from a deprecation
window on the same grounds 004 recorded — pre-1.0 (`version = "0.0.0"`), one in-repo
implementation, no external consumers — and declared in the `feat/005` PR under the template's
breaking-change section rather than assumed.

## Related

- [grant-and-resume.md](./grant-and-resume.md)
- [conformance-durability.md](./conformance-durability.md)
