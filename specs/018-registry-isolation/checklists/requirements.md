# Specification Quality Checklist: Registry isolation — the refusal is observed, not argued

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-31
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Passed on the first draft, verified by search rather than by reading: no product, language,
protocol or file name appears. 017's first draft failed this badly — its subject was
infrastructure and it was written in infrastructure vocabulary — so this one was written
against "bounding record", "control plane", "run authority", "observed refusal" from the
start.

**The strongest requirement is FR-002, and it is the one an implementation will weaken by
accident.** The claim is *structural exclusion*: a run cannot widen its bounds even if its
own code tried. A check that never issued the request, or one refused by a guard above the
control plane, produces the same green and asserts nothing. FR-004 makes the distinction
explicit and SC-003 makes it measurable, because "the write did not happen" has at least
four causes and only one of them is evidence.

**FR-003 exists because of a specific near-miss.** A run's authority carries several bounds
at once. A refusal caused by the absence of an unrelated one would satisfy a careless check
while proving nothing about the bound under test — the same trap 017 hit and documented when
a row could have been satisfied by a grant arriving from a different policy.

**FR-008 is not housekeeping.** The break fixture temporarily widens real authority on a real
control plane. A fixture that failed partway would leave the platform more permissive than it
found it, which is a worse outcome than having no test — so restoration is verified rather
than attempted.

**FR-011 bounds the claim deliberately.** This proves the refusal, not that the bounds are
right. A record that is wrong in a way the reviewed configuration wrote is invisible here,
and the contract must say so rather than let a green row imply more than it asserts.

**Clarify asked three questions; the third was the developer's and it was the best one.**

1. *The break fixture's blast radius* — proving the gate can fail means temporarily granting
   a run write access to its own bounds on a real control plane. Never in a merge lane: once,
   by hand, recorded. An automated fixture killed between grant and revoke would leave the
   platform permissive with nobody watching, and a window that is small is not one that is
   closed.
2. *A successful write* — its own outcome, and the check removes what it wrote. An ordinary
   red test is something someone reruns; a widened ceiling is a live condition. The check
   created it and must not walk away from it.
3. *"There are absolutely instances where an agent would be permitted to write something"* —
   raised by the developer against the spec's framing, and correct. Agents write constantly:
   secrets in their own space, configuration, product state. The `vault` pack ships a
   `vault_write` tool for exactly that. The spec said "bounding record" and meant something
   narrow, but did not say where the line was.

   FR-004c and a rewritten entity definition now say it: **acting within authority versus
   changing what the authority is.** A run may spend the budget and may not edit the budget.
   A check that drifted across that line would forbid the platform's whole purpose while
   looking stricter — which is a worse failure than the one this feature exists to fix, and
   the spec was one careless implementation away from inviting it.

**Analysis pass 1 — 2026-07-31.** Five findings, and the first was predicted before the pass
ran, which is weak evidence it was the obvious hole rather than the only one.

- **The bounding set was fail-open.** It derives from what a run may *read*; a record placed
  outside those grants is invisible to the derivation — and still bounds the run, because the
  platform consults it whether or not the run can. FR-006 promised that an uncovered kind
  fails the gate; the design could only deliver that for records already inside the policy,
  and the contract had recorded the difference as a *known limit* rather than a defect. A
  limit nobody would notice being exceeded is not a limit. FR-006a makes it a failure, by
  cross-checking against what exists.

  017 found the identical hole in its own coverage after four analysis passes. Twice now, a
  set built from enrolments has been blind to what never enrolled.
- **FR-008 had no check.** "No automated check may widen authority" is the sharpest safety
  property here — the reason the demonstration is manual — and it rested entirely on nobody
  adding such a fixture later. T007a asserts it by source inspection.
- **One task forbade what another required.** T014 said no row may use administrator
  authority; the cross-check above needs exactly that to enumerate. The resolution is a
  distinction rather than a compromise: refusal assertions use a run's authority and nothing
  else, enumerations may use admin and must never assert a denial. A denial to an
  administrator proves nothing.
- Terminology settled on one concept with two spellings, and the model says they are the
  same. `FR-004aa` renumbered — it was the most important requirement in the feature and had
  the least legible identifier.

**Analysis pass 2 — 2026-07-31.** Four findings, and the first is pass 1's own fix having
the defect pass 1 was fixing.

- **The cross-check's scope was unbounded and covered one of two mounts.** FR-006a said
  "anything present in the control plane", which is every mount — the gate fails on day one —
  and which an implementer would narrow to whichever mount came to mind. The bounding paths
  span **two**: the authority store and the agent registry. Narrowing to the first leaves the
  record deciding whether a definition exists at all outside the check added to make coverage
  complete. The jurisdictions are now derived from the paths, so a third extends the check for
  free.

  Third time in two features that a coverage mechanism has been blind in a direction its
  author did not consider. Worth watching for by name.
- **The exclusion list had no home and no staleness check.** 017 accepted an exclusion list
  after rejecting a subject list, on the grounds that a stale exclusion names something that
  is not there and fails, while a stale subject list omits silently. That reasoning only holds
  if something checks — T003b now requires every exclusion to name something that exists.
- **T007a forbade what T003a requires.** A rule against "widening authority", checked by
  source inspection, would flag the enumeration that legitimately reads with an administrator
  token. Scoped to the *act* now — writing a policy, granting a capability — not to which
  authority appears. The identical shape as 017's rule that forbade retry loops in words that
  caught its own readiness wait.
- FR-011's "the contract MUST say so" is now checked rather than trusted.

**Analysis pass 3 — 2026-07-31.** Three findings, and the first is the same wrong instinct
for the third time.

- **The gate checked the records that DESCRIBE a run's bounds and missed the record that IS
  one.** A run's ceiling is stated twice: as a KV record the platform consults, and as the
  grant the control plane enforces. Writing the second widens authority directly, bypassing
  every record the derived rows check — and it sits outside both halves by construction,
  because a run holds no read access to it. Two more surfaces share the blind spot: what
  decides which grants a run receives, and the attachment of grants to an identity.

  All three refuse today, probed against the live control plane. **The platform was sound and
  the gate's claim was not** — it would have reported "a run cannot widen its bounds" while
  never testing the most direct way to do so. That distinction is what ADR-0047 exists for,
  arriving against this feature's own coverage.
- **The derivation principle was stated as sufficient and is provably not.** Pass 2 wrote
  that a record added in a third mount extends the check for free — true only where a derived
  path already exists. Any scheme anchored on a run's grants is blind to what the run cannot
  read, and that is structural rather than a gap a better derivation closes.
- The model implied derivation was the whole story; it now carries both halves.

**Three passes, three HIGHs, each inside the previous pass's fix.** The pattern is now
explicit enough to state: every coverage mechanism in this feature was anchored on what a run
can see, and every bound a run cannot see was invisible to it. Not a bug in any one design —
the same instinct three times.

Two things flagged for planning rather than fixed here:

- **US4's amendment and US1's gate could be separated.** They are one feature because the
  amendment without the gate leaves the row unowned, and the gate without the amendment
  leaves the next row in the same ambiguity. But they land in different artifacts, and the
  plan should decide whether they are one change or two.
- **Enumerating "every kind of bounding record" (FR-005, FR-006) needs a discovery
  mechanism**, or it is a list that goes stale — which is the failure mode 017's FR-005a was
  raised for after analysis found an opt-in scheme fail-open. The plan should not repeat that
  by hand-listing three kinds.
