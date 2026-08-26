# Feature Specification: Adopted skills reach the phase that needs them

**Feature Branch**: `051-phase-skill-binding`

**Created**: 2026-08-26

**Status**: Draft

**Input**: User description: "HashiCorp has an official agent skills repo, but I want to make sure that the agents are using those skills where applicable. For instance, during the write phase, an agent could create a Terraform template. There is a HashiCorp sanctioned skill specifically for this: terraform-style-guide. This skill should be used by the writing agent any time any Terraform HCL is written. I want to make sure agents are leveraging these skills appropriately when doing so."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12 (eval / gate)** — a phase's behaviour under a skill must be expressible as rows that can lose. **R16 (sealed core, versioned seams)** — skill delivery is a pack seam, not core logic. **R4 / R13 (evidence)** — the run record must distinguish a skill that shaped a phase from one that was merely present in the pack |
| **ADRs touched** | **ADR-0004** (adopt upstream skills as a pinned, governed supply chain — this feature is the consumption half it never got). **ADR-0030** (pinned vs consulted — a skill is *executed* content, so it is pinned and must actually be executed). **ADR-0025** (registry isolation — a skill is pack content and must not become core knowledge). **ADR-0038** (the agent authors and a person merges — what the platform cannot perform is handed to the reviewer, not silently skipped). **ADR-0049** (phase instructions are executed artifacts, versioned and digest-pinned; skills join them). **ADR-0047** (a passing stub is worse than a missing one — the current state is its content-supply-chain equivalent) |
| **Evidence class** | attestation-relevant — `content_pins` at `RUN_START` currently names skills that did not reach the model |

## Clarifications

### Session 2026-08-26

- Q: Which phases should actually receive the vendored Terraform skills? (FR-012) → A: Option C — `plan`, `write` and `judge`. Plan is bound because its output is what tells Write how to proceed: a plan made without the skills can direct Write toward something the skills would not sanction. `research` and `propose` are not bound, and their instruction prose is corrected instead.
- Q: Must a phase be re-qualified before a newly bound skill takes effect, or do binding and re-qualification ship together? (FR-013) → A: Option B — they ship together in one change. Phase-agent promotion is already all-five-or-none and gates on both suites passing, so the eval run is unavoidable; the platform adds no runtime state for a binding that exists but is not yet in force.
- Q: When adopted skill content instructs an action the platform does not offer (e.g. `terraform fmt`, `terraform validate` — no registry tool exists), what governs? → A: The skill is delivered byte-exact (ADR-0004 forbids editing it) and is NOT performed or claimed; the phase instruction states that precedence. What the platform cannot satisfy is surfaced in the pull request so the reviewer knows what is left to do.
- Q: Who determines which skill recommendations the platform cannot satisfy — the pack, or the model at run time? → A: Option A — the pack declares them per skill in the manifest. A model's account of its own work is not evidence (Principle IX), and a declaration is pinned, reviewed, identical on every run, and checkable against the registry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authored Terraform follows the vendored HashiCorp style guide (Priority: P1)

A person asks Build to make a Terraform change. The write phase authors HCL. The
HashiCorp `terraform-style-guide` skill — already vendored, pinned and digest-verified in
this repository — is in the write model's context while it writes, so the output follows
vendor practice because the platform supplied that practice, not because the model happened
to have absorbed it during training.

**Why this priority**: This is the whole request, and without it every other story is
bookkeeping about content nobody reads. It is also the story that makes ADR-0004 true:
the supply chain exists to govern instruction content the agent follows, and today it
governs content the agent never receives.

**Independent Test**: Run a Terraform Build whose task requires a style-sensitive choice
the skill rules on and the base model does not reliably make. Assert the authored files
follow the skill's rule. Remove the binding and assert the same case is no longer reliably
correct — a rule that passes with the skill absent is not evidence the skill did anything.

**Acceptance Scenarios**:

1. **Given** a Terraform pack whose `write` phase is bound to `terraform-style-guide`,
   **When** the write phase authors HCL, **Then** the skill's content is present in the
   instruction the model receives for that phase.
