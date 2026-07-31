# Feature Specification: Registry isolation — the refusal is observed, not argued

**Feature Branch**: `spec/018-registry-isolation`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Registry isolation — a run is observed being refused when it writes the control plane that bounds it, and ADR-0047 gains the distinction that let this row sit unowned. Closes the last of the three open items on the ROADMAP page, and it is the only one that is a GATE rather than a document."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — the whole of this feature. The guarantee currently rests on a person reading configuration and concluding that no write was granted, which is an argument. Afterwards it rests on the control plane having refused one). **R2, R3** (the authority bounds themselves, which this proves a run cannot move). |
| **ADRs touched** | **ADR-0047** (amended, PATCH — it assumes every deferred gate row traces to an ADR that defers it, and this row never did. Two states are named where there was one). **ADR-0025** (the rule this row asserts — agents are structurally excluded from managing their own platform). **ADR-0015** (the division of labour it depends on: definitions authored as reviewed configuration, enforcement in the control plane — a run that could write its own bounds would erase that line). **ADR-0016** (widening a bound is a governed act; this proves a run cannot perform one directly). **None superseded.** |
| **Evidence class** | **Attestation-relevant.** Every authority decision this platform makes is bounded by records a run must not be able to change. This does not add to the audit trail; it establishes that the bounds the trail's decisions cite could not have been moved by the thing they bound. |

## Clarifications

### Session 2026-07-31

- Q: FR-007 proves the gate can fail by granting a run write access to its own bounds, which
  temporarily makes a real control plane permissive. When does that run? → A: **Never in a
  merge lane.** Performed once at implementation against a developer's own enclave and
  recorded with its output; the merge lane runs only the refusal rows. Nothing automated
  ever widens authority, so no interrupted run can leave a control plane permissive.
- Q: What does the gate do if the write SUCCEEDS? → A: **Its own outcome, and it removes what
  it wrote.** Not "assertion failed" but "a run changed the record bounding it" — an ordinary
  red test is something someone reruns, while this leaves a widened ceiling live on the
  control plane until somebody notices. The check created that condition and must not walk
  away from it.
- Q: Agents write constantly — secrets in their own space, configuration, product calls. Is
  that in scope? → A: **No, and the spec now says where the line is.** An agent acting
  *within* its authority is the product. This feature is about an agent changing *what its
  authority is* — the records the control plane consults when deciding whether to let it act.
  A run may spend the budget; it may not edit the budget.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run cannot widen its own bounds, and that is observed (Priority: P1)

A run holds the authority its definition grants. It attempts to rewrite the record that
states those bounds — the one naming what it may ever do. The control plane refuses, and
the refusal is recorded by a merge-blocking check rather than inferred from configuration
nobody re-reads.

**Why this priority**: This is the row the constitution names and nothing implements. Today
the guarantee is an argument: someone read the configuration, saw that no write capability
was granted, and concluded a run cannot write. That argument is correct and unverified — a
configuration change granting the write would pass every check in the repository.

**Independent Test**: Have a run attempt to widen its own bounds against the live control
plane and confirm the attempt is refused. Separately and once, grant the write, confirm the
check fails, and revoke it — that demonstration is not part of the merge lane. Delivers the
whole of the feature's value on its own.

**Acceptance Scenarios**:

1. **Given** a run holding an agent definition's authority, **When** it attempts to rewrite
   that definition's bounds, **Then** the control plane refuses and the check records the
   refusal.
2. **Given** the same run, **When** it attempts to rewrite a **different** definition's
   bounds, **Then** the control plane refuses — a run may not widen anyone's bounds, not
   merely its own.
3. **Given** a configuration that grants the write, **When** the check runs, **Then** it
   fails. The check must be able to fail for the reason it exists — established once, by
   hand, and recorded, because no automated lane may widen authority.

---

### User Story 2 - The refusal comes from the control plane, not from our code (Priority: P1)

