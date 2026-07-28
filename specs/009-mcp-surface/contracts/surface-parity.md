# Contract: Surface parity

**Feature**: `specs/009-mcp-surface`
**Status**: Planned
**Depends on**: ADR-0033; Principle II; `specs/008-northbound-api/contracts/operations.snapshot.json`

## The row that has been owed since 008

ADR-0033 requires that the same operation on any transport yields the same verdict and
equivalent audit events, **asserted rather than intended**. 008 could not claim it: parity is
a property *between* transports and there was one, so a green row would have been the stub
ADR-0047 forbids.

**009 claims it.** Two transports exist. Deferring a second time would stop being rigour.

## What "equivalent" means

Left vague, this is the easiest assertion in the feature to pass dishonestly — "both produced
some audit" is satisfied by two surfaces that agree about nothing.

| Compared | Not compared |
| --- | --- |
| The verdict | Timestamps |
| Audit event **types** | Correlation IDs |
| Their **order** | Entry hashes |
| The subject | The transport field |
| Decision fields (outcome, reason code) | |

Transport is recorded as a **field**, not as a structural difference. If the two trails
differ in shape rather than in that one field, they are not equivalent.

## How it is driven

From 008's committed operation snapshot, as the same subject, through both transports.

**That prerequisite is also a check.** If the snapshot has drifted from the API, parity is
measuring the wrong thing — so this row implicitly re-verifies 008's snapshot assertion, and
drift surfaces here as the first failure rather than as a mystery three commits later.

## Divergence detection

An operation present on one transport and absent from the other must be **detected**, not
noticed. The comparison enumerates both sets and fails on asymmetry in either direction —
including MCP exposing something the API does not, which is the direction a transport-specific
convenience would grow.

## Why one core, structurally

MCP reaches the authorization core through the interface 008 exposes, **as the calling user**
(FR-002a). Not as a service account: that would collapse every caller into one subject and
destroy the non-repudiation the delegation chain exists for — invisibly, because everything
would still appear to work.

A transport with its own path to the core would make parity a comparison between two
implementations rather than two front doors to one. The conformance row asserts the path, not
only the outcome.
