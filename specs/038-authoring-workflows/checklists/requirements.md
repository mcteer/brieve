# Specification Quality Checklist: The agent authors, and a person merges

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-05
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

**16/16 passing.** Four clarifications resolved in the 2026-08-05 session, and the first
changed the feature's shape rather than filling a gap.

### The scope question the maintainer raised

The draft deferred "applying" without checking whether that matched intent. It did — but
arriving at that answer produced a better rule than the draft had: **the platform does not
enact an artifact it authored**, expressed as *provenance* rather than as capability.

That distinction is what makes it enforceable and what makes it uniform. `terraform_apply` is
untouched and keeps doing what it does today; a merged proposal is ordinary reviewed
configuration and applying it is the act it always was. One boundary covers a Terraform module
standing up infrastructure and a Vault integration landing in application code, rather than a
rule per artifact type. FR-020b follows from it: a rule that turns on provenance requires
provenance to be **recorded and checkable at the moment of enactment**, which is a real
requirement the capability framing would never have surfaced.

Also measured while deciding: applying is **already governed** (`destructive`, non-repeatable,
observer required). The gap this feature fills is authoring, not enacting — and had the answer
gone the other way, ADR-0038 would have needed *amending* rather than implementing, since its
stated reason the family is safe rests on the pull-request boundary.

### The other three

- **FR-013 — the proposal is bounded to the change.** Files created plus diffs of files
  edited, nothing else. Decidable by inspecting the artifact rather than by trusting the
  agent, which is the property that matters: a proposal either contains an untouched file or
  it does not. FR-013b exists so the rule cannot be read as forbidding the surrounding context
  a diff necessarily shows — that is the change, not a leak.
- **FR-018 — two gates, reported separately.** Tooling catches malformed; a human-authored
  reference catches *subtly wrong*, which is ADR-0038's actual warning and the one tooling
  cannot see. Collapsing them into a single score would hide which failure occurred.
- **FR-005 — read-only mount, and the reasoning recorded because it looks like a reversal.**
  037's "no mount" never meant "mount nothing"; it meant *do not hand a redirected agent the
  platform's own tree*. That rule is held, not relaxed: the requester's repository is mounted,
  the platform's is not, and the egress allowlist stays static so the tier's posture remains
  structurally assertable.

### What this feature is most likely to get wrong

**FR-018c** — every golden task needs a human-authored reference, and that is the expensive
clause. The temptation under time pressure is a corpus of tasks whose references are generated
rather than authored, which would measure the generator against itself. 037's precedent
applies: a corpus without a real floor leaves the honesty of an entire half of the feature to
whoever wrote the tasks.

**And the sharpest tension is US3.** Analysing a private repository and then opening a pull
request creates a legitimate channel out of the isolation the analysis ran in. The channel is
the feature working correctly. FR-013 is what keeps it narrow, and it is the requirement to
scrutinise first in analyze.
