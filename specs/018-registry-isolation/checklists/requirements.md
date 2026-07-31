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

Two things flagged for planning rather than fixed here:

- **US4's amendment and US1's gate could be separated.** They are one feature because the
  amendment without the gate leaves the row unowned, and the gate without the amendment
  leaves the next row in the same ambiguity. But they land in different artifacts, and the
  plan should decide whether they are one change or two.
- **Enumerating "every kind of bounding record" (FR-005, FR-006) needs a discovery
  mechanism**, or it is a list that goes stale — which is the failure mode 017's FR-005a was
  raised for after analysis found an opt-in scheme fail-open. The plan should not repeat that
  by hand-listing three kinds.
