# ADR-0055: Tamper-evidence requires a copy outside the writer's blast radius

- **Status**: Proposed
- **Date**: 2026-07-29
- **Extends**: [ADR-0020](0020-otel-only-backends-at-the-collector.md)
- **Relates to**: [ADR-0021](0021-connectivity-tiers.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0035](0035-audit-as-a-governed-read-path.md)
- **Requirements**: R4 (evidence over claims)

## Context

Everything this platform claims downstream of the audit plane rests on the trail being
trustworthy. [ADR-0035](0035-audit-as-a-governed-read-path.md) makes reading it governed and
makes evidence access itself audited. Principle IX makes it append-only, never sampled, and
hash-chained.

The chain is honest about what it provides, and the schema comments say so plainly:
`audit_entries` is append-only **by grant** — the evidence role holds `SELECT` and nothing at
all on `audit_stream_heads` — and `audit_stream_heads` exists precisely because *a hash chain
cannot detect truncation.* Delete the newest three entries and `seq 0..N-4` verifies
perfectly. The head record is what closes that.

**But detection is not prevention, and both tables live in the same Postgres.** An actor with
write access to that database can rewrite entries *and* the head that would have exposed the
rewrite, consistently, and nothing anywhere disagrees. Every mechanism guarding the trail —
the grant, the chain, the head — sits inside the same blast radius as the data it guards. The
property the platform claims is currently enforced by a permission adjacent to the thing it
protects, which is a weaker position than the claim implies.

The obvious mitigation is to put a copy somewhere else as each entry is written, so tampering
requires compromising two systems that do not trust each other. **And the obvious mitigation
runs straight into an existing decision.**
[ADR-0020](0020-otel-only-backends-at-the-collector.md) states that **the audit plane never
egresses by default**, that hosted services are off by default in regulated profiles, and that
export to a SIEM is an explicit, configured act. That is not an oversight to be corrected — it
is a deliberate posture for estates where shipping audit content anywhere is itself the
problem, and where capture policy must be enforced once, before any egress, with no
observability credentials held by the workloads.

So the tension is real and specific: **tamper-evidence wants the copy elsewhere immediately;
regulated-profile posture wants nothing leaving by default.** An ADR that simply reversed
ADR-0020 would trade one integrity property for a different one and call it progress.

The resolution turns on a distinction the existing records do not draw sharply.
[ADR-0025](0025-enclave-is-the-default-topology.md) already separates *adjacency* from *containment* — the
enclave sits beside the estates it manages and holds no standing credentials to them. The same
move applies here: **"outside the platform's blast radius" and "outside the organization's
boundary" are different axes**, and ADR-0020's default is about the second. A collector the
organization operates, inside its own boundary, under administrators who are not the platform's
administrators, is not the third-party egress that default guards against. What tamper-evidence
needs is **different administrative control**, not distance.

## Decision

**The audit trail ships to a destination outside the writing system's administrative control,
and that destination is not required to be outside the organization's boundary.**

- **The trust boundary is administrative, not topological.** The requirement is that the
  platform's own credentials cannot alter the second copy. An organization-operated collector
  in the same data centre satisfies it; a bucket the enclave's own role can write does not.
- **ADR-0020's default is unchanged for third-party and hosted destinations.** Export beyond
  the organization's boundary remains an explicit, configured act, off by default in regulated
  profiles. This record adds a *near* destination; it does not open a far one.
- **The shipped record is the chain entry, not a summary.** Sequence, tenant, correlation ID,
  event type, payload, and both hashes — enough that the second copy can be independently
  chain-verified and compared entry-for-entry against the first. A digest-only copy detects
  that something changed and cannot say what, which is the wrong half.
- **`audit_stream_heads` ships too, and this is the load-bearing part.** The head is what
  detects truncation; a second copy of the entries without a second copy of the head leaves
  the truncation attack intact against both.