2. **Given** a phase bound to a skill whose bytes no longer match the manifest digest,
   **When** that phase starts, **Then** the run stops with the mismatch named, and no model
   is asked to author under unverified instruction content.
3. **Given** a phase bound to no skills, **When** it runs, **Then** its behaviour is
   unchanged from today.

---

### User Story 2 - The record says which skills shaped the run (Priority: P2)

An auditor reading a run record can tell which skills were *delivered to a phase* as
opposed to which were merely present in the bound pack. Today `content_pins` records a
digest for every skill in the manifest, which reads as "this governed the run" and is not
true of any of them.

**Why this priority**: Evidence that overstates what happened is the specific liability
Principle IX names. It ranks below P1 because a correct record of nothing useful is worth
less than the behaviour itself — but it must not ship after P1, or the first correct runs
are recorded by a scheme that could not distinguish them from the incorrect ones.

**Independent Test**: Inspect the run record for a Build. Assert a skill bound to a phase
that executed is distinguishable from a skill present in the pack but bound to no phase
that ran.

**Acceptance Scenarios**:

1. **Given** a pack with a skill bound to `write` and a skill bound to no phase, **When** a
   Build runs, **Then** the record distinguishes the two.
2. **Given** a Build that stopped before the write phase, **When** the record is read,
   **Then** a skill bound only to `write` is not recorded as having shaped the run.

---

### User Story 3 - Binding a skill to a phase is a declaration, not a code change (Priority: P3)

Whoever adopts the next skill binds it to the phases it applies to by editing the pack
manifest, the same place its pin, version and digest already live. No platform code names a
skill or a phase.

**Why this priority**: ADR-0025 keeps product knowledge in packs. A binding expressed in
code would put "Terraform's style guide belongs to the write phase" inside the core, which
is the boundary that principle exists to hold. It is P3 because a hard-coded first binding
would deliver P1 and could be moved later — but it would be moved by someone who has to
notice it first.

**Independent Test**: Add a skill binding to a pack manifest with no source change and
observe the bound phase receive it.

**Acceptance Scenarios**:

1. **Given** a manifest that binds an adopted skill to a phase, **When** that phase runs,
   **Then** the skill is delivered without any platform source change.
2. **Given** a manifest that binds a skill to a phase name that does not exist, **When** the
   pack loads, **Then** loading refuses and names the unknown phase.

---

### User Story 4 - The pull request says what the platform could not do (Priority: P2)

A reviewer opening a Build's pull request can see which recommendations from the vendored
skills this platform is not able to carry out — `terraform fmt` and `terraform validate` have
no registry tool — so the work left to a human is stated rather than left to be discovered.

**Why this priority**: It is the same move that withdrew the plan gate: a check the platform
cannot perform honestly belongs to the person who can. Without it, binding a skill that
recommends unperformable steps makes the platform quietly non-compliant with its own adopted
practice, and the reviewer has no way to know.

**Independent Test**: Open a pull request from a Build bound to a skill with declared
unsatisfiable recommendations. Assert each appears in the pull request body, and that the
text is identical across two runs of different content.

**Acceptance Scenarios**:

1. **Given** a phase bound to a skill declaring recommendations this platform cannot satisfy,
   **When** the Build opens a pull request, **Then** the body names each of them.
2. **Given** two Builds bound to the same skills, **When** both open pull requests, **Then**
   the unsatisfiable-recommendation text is identical in both — it derives from the manifest,
   not from what either model said.
3. **Given** a pack declaring an unsatisfiable recommendation that names a tool the registry
   **does** offer, **When** the pack loads, **Then** loading refuses and names the stale
   declaration.

---

### Edge Cases

- **A phase instruction claims a skill it is not bound to.** **All five** Terraform phase
  instructions — research, plan, write, judge and propose — read *"Practice is this file and
  the pinned skills `terraform-style-guide` / `terraform-style-guide-security`"*, and not one
  of them receives either. The pack's authors have already declared where these skills apply;
  the platform does not honour the declaration anywhere. A phase whose prose names a skill it
  will not be given is the defect this feature removes, and it must not be reintroducible
  silently.
