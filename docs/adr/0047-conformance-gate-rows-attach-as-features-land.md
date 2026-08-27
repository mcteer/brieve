# ADR-0047: Conformance gate rows attach as their features land

- **Status**: Accepted
- **Date**: 2026-07-25
- **Relates to**: [ADR-0001](0001-framework-agnostic-core.md), [ADR-0017](0017-primary-adapter-selection.md), [ADR-0019](0019-adapter-on-framework-capabilities.md), [ADR-0024](0024-durability-provider-seam.md), [ADR-0033](0033-four-transports-one-authorization-core.md), [ADR-0040](0040-deferred-tool-disclosure.md)
- **Requirements**: R16

## Context

The constitution's Quality Gates name the conformance suite blocking for adapters and
providers, and enumerate its rows: governance-ordering and fail-closed assertions,
tool-call parity under deferred disclosure, registry isolation, surface parity across all
four transports, and the durability scenario matrix from
[ADR-0024](0024-durability-provider-seam.md).

Read strictly, that list binds the first adapter to features that do not yet exist. The
primary adapter ([ADR-0017](0017-primary-adapter-selection.md)) lands before northbound
transports ([ADR-0033](0033-four-transports-one-authorization-core.md)), before
deferred-disclosure productization ([ADR-0040](0040-deferred-tool-disclosure.md)), and
before full durability depth. No adapter could satisfy surface parity across four
transports when zero transports have shipped.

The tension is real in both directions. A gate that cannot be satisfied is not a gate —
the first feature to hit it either stalls or quietly redefines it, and the second reading
is what actually happens in practice. But a gate loosened to fit the first arrival stops
constraining the tenth.

Two resolutions were available and both are wrong. Weakening the gate to what an early
adapter can pass discards the rows permanently; nothing later restores them. Stubbing the
missing rows green is worse, because a silent pass is indistinguishable from a real one at
review time — the suite reports success for a property no test examined, which is the
failure mode the suite exists to prevent.

## Decision

**Each conformance gate row is blocking from the moment its underlying feature exists, and
not before.** A row whose feature has not landed is absent from the suite, or present as a
single explicit skip carrying the ADR reference that defers it. A deferred row MUST NOT be
represented by a passing stub.

**The set of rows in force is recorded per feature**, in that feature's conformance
contract, so a reviewer can hold a pull request against a specific list rather than
against the full enumeration. For the primary adapter the in-force slice is
governance-first ordering, fail-closed denial, and governed-entry (`invoke_tool`)
interception.

**Adding a feature adds its rows in the same change.** Shipping northbound transports
without adding surface-parity cases is a gate regression and is reviewable as one. This is
the obligation that keeps the deferral honest: rows are postponed, never dropped.

This decision governs when a row binds. It does not change what any row asserts, does not
relax any row that is already in force, and does not authorize skipping a row whose
feature has landed.

## Consequences

The gate stays honest at every point on the timeline rather than only at the end. Review
gains a question that can actually be answered — which rows are in force for this feature,
and are they all present — in place of one that could only be answered "not yet, and that
is apparently fine."

The cost is bookkeeping, and it is not trivial. The in-force set now lives across
per-feature conformance contracts, so the constitution alone no longer tells a reader what
conformance means today; that reader has to assemble it from the features that have
shipped. This is the price of a gate that binds incrementally, and it is paid in documents
rather than in enforcement strength.

The failure mode this leaves open is a feature landing without its rows — the obligation
above is a review responsibility, not a structural guarantee. Nothing in the suite detects
its own incompleteness. If that happens even once, the right response is a mechanical
check that maps shipped features to required rows, and this decision should be revisited
with that evidence in hand.

## Notes

The constitution's Quality Gates were amended in the same change that Accepted this
record (v1.0.0 → v1.0.1), per the rule in this directory's README and the constitution's
own header. The amendment is a PATCH-level clarification of when an existing gate binds —
it neither removes nor redefines a principle.

First application: [`specs/004-primary-adapter/contracts/conformance-adapter.md`](../../specs/004-primary-adapter/contracts/conformance-adapter.md),
whose "Deferred" section is the per-feature record this ADR makes authoritative.

Raised by `/speckit-analyze` against `specs/004-primary-adapter`, which surfaced that the
first adapter to reach the gate could not satisfy rows belonging to features scheduled
after it.

## Amendment — 2026-07-31

**The Decision above assumes every row not yet in force traces to a deferring ADR.** It says
a row whose feature has not landed is "absent from the suite, or present as a single explicit
skip carrying the ADR reference that defers it." One row never fit that: registry isolation.
It derives from Principle IV and [ADR-0025](0025-enclave-is-the-default-topology.md)'s
structural-exclusion rule, and neither of those defers it. Nothing chose to postpone it; no
feature had yet existed that could carry it.

004's conformance contract recorded the situation exactly and declined to invent a citation
to satisfy the clause:

> This is a wording gap in ADR-0047, not a gap in 004. If a second row turns out to lack a
> deferring ADR, the fix is a PATCH to ADR-0047 distinguishing deferred by decision from not
> yet applicable, rather than inventing citations to satisfy the clause.

A second row did not turn up. Something better did — the row itself landed, in
[018](../../specs/018-registry-isolation/spec.md), which makes the fix concrete rather than
anticipatory.

**A row not in force is in one of two states, and they are recorded differently:**

| State | What happened | What the contract must carry |
| --- | --- | --- |
| **Deferred by decision** | An ADR considered the row and chose to postpone it | The ADR reference. This is the original Decision's case and it is unchanged |
| **Not yet applicable** | No feature exists that could carry the row. Nothing was deferred, so there is nothing to cite | The reason, in the feature's own conformance contract. **Absence of a citation is the honest record here, not a missing one** |

The second state was always the more common one and had no vocabulary, which is why the gap
went a year without being noticed: a reviewer reading the clause literally would have gone
looking for an ADR that does not exist, and the likeliest resolutions are the two this record
already rejects — cite something adjacent, or stub the row green.

**This changes no assertion and relaxes nothing.** It adds a name for a situation the
original Decision did not distinguish. Every row in force stays in force; the obligation that
adding a feature adds its rows in the same change is untouched; a passing stub is still
forbidden in both states. The Decision is left intact above — this record is append-only, the
shape [ADR-0048](0048-nomad-is-the-agent-execution-substrate.md) set earlier the same
day.

**Registry isolation was the second state and is now in force**, carried by 018 against the
live control plane. `specs/004-primary-adapter/contracts/conformance-adapter.md` moves it out
of the not-yet-attached list in the same change, because an amendment that named the states
without placing the row that prompted it would leave exactly the situation it exists to end.
