# Feature Specification: Product-and-phase Build instructions

**Feature Branch**: `spec/049-phase-product-prompts`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: Build today uses one generic instruction shape across Research,
Plan, Write, Judge, and Propose. Results suffer because a Terraform research step is not a
Vault research step, and a write step is not a plan step. Each Build phase needs its own
instruction, and that instruction must be specific to the HashiCorp product the change is
for (Terraform, Vault, and the same pattern for further products). The instructions must
encode current published practice for designing and implementing that product in that
phase. Each instruction is then refined on its own against that phase's success measure,
and then the five instructions for one product are refined together against a full Build
for that product.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12 (eval / gate)** — phase×product instructions are prompts; they promote only through eval gates that can fail (Principle VIII). **R7 (fail-closed)** — a Build that cannot name a complete instruction set for its product must stop rather than run on another product's instruction or an unnamed generic. **R4 / R13 (evidence)** — which instruction a phase used must be joinable to the run (identity and version), so a PR is reconstructable as "what the run was told." **R1 (product-blind core)** — new products are new packs; the core does not gain product names |
| **ADRs touched** | **ADR-0004** (pack content is pinned, provenance-bearing, injection-reviewed). **ADR-0022** (competence is pack × model, not "the model is good"). **ADR-0039** (per-role bindings; Research/Plan/Write/Judge/Propose are different roles' work). **ADR-0047** (a gate row that cannot fail is not a gate). **ADR-0030** (executed vs consulted — what the agent executes is pinned; it does not fetch a fresh instruction mid-run). **ADR-0068** (product impact is measured by the product — Terraform and Vault already have distinct oracles; their instructions must not be interchangeable). **ADR-0034** (the portal remains a thin client; it does not hold or compose these instructions). Consumes 013 (packs), 038/041 (authoring), 047 (phase spine) |
| **Evidence class** | **attestation-relevant.** Opening a PR asserts the change passed gated phases; the record must name which product-phase instruction each phase ran under |
| **Sealed core** | **Pack content is the extension.** Wiring "this phase uses this pack's instruction" into the existing Build path may touch dispatch/adapter glue. It MUST NOT put Terraform or Vault knowledge in `src/core`, MUST NOT add a second authorization path, and MUST NOT fetch instruction text from the public internet during a run. A new library to *refine* instructions is a planning/ADR question, not a runtime product capability |

## What is actually wrong

**Build phases share a generic steer.** Research, Plan, Write, Judge, and Propose are
already distinct phases (047). The model is not given a distinct, reviewed instruction for
each. A write step is asked to author files; a research step is asked to look; the
difference is mostly which tools are permitted, not what good work in that phase *is*.

**Product knowledge lives in packs and is not used as phase instructions.** Terraform and
Vault are different products with different published practice, different hazards, and
different oracles. A Terraform research instruction that talks about Vault policies, or a
Vault write instruction that talks about `aws_instance` resources, is the wrong product
steering the wrong work. Today's write loop has already shown the cost: later files invent
a second architecture because nothing in the instruction set is a Terraform-shaped
contract for that phase.

**"Current best practice" is not a thing a running Build should look up.** If a run
fetched the public web to refresh its own instructions, air-gapped and restricted
deployments could not make the same claim, the instruction would not be pinned, and
Principle VIII's "what the agent executes is pinned" would be false. The research of
published practice belongs to *authoring* the instruction, with provenance, the same way
skills are adopted.

**Refinement that cannot fail is theatre.** Individually polishing five texts, then
polishing them together, only matters if each pass has a measure that can lose and if
promotion is blocked when it loses. That is already this platform's eval rule for prompts.

## Clarifications

### Session 2026-08-19

- Q: What form is each phase×product instruction? → A: **One `AGENTS.md` file per phase
  per product.** Not a single combined prompt, not a field in `pack.toml`, and not a
  substitute of an existing skill file. Terraform Research is its own `AGENTS.md`;
  Terraform Write is another; Vault Research is another — ten files for the two packs
  this feature ships, each a complete instruction for that phase of that product.
- Q: Is that the same `AGENTS.md` this repository already has at the root? → A: **No.**
  The root file instructs people and coding agents working *on this platform*. Pack
  `AGENTS.md` files instruct the Build agent *for one product phase*. They share a
  filename convention, not a file. A Build MUST NOT read the repository-root contributor
  file as a phase instruction, and a missing pack `AGENTS.md` MUST NOT fall back to it.
- Q: Can an existing pack `SKILL.md` stand in for a missing phase `AGENTS.md`? → A:
  **No.** Skills remain skills (ADR-0004). A skill is not a phase instruction. Absence
  of the phase file is FR-004 (fail closed).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A Terraform Build is steered per phase (Priority: P1)

Someone asks Build for Terraform work on an owned repository. Research is steered as
Terraform research, Plan as Terraform planning, Write as Terraform authoring, Judge as
Terraform review, Propose as Terraform proposal copy — five distinct instructions, all
Terraform, none borrowed from Vault or from a nameless default.

**Why this priority**: This is the current Build path's product. If Terraform is not
covered, the feature has not started.

**Independent Test**: Start a Terraform-shaped Build. For each of the five phases, the
durable record names that phase's Terraform `AGENTS.md`, distinct from the other four
and distinct from Vault's `AGENTS.md` for the same phase. A missing Terraform `AGENTS.md`
for a phase stops the run at that phase with a user-safe reason and does not open a PR.

**Acceptance Scenarios**:

1. **Given** a Build bound to the Terraform product, **When** Research runs, **Then** it
   is steered by the Terraform Research instruction, not by Plan, Write, Judge, Propose, or
   any Vault instruction.
2. **Given** the same Build, **When** each later phase runs, **Then** that phase is steered
   by that phase's Terraform instruction.
3. **Given** a Terraform pack that omits the Write `AGENTS.md`, **When** a Terraform Build
   reaches Write, **Then** the run stops fail-closed and no pull request is opened.

---

### User Story 2 — A Vault Build is steered per phase (Priority: P1)

The same matrix for Vault: five Vault-specific instructions, never Terraform's, never a
generic substitute.

**Why this priority**: Two packs are how this platform proves packs are independent
(013). One product's instructions would leave the "per product" claim untested.

**Independent Test**: Same as US1, with Vault as the bound product. Cross-check that
Vault Research is not the Terraform Research text.

**Acceptance Scenarios**:

1. **Given** a Build bound to Vault, **When** any phase runs, **Then** it is steered by
   that phase's Vault instruction.
2. **Given** both packs present, **When** a reviewer compares Terraform Research and Vault
   Research, **Then** they are different texts with different product practice, not a
   renamed copy.

---

### User Story 3 — Instructions encode current published practice, with provenance (Priority: P2)

Each phase×product instruction tells the model what good work looks like for *that*
product in *that* phase: design, safety, layout, and known anti-patterns, drawn from
published practice as of authorship — not from folklore and not from a live web fetch
during the Build.

**Why this priority**: Distinct empty templates would satisfy US1/US2 without improving
results. The content is the point; provenance is how a reviewer can challenge it.

**Independent Test**: For each shipped instruction, a reviewer can read a provenance
record naming the sources consulted and the date of authorship. The instruction text
itself contains product-specific practice (not only "be careful" or "follow the plan").
A Build in progress does not open a public-internet session to refresh that text.

**Acceptance Scenarios**:

1. **Given** a shipped Terraform Write instruction, **When** a reviewer reads it, **Then**
   it constrains Terraform authoring specifically (modules, state, variables, secrets
   handling, and named anti-patterns), not a generic "write files" brief.
2. **Given** a shipped Vault Write instruction, **When** a reviewer reads it, **Then** it
   constrains Vault authoring specifically, and does not instruct the model to emit
   Terraform resources as the change.
3. **Given** an in-flight Build, **When** a phase starts, **Then** the instruction it
   executes is the pinned pack artifact, not a page fetched at that moment from the
   public internet.
4. **Given** the provenance record for an instruction, **When** a reviewer opens it,
   **Then** it names what was consulted and when, so a stale instruction is visible
   rather than silent.

---

### User Story 4 — Refine each instruction, then refine the five as one Build (Priority: P2)

Each phase×product instruction is refined against a measure of *that phase* that can
fail. After those individual passes, the five instructions for one product are refined
together against a measure of a *full Build* for that product that can fail. Promotion
of an instruction set requires both kinds of gate.

**Why this priority**: Authored text without a losing gate is a suggestion. Joint
refinement is what catches a Research instruction that looks good alone and poisons
Write.

**Independent Test**: For one product, show a phase-level eval that can fail that
phase's instruction, and a full-Build eval that can fail the five together. An
instruction set that loses either gate is not the set a production Build executes.

**Acceptance Scenarios**:

1. **Given** a Terraform Write instruction under individual refinement, **When** the
   phase-level measure fails, **Then** that instruction is not promoted for production
   Builds.
2. **Given** five Terraform instructions that each passed individually, **When** the
   full-Build measure for Terraform fails, **Then** the set is not promoted — individual
   passes are not sufficient.
3. **Given** the same two-pass refinement for Vault, **When** either gate fails, **Then**
   Vault Builds do not execute the losing set.
4. **Given** a production Build, **When** it runs, **Then** it executes the promoted
   pinned set; it does not refine instructions as part of serving that person.

---

### Edge Cases

- A Build whose product cannot be determined does not pick Terraform as a default and
  does not concatenate every pack's instructions. It stops with a user-safe reason.
- A pack that ships four of five phase `AGENTS.md` files is incomplete. The missing phase
  fails closed; later phases do not run. A `SKILL.md` or the repository-root contributor
  `AGENTS.md` is not a stand-in.
- Ask is unchanged. These instructions are Build (authoring) only. An Ask about Terraform
  still uses the answering path, not the Terraform Research Build instruction.
- Judge remains a distinct role from Write (different cell). A product-specific Judge
  instruction does not license the writer to judge itself.
- Restricted or air-gapped deployments execute the same pinned instructions as connected
  ones. They do not skip product-specific steering because they cannot reach the public
  web at run time.
- Updating published practice is a new revision of the pack artifact (provenance,
  review, eval), not a hot patch inside a running allocation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each capability pack that participates in Build MUST ship one `AGENTS.md`
  for each of the five Build phases: Research, Plan, Write, Judge, Propose. Each file is
  the complete instruction for that phase of that product — not a fragment merged with
  another phase's file at run time.
- **FR-002**: A Build bound to a product MUST execute that product's instruction for the
  current phase, and MUST NOT execute another product's instruction for any phase.
- **FR-003**: Phase instructions for the same product MUST be distinct from each other
  (Research is not Write with the tools changed).
- **FR-004**: A phase MUST NOT start if its product-phase instruction is missing,
  empty, or unpromoted. The run stops fail-closed; no pull request opens.
- **FR-005**: The platform core MUST remain product-blind: Terraform and Vault knowledge
  lives in those packs. Adding Consul (or any further HashiCorp product) is a new pack
  that ships the same five phase `AGENTS.md` files, not a core change.
- **FR-006**: Each shipped instruction MUST encode current published practice for that
  product in that phase (design, implementation, safety, and named anti-patterns), not
  only a role label.
- **FR-007**: Each shipped instruction MUST carry a provenance record of sources
  consulted and authorship date, reviewable like other pack content (ADR-0004).
- **FR-008**: A running Build MUST NOT fetch instruction text or "best practice" pages
  from the public internet. What it executes is the pinned artifact.
- **FR-009**: Each phase×product instruction MUST be refinable against a phase-level
  measure that can fail (ADR-0047). Losing that measure blocks promotion of that
  instruction.
- **FR-010**: For each product, the five instructions MUST be jointly refinable against
  a full-Build measure that can fail. Losing that measure blocks promotion of the set
  even if every individual instruction had passed.
- **FR-011**: Production Builds MUST execute only promoted, pinned instruction sets.
  Refinement is authoring and promotion work, never part of serving a person's Build.
- **FR-012**: The durable run record MUST name which product-phase instruction (identity
  and version) each executed phase used, joinable on the run's correlation ID.
- **FR-013**: The portal MUST NOT compose, store, or select these instructions. It
  remains a thin client of the platform (ADR-0034).
- **FR-014**: Ask MUST NOT start using Build phase instructions. Never-acts is unchanged
  (ADR-0039).
- **FR-015**: A product-specific Judge instruction MUST NOT collapse Judge into Write:
  the judging role remains a different binding than the writing role.
- **FR-016**: A phase instruction MUST be the pack's `AGENTS.md` for that phase. The
  platform MUST NOT treat a pack skill, `pack.toml` prose, or this repository's
  contributor `AGENTS.md` as that instruction.

### Key Entities

- **Phase `AGENTS.md`**: The pinned file that steers one Build phase for one product.
  One file per phase per pack. Identity, version, phase name, product (pack),
  provenance, promotion state. Distinct from this repository's contributor `AGENTS.md`.
- **Instruction set**: The five phase instructions for one product, promoted together
  for production Builds after both individual and joint measures pass.
- **Provenance record**: What was consulted to author or revise an instruction, and
  when. Not the live web at run time.
- **Phase measure / Build measure**: Eval suites that can fail. Phase measure scores
  one instruction; Build measure scores the five as a pipeline for that product.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every product pack this feature ships, a reviewer can point at five
  distinct `AGENTS.md` files and name which phase each belongs to without reading the
  path alone (the body must differ by phase).
- **SC-002**: A Terraform Build never executes a Vault phase instruction, and a Vault
  Build never executes a Terraform phase instruction — checked as a property, not as a
  one-off demo.
- **SC-003**: 100% of Builds that lack a promoted instruction for the phase they are in
  stop without opening a pull request.
- **SC-004**: Each shipped instruction set has lost its phase-level measure at least
  once in the suite that guards it (the suite is capable of failing), and has lost its
  full-Build measure at least once in the suite that guards the set.
- **SC-005**: Connected, restricted, and air-gapped profiles execute the same pinned
  instructions; none of them require a public-internet fetch to start a phase.
- **SC-006**: After promotion, a full Terraform Build and a full Vault Build each show
  (in eval, not in a unit test) a higher rate of coherent, product-correct proposals
  than the generic pre-feature steer, on the same tasks the suites already use to
  score authoring.

## Assumptions

- **Products in this feature**: Terraform and Vault — the two packs that exist. Further
  HashiCorp products (Consul, Nomad, Packer, Boundary, and others) follow FR-005: a new
  pack ships the same five phase `AGENTS.md` files. They are not authored in this feature.
- **Product binding**: A Build is already bound to authoring work that implies a
  product (047 is Terraform-shaped; 042 is Vault-shaped). This feature does not invent
  a new "pick your product" control. If binding is ambiguous, FR-004's fail-closed path
  applies rather than a default product.
- **Published practice is authored, then pinned**: Maintainers (and the specified
  refinement passes) consult current public product documentation and style guidance
  *when writing or revising* an instruction. The Build does not.
- **Two-pass refinement is in scope**: Individual then joint, per product, with gates
  that can fail. The requester named specific methods for those two passes; planning
  must use those named methods rather than a silent substitute, and must justify any
  new dependency those methods require. The methods are not runtime behaviour.
- **Evals, not tests**: Refinement and SC-006 are statistical evals (live or recorded
  according to existing eval-lane rules). Hermetic tests assert binding, fail-closed
  omission, product isolation, pinning, and record-keeping — never that a model "wrote
  good Terraform."
- **No portal or Ask change** beyond not leaking instruction composition into the
  browser.

## Out of scope

- Changing the five-phase spine (047).
- Letting Ask open pull requests or use Build instructions.
- Live retrieval of vendor documentation during a Build to "stay current."
- A person-editable prompt box on the portal for these instructions.
- Weakening Judge, plan-as-gate, or ownership checks in order to raise allow-rate.
- Authoring packs for HashiCorp products that do not yet have a pack.
- Replacing or merging this repository's contributor `AGENTS.md` with pack phase files.
