# Contract: Durability conformance lane

**Feature**: `specs/005-durable-execution`
**Status**: Planned
**Depends on**: Constitution Quality Gates; ADR-0024; ADR-0026; ADR-0047

## Purpose

Define the durability rows and record that they are **in force** from the moment this feature
lands (ADR-0047). Until then they are absent — never stubbed green.

## Command

```text
make conformance
```

Runs `tests/conformance` with the local enclave available. The durability rows require Vault and
Postgres; `make dev-up` is a prerequisite for them, not an alternative to them.

## Rows in force (all seven)

| Row | Asserts | Spec |
| --- | --- | --- |
| Kill / resume | A disrupted run resumes and completes; already-completed steps show exactly one execution across the whole run | FR-006, SC-001 |
| Re-authenticate, never replay | Resume manufactures fresh authority; no checkpoint contains credential material; a pre-disruption credential is not honoured | FR-003/004, SC-002/003 |
| Re-observe, never re-execute | An interrupted non-repeatable step is resolved against observed external state, in both directions | FR-006/007, SC-005 |
| Fencing against double resume | A superseded holder's tool calls and checkpoint writes are rejected; zero side effects, zero state mutation | FR-009, SC-006 |
| Parking on grant expiry | Resume under expired consent parks with zero subsequent steps; renewed consent permits resume | FR-005, SC-004 |
| Duplicate side-effect rejection | A repeated step carrying the same stable key is recognised as the same step | FR-010, SC-001 |
| Drain across upgrade | A controlled in-process handover preserves the run and its evidence | FR-015, SC-008 |

## Break fixtures (FR-014)

Each row ships a fixture demonstrating it **fails** when its guarantee is weakened. Following
004's pattern, break fixtures are **self-verifying**: they construct the weakened arrangement and
assert the check raises, so they pass on a clean tree. A row whose failure nobody has observed is
a row nobody knows works.

## Provider independence

Rows are written against the seam, not an implementation (FR-012). Running them against a second
provider must require no rewriting — that is the executable form of ADR-0024's central claim.

## Honest limits

- **Single-node.** The enclave runs one Vault node and one Nomad server. Fencing and parking are
  proven against single-node behaviour; multi-node partition is not exercised. Recorded so the
  conformance claim is not read as broader than it is.
- **Drain-across-upgrade is simulated** as a controlled handover, not by upgrading a running
  deployment.
- **Parking has no consent surface.** Parked runs are observable and resumable programmatically;
  the human-facing surface is Control Groups (ADR-0016) and northbound (ADR-0033), both out of
  scope.

## Invariants

1. Conformance failures are merge-blocking for durability changes (as 004 established for the
   adapter lane).
2. These seven rows move from deferred to in force when this feature lands, and
   `contracts/conformance-adapter.md`'s deferred list is updated in the same change.
3. No row is represented by a passing stub at any point.

## Related

- [durability-seam.md](./durability-seam.md)
- [grant-and-resume.md](./grant-and-resume.md)
