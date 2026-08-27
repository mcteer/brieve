# Feature Specification: A phase card delegates to the skill it is bound to

**Feature Branch**: `053-cards-delegate-to-skills`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "The pinned skill teaches nothing the card has not already said by hand."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12 (eval / gate)** — the effect of a bound skill must be expressible as a row that can lose; today it cannot, and this feature is what makes it able to. **R16 (sealed core, versioned seams)** — the whole change is pack content on the far side of the pack seam; no core source changes. **R4 / R13 (evidence)** — a run whose record names a pinned skill must be a run that skill could have changed |
| **ADRs touched** | **ADR-0004** (skills are an adopted, pinned supply chain — a pin that governs nothing is the half this feature repairs). **ADR-0030** (executed content is pinned — content that is pinned *and* independently restated is not the executed copy). **ADR-0047** (a passing stub is worse than a missing one — a binding whose removal changes nothing is that failure in the content plane). **ADR-0003** (a vertical ships as a content profile — the practice belongs in the adopted skill, not hand-copied into the card). Consumed unchanged: ADR-0038, ADR-0063 |
| **Evidence class** | eval-relevant — the SC-002 row of 051 currently cannot fail, and the record's `content_pins` names skills that could not have altered the output |

## User Scenarios & Testing *(mandatory)*

### The measurement that produced this feature

051 proved *delivery* byte-for-byte and could not prove *effect*. The 2026-08-27 SC-002 run
returned NOT DEMONSTRATED across three arms and forty model calls. The contract left two
sub-questions open. Both were answered hermetically on 2026-08-27, and the answers are
structural rather than statistical:

| Measured | Result |
| --- | --- |
| Prose share of `terraform-style-guide/SKILL.md` | 64 of 314 lines; the rest is example HCL |
| Its prose-stated rules also stated by `agents/write/AGENTS.md` | **16 of 16** |
| Skill content the card does not carry | exactly four: aliased providers, `default_tags`, `validation` blocks, `tflint` |
| Of those four, how many are stated as instructions | **zero** — three appear only inside fenced code examples, the fourth is process tooling that cannot appear in authored HCL |
| The same comparison on `packs/vault` | **2 of 8** restated — the control case |

**This retires the second sub-question rather than answering it.** SC-002 was measured on
`variable_has_validation` and `tags_are_shared_not_ad_hoc`; both were selected from example
code, not from stated rules, and every occurrence of "tag" in the guide is inside a fenced
block. The tagging arm therefore never tested whether the Write card's minimality clause
suppresses delivered stylistic guidance, because no stylistic guidance on tagging was ever
delivered as an instruction. That hypothesis rested on a false premise and is withdrawn.

**And it explains the first.** With all sixteen rules restated by hand, removing the binding
entirely would leave every rule in force. SC-002 asks whether receiving the skill changes the
output; on this pack the answer is structurally no, whatever the model does.

### User Story 1 - The pin becomes load-bearing (Priority: P1)

A maintainer bumps the vendored guide to a new upstream digest. Today that changes what the
model receives and cannot change what it is told to do, because the Write card states all
sixteen rules itself. After this feature the card delegates: the rules arrive from the pinned
copy, and the pin governs the behaviour it is supposed to govern.

**Why this priority**: This is the defect. Everything else here is a consequence of it or a
guard on it. ADR-0004 adopts skills *as a supply chain*; a supply chain that is shadowed by a
hand-maintained duplicate is a supply chain in name only, and Principle VII names the shape —
one body of practice maintained in two places, one of them vendored and unmodifiable.

**Independent Test**: Remove the skill binding from the pack manifest and author a corpus task.
Before this feature the sixteen rules still hold because the card states them. After it, the
run refuses to start (051 made absent delivery fail-closed), and with delivery forced empty the
authored output no longer follows rules the card no longer carries. Either outcome is a change
from "identical"; today there is none.

**Acceptance Scenarios**:

1. **Given** the Write card after this feature, **When** its text is compared against the
   bound skill's stated rules, **Then** no rule is stated in both places except where the card
   records an explicit, reasoned override.
2. **Given** a rule the card overrides, **When** a reader reads the card, **Then** the card
   says what it overrides and why, so the disagreement is visible rather than resolved silently
   by precedence at runtime.
