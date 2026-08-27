# ADR-0070: Endorsed-content sync is an enumerated egress class, and customer content is pinned rather than fetched

- **Status**: Accepted (2026-08-27, decided by `specs/045-customer-endorsed-context`)
- **Date**: 2026-08-07
- **Amends**: [ADR-0030](0030-pinned-versus-consulted-artifacts.md) (names the one class of consulted material that is *not* fetched fresh, and why)
- **Relates to**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0021](0021-connectivity-tiers.md), [ADR-0046](0046-multi-tenancy.md), [ADR-0066](0066-version-control-is-reached-through-adopted-clis.md), [ADR-0069](0069-governance-configuration-is-requested-at-a-console.md)
- **Requirements**: R1, R3, R5, R6, R8

## Context

Principle II limits **non-tool egress** to enumerated classes — model inference, identity,
telemetry — and states in so many words that *adding a class REQUIRES an ADR*.

045 lets an administrator endorse a source of the customer's own documents, which the platform
then syncs, pins, and cites. Syncing reaches a customer's repository **from a served process**.
That is non-tool egress, and there is no honest reading under which it falls inside an existing
class: it is not inference, not identity, not telemetry.

**The comparison that makes this new.** `corpus-sync` also reaches outside, and it needed no
class because it runs from `infra/bin` on an operator's machine and commits its output into the
repository. Nothing served ever fetches. Customer content cannot work that way: it arrives at
runtime in one deployment, there is no commit to put it in, and an allocation's filesystem does
not survive rescheduling.

**A second tension arrives with it.** ADR-0030's rule is about *what an artifact does*:
executed artifacts are pinned because ungated behaviour change is unacceptable, and consulted
artifacts are fetched fresh because "an attestation claiming alignment with a baseline that has
since changed is misleading in a way nobody can detect from the report." Customer material is
plainly *consulted* — nobody executes a compliance policy — and yet the pinned corpus, which is
also consulted, does the opposite of what the rule says: sync, then read, refusing what does not
match the pin. That is much closer to ADR-0021's date-stamped snapshot, which that record chose
for restricted estates.

So 045 either inherits a rule describing a mechanism the tree does not use, or says which shape
it takes and why. Leaving it unsaid is how a principle comes to describe something nobody
built.

## Decision

### 1. Endorsed-content sync is an enumerated egress class, with bounds stated here

The platform may make outbound requests to synchronise content from an endorsed source, subject
to all of the following:

- **Only sources named in the endorsement record.** The set of reachable locations is exactly
  the set of endorsed sources; there is no path by which a question, a run, or a document's
  contents can cause the platform to reach anywhere else.
- **Only during detection, review-sync, and endorsement-sync.** Three named operations, each
  triggered by an administrator's act or by the health checker's own cadence.
- **Never during answering.** Not "we do not do that" — asserted by instrumentation, because
  the absence of code is a claim about today and the assertion is a claim about every commit
  after (SC-003).
- **Read-only.** Listing refs and cloning. The platform never writes to a customer's source.
- **Credentials are trust-store material referenced per sync, never entered through the
  console.** 044's FR-018b posture, unchanged: a source's record names *where* it is, and the
  vocabulary has no field a credential could be written into. Public sources need none.

### 2. Customer content is *consulted* material handled by the *pinned* mechanism

ADR-0030's rule stands for what it was written about: upstream reference guidance, where being
stale makes an attestation misleading. Endorsed customer content is the named exception, and the
reasoning is the pinned corpus's own:

> a corpus that fetched at answer time would make every answer depend on a third party being
> reachable, and would make "pinned" untrue.

A customer's compliance policy is **ground for an attested answer**, not a reference lookup. It
takes ADR-0021's date-stamped-snapshot shape: sync, verify on read, refuse a mismatch, disclose the
age of the material. An answer citing a customer's standard names the version it rested on, and
that version can be read again a year later — which is what "attested" means and what
fetch-at-answer cannot provide.

### 3. Adoption is a decision, and noticing is not one

Detection compares an upstream tip against the adopted version's recorded tip — a refs listing,
no content transfer — and raises a flag. **Noticing changes nothing.** What answers rest on
moves only when an administrator reviews and adopts, through ADR-0069's request-and-decide path.

This is the shape the egress class needs to be safe: the cheap, frequent, automatic operation
(detection) cannot alter behaviour, and the operation that alters behaviour (adoption) is a
person's act with a name and a timestamp against it.

## Consequences

**A served process now makes outbound requests to a location a customer chose.** That is a real
widening and it is why the bounds above are enumerated rather than described. The mitigations
are structural: the reachable set is the endorsement record, the answering path is instrumented
to assert zero such requests, and the sync is read-only.

**Drift is noticed at the health checker's cadence, not instantly.** Detection rides the
existing checker rather than a scheduler of its own (Principle VI — nothing new is operated).
For content that changes on human timescales this is acceptable; if it ever is not, the fix is a
cadence change, not a second mechanism.

**A failure message must not echo what `git` said.** git puts the remote URL in `stderr`, and a
URL can carry material in it. Failures name an exit code. This is the kind of consequence that
is invisible until it is a credential in a log nobody redacts.

**ADR-0030 now has a named exception rather than a silent one.** Anyone reading it will find
this record; anyone reading this one will find the reasoning rather than an inconsistency.

## Alternatives considered

**Fetch customer content at answer time (inherit ADR-0030 unchanged).** Rejected for the pinned
corpus's stated reason: every answer would depend on a third party being reachable, and a
citation could resolve to different content each time it was followed. It would also make the
egress class *unbounded in time* — the platform reaching outward on every question — which is a
far larger widening than the one taken here.

**Sync from outside the platform, as `corpus-sync` does.** Rejected because it does not work:
customer content is per-deployment and arrives at runtime, so there is no commit and no
operator's machine in the loop. Attempting it would mean an operator running a script per
customer per change, which is an operational burden invented to avoid writing this record.

**Treat the sync as a tool call, and let the governed tool layer carry it.** Rejected: tools are
what a *run* may do, and syncing is something the *platform* does on an administrator's
instruction. Modelling it as a tool would put a capability into the ceiling vocabulary that a
dispatched run could then name — the opposite of E24, which asserts no run can reach any of this
in any wording.

**Adopt automatically when drift is detected.** Rejected, and this is the alternative that would
have been easiest to ship. It would mean a customer's edit silently changing what the platform
answers, with no person's decision between the two — and the trail would record a version change
authored by a timer. Detect is not adopt.
