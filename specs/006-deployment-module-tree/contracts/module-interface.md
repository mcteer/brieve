# Contract: Module interface

**Feature**: `specs/006-deployment-module-tree`
**Status**: Planned
**Depends on**: ADR-0025 (substrate is the only permitted delta), Principle VII

## Purpose

Define the boundary that makes FR-002 checkable. "One tree, substrate as the only delta" is a claim
about *structure*; this contract is what turns it into something a reviewer can verify without
tracing code paths.

## The rule

**`trust-fabric` may not know which substrate it is running on.** Its only substrate-derived inputs
are three endpoint strings — where the trust store answers, where workload identities are verified,
and where the state store listens.

A fourth substrate input appearing is the signal that the boundary has moved. That is not
automatically wrong, but it MUST be a deliberate change to this contract rather than a variable
someone added.

## Interfaces

| Module | Consumes | Produces |
| --- | --- | --- |
| `trust-fabric` | agent definitions, JWKS URL, database endpoint, profile, seal config | auth path, credential path, CA certificate, **configuration digest** |
| `substrate-*` | environment-specific inputs | Vault address, JWKS URL, database endpoint |

## Invariants

1. **`trust-fabric` references no substrate resource.** No container, no instance, no
   substrate-only provider.
2. **A substrate module configures no trust.** No policy, role, registry entry, or secrets engine.
   If it does, the delta has escaped its layer.
3. **Profile is not substrate.** Posture and placement are separate axes; conflating them puts a
   hardening choice behind a placement choice, and then nobody can run production posture on a
   workstation to test it.
4. **The configuration digest excludes everything substrate-derived.** Including an address would
   make the digests differ by construction and the comparison worthless.
5. **Identical digests across substrates is produced, not asserted** (FR-016). The comparison runs;
   its output is the evidence.

## Related

- [bring-up-contract.md](./bring-up-contract.md)
- [substrate-requirements.md](./substrate-requirements.md)
