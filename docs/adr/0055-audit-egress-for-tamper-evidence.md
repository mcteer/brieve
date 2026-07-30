# ADR-0055: Tamper-evidence requires a copy outside the writer's blast radius

- **Status**: Accepted
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

**Accepted, and nothing is built.** No shipper exists, no spool exists, no collector is
configured for the audit plane, and no reconciliation operation is defined. What is settled is
the *rule* — the trust boundary is administrative, the head ships with the entries, and storage
the enclave's own role can write does not qualify. The two questions in the Decision remain
open by design, and accepting this record does not answer them: it makes them the questions the
implementing feature must answer rather than ones it may resolve by accident.

Raised by Dan on 2026-07-29 during 013's live gate run, and recorded as the first known gap in
[`ROADMAP.md`](../../ROADMAP.md) — a gap in the evidence plane is the one kind this platform
cannot carry silently.

Not addressed here, and worth its own record if it turns out to matter: whether the *shipped*
copy needs its own retention policy distinct from the local one, and what happens when the two
disagree about how long an entry lives.

**Built by `specs/015-audit-egress` (2026-07-30).** Both open questions were answered in
clarification: shipping is **spooled**, draining from the entries already written rather than
from a separate spool table, and a failed *delivery* refuses nothing while a failed *capture*
still refuses the step. The seam is asserted from both sides in
`tests/component/test_capture_refuses.py`.

**This feature was going to introduce the platform's SECOND standing credential, and in
the end does not.** ADR-0044 says a second one "would be a constitutional event rather than
a configuration change"; that count stands at one.

**The argument below for why a standing credential was unavoidable is wrong**, and is kept
rather than deleted because the record is append-only and a wrong argument is worth being
able to find. Both drafts of it were written without checking what Vault provides, and both
turned a limitation into a principle. What was actually built is under "Correction" at the
end of this section.

It is the append-only account the platform holds at the collector: `INSERT` and `SELECT` on
two tables, no `UPDATE`, no `DELETE`, no `TRUNCATE`, and the separation probe demonstrates
those refusals on every reconcile pass rather than asserting them. It is deliberately **not**
minted by the platform's Vault, because a credential the platform's secrets engine issues is
one the platform's administrators govern — which would re-capture the destination and defeat
this entire record.

**It is standing because the dev enclave has one trust store, not because the design
requires it, and an earlier draft of this note claimed otherwise.** That claim — "federation
is not available across an administrative boundary" — was backwards. Federation is exactly
the mechanism for crossing one. The correct target design is a Vault the *collector's*
administrators own, holding its own database secrets engine against the collector Postgres
and its own JWT auth backend trusting Nomad's JWKS — the same verifiable public issuer this
platform's Vault already trusts. The mcp service would present the workload identity it
already carries, to a store the platform does not administer, and receive a leased
credential. Zero standing credentials, lifecycle control provably on the collector's side of
the line, and revocation available to the collector's administrators unilaterally.

What blocks that here is that the dev enclave runs a single Vault, and a single Vault cannot
demonstrate the separation: the platform's root token administers all of it, so a second
mount inside it would be a boundary drawn on paper. Standing up a second trust store is a
feature — its own container, unseal, PKI, and bring-up sequencing — not a detail 015 could
absorb. **So the standing credential is an artifact of the substrate, and it should not
survive contact with a real deployment**, where the collector's operator has a secrets store
of their own and the federated shape is available immediately.

Two things follow, and they are separable:

- **Manual rotation is not required even today.** Rotation belongs to whoever administers
  the collector, and that party can rotate `harness_shipper` on a schedule and write the new
  value to the KV path the platform reads. The platform stores the credential; it does not
  own its lifecycle. Nothing here needs a human, and the current bring-up simply does not
  automate it.
- **The standing-ness itself needs the second trust store**, and is worth its own record.

### Correction — and what was built (2026-07-30, after reading the documentation)

Raised by Dan: Vault has native mechanisms for exactly this, and needing a human to rotate a
credential is not a design constraint anyone should accept. Both points are correct, and the
second trust store the reasoning above leans on is **not required**.

**Vault rotates database credentials two ways**, and neither needs a human past initial
seeding. *Dynamic roles* mint an ephemeral user per request under a lease. *Static roles*
take over an existing named account and rotate its password on a `rotation_period` (default
24 hours) or a `rotation_schedule`; the application reads the current value from
`database/static-creds/<role>`. This repository already runs the seed-once pattern for its
own state store — a bootstrap user, `rotate-root` so that afterwards only Vault knows the
password ([`database.tf`](../../infra/modules/trust-fabric/database.tf)), then dynamic roles
for the harness and evidence personas. The collector is the only store built outside it.

**The objection to registering the collector in the platform's Vault was that doing so means
seeding the collector's root credential there** — handing the platform's administrators the
destination's credential lifecycle, which is the capture this record forecloses. That
objection is sound and the conclusion drawn from it was not, because it assumed root seeding
is the only way in.

**Rootless static roles are the way in.** Vault Enterprise 1.18+ supports `self_managed=true`
on a Postgres connection with `self_managed_password` on the static role: Vault connects *as*
`harness_shipper` itself and rotates that account's own password. The platform's Vault holds
**no privileged account on the collector** and gains nothing beyond what `harness_shipper`
already has — `INSERT` and `SELECT` on two tables. The enclave already runs
`hashicorp/vault-enterprise:2.0.3-ent`, so this is available today rather than pending.

**The tamper-evidence property is untouched by any of this, because it never rested on
password secrecy.** It rests on the grant list. Even an administrator who obtained
`harness_shipper`'s password gains exactly the capability the platform already legitimately
has, and `probe()` goes on demonstrating that `UPDATE` and `DELETE` are refused. Confusing
"who knows the password" with "what the account may do" is what made the second trust store
look load-bearing.

**So the credential should stop being standing at all**: a Vault-managed account whose
password rotates on a period and which no human knows, read from `database/static-creds/`
under the same attested identity as every other credential here, replacing the hand-written
value at a KV path. On that footing ADR-0044's count returns to **one**, and this record
should not have claimed otherwise.

Two honest caveats, which held up in practice: a rootless connection does not support
dynamic roles (documented limitation), and out-of-band password changes desynchronise Vault
from the database. Neither bites here — one account, rotated only by Vault.

**Built, in this feature.** [`audit-egress.tf`](../../infra/modules/trust-fabric/audit-egress.tf)
onboards `harness_shipper` as a rootless static role on a 24-hour period; the policy grants
read on `database/static-creds/audit-shipper` instead of a KV path; the shipper reads the
current value each time it builds a destination, so rotation needs no restart and no human;
and the collector's coordinates travel in the jobspec, where an address belongs and a
credential does not. Verified live — the seed in `roles.sql` no longer authenticates, and the
running service ships under a password nobody has ever seen.

One ordering consequence worth knowing before debugging bring-up: the static role imports an
account that must already exist, so it is applied *after* `roles.sql` rather than in the main
trust-fabric apply. And the connection is expressed as reachable from the trust store's
container, not from the operator's shell — the same trap `database_endpoint` already carries.

What a second trust store would still add is narrower than the reasoning above suggests:
it would put the *auth* decision on the collector's side too, rather than only the grants.
That is worth wanting and is not what "the platform must not administer the destination"
requires, since the collector's operator can already revoke this access unilaterally by
altering the grants or dropping the role.

ROADMAP gap 0b, opened and closed the same day this record was corrected.