The check must observe the trust fabric refusing. A refusal produced by the platform's own
code — a guard that declines to issue the request — would satisfy a naive check while
proving nothing about what the control plane would have done.

**Why this priority**: Also P1, and inseparable. The claim is *structural exclusion*: a run
cannot do this even if its own code tried. A check that never issued the request, or that
was refused by a layer above the control plane, asserts something weaker than the claim and
reads identically in a report.

**Independent Test**: Confirm the request reached the control plane and that the refusal
carries the control plane's own account of it, not the platform's.

**Acceptance Scenarios**:

1. **Given** an attempted write, **When** it is refused, **Then** the refusal is the control
   plane's, and the check reports what the control plane said.
2. **Given** a check that did not issue the request at all, **When** it is reviewed, **Then**
   it is distinguishable from one that did — a check proving nothing must not read as green.
3. **Given** the authority under test, **When** it is assembled, **Then** it carries **only**
   the bound being tested — a refusal caused by the absence of some other grant proves less
   than one caused by the absence of this one.

---

### User Story 3 - Every place a run could widen a bound is covered (Priority: P2)

Bounds are not one record. A definition's ceiling, the registry entry that makes a
definition exist at all, and the bindings that decide what a person may delegate are
separate, and a run must be refused at each. Covering one and calling it isolation would be
the appearance of a gate.

**Why this priority**: P2 rather than P1 because the first covered surface is worth having on
the day it lands, and because the constitution's wording names the class rather than
enumerating members. But an incomplete set is how this row would degrade into a formality.

**Independent Test**: Enumerate the record kinds a run could widen, and confirm each has an
attempted write and an observed refusal.

**Acceptance Scenarios**:

1. **Given** the set of record kinds that bound a run, **When** the check runs, **Then**
   every kind has an attempted write and an observed refusal.
2. **Given** a new kind of bounding record added later, **When** the check runs without one
   being written for it, **Then** the check fails rather than passing silently.

---

### User Story 4 - A gate row with no deferring record has a defined state (Priority: P2)

The governing record says a gate row not yet in force is either absent or explicitly skipped
**citing the record that defers it**. That assumes every such row traces to one. This row
never did — it derives from a principle and a structural rule, neither of which defers it —
so for four features it has been neither in force nor properly deferred, and the situation
had no name.

**Why this priority**: P2 because the gate is the substance and this is the record catching
up. But it is not optional: without it, the next row in the same position repeats four
features of ambiguity, and the feature that hits it has to explain itself from scratch, as
the last one did.

**Independent Test**: A reviewer holding a feature against the gate list can determine, for
every row not in force, which of the two states it is in and where the reason is recorded.

**Acceptance Scenarios**:

1. **Given** a gate row not in force, **When** a reviewer asks why, **Then** it is either
   deferred by a decision that is cited, or not yet applicable with the reason recorded in
   the feature's own contract.
2. **Given** this row specifically, **When** the amendment lands, **Then** it moves from *not
   yet applicable* to *in force*, and the record says so.

---

### Edge Cases

- **The write succeeds.** Its own outcome, and the check removes what it wrote. This is the
  one result meaning the platform's central claim is false, and it is the only failure that
  leaves the system changed.
- **A run's ordinary write is mistaken for a violation.** A run writing a secret in its own
  space is the product working. A check that flagged it would be stricter in appearance and
  wrong in substance.
- **The request never reaches the control plane.** Refused by a name that does not exist, by
  an unreachable fabric, or by a guard in the platform's own code — all produce "the write
  did not happen" and none proves the claim. These must be distinguishable from a refusal.
- **The refusal is for the wrong reason.** An expired or malformed authority is also refused.
  A check that accepted any refusal would pass against an authority that could have written
  had it been valid.
- **A bounding record kind exists that nobody enumerated.** The gap this row exists to close,
  reproduced inside it — and it happened, twice, before implementation began. First the
  derivation was blind to records outside a run's read grants; then the cross-check added to
  fix that was blind to the grant of authority itself.