3. **Given** the bound skill fails to deliver for any reason, **When** a run starts, **Then**
   it refuses with the distinct reason 051 defined, and no run authors under a card that has
   delegated rules nobody supplied.
4. **Given** the pinned digest changes, **When** the pack is loaded, **Then** the existing
   051 re-review obligation still forces a human to read what the new bytes now say, because
   the card is now relying on them.

### User Story 2 - SC-002 can finally return a real answer (Priority: P2)

A maintainer runs the standing SC-002 harness and gets a result that means something —
either a demonstrated effect, or a recorded finding that this skill has no teachable surface
for this model. Today it can only return the artefact of the duplication.

**Why this priority**: 051's SC-002 is unmet and its row cannot currently fail, which is
ADR-0047's failure in the content plane. It depends on US1 and is worthless before it.

**Independent Test**: Run `evals/prompt-tune/sc002_skill_effect.py` on a rule that the skill
states, the card no longer restates, and the unaided model does not reliably follow. Bound and
unbound arms are now genuinely different instructions, so a delta is possible where before it
was excluded by construction.

**Acceptance Scenarios**:

1. **Given** a de-duplicated card, **When** a candidate rule is sought, **Then** the search is
   over rules the skill *states*, never rules that appear only in its example code — the
   selection error that produced the original null result.
2. **Given** the harness runs both arms, **When** the result is level, **Then** it is recorded
   as a finding about this skill and this model, and neither the threshold nor the rule is
   adjusted to manufacture a pass.
3. **Given** no qualifying rule exists even after de-duplication, **When** that is established,
   **Then** it is recorded as the outcome and SC-002 is amended to say so — not left open to
   drive further edits.

### User Story 3 - No card silently re-absorbs the practice (Priority: P3)

A contributor edits a phase card months from now and adds two style rules for convenience,
not knowing they are already in the bound skill. Nothing today would notice, and the pack
would drift back to where it started.

**Why this priority**: The terraform card did not arrive duplicated; it drifted there one
helpful edit at a time. Fixing the text without fixing the ratchet buys one release. 051 set
the precedent for this exact shape in SC-006 — "enforced, not audited by hand".

**Independent Test**: Add a rule to a phase card that its bound skill already states, and the
check fails naming both locations. Remove it and the check passes. `packs/vault` passes
throughout, unmodified, as the control that the rule is satisfiable rather than aspirational.

**Acceptance Scenarios**:

1. **Given** a card that restates a rule its bound skill states, **When** the check runs,
   **Then** it fails, naming the rule and both documents.
2. **Given** a card that overrides a rule and says so, **When** the check runs, **Then** it
   passes — an override is the sanctioned case, not an exemption from being noticed.
3. **Given** `packs/vault` unchanged, **When** the check runs, **Then** it passes, and it would
   have failed against the terraform pack before this feature.

### Edge Cases

- **The card delegates a rule and the skill stops stating it.** Upstream re-pins and drops a
  rule. The digest changes, which 051 already refuses to load past without a recorded
  re-review; this feature raises what that review is *for*, because the card now depends on
  content it does not hold.
- **The skill and the card genuinely disagree.** They already do: the guide shows
  `required_version = ">= 1.14"` while the card instructs that `>=` is not a pin. The card must
  keep its rule. A precedence rule is how the platform survives a contradiction at runtime; it
  is not a reason to leave one unstated on the page.
- **A rule is stated in the skill only as an example.** Three of the four non-duplicated items
  are exactly this. Example code is not taught practice, and must not be counted as delegated
  or as a candidate for measurement.
- **Delegating leaves a card that is nearly empty for some phase.** Judge and Plan also receive
  these skills; a card reduced to nothing is a signal the phase's own instruction was never
  more than a copy, which is worth surfacing rather than padding.
- **Re-qualification.** 051 established that phase-agent promotion is all-five-or-none and
  gates on both suites. Editing a card is a change to the instruction that was qualified, so
  this feature cannot ship its edits without re-running that gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A phase card MUST NOT state a rule that a skill bound to that phase already
  states, unless it is recorded as an override under FR-002.
- **FR-002**: Where a card's rule contradicts or narrows a bound skill's rule, the card MUST
  keep it and MUST say what it overrides and why. The known instance is version pinning.
