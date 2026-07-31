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
control plane, produces the same green and asserts nothing. FR-005 makes the distinction
explicit and SC-003 makes it measurable, because "the write did not happen" has at least
four causes and only one of them is evidence.

**FR-004 exists because of a specific near-miss.** A run's authority carries several bounds
at once. A refusal caused by the absence of an unrelated one would satisfy a careless check
while proving nothing about the bound under test — the same trap 017 hit and documented when
a row could have been satisfied by a grant arriving from a different policy.

**FR-017 is not housekeeping.** The break fixture temporarily widens real authority on a real
control plane. A fixture that failed partway would leave the platform more permissive than it
found it, which is a worse outcome than having no test — so restoration is verified rather
than attempted.

**FR-022 bounds the claim deliberately.** This proves the refusal, not that the bounds are
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

   FR-009 and a rewritten entity definition now say it: **acting within authority versus
   changing what the authority is.** A run may spend the budget and may not edit the budget.
   A check that drifted across that line would forbid the platform's whole purpose while
   looking stricter — which is a worse failure than the one this feature exists to fix, and
   the spec was one careless implementation away from inviting it.

**Analysis pass 1 — 2026-07-31.** Five findings, and the first was predicted before the pass
ran, which is weak evidence it was the obvious hole rather than the only one.

- **The bounding set was fail-open.** It derives from what a run may *read*; a record placed
  outside those grants is invisible to the derivation — and still bounds the run, because the
  platform consults it whether or not the run can. FR-011 promised that an uncovered kind
  fails the gate; the design could only deliver that for records already inside the policy,
  and the contract had recorded the difference as a *known limit* rather than a defect. A
  limit nobody would notice being exceeded is not a limit. FR-014 makes it a failure, by
  cross-checking against what exists.

  017 found the identical hole in its own coverage after four analysis passes. Twice now, a
  set built from enrolments has been blind to what never enrolled.
- **FR-017 had no check.** "No automated check may widen authority" is the sharpest safety
  property here — the reason the demonstration is manual — and it rested entirely on nobody
  adding such a fixture later. T007a asserts it by source inspection.
- **One task forbade what another required.** T014 said no row may use administrator
  authority; the cross-check above needs exactly that to enumerate. The resolution is a
  distinction rather than a compromise: refusal assertions use a run's authority and nothing
  else, enumerations may use admin and must never assert a denial. A denial to an
  administrator proves nothing.
- Terminology settled on one concept with two spellings, and the model says they are the
  same. The read-discriminator requirement was renumbered — it was the most important one in
  the feature and had the least legible identifier, reading as a typo. (Renumbered again in
  pass 6, when the whole list was made sequential; it is FR-006 now.)

**Analysis pass 2 — 2026-07-31.** Four findings, and the first is pass 1's own fix having
the defect pass 1 was fixing.

- **The cross-check's scope was unbounded and covered one of two mounts.** FR-014 said
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
- FR-022's "the contract MUST say so" is now checked rather than trusted.

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

**Analysis pass 4 — 2026-07-31.** Three findings, and the first is this feature committing
the second anti-pattern it had already written down.

- **`NAMED_BOUNDS` was a subject list, and it was incomplete the day it was written.** Pass 3
  named three surfaces. Four more bound a run just as directly: the trusted-key configuration,
  identity groups, the auth methods the control plane serves, and its mounts. The first of
  those outranks everything in either half — write it and the control plane starts believing
  identities somebody else mints, and no record in any jurisdiction has to change.

  All seven refuse today. The platform was sound; the claim was not, for the fourth
  consecutive pass.
- **The reasoning was available and went unused.** These notes already say why 017 accepted an
  exclusion list after rejecting a subject list — *"a stale exclusion names something absent
  and fails; a stale subject list omits silently."* Pass 3 then closed its gap with a subject
  list. Pass 3 also correctly named the *other* pattern — every mechanism anchored on what a
  run can see — and did not notice its own fix was an instance of a different one.

  Both halves now have a completeness check and neither rests on a maintained list.
- T003d's "removing an entry is a deliberate act" named no mechanism; T003e names the
  expected entries so shrinking fails rather than being deliberate-by-convention.

**Four passes, four HIGHs, each inside the previous pass's fix.** The useful conclusion is
not about this feature. Twice now the correct principle was written in these very files and
the next design violated it anyway — so recording a lesson does not prevent repeating it, and
what caught each repetition was re-reading the whole chain rather than remembering.

**Analysis pass 5 — 2026-07-31.** Three findings, and for the first time none is a bound
going unchecked.

- **The completeness check's predicate was undecidable**, so it would have collapsed into the
  hand-chosen set it replaced. It asked for "every enumerable surface where a write would
  change what a run may do". A control plane enumerates what it HAS — mounts, auth methods,
  roles, grants — not what bounds a run, which is a judgement. An implementer would have
  enumerated those four and believed the set complete. Now the requirement names the four and
  records the residual instead of implying there isn't one.
- Two checks overlapped without saying so: for the four enumerated kinds, T003d already covers
  what T003e asserts. T003e's value is the entries a judgement put there, and that is now what
  it asserts.

**Different in kind from passes 1–4.** Those each found a bound that would go entirely
unchecked. This one found a sentence claiming more than any mechanism can deliver — the
coverage is unchanged; what changed is whether the artifact admits its own limit. First
evidence of convergence rather than another instance of the same failure.

**Analysis pass 6 — 2026-07-31.** Three findings, none about coverage — the first pass where
that is true.

- **"Amend ADR-0047 at PATCH level" applied semver to a document with no version.** ADRs carry
  Status, Date, Relates-to and Requirements. PATCH/MINOR is the *constitution's* vocabulary,
  borrowed without noticing the difference, and an implementer would look for a field that does
  not exist. The repo's actual convention — set by ADR-0048's amendment the same day — is an
  appended `## Amendment` section with the Decision left intact.
- **The identifiers had accreted past readability.** `FR-006, FR-006aa, FR-006ab, FR-006a,
  FR-006b` — three suffix generations on one number, presented out of their own order, in the
  document whose job is to be held against a pull request. Renumbered sequentially, once, before
  implementation makes them load-bearing in code comments.

  Renumbering is also where this pass made its own mistake: the first attempt applied the
  renames in sequence, so a requirement renamed to FR-004 was then caught by the FR-004 rule
  and renamed again. A single pass with one callback fixes it — every occurrence matched once
  against the original text. Two references to *017's* FR-005a were nearly rewritten as well,
  and are correct as they stand.
- **"MVP: phases 1–3" had stopped describing what it points at.** Phase 2 grew from 6 tasks to
  13 across six passes, each adding a coverage mechanism rather than a story. The MVP is 18
  tasks and now says so, with the smaller split named for anyone who wants one.

**Six passes.** Findings moved from *a bound is invisible* (1–4) to *a claim exceeds its
coverage* (5) to *the artifact is hard to use* (6). Three categories, in that order, each
strictly less serious than the last — offered as a description of what happened, not a
forecast.

Two things flagged for planning rather than fixed here:

- **US4's amendment and US1's gate could be separated.** They are one feature because the
  amendment without the gate leaves the row unowned, and the gate without the amendment
  leaves the next row in the same ambiguity. But they land in different artifacts, and the
  plan should decide whether they are one change or two.
- **Enumerating "every kind of bounding record" (FR-010, FR-011) needs a discovery
  mechanism**, or it is a list that goes stale — which is the failure mode 017's FR-005a was
  raised for after analysis found an opt-in scheme fail-open. The plan should not repeat that
  by hand-listing three kinds.