- **A bound that a run cannot read.** Invisible to any scheme anchored on what a run can see,
  which is what every version of this design was until analysis pass 3.
- **The demonstration is interrupted.** Whoever grants the write to prove the gate can fail
  is responsible for revoking it, and must verify the revocation. This is why the
  demonstration is manual and one-time: an automated fixture killed between grant and revoke
  would leave a real control plane permissive with nobody watching.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The gate MUST attempt a real write to each kind of record that bounds a run,
  using authority a run actually holds, and MUST observe the control plane refusing it.
- **FR-002**: The refusal MUST come from the control plane. A refusal produced by the
  platform's own code, or the absence of an attempt, MUST NOT satisfy the gate.
- **FR-002a**: Two kinds of act, two authorities, and they MUST NOT be mixed:

  | Act | Authority | May assert |
  | --- | --- | --- |
  | **Assert a refusal** | a run's own, all of it | that a run cannot write |
  | **Enumerate what exists** | administrator | what the set must contain |

  An enumeration that drifted into asserting a denial would assert that an *administrator*
  was refused, which is the opposite of interesting.
- **FR-003**: The authority used MUST be **the authority a run actually holds** — all of it,
  as deployed. The claim is that a run cannot write its own bounds; stripping its authority
  to a single grant would prove something narrower, leaving open whether some combination
  permits the write.

  *Corrected during planning.* This originally required the opposite — an authority carrying
  only the bound under test — to stop a refusal being caused by the absence of an unrelated
  grant. That concern was real and is met better by FR-004a: discriminating on whether the
  **path** is readable, rather than on which grants are present.
- **FR-004**: The gate MUST distinguish "refused" from "never attempted", "unreachable", and
  "refused for an unrelated reason" — and MUST treat only a genuine refusal as evidence.
- **FR-012**: A refusal counts **only when the same authority can read the path**. The
  control plane deliberately answers identically for *forbidden* and *absent* — it will not
  disclose which, because that would leak the shape of the tree to an unauthorized caller.
  Verified during planning: a mount that does not exist is refused in exactly the same words
  as a real bounding record. So a row with a typo in its path passes while asserting nothing,
  and only a successful read proves the refusal was about the capability.
- **FR-004a**: A write that **succeeds** MUST be reported as its own outcome, distinct from
  an assertion that could not be made. A red check is something someone reruns; a bounding
  record that was actually changed is a live condition the platform claims cannot exist.
- **FR-004b**: A gate that succeeded in writing a bounding record MUST remove what it wrote,
  and MUST say whether it managed to. The check created that condition; leaving it for
  someone to notice would make the gate the thing that widened a ceiling.
- **FR-004c**: The gate MUST NOT treat a run's ordinary writes as violations. Writing
  secrets in its own space, configuration, or product state is what a run is for. Only the
  records that decide what a run may do are in scope, and a check that drifted into the
  first would forbid the platform's purpose while appearing stricter.
- **FR-005**: The gate MUST cover every kind of record that bounds a run, in **both** of the
  places such records live:

  **Records a run can read** — what a definition may ever do, whether a definition exists,
  what a person may delegate, and the rest of that jurisdiction. These are derived.

  **Bounds a run cannot read, and which bind it anyway** — the grant of authority *itself*,
  the rule deciding which grants a run receives, the configuration deciding **whose
  identities are trusted at all**, and the attachment of grants to identities and groups. A
  run holds no read access to any of them, so no derivation from its grants can find them.

  These are named — **and the named half MUST have its own completeness check** (FR-005a).
  A hand-written list is a *subject* list, which this repository has twice concluded goes
  stale silently, and pass 3's version of it was incomplete on the day it was written. The
  most powerful surface of all was missing: write the trusted-key configuration and the
  control plane starts believing identities somebody else mints, which outranks every record
  in either half.

  The second kind is the more direct route and was missed for two analysis passes. A run's
  limits are stated twice — once as a record the platform consults, and once as the grant the
  control plane enforces — and rewriting the second moves the bound without touching the
  first. A gate covering only records *about* the bounds, while missing the bound itself,
  asserts the wrong half of its own name.