- **Air-gapped estates ship to a local collector under separate administrative control**
  ([ADR-0021](0021-connectivity-tiers.md)). The tier changes where the destination is, never
  whether there is one — an estate with no second copy has no tamper-evidence, and saying so
  is better than a substitution that quietly is not one.
- **Reconciliation is a named operation, not an implied capability.** Comparing the two copies
  and reporting divergence is what makes the second copy worth having. It runs through the
  governed read path ([ADR-0035](0035-audit-as-a-governed-read-path.md)) and is itself audited,
  because reading evidence is audited.

**Two questions this record leaves open deliberately, because both decide what kind of control
this is and neither should be settled by whoever implements it first:**

**Synchronous or spooled.** Principle VI says nothing blocking that could be an async emitter,
and an emitter that can silently drop is an evidence gap nobody sees — which is the failure
this record exists to close. The likely answer is a **local durable spool the shipper drains**,
so the write blocks on local disk rather than on the network and the spool's depth is itself an
observable. That is a guess, not a decision, and the alternative — a synchronous ship where a
step waits on the second copy — is defensible and has a different cost profile.

**What a failed ship means.** `start_governed_run` already refuses a run whose
`AUTHORITY_ISSUED` could not be audited: an unauditable authority issuance is not permitted to
proceed. Whether an **unshippable** entry should refuse a *step* is the same question one layer
out, and the answer decides whether this is a governance control or a convenience. A control
that degrades to best-effort under load is a convenience with a control's name.

## Consequences

The platform's central claim stops being enforced by a permission sitting next to the data it
protects. Tampering requires compromising the enclave's Postgres *and* a collector under
different administration, and the second copy is what an investigator reconciles against
rather than a second view of the same substrate. That is the point, and it is the difference
between "the trail is hash-chained" and "the trail is hash-chained and a divergence would be
visible."

The seam is already in place, which is why this is a decision rather than a project.
`AuditSink` is a protocol with two implementations; a fan-out sink that writes Postgres *and*
hands the entry to a shipper needs no signature change and no core rework. ADR-0020's
collector is the natural destination, so the transport is a configuration surface the platform
already has.

The costs are real and land in three places. **Operational surface grows**: a spool with a
depth, a shipper with a failure mode, a collector under someone else's administration, and a
reconciliation job with a schedule — all of which have to be monitored, and none of which the
enclave previously needed. **Duplicate storage of the most sensitive record the platform
keeps**, which is an exposure increase even inside the organization's boundary: two copies is
two places to get the access control right, and the second one is administered by people who
are deliberately not the platform's administrators. And **the regulated-profile conversation
gets harder rather than easier** — "audit never egresses" is a simple, checkable promise, and
"audit ships to a destination you operate, under your administrators, and here is why that is
not egress" is a correct answer that takes longer to land.

The honest limit is that this detects and does not prevent, one level up. A second copy makes
divergence visible; it does not stop the first copy being rewritten, and an attacker who
compromises both systems defeats it. What it buys is that the compromise must be *broader* —
two administrative domains rather than one — and that a single-domain compromise leaves
evidence of itself. That is a genuine improvement and not a guarantee, and any claim that this
makes the trail immutable would be false.

This record also foreclosed a tempting shortcut worth naming: shipping to object storage the
enclave's own workload role can write would be trivial to build, would look like a second
copy, and would be worthless — the same credentials that can rewrite the first copy could
rewrite the second. The administrative-control requirement exists to make that non-solution
visibly non-compliant rather than arguably sufficient.

## Notes

**Status is Proposed.** No shipper exists, no spool exists, no collector is configured for the
audit plane, and no reconciliation operation is defined. This captures a decision so the two
open questions above can be argued before something is built that answers them by accident.

Raised by Dan on 2026-07-29 during 013's live gate run, and recorded as the first known gap in
[`ROADMAP.md`](../../ROADMAP.md) — a gap in the evidence plane is the one kind this platform
cannot carry silently.

Not addressed here, and worth its own record if it turns out to matter: whether the *shipped*
copy needs its own retention policy distinct from the local one, and what happens when the two
disagree about how long an entry lives.
