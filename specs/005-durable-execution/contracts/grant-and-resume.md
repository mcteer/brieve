# Contract: Delegation grant and resume

**Feature**: `specs/005-durable-execution`
**Status**: Planned
**Depends on**: `specs/003-per-task-authority`, ADR-0026, ADR-0048

## Purpose

Pin the two-level authority split and what resume may and may not do.

## Grant rules

1. A grant records consent, bounded by the agent definition's maximum run duration. It holds **no
   credential material**.
2. Per-step authority is manufactured under a grant and expires normally. A run MUST NOT hold one
   long-lived credential for its duration.
3. A grant is **not renewable from inside a run**. Only a human extends consent — through a
   surface this feature does not build.
4. An expired grant is withdrawn permission. The run parks; it does not resume.

## Resume rules

1. Resume re-attests and re-exchanges under the surviving grant.
2. **No supported path accepts a credential recovered from durable state**, and none is written
   for a path to accept.
3. Resume acquires the lease before acting. A superseded holder is rejected by identity
   comparison.
4. Open intents are resolved by observation before any step proceeds.
5. `cannot_determine` parks. Resume never guesses.

## What the substrate provides, and what this code must not undo

Under ADR-0048 a resumed run is a **new allocation with a new attested identity**, so the prior
credential is unobtainable rather than forbidden. The implementation's obligation is therefore
*negative*: introduce no path that reintroduces a credential across the boundary — no
credential-bearing checkpoint field, no cache keyed by run, no "resume token".

Demonstrated in [`infra/dev-enclave`](../../../infra/dev-enclave/): a Nomad-scheduled container
exchanged its workload identity for a ceiling-scoped 300-second token with no credential in the
jobspec.

> Stating it this way matters for review. The question to ask of this code is not "does it
> re-authenticate correctly" — the substrate settles that — but "does anything here smuggle
> authority across a disruption."

## Related

- [durability-seam.md](./durability-seam.md)
- [conformance-durability.md](./conformance-durability.md)