- **FR-006**: A bounding record kind with no attempted write MUST fail the gate rather than
  be silently uncovered.
- **FR-006aa**: **Both halves MUST have a completeness check, and neither may rest on a list
  somebody maintains.** The named half is checked against the control plane's own enumeration
  of its configuration surfaces — the auth methods it trusts, the mounts it serves, the grants
  it holds. Every enumerable surface where a write would change what a run may do MUST be
  named or excluded with a reason. Enumerating is a COVERAGE act under FR-002a and may use
  administrator authority; it must never assert a denial.

  **Why, stated because the reasoning was available and went unused**: a set with one
  mechanism is a list, and a list omits silently. That is written down in this feature's own
  checklist as the reason 017 accepted an exclusion list after rejecting a subject list — and
  the named half was introduced as a subject list anyway, incomplete on the day it was
  written. Two documented anti-patterns in one feature, and the fix for one was an instance of
  the other.

- **FR-006a**: The **derived** half MUST be checked against **what actually exists in the
  jurisdictions the derived paths occupy** — not only against what a run may read, and not against the
  whole control plane. Deriving from a run's read grants is sound for every record inside
  them and blind to any outside; a record placed where a run cannot read still bounds that
  run, because the platform consults it whether or not the run can. Anything present in
  those jurisdictions and absent from the set MUST fail.

  **The jurisdictions are derived where derivation works, and named where it cannot.** They
  are wherever the derived bounding paths already live — two at planning time — and a
  bounding record added in one of those extends the check without anyone editing it.

  **Derivation is structurally blind to bounds a run cannot read**, and that is not a gap to
  be closed by a better derivation. Any scheme anchored on a run's grants cannot see a
  surface the run holds no grant on, and the grant of authority itself is exactly such a
  surface. So FR-005's second kind is named rather than derived, each entry carrying the
  reason — and the named part MUST NOT shrink silently, for the same reason the exclusion
  list must not.

  This is the direction a derivation cannot see by construction, and it is the same hole 017
  found in its own coverage mechanism after four analysis passes: a subject that never
  enrolled is invisible to a scheme built from enrolments.
- **FR-006b**: Enumerating what exists MAY use administrator authority; **asserting a
  refusal MUST NOT**. Those are different acts and conflating them would destroy the
  feature — a denial to an administrator proves nothing, because an administrator is not
  what the claim is about.
- **FR-007**: The gate MUST fail when the refusal stops holding, demonstrated by granting
  the write, observing the failure, and revoking it — **performed once at implementation and
  recorded with its output**, never in a merge lane.
- **FR-008**: **No automated check may widen authority.** The demonstration in FR-007 is
  manual and one-time precisely because an automated one would make a real control plane
  permissive on every run, and a lane interrupted mid-fixture would leave it that way. A
  window that is small is not a window that is closed, and this is the one guarantee whose
  temporary suspension is least acceptable.
- **FR-008b**: FR-008 MUST be enforced by a check rather than by convention, and the check
  MUST be scoped to **the act, not the authority**. Nothing in the suite may *write a policy*
  or *grant a capability*; reading with an administrator's authority is neither, and is
  required by FR-006b. A check keyed on which authority appears rather than on what is done
  with it would forbid the enumeration another requirement mandates.

  Recorded this precisely because a safety property resting on everyone remembering is the
  shape this repository has paid for more than once — and because a rule that catches the
  wrong thing gets relaxed until it catches nothing.
- **FR-008a**: The one-time demonstration MUST restore the authority it changed, and MUST
  verify the restoration rather than assume it. Whoever performs it is responsible for
  leaving the platform exactly as they found it, and the recorded output MUST show that.
- **FR-009**: The governing record MUST name **two** states for a gate row not in force:
  deferred by a decision that is cited, and not yet applicable with the reason recorded in
  the feature's contract. A row in neither state MUST be a defect.
