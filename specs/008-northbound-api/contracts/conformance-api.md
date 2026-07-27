# Contract: Northbound API conformance lane

**Feature**: `specs/008-northbound-api`
**Status**: Planned
**Depends on**: Constitution Quality Gates (v1.1.0); ADR-0033; ADR-0035; ADR-0047

## Purpose

Record the rows this feature puts **in force** from the moment it lands, the row it
**refuses to claim**, and — per constitution v1.1.0 — **who runs the rows no automated
check executes**.

## Command

```text
make conformance
```

Gains `tests/conformance/api`. Rows marked *enclave* below need `make dev-up`: they run
against the real Vault, the real Postgres, and a real allocation, and **fail loudly when
the enclave is absent rather than skipping**. A test that skips itself reports the same
green as one that ran.

## Rows in force

| Row | Asserts | Spec | Enclave |
| --- | --- | --- | --- |
| Identity is the subject | The authenticated identity is the subject of manufactured authority and of every audit record for that correlation ID | FR-004, SC-001 | no |
| Fail closed on identity | Absent, expired, and unverifiable identities each refuse with zero executions | FR-005, SC-003 | no |
| Unmapped claim refuses | A valid token whose claims map to no role refuses; zero resolve to a default | FR-006, SC-004 | no |
| No static credential | No authentication path accepts or issues a platform-issued long-lived credential, and no supported configuration creates one | FR-003, SC-002 | no |
| No tool route | No registered route reaches a tool body; the API exposes no direct tool invocation | FR-007, SC-005 | no |
| Run start does not block | Starting a run returns a handle; zero requests hold a connection for a run's duration | FR-007a, SC-005a | **yes** |
| Evidence is scope-bounded | Two identities with differing entitlements each see only their own scope; neither can widen it | FR-008, SC-006 | **yes** |
| Read path cannot mutate | A write attempted on the evidence connection is refused **by Postgres**, not by application code | FR-009, SC-007 | **yes** |
| Evidence access is audited | Every read produces exactly one meta-audit record naming who and when, carrying **its own** correlation ID rather than being appended to the chain it read | FR-010 / FR-010a, SC-008 / SC-009a | **yes** |
| Zero rows are distinguishable | A cross-tenant *attempt* — narrowing by another tenant's correlation or run ID, since no tenant parameter exists — and a legitimately empty query both return zero rows and are distinguishable in the trail | FR-011, SC-009 | **yes** |
| Description is complete | Every exposed operation appears in the generated description; an operation added without updating the snapshot is detected | FR-012, SC-010 | no |
| Mapping change is gated | A claim-to-role mapping change returns **pending**, not denied, and takes effect only on approval | FR-013 | **yes** |
| Nothing pauses a run | No path in this feature pauses, interrupts, or blocks a run | FR-015, SC-011 | no |
| IdP unreachable fails closed | With a cold key cache and an unreachable provider, authentications succeed in zero cases | FR-016, SC-012 | no |

## The row this feature refuses

**Four-transport surface parity — not claimed** (FR-014).

Parity is a property *between* transports, and there is one. A green row would assert a
comparison it cannot perform, which is precisely the passing stub ADR-0047 forbids. The row
stays **Deferred** in `ROADMAP.md` until a second transport exists.

What lands instead is the thing that makes the row *satisfiable*: a committed snapshot of
the operation set and its dispositions, so the second transport compares against something
recorded rather than against whatever this surface happens to do by then.

## Break fixtures

Each row ships a fixture demonstrating it **fails** when its guarantee is weakened,
following 004's pattern: fixtures are **self-verifying** — they construct the weakened
arrangement and assert the check raises, so they pass on a clean tree. A row whose failure
nobody has observed is a row nobody knows works.

Three are worth naming because they are the ones most likely to be written to pass rather
than to check:

- **Read path cannot mutate** — the break fixture hands the evidence path a *writable*
  connection and asserts the check still catches the mutation. A fixture that only removes
  the Protocol's type hint proves nothing; the database grant is the defence being tested.
- **No tool route** — the break fixture registers a route that reaches a tool through an
  alias, not one that literally names `invoke_tool`. A checker satisfied by the literal name
  passes the wrong thing, which is how this repository got it wrong twice before.
- **Zero rows are distinguishable** — the break fixture makes both cases return the same
  disposition and asserts detection. Both already return zero rows, so a fixture comparing
  row counts would pass against a broken implementation.

## CI does not run the enclave rows, and that is the same gap 005 recorded

Six of the fourteen rows need the enclave. The CI fast lane runs `make conformance-hermetic`
and cannot stand up a licensed Vault Enterprise, so **no required GitHub check covers those
six.** Stated plainly rather than papered over.

**That lane must exclude by marker, not by path.** It currently passes
`--ignore=tests/conformance/durability`, which worked while every enclave-dependent row
lived in one directory. `tests/conformance/api/` holds both kinds, so the path exclusion
would collect the six enclave rows and **fail the fork-safe lane on the merge commit** —
they fail loudly when the enclave is absent, by design. T057a changes it to `-m "not
enclave"`.

**Responsible party (constitution v1.1.0): the agent harness in the IDE.** Named here
because the constitution requires a blocking row with no automated runner to record who runs
it *in this contract*, rather than leaving it to whoever remembers. `AGENTS.md` instructs
the harness to bring the enclave up and run `make conformance` before merging anything
touching a surface, sealed core, an adapter, a provider, or `infra/` — and to refuse the
merge and report the gap if the enclave cannot come up.

The mechanism is an instruction the harness follows, which is only as good as that
instruction being kept current and obeyed. One property holds regardless: the lane **fails
loudly when the enclave is absent** rather than skipping, so a false green is not obtainable
by running it in the wrong place — only by not running it at all.

Closing this needs a second CI lane with the licence available as a secret, which remains a
deployment-tree concern rather than this feature's.

## Sealed-core review

This feature changes sealed core in four places, and **one of them is not additive**:

- Additive: two `AuditEventType` members, `EvidenceDisposition`, and the `EvidenceQuery`
  protocol.
- **Not additive**: `AuditEntry` gains `tenant_id` and `compute_entry_hash` takes it as an
  input, changing the shape of an existing seam.
- Identity flows move *into* `src/core/identity/` rather than living in a transport, per
  Principle V.

An earlier draft of this contract claimed all of it was additive. It could not have been:
the evidence table required a `tenant_id` that `AuditEntry` had no field for. Putting the
column outside the hash would have been the cheaper fix and the wrong one — the field
deciding who may see a record would then be alterable without breaking the chain.

Per the Development Workflow and CODEOWNERS this requires **security-maintainer review**,
and the specific claim to verify is that no persisted entry exists with a hash computed the
old way. That is true only because audit has never left memory, and will not be true next
time.