- **The combined instruction and skills exceed what the model will accept.** Silent
  truncation would deliver partial practice while the record claims the whole skill.
- **A skill is bound to a phase whose model was qualified without it.** The qualified cell
  was scored against different instruction content than the one now being sent.
- **A pack declares a skill that no phase binds.** Adopted, reviewed, pinned, and inert —
  legitimate during staged adoption, and it must be visible rather than look like delivery.
- **A skill recommends a step the platform has no tool for.** The vendored style guide says
  to run `terraform fmt -recursive` and `terraform validate`; neither exists in the registry.
  Delivered with no precedence rule, the model either names tools that will be rejected or
  reports a checklist item it did not perform.
- **An upstream skill bump adds an unsatisfiable step nobody declared.** The declaration
  would then be silently incomplete — the reverse of a stale one, and not visible at load.
- **Two skills bound to one phase.** Order must be deterministic, or two runs of identical
  content produce different instructions.
- **A skill file present on disk but absent from the manifest.** Unpinned content next to
  pinned content; it must never be delivered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST deliver the content of every skill bound to a phase into the
  instruction that phase's model receives, for every phase that consults a model.
- **FR-002**: A skill's binding to a phase MUST be declared in the pack manifest, beside the
  pin, version and digest that already govern it. No platform source may name a skill.
- **FR-003**: Skill content MUST be digest-verified against the manifest at the moment it is
  delivered, on the same terms as today's load-time verification.
- **FR-004**: A bound skill that is missing, unreadable, or digest-mismatched MUST stop the
  run with the reason recorded. Delivery of unverified instruction content is never a
  fallback, and neither is proceeding without it.
- **FR-005**: The run record MUST distinguish a skill delivered to a phase that ran from a
  skill present in the bound pack but not delivered.
- **FR-006**: Delivery order for multiple skills bound to one phase MUST be deterministic
  and derived from the manifest, so identical content produces an identical instruction.
- **FR-007**: The platform MUST refuse to load a manifest binding a skill to an unknown
  phase, or binding a name no `[[skills]]` entry declares.
- **FR-008**: A skill file present in a pack but absent from the manifest MUST never be
  delivered.
- **FR-009**: When the assembled instruction cannot be delivered whole, the run MUST stop
  with the reason recorded rather than delivering a truncated skill.
- **FR-010**: Phase instruction prose MUST NOT claim practice from a skill the phase is not
  bound to, and a check MUST make a divergence between the two visible.
- **FR-011**: A phase bound to no skills MUST behave exactly as it does today.
- **FR-012**: The Terraform pack MUST bind both `terraform-style-guide` and
  `terraform-style-guide-security` to the `plan`, `write` and `judge` phases. **Plan is
  bound because its output is Write's instruction.** The paths and intent Plan names are
  what Write then works from, so a plan formed without the skills can direct Write toward
  something the skills would not sanction — and Write receiving the skills does not undo a
  direction it was told to take. Binding Plan is not about what Plan emits; it is about
  what Plan tells the next phase to do.
- **FR-012a**: The `research` and `propose` phase instructions MUST stop claiming practice
  from skills they are not bound to. Both currently read *"Practice is this file and the
  pinned skills …"*; that sentence is false today for all five phases and remains false for
  these two after FR-012.
- **FR-013**: A phase whose model cell was eval-qualified against instruction content that
  did not include a now-bound skill MUST be re-qualified in the same change that introduces
  the binding. The binding and its passing eval promote together, or neither promotes.
- **FR-013a**: The platform MUST NOT carry runtime state for a binding that exists but is
  not yet in force. A binding present in a loaded manifest is in force; there is no
  "declared but unqualified" condition for a run to interpret, and no way to ship one.

- **FR-014**: A skill step naming a capability the registry does not offer MUST NOT be
  performed or reported as performed. The phase instruction MUST state this precedence: the
  registry bounds what can be done, and adopted practice does not widen it.
- **FR-015**: The pack manifest MUST declare, per skill, the recommendations this platform
  cannot satisfy. Skill content itself is never edited or filtered — ADR-0004 requires the
  adopted bytes stay identical to upstream.
