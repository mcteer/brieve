# Contract: Evidence

**Feature**: `specs/007-control-groups`
**Status**: Planned
**Depends on**: Principle IX, FR-011, ADR-0015

## Purpose

An authority change is the highest-consequence write in the system: it changes what an
agent may become. This contract says what must be reconstructable afterwards, and — as
importantly — what the harness must *not* keep.

## What must be recorded

| | |
| --- | --- |
| The request | What path, proposed by whom |
| Each approval and denial | With the identity responsible |
| The disposition | Approved, denied, or expired |
| The join | A correlation ID linking it to everything else an investigator walks |

## What must NOT be recorded

- **Credential material or policy content.** An audit record of an authority change is not
  a place to copy the authority itself.
- **A mirror of Vault's approval state.** Vault is where the decision *is*; this records
  that a decision happened and what it was. A synchronised copy creates a second answer to
  "who approved this", and during an incident someone reads the wrong one.

## Invariants

1. **The harness observes; it does not decide.** No evaluation happens here.
2. **The harness never writes quorum policy.** A harness that could would be one that could
   lower the gate constraining it.
3. **Blocked-pending-approval is distinguishable from denied.** Collapsing them makes an
   in-flight approval look like a refusal, and a caller then either retries forever or
   reports a failure that is not one.
4. **Vault's own audit device is not a substitute.** It is not joined to harness correlation
   IDs, so an investigator would correlate by hand — which is the state this contract
   exists to prevent.

## Testing note

Component tests run against the real control-plane Vault. A faked Control Group that always
approves proves the caller can proceed; one that never approves proves the caller handles
denial. Neither proves the gate holds, which is the only claim that matters.

That puts these tests in the lane CI cannot run — so under constitution v1.1.0, this
feature's conformance contract must name who runs them before merge.

## Related

- [gated-paths.md](./gated-paths.md)
- [quorum-policy.md](./quorum-policy.md)
