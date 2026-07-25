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
