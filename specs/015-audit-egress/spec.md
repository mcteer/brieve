# Feature Specification: Audit egress for tamper-evidence

**Feature Branch**: `spec/015-audit-egress`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "Ship the audit trail to a destination outside the writing system's administrative control, and reconcile the two copies. Implements ADR-0055 (Accepted, nothing built) and closes ROADMAP gap 0 — every mechanism guarding the trail lives in the same Postgres as the data it guards, so the platform's central claim is enforced by a permission sitting next to the thing it protects."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — cited by ADR-0055 itself, and the whole of this feature. Today the trail's integrity rests on a grant adjacent to the data; afterwards a single-domain compromise leaves evidence of itself). |
| **ADRs touched** | **ADR-0055** (implemented — Accepted with nothing built, and this is the feature that builds it). **ADR-0020** (constrains, and is *not* reversed — the audit plane still never egresses beyond the organization's boundary by default; this adds a near destination only). **ADR-0035** (audit as a governed read path — reconciliation runs through it and is itself audited, because reading evidence is audited). **ADR-0021** (connectivity tiers — the tier changes where the destination is, never whether there is one). **ADR-0025** (adjacency vs containment — the distinction the resolution turns on, reused one level in). |
| **Evidence class** | **Attestation-relevant, and this is the evidence plane itself.** Every other feature adds records to the trail; this one changes what the trail's own integrity rests on. A weakness here is not one claim failing — it is every claim downstream of the audit plane resting on something weaker than it reads. |

## Clarifications

### Session 2026-07-30

- Q: When an entry cannot be shipped to the second destination, what must the platform do? →
  A: **Refuse the step only if the entry could not be durably captured for shipping.** Once it
  is durably recorded for delivery, the step proceeds even with the destination unreachable.
  *(Chosen over refusing until the destination acknowledges, which is the strongest reading of
  "governance control" and has a cost ADR-0055 does not weigh: the collector is administered by
  someone who is deliberately not the platform's administrator, so making the platform wait on
  it hands a third party the ability to halt all work — and an availability dependency on the
  party you do not control is a strange thing to accept in the name of integrity. Chosen over
  best-effort, which ADR-0055 names as "a convenience with a control's name". The line lands on
  **capture**, not delivery: what must never fail silently is the platform's own record that an
  entry is owed to the second copy. Delivery may lag; capture may not.)*

- Q: What must establish that the destination is genuinely under separate administrative
  control? → A: **An active probe**, at configuration and periodically after: the platform
  attempts to modify and to delete something already shipped, using its own credentials, and
  requires both to be refused.
  *(Chosen over an operator assertion recorded in configuration. The assertion is not
  worthless — the operator has knowledge the platform does not — but a platform reporting a
  control it has never exercised is the same shape ADR-0055 rejected when it foreclosed object
  storage the enclave's own role can write: something that looks like a second copy and is not.
  Relocating that into a config file does not change what it is. The probe turns the
  requirement into an observation, and it fails in the safe direction: a destination that
  cannot be tested is reported as unverified rather than assumed sound. Periodic, not
  once — administrative control is a property of the deployment and deployments drift, so a
  check performed only at configuration time certifies a state of affairs that may have ended
  months ago.)*

- Q: Must divergence be detected without anyone asking? → A: **Yes — reconciliation runs
  proactively on a schedule, and is also invokable on demand.**
  *(The threat this feature exists for is an administrator rewriting the local trail. A check
  that only runs when someone is already suspicious adds little to an investigation that was
  going to happen anyway, and leaves the attacker's window open until somebody wonders — which
  may be never. Scheduling bounds that window to one interval. On-demand is kept because an
  investigator with a specific question should not have to wait for a timer. This settles the
  OBLIGATION only; where the operation runs and what each pass compares remain planning
  questions.)*

## Why this exists

The chain is honest about what it provides. `audit_entries` is append-only **by grant**; the
evidence role holds `SELECT` and nothing at all on `audit_stream_heads`; and the head record
exists precisely because *a hash chain cannot detect truncation* — delete the newest three
entries and `seq 0..N-4` verifies perfectly.

**But detection is not prevention, and both tables live in the same Postgres.** An actor with
write access to that database can rewrite the entries *and* the head that would have exposed
the rewrite, consistently, and nothing anywhere disagrees. Every mechanism guarding the trail
sits inside the same blast radius as the data it guards.

ADR-0055 resolves this against ADR-0020's "the audit plane never egresses by default" by
drawing a distinction the earlier records did not draw sharply: **"outside the platform's
blast radius" and "outside the organization's boundary" are different axes.** What
tamper-evidence needs is different *administrative* control, not distance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An investigator has a second copy to reconcile against (Priority: P1)

An auditor asks whether the trail for a given tenant has been altered. Today the only answer
available is "the chain verifies", which is true of a trail an administrator rewrote
consistently. After this feature there is a second copy, held where the platform's own
credentials cannot reach it, and the answer becomes a comparison rather than a self-report.

**Why this priority**: it is the feature. Everything else here exists to make this copy
trustworthy or to make its divergence visible.

**Independent Test**: write entries through the normal path, read them back from the second
destination under that destination's own credentials, and verify the chain independently
there. Delivers value alone: even with no reconciliation operation, an investigator with two
copies can compare them by hand, and today cannot.

**Acceptance Scenarios**:

1. **Given** a run that writes audit entries, **When** those entries are written, **Then** each
   one appears at the second destination carrying sequence, tenant, correlation id, event type,
   payload, and both hashes — enough to chain-verify without consulting the first copy.
2. **Given** the second copy alone, **When** an investigator verifies its hash chain, **Then**
   verification succeeds or fails on the second copy's own contents, with no read of the first.
3. **Given** an entry rewritten in the first copy only, **When** the two are compared
   entry-for-entry, **Then** the altered entry is identifiable — not merely "something changed".

---

### User Story 2 - Truncation is detectable, not just alteration (Priority: P1)

The attack the chain cannot see is deletion of the newest entries. `audit_stream_heads` is what
closes it locally, and a second copy of the entries *without* a second copy of the head leaves
the attack intact against both copies at once.

**Why this priority**: equal to US1 and separated from it because it is the half most likely to
be dropped as an optimisation. Shipping entries is the obvious work; shipping the head is the
part that makes shipping entries worth anything against the strongest local attack.

**Independent Test**: truncate the newest entries in the first copy *and* adjust its head to
match — the consistent rewrite that currently defeats detection — then compare against the
second destination's head.

**Acceptance Scenarios**:

1. **Given** a stream with N entries, **When** entries are shipped, **Then** the head record
   for that stream is shipped as well.
2. **Given** the newest entries deleted from the first copy and its head lowered to match,
   **When** the two copies are compared, **Then** the divergence is reported and names
   truncation rather than "verification passed".

---

### User Story 3 - Divergence is reported by a named operation (Priority: P1)

Comparing the copies is what makes the second copy worth having. ADR-0055 requires it be a
named operation rather than an implied capability — something an operator invokes and an
investigator can point at — running through the governed read path, and audited, because
reading evidence is audited.

**Why this priority**: a second copy nobody compares is storage, not evidence. The three P1
stories are the minimum viable claim: a copy, its head, and a way to ask whether they agree.

**Independent Test**: invoke reconciliation against copies known to agree and known to differ,
and read the operation's own record back out of the trail.

**Acceptance Scenarios**:

1. **Given** two copies that agree, **When** reconciliation runs, **Then** it reports agreement
   over a stated range rather than silence.
2. **Given** copies that differ, **When** reconciliation runs, **Then** it reports what
   diverged and where.
3. **Given** any reconciliation run, **When** it completes, **Then** the fact that evidence was
   read is itself in the trail (ADR-0035), naming who asked.
4. **Given** a caller without evidence-read authority, **When** reconciliation is attempted,
   **Then** it is refused, and the refusal is recorded.

---

### User Story 4 - A destination the platform can rewrite is refused (Priority: P2)

ADR-0055 foreclosed a specific shortcut: shipping to storage the enclave's own workload role
can write would be trivial, would look like a second copy, and would be worthless — the same
credentials that rewrite the first copy rewrite the second. The record exists to make that
non-solution *visibly* non-compliant rather than arguably sufficient.

**Why this priority**: P2 because the platform is useful without it and dishonest without it.
A configuration that satisfies the letter of "ships somewhere else" while failing its purpose
is worse than no shipping at all, because it reads as compliant.

**Independent Test**: configure a destination the platform's own credentials can alter and
observe that the platform refuses it or reports the configuration as non-compliant.

**Acceptance Scenarios**:

1. **Given** a destination writable by the platform's own credentials, **When** audit egress is
   configured against it, **Then** the configuration is refused or reported as not satisfying
   tamper-evidence, naming the reason.
2. **Given** a destination under separate administrative control, **When** the same check runs,
   **Then** it is accepted.

---

### User Story 5 - An air-gapped estate still has a second copy (Priority: P2)

The connectivity tier changes *where* the destination is, never *whether* there is one. An
air-gapped estate ships to a local collector under separate administrative control. An estate
with no second copy has no tamper-evidence, and saying so is better than a substitution that
quietly is not one.

**Why this priority**: P2 because it is a deployment shape rather than a new mechanism, and the
P1 stories must work before there is anything to place differently.

**Independent Test**: configure a destination reachable only on the local network, with no
egress beyond the boundary, and observe the same guarantees as US1–US3.

**Acceptance Scenarios**:

1. **Given** an estate with no outbound connectivity, **When** audit egress is configured to a
   local collector under separate administration, **Then** entries and heads ship and
   reconciliation works.
2. **Given** an estate configured with no second destination at all, **When** its posture is
   reported, **Then** it states plainly that tamper-evidence is not in force — rather than
   reporting a control that is not there.

### Edge Cases

- **The destination is unreachable when an entry is written.** Settled: the step proceeds,
  because the entry has been durably captured and is owed to the destination (FR-014a). What
  refuses a step is failure to capture, not failure to deliver — a destination administered by
  someone who is deliberately not the platform's administrator must not be able to halt the
  platform's work by being down.
- **Durable capture itself fails** — the disk backing it is full or unavailable. The step is
  refused (FR-014). This is the case that keeps the feature a control rather than a
  convenience: the platform will not do governed work it cannot account for.
- **The probe cannot run** because the destination does not support being tested. Reported as
  unverified, and the estate does not report tamper-evidence as in force (FR-020b) — the safe
  direction, since the alternative is a control the platform has never exercised reading as
  compliant.
- **The platform has entries written before egress was configured.** A second copy that starts
  mid-stream cannot verify what came before, and must not imply that it can. What the range of
  the guarantee is, and how it is stated, has to be explicit.
- **The two copies disagree about retention.** ADR-0055 defers this deliberately and says it
  may deserve its own record. Out of scope here, and named so the silence is a decision.
- **Reconciliation runs while entries are still being written.** The newest entries may
  legitimately be in one copy and not yet the other; a report that called that divergence would
  cry wolf on every run, and one that ignored it could hide real truncation at the tail.
- **A tenant's entries must not become readable to another tenant via the second copy.** The
  first copy's read path is tenant-scoped inside the hash chain (008); the second copy is a new
  place to get that wrong.
- **The second destination is itself compromised.** Detection is one-directional here: the
  feature reports that the copies differ, and cannot say which one is right.

## Requirements *(mandatory)*

### Functional Requirements

**Shipping**

- **FR-001**: The system MUST send every audit entry it records to a second destination.
- **FR-002**: The shipped record MUST carry the full chain entry — sequence, tenant,
  correlation id, event type, timestamp, payload, previous hash, and entry hash — so the second
  copy can be chain-verified independently and compared entry-for-entry. A digest-only or
  summary copy MUST NOT satisfy this.
- **FR-003**: The system MUST ship the `audit_stream_heads` record for a stream, not only its
  entries, because the head is what makes truncation detectable.
- **FR-004**: Shipping MUST NOT alter what is written to the first copy: the local trail's
  contents, ordering, and hashes are unchanged by the presence or absence of a destination.
- **FR-005**: The system MUST NOT require the second destination to be outside the
  organization's boundary. A destination inside it, under different administration, satisfies
  this feature.
- **FR-006**: The system MUST continue to treat export beyond the organization's boundary as an
  explicit, configured act that is off by default in regulated profiles (ADR-0020 unchanged).

**Administrative separation**

- **FR-007**: The system MUST reject, or report as non-compliant, a configured destination that
  the platform's own credentials can alter.
- **FR-008**: The system MUST hold no credential that grants it the ability to modify or delete
  what has already been shipped. Append is the most it may be able to do.
- **FR-009**: An estate with no second destination configured MUST be reported as having
  tamper-evidence **absent**, rather than defaulting to a state that reads as protected.

**Reconciliation**

- **FR-010**: The system MUST provide a named operation that compares the two copies over a
  stated range and reports agreement or divergence.
- **FR-010a**: That operation MUST run **proactively on a schedule**, so divergence surfaces
  without anyone suspecting it first, **and** MUST remain invokable on demand, so an
  investigator with a specific question does not wait for a timer.
- **FR-011**: Reconciliation MUST report *what* diverged — which stream, which sequence — and
  not only that something did.
- **FR-012**: Reconciliation MUST run through the governed read path and MUST itself be audited,
  naming the caller, because reading evidence is audited (ADR-0035).
- **FR-013**: Reconciliation MUST distinguish entries legitimately not yet shipped from entries
  missing at the destination, so a run concurrent with normal writing does not report false
  divergence — and does not hide truncation at the tail either.

**Failure**

- **FR-014**: When an entry cannot be **durably captured for shipping**, the system MUST refuse
  the step that produced it — the same posture `start_governed_run` already takes toward a run
  whose `AUTHORITY_ISSUED` could not be audited.
- **FR-014a**: When the entry HAS been durably captured but the destination is unreachable, the
  system MUST allow the step to proceed. The guarantee is that no entry is ever lost, not that
  every entry has already arrived; delivery may lag, and a destination administered by someone
  who is deliberately not the platform's administrator MUST NOT be able to halt the platform's
  work by being down.
- **FR-015**: The system MUST NOT silently drop an entry it failed to ship. Whatever FR-014
  resolves to, an unshipped entry MUST be visible — an emitter that can drop without anyone
  seeing is the evidence gap this feature exists to close.
- **FR-016**: The system MUST make the backlog of unshipped entries observable, so an operator
  can see the second copy falling behind before it becomes a gap.

**Scope of the guarantee**

- **FR-017**: The system MUST state the range over which tamper-evidence holds, so entries
  written before egress was configured are not implied to be covered.
- **FR-018**: The system MUST NOT claim that a shipped copy makes the trail immutable. What it
  provides is that a single-domain compromise leaves evidence of itself.
- **FR-019**: The second copy MUST preserve the tenant scoping the first copy enforces; a
  tenant's entries MUST NOT become readable to another tenant by way of the destination.
- **FR-020**: The system MUST establish that the destination is under separate administrative
  control by **actively probing it**: using its own credentials, the platform attempts to
  modify and to delete an already-shipped record, and both attempts MUST be refused.
- **FR-020a**: The probe MUST run at configuration time **and periodically thereafter**.
  Administrative control is a property of the deployment and deployments drift; a check
  performed once certifies a state of affairs that may since have ended.
- **FR-020b**: A destination that cannot be probed MUST be reported as **unverified** rather
  than assumed compliant, and an estate relying on one MUST NOT be reported as having
  tamper-evidence in force.
- **FR-020c**: The probe MUST NOT leave the destination altered. A test that succeeded in
  modifying something to prove it could not would be self-refuting.

### Key Entities

- **Shipped entry**: the full chain entry as it exists at the second destination — same
  sequence, tenant, correlation id, event type, payload and hashes as the first copy. Its
  defining property is that the platform cannot alter it after the fact.
- **Shipped head**: the per-stream high-water record at the destination, whose disagreement
  with the local head is what makes truncation visible.
- **Destination**: a location under administration that is not the platform's. Characterised by
  who can change what is there, not by where it is.
- **Reconciliation report**: the result of comparing the copies over a range — agreement, or
  divergence naming stream and sequence. Produced by a governed, audited operation.
- **Unshipped backlog**: entries recorded locally and not yet confirmed at the destination. Its
  depth is the observable that tells an operator the guarantee is degrading.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every audit entry written during a run is present at the second destination, with
  all chain fields intact, verified by reading the destination under its own credentials.
- **SC-002**: The second copy's hash chain verifies using only the second copy.
- **SC-003**: An entry altered in the first copy alone is identified by sequence when the copies
  are compared.
- **SC-004**: A truncation of the first copy *and* its head — the consistent rewrite that
  currently defeats all local detection — is reported as divergence.
- **SC-005**: A destination writable by the platform's own credentials is refused or reported
  non-compliant, naming why — established by the platform actually attempting the write and
  the delete, not by reading a configuration flag.
- **SC-005a**: A destination that cannot be probed is reported as unverified, and the estate
  relying on it does not report tamper-evidence as in force.
- **SC-006**: An estate with no destination configured reports tamper-evidence as absent.
- **SC-007**: Every reconciliation run appears in the trail naming its caller, and an
  unauthorized attempt is refused and recorded.
- **SC-008**: Reconciliation run concurrently with active writing reports no false divergence.
- **SC-009**: The backlog of unshipped entries is observable at any time.
- **SC-009a**: With the destination unreachable for a sustained period, runs continue to
  completion and every entry written during the outage reaches the destination once it returns
  — none is lost, and the backlog reflects the outage while it lasts.
- **SC-009b**: With durable capture itself failing, the step is refused rather than proceeding
  unrecorded.
- **SC-010**: The conformance rows assert all of the above against a **real** second destination
  holding credentials the platform does not have — not an in-process double, and not storage
  the platform's own role can write, which is the non-solution ADR-0055 named.

## Assumptions

- **The `AuditSink` protocol is the integration point.** It has two implementations already, so
  a fan-out that writes locally and hands the entry onward needs no signature change. Assumed
  rather than mandated: the plan may find a better seam, but this feature is an integration and
  not a rework of the audit plane.
- **The collector ADR-0020 already describes is the natural destination**, so the transport is a
  configuration surface the platform has rather than a new one.
- **"Different administration" is a property of the deployment, not something the platform can
  create.** The platform can refuse a destination it can obviously alter and can state what it
  requires; it cannot make an organization run the collector under separate administrators.
- **The dev enclave must be able to demonstrate this**, which means standing up a second
  destination with its own credentials in the enclave — the same posture the durability rows
  take toward Postgres. What cannot be demonstrated locally is genuine *organizational*
  separation of administrators, which is a deployment property; the rows can demonstrate that
  the platform's credentials do not work against the destination.
- **Retention divergence between the copies is out of scope** and ADR-0055 says so explicitly,
  flagging it as possibly deserving its own record.

## Deferred to planning

Recorded here rather than resolved, because they are implementation shape rather than
requirements, and because ADR-0055 names the first one as a guess it declined to make:

- **Synchronous or spooled.** ADR-0055's guess is a local durable spool the shipper drains, so
  the write blocks on local disk rather than the network and spool depth is itself observable.
  The alternative — a synchronous ship where a step waits on the second copy — is defensible
  with a different cost profile. Principle VI ("nothing blocking that could be an async
  emitter") pulls one way; FR-015 pulls the other. This decides latency and failure behaviour,
  not what the feature guarantees, so it belongs in research rather than here.
- **Transport and wire format.** Whether entries reach the collector over the existing OTel path
  or a dedicated one, and in what encoding, is a plan-level question. FR-002 constrains the
  *content*; nothing here constrains the carriage.
- **Where reconciliation runs, and what each pass compares.** FR-010/FR-010a settle the
  *obligation* — proactive on a schedule, and invokable on demand — and deliberately not the
  shape. Which process holds it follows from where credentials for both copies can legitimately
  meet, and whether a scheduled pass compares every entry or something cheaper that still
  catches truncation is a cost question with a real answer either way. Both belong in research.
