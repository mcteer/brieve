# Specification Quality Checklist: Capability Packs and Eval Gates

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-29
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

**16/16 → 16/16.** No item changed state in the clarification session. It did not fix a
failing spec; it changed what the passing spec describes, which is the more useful outcome
and the one this checklist cannot see.

**The clarifications shrank the feature in one place and grew it in another**, which is
worth noting because the net is not obviously smaller. Deferring US6 removes the largest
dependency — a corpus, a retrieval path, precedence resolution. Shipping *two* packs rather
than one adds content work, deliberately, because FR-004's claim is about independence and
one pack has nothing to be independent of. That trade is the session's main decision.

**Two things carried forward rather than resolved**, both visible in the spec:

- **A cell qualified against a fixture is qualified against a recording.** The blocking lane
  scores fixtures so a merge gate does not fail for reasons unrelated to the change; a
  marked lane scores a live model. SC-013 exists so the contract cannot record a cell as
  qualified without saying which of the two it means.
- **The judge regress is no longer carried forward — it is a precondition.** Qualifying all
  five roles made it binding, and FR-012a requires it resolved and recorded *before any cell
  is qualified*, with the acceptable options bounded and the implicit answer forbidden. The
  spec still does not choose among them, because that is architecture and belongs to
  planning.
- **`write` qualified against a fixture** is the sharpest edge here: a model permitted to
  make changes, qualified against a recording. SC-013 keeps the distinction visible per
  cell; the marked live lane is what makes it mean something.

**Six requirements are deliberately negative** — FR-003 (no bypass path), FR-004 (no core
module names a product), FR-010 (no path reaches an unqualified model), FR-011 (no
auto-tracking anywhere), FR-014 (a gate that cannot run reports failure), FR-015 (a model
verdict never satisfies a human approval). All are testable by construction rather than by
observation. FR-004 in particular reads as a slogan until asserted structurally over the
real tree, and SC-012 makes it a diff rather than an argument.

### What the clarification session changed

Four questions, and two of them reversed earlier answers on evidence those answers did not
have — which is the pattern worth noticing rather than the exception:

1. **Packs became Terraform + Vault**, not Vault + Nomad. ADR-0004 says skills are *adopted*;
   the upstream source turned out to exist (`hashicorp/agent-skills`, MPL-2.0) and to cover
   Terraform and Packer only. Two authored packs would have left the supply chain with no
   subject — no real provenance, no real version to pin, nothing genuine to review for
   injection. The pair now proves adoption *and* invocation.
2. **Report fidelity is recorded as owed**, because `RunReport` does not exist in `src/`.
   ADR-0047's rule applied literally: absent or an explicit skip citing its deferring
   record, never a stub, and never a weaker property asserted under its name.
3. **All five roles are qualified**, which made the judge regress a precondition.
4. **The authored Vault skills use the upstream format**, because they are intended for
   contribution back — making this repository's authoring a temporary state by design
   rather than a permanent fork.