- **FR-010**: This row MUST move to in-force, and the record MUST say so — an amendment that
  only described states without placing the row that prompted it would leave the situation
  it exists to end.
- **FR-011**: The gate MUST NOT assert that the bounding records' **contents** are correct.
  A record that is wrong in a way the reviewed configuration wrote is outside what a
  refusal can show, and the contract MUST say so — **checked, not trusted**, since a later
  edit could remove the statement and let a green row imply more than it asserts.

### Key Entities

- **Bounding record**: A record the control plane consults **when deciding whether to let a
  run act**, which the run must therefore not be able to change. Three kinds today: what a
  definition may ever do, whether a definition exists, and what a person may delegate.

  **Not** the things a run writes as its work. A run writes secrets in its own space,
  configuration, and product state constantly — that is the product, and it is governed by
  the bounds rather than being one. The distinction is acting *within* authority versus
  changing *what the authority is*: a run may spend the budget and may not edit the budget.
  A check that confused the two would forbid the platform's whole purpose.
- **Run authority**: What a run actually holds while executing — the thing whose limits are
  being tested. Not an administrator's, and not the platform's.
- **Observed refusal**: The control plane declining an attempted write, reported with its own
  account. Distinct from an absent attempt, an unreachable fabric, and a refusal caused by
  something other than the bound under test.
- **Gate row state**: Whether a named gate row is in force, deferred by a cited decision, or
  not yet applicable. Previously two states existed where three were needed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A configuration change granting a run write access to its own bounds fails a
  merge-blocking check. Demonstrated by making the change and observing the failure, not
  argued.
- **SC-002**: Every kind of bounding record has an attempted write and an observed refusal —
  **both the records a run can read and the grants it cannot**. A kind with no attempt is
  itself a failure, and the second kind is where "every" was quietly untrue for two analysis
  passes.
- **SC-003**: A check that did not issue its write is distinguishable from one that did and
  was refused. The first must not report success.
- **SC-004**: After the one-time demonstration, and after any run in which a write
  unexpectedly succeeded, the platform's authority is exactly what it was before — verified
  and recorded, not assumed. **No merge-blocking check ever widens
  authority**, so this is a property of a single documented act rather than of every run.
- **SC-005**: For every gate row not in force, a reviewer can determine which of the two
  states it is in and where the reason is recorded, without reading the feature's history.
- **SC-006**: The row the amendment was written for is in force when the amendment lands.
- **SC-007**: Every merge-blocking check that ran before this feature still runs afterwards.

## Assumptions

- **The mechanism already holds; only the evidence is missing.** The configuration grants
  read access and nothing more, and the records are written by a reviewed, separate path.
  This feature is expected to observe a refusal that already occurs — and if it does not,
  that is a far more serious finding than a missing test.
- **The gate asserts the denial, not the contents.** A bounding record that is wrong in a way
  the reviewed configuration wrote is invisible here. Anyone describing this as proving the
  bounds correct would be overstating it.
- **More kinds of bounding record exist than the three this spec named.** Planning found at
  least six readable bounding paths, one of which was added the same day this spec was
  written. The set must therefore be derived from the deployed configuration rather than
  listed here — a list would have been stale before the feature landed, which is the failure
  mode FR-006 exists to prevent.
- **Proving the gate can fail requires temporarily widening real authority**, and that is
  why it happens once, by hand, and is recorded — rather than on every merge. 017's break
  fixture set the precedent for a one-time recorded demonstration; here the stakes are higher,
  because what gets temporarily granted is authority rather than a role name. An automated
  fixture would leave a real control plane permissive for a short window on every run, and
  for an unbounded one if the run were killed between grant and revoke.
- **The amendment is a PATCH.** It names a state that already existed in practice and was
  unnamed. No row's assertion changes, nothing in force is relaxed, and nothing previously
  permitted becomes forbidden.