- **FR-016**: A pull request opened by a run whose phases were bound to skills carrying
  declared unsatisfiable recommendations MUST state them, so the reviewer sees what adopted
  practice remains for a person to carry out.
- **FR-017**: The platform MUST refuse to load a manifest declaring an unsatisfiable
  recommendation that names a capability the registry **does** offer. A declaration that has
  gone stale would tell a reviewer to do work the platform already did.
- **FR-018**: The text of an unsatisfiable recommendation in a pull request MUST derive from
  the manifest alone, identical across runs, and never from what a model reported.

### Key Entities

- **Skill**: adopted upstream instruction content, already carrying a name, path, upstream
  version and content digest in the pack manifest. This feature adds *where it applies*.
- **Skill binding**: the association between a skill and the phase(s) whose model should
  receive it. Declared, not inferred.
- **Phase instruction**: what a phase's model is given today — the pack's `AGENTS.md` for
  that phase. Becomes that file plus the skills bound to the phase.
- **Unsatisfiable recommendation**: a step an adopted skill recommends that this platform
  has no capability to perform. Declared in the manifest beside the skill, not inferred.
- **Content pin record**: the `RUN_START` evidence naming executed content by digest.
  Gains the ability to say *delivered to a phase that ran*.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every phase that consults a model, the instruction it receives contains
  the full content of each skill bound to it, verified byte-for-byte against the pin — 100%
  of runs, with no partial delivery.
- **SC-002**: A style rule the vendored skill states and the unaided model does not reliably
  follow is followed in authored output in at least 4 of 5 runs, and demonstrably less often
  with the binding removed. A rule the model already follows without the skill cannot serve
  as evidence.
- **SC-003**: Reading a completed run's record, an auditor can determine which skills shaped
  which phase without consulting the pack — 100% of runs.
- **SC-004**: Adding or removing a skill binding requires changes to the pack manifest only,
  with zero platform source changes.
- **SC-005**: Every failure mode in FR-004, FR-007, FR-008 and FR-009 stops the run with a
  distinct recorded reason; none proceeds silently and none is reported as another.
- **SC-006**: No phase instruction in any shipped pack names practice the phase is not bound
  to receive — enforced, not audited by hand.
- **SC-008**: Every declared unsatisfiable recommendation for a bound skill appears in the
  pull request body — 100% of runs that open one — and is byte-identical across runs.
- **SC-009**: A declaration naming a capability the registry offers fails pack loading; none
  ever reaches a pull request.
- **SC-007**: No phase ships bound to a skill whose combined instruction content has not
  passed both the phase-agents and build-agents suites — 100%, enforced by the existing
  promotion gate rather than by review.

## Assumptions

- **Skills are executed content, not consulted content.** ADR-0030 splits the two; the
  manifest already pins skills by digest, which places them on the executed side. This
  feature delivers them under that reading and does not introduce runtime fetching.
- **Delivery is per phase, not per run.** A phase that consults no model receives nothing;
  a phase bound to no skill is unchanged.
- **The existing five phases are the binding surface.** Research, plan, write, judge and
  propose are the closed set from `core/authoring/progress.py`; this feature adds no phases.
- **The instruction is assembled by the platform, not by the model.** No tool is added for a
  model to request a skill: what a phase is governed by is not the model's choice.
- **Only the already-adopted skills are in scope.** `terraform-style-guide` and
  `terraform-style-guide-security` are vendored and reviewed. Adopting more from
  `hashicorp/agent-skills` is the existing ADR-0004 intake path and is out of scope here.
- **The Vault pack is in scope for the mechanism, not for new bindings.** Whatever bindings
  it declares today (none) continue to work.
- **Phase-agent promotion is all-five-or-none.** The existing gate requires all five phase
  files and passes of both suites, so correcting `research` and `propose` prose (FR-012a)
  forces a full promotion regardless of how many phases are bound. This is why binding and
  re-qualification shipping together costs nothing extra.
- **No change to how phase instructions themselves are pinned.** ADR-0049's `[[agents]]`
  pins keep their current shape.