- **FR-003**: Only rules a skill **states** count as delegated. Content appearing solely inside
  example code MUST NOT be treated as taught practice, by this feature or by SC-002 selection.
- **FR-004**: The terraform Write card MUST delegate the sixteen duplicated rules, retaining
  only overrides under FR-002 and instruction that is genuinely the platform's own.
- **FR-005**: The same comparison MUST be applied to every phase bound to a skill in every
  shipped pack, not to the terraform Write card alone.
- **FR-006**: A check MUST fail when a card restates a bound skill's stated rule, naming the
  rule and both documents. It MUST pass for a recorded override.
- **FR-007**: The check MUST pass against `packs/vault` unmodified, and MUST have failed
  against the terraform pack in its pre-feature state. A check that cannot demonstrate both is
  not evidence.
- **FR-008**: 051's SC-002 contract MUST be amended to record the withdrawal of the minimality
  hypothesis and the measured reason the original arms were invalid.
- **FR-009**: A level SC-002 result MUST remain recordable as a finding. Nothing in this
  feature may make a null outcome look like a failure to be edited away.
- **FR-010**: Affected phases MUST be re-qualified before promotion, under the all-five-or-none
  rule 051 established. No card edit ships on the strength of the eval that qualified the
  previous text.
- **FR-011**: Run records MUST continue to name which skills shaped which phase. This feature
  changes what the card says, never what the record reports.

### Key Entities

- **Stated rule**: an instruction a skill gives in prose. The unit this feature deduplicates
  against, and the unit SC-002 may select from. Distinguished from example code, which is
  neither.
- **Override**: a card rule that knowingly contradicts or narrows a bound skill's stated rule,
  carrying its reason. The one sanctioned form of overlap.
- **Rule inventory**: the enumerated stated rules of a bound skill, against which a card is
  compared. Per skill, revisited when its digest changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero rules are stated in both a phase card and a skill bound to that phase across
  every shipped pack, except overrides carrying a recorded reason. Measured, not reviewed.
- **SC-002**: Removing a skill binding changes the instruction the phase receives in a way a
  reader can point to — for at least one rule per bound skill, or a recorded finding that the
  skill has no stated rule the platform relies on.
- **SC-003**: The check fails against the terraform pack's pre-feature text and passes against
  `packs/vault` unmodified.
- **SC-004**: 051's SC-002 is either met on a rule selected from stated instruction, or amended
  to record that this skill has no teachable surface for the qualified model — with the
  measurement that establishes it. No third outcome is left open.
- **SC-005**: Every affected phase is re-qualified before promotion, and no phase ships on a
  prior qualification.
- **SC-006**: Zero platform source changes. The whole feature is pack content and gate rows.

## Assumptions

- **The rule inventory is curated per skill, not inferred by similarity.** A semantic-overlap
  detector over prose would be a large build with false positives on both sides. The
  measurement that produced this feature used an enumerated rule list checked by targeted
  matching, which is precise, cheap, reviewable, and honest about being hand-built. It is
  revisited when a digest changes — the moment 051 already forces a human to read the content.
- **Delegation is safe because 051 made absence fail-closed.** `skill_missing`, `skill_empty`
  and `digest_mismatch` each refuse the load, so a card that delegates cannot silently run
  without what it delegated. This assumption is load-bearing and is asserted, not trusted.
- **Vault is the control, not a second subject.** At 2 of 8 it is close enough to correct that
  it demonstrates the rule is satisfiable. Any residue found is in scope; a rewrite is not.
- **Judge and Plan are in scope with Write.** All three are bound to these skills, and FR-005
  applies to bindings rather than to one phase.
- **"Genuinely the platform's own" covers instruction about this platform** — precedence,
  minimality, what to do when a task names nothing, how to hand back what cannot be performed.
  None of it is Terraform style practice and none is delegated.

## Out of Scope

- Editing any vendored skill. `SKILL.md` is upstream, digest-pinned to commit `8c6573ab`, and
  the whole remedy is on this side of the seam.
- Changing 051's delivery mechanism, its precedence rule, or its refusal codes. This feature
  consumes them.
- Adopting new skills, or widening what any phase is bound to.
- Re-running the withdrawn minimality experiment.
