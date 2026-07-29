# Feature Specification: Capability Packs and Eval Gates

**Feature Branch**: `spec/013-capability-packs`

**Path**: `specs/013-capability-packs/spec.md`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "Capability packs and the eval gates that promote them. The platform governs runs end to end and knows nothing about any product — every definition in the enclave is a fixture named `planner` doing `echo`. A pack is the unit of product knowledge: tools with risk classes, skills, pack hooks, workflows, and evals for one managed product. New products are new packs; the core does not change. This also brings Principle VIII online for the first time — eval-gated promotion is currently a principle with no machinery, and its absence blocks portal answering."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12** (lean by default — a pack must not require a new operated component). R5 / R11 (total interception — every pack tool is a registered, hook-wrapped call, and a pack is the most tempting place to add a shortcut). R2 / R3 (per-task authority — a pack's tools are bounded by the same ceiling machinery 010 built, and a pack cannot widen it). R4 / R10 / R13 (evidence — provenance-at-read, and the distinction between a model gate and a human approval). |
| **ADRs touched** | **ADR-0004** (skills as a pinned, governed supply chain — built), **ADR-0022** (Qualified Model Matrix — built), **ADR-0030** (executed vs consulted, provenance-at-read — built), **ADR-0039** (per-role bindings over pack × model × role cells — the thing portal answering waits on), **ADR-0045** (competency tiers), ADR-0023 (validated designs — **deferred by clarification; recorded as owed**), **ADR-0031** (retrieval telemetry as the authoring backlog), ADR-0009 (the lifecycle stage where that backlog is reviewed). |
| **Evidence class** | **Attestation-relevant, and newly so.** Everything prior evidenced *what a run did*. This evidences *what the run was told* — which skill version, which model cell, which guidance as published at that moment. An attestation that cannot name its inputs is an attestation about a system nobody can reconstruct. |

## Clarifications

### Session 2026-07-29

- Q: How many packs does this feature ship, and for which product? → A: ~~**Two — Vault and Nomad**~~ — **superseded by the question below**, which found the upstream skills source. Left standing rather than edited, per Principle X. Original answer: **Two — Vault and Nomad.**
  *(Both already run in the enclave, so neither needs a new operated component. Two rather than one because FR-004's real claim is that packs are independent of each other and of the core, and with a single pack there is nothing to be independent OF — the property would be argued rather than demonstrated. Two also surfaces the collision the edge cases name: what happens when two packs declare the same tool name. The cost is real and is content work, which is the slow part of this feature.)*
- Q: Upstream skills exist for Terraform and Packer, not Vault or Nomad. Which two packs? → A: **Terraform and Vault** — one adopted, one authored.
  *(Supersedes the Vault-and-Nomad answer above, on evidence that answer did not have: ADR-0004 says skills are ADOPTED from upstream with original content only for genuine gaps, and the upstream source turns out to exist — [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills), MPL-2.0, in Anthropic's open Agent Skills format — covering Terraform and Packer, with Vault and Nomad listed as future products. Two packs of authored-only content would have left ADR-0004's supply chain with no subject: no real provenance to check, no real upstream version to pin, nothing genuine to run an injection-lens review over. **The pair now proves both halves.** Terraform exercises adoption against a real upstream; Vault runs in the enclave, so its tools are callable end to end and its skills are the "genuine gap" ADR-0004 permits authoring for. The cost is stated rather than hidden: Terraform is not in the enclave, so that pack's TOOL layer stays fixture-backed, and the tool half is the one Principle II cares about.)*
- Q: Do the eval gates run against a real model, or against recorded fixtures? → A: **Fixtures in the merge-blocking lane; real models behind a marker.**
  *(The gate machinery, the matrix, the promotion rules, and the refusals are all real and all blocking. What they score in the fast lane is a recorded fixture, and a separate marked lane scores a live model — the same shape as the enclave lane today. A merge-blocking gate carrying a provider dependency and non-determinism fails for reasons unrelated to the change under review, and a gate that fails for unrelated reasons is one people learn to re-run rather than read. **The honest cost, stated because it is the thing to watch: a cell qualified only against a fixture is qualified against a recording.** The marked lane is what makes a cell mean something, and the contract must record which cells have actually been through it.)*
- Q: Are validated-design corpora and the deviation register (US6) in this feature? → A: **Deferred to a follow-on.**
  *(US1–US5 are coherent without it. US6 needs a corpus, a retrieval path, and precedence resolution — the largest single dependency here, in a feature that already brings Principle VIII online for the first time. What it leaves unbuilt is ADR-0023: "silent deviation is prohibited" stays a rule nothing enforces, and that is recorded as an owed gate rather than quietly dropped. The corpus question is already settled from 012's research (HashiCorp Validated Patterns), so the follow-on starts from a known source.)*

- Q: Report fidelity is a named blocking eval gate, but `RunReport` (ADR-0018) is unbuilt. What should 013 do with it? → A: **Record it owed; build the other four.**
  *(Must-deny, must-decline, citation accuracy, and estate-state fixtures all have subjects and all ship blocking. Report fidelity does not: nothing in `src/` is a typed report compiled from run records, so a gate over it would be asserting something about a thing that does not exist. ADR-0047's rule applies exactly — absent or an explicit skip citing its deferring record, never a passing stub — so it is recorded as owed against ADR-0018 rather than satisfied by asserting something weaker under its name. The cost is stated: the constitution's eval-gate row is still partially owed after the feature whose job was to close it, and the record must say so rather than reading as complete.)*
- Q: The Vault skills are authored here because upstream has none. Where do they end up? → A: **Authored in the upstream format, and intended for contribution back to `hashicorp/agent-skills`.**
  *(Dan's intent, recorded during this session. It is a constraint on authoring rather than a deliverable of this feature: the Vault skills are written in the same open Agent Skills format the upstream repository uses, so contributing them is a pull request rather than a rewrite. Cheap to honour now, expensive to retrofit — and it means this platform's "genuine gap" authoring under ADR-0004 is a temporary state by design, closing the loop that ADR says it wants: adopt what upstream ships, and migrate onto it as it matures.)*

- Q: Which roles does 013 qualify cells for? → A: **All five** — ask, plan, write, judge, summarize.
  *(The complete matrix, so any definition can be fully bound and nothing downstream waits on a second qualification pass. Two consequences, both stated rather than absorbed. **`write` means qualifying a model to make changes**, and in the blocking lane that qualification is against a fixture — so the marked live lane matters more for `write` than for any other role, and SC-013's per-cell record is what keeps the difference visible. **`judge` makes the regress binding**: FR-012 requires eval-time judges to be eval-promoted artifacts, so something must qualify the first one, and that is no longer a question this feature can carry forward unresolved. It is architecture, so it is planning's to decide rather than this session's — but it is now a blocker rather than a note, and FR-012a says so.)*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A pack makes the platform competent at one product (Priority: P1)

An operator installs a capability pack. The platform gains that product's tools — each with
a declared risk class — and an agent can be defined against them. Nothing in the core
changed to make this possible.

**Why this priority**: It is the feature. Everything else here governs packs; this is the
thing being governed, and without it the rest has no subject.

**Independent Test**: Load a pack, start a run whose definition names its tools, and observe
the tools reached through the same hook pipeline every other tool uses — then confirm no
core module names the product.

**Acceptance Scenarios**:

1. **Given** a pack manifest declaring tools, skills, and evals, **When** it is loaded,
   **Then** its tools appear in the one governed registry with their risk classes intact.
2. **Given** a loaded pack, **When** an agent calls one of its tools, **Then** the call
   passes the same pre- and post-execution hooks as any other tool, and a bypass is not
   available.
3. **Given** a second pack for a different product, **When** it is loaded alongside the
   first, **Then** neither pack's tools are reachable from a definition that does not name
   that pack.
4. **Given** any pack, **When** the core is inspected, **Then** no core module references
   the product by name. **New products are new packs; the core does not change.**

---

### User Story 2 - A definition cannot pin what has not been qualified (Priority: P1)

An author writes an agent definition pinning a model for each role. The platform accepts
only combinations that evaluation has demonstrated, and refuses the rest — including the
tempting case where a newer model is obviously better.

**Why this priority**: This is Principle VIII's central rule and the specific thing
portal answering is blocked on. It shares P1 because a pack whose models are unqualified is
a pack that has not actually been governed.

**Independent Test**: Pin a qualified cell and start a run; pin an unqualified one and
watch the definition be refused before anything executes.

**Acceptance Scenarios**:

1. **Given** a Qualified Model Matrix with a green (pack × model × role) cell, **When** a
   definition pins it, **Then** the definition is accepted.
2. **Given** a cell that has not passed evaluation, **When** a definition pins it, **Then**
   the definition is refused, naming the cell — at definition time, not at run time.
3. **Given** a definition whose pinned model is unavailable at run time, **When** the run
   starts, **Then** it falls back only to another **qualified** cell and records the
   fallback, or **stops with the reason recorded** — never to an unqualified model, and
   never silently.
4. **Given** a model version bump, **When** it is proposed, **Then** it promotes only
   through the eval gates. There is no auto-tracking of "latest".

---

### User Story 3 - An upstream skill bump is a reviewed change (Priority: P2)

Upstream publishes a new version of a skill the platform adopts. It does not take effect
until someone has checked where it came from, read it for content that tries to redirect the
agent, and run the evals.

**Why this priority**: ADR-0004's supply-chain rule, and the one place a content change can
alter production behaviour without any code changing. P2 because it needs packs to exist
before it has anything to govern.

**Independent Test**: Propose a skill bump; confirm it cannot promote without all three
checks, and that a skill carrying an injection attempt is caught.

**Acceptance Scenarios**:

1. **Given** an adopted skill pinned to a version, **When** upstream publishes a newer one,
   **Then** nothing changes until the bump is promoted deliberately.
2. **Given** a proposed bump, **When** it is promoted, **Then** provenance is checked, the
   content passes injection-lens review, and the evals pass — all three, or it does not
   promote.
3. **Given** a skill whose content attempts to redirect the agent's behaviour or exfiltrate
   context, **When** it is reviewed, **Then** it is refused and the refusal is recorded.
4. **Given** an overlay authored here on top of an adopted baseline, **When** the baseline
   is bumped, **Then** the overlay's relationship to it stays explicit rather than being
   silently merged.

---

### User Story 4 - What the agent consulted is part of the record (Priority: P2)

An agent reads reference guidance while designing something. Later, someone asks what it
was working from. The answer is the guidance **as published at that moment**, not as it
stands today.

**Why this priority**: ADR-0030's provenance-at-read, and the half of attestation the
platform does not yet have. P2 because it needs something worth consulting, which packs
supply.

**Independent Test**: Run an agent that consults guidance, change the guidance upstream,
and confirm the run record still names what was actually read.

**Acceptance Scenarios**:

1. **Given** an agent consulting reference guidance, **When** it reads, **Then** the URL,
   timestamp, and content hash are archived with the run record.
2. **Given** guidance that has changed since a run, **When** the run is attested, **Then**
   the attestation cites what was read, not what is current.
3. **Given** an executed artifact (skill, prompt, policy, model, pack code), **When** a run
   uses it, **Then** it was pinned — the executed/consulted distinction holds in both
   directions.

---

### User Story 5 - A definition's tier bounds what it may compose (Priority: P2)

An author pins a competency tier. A lower-tier definition can follow paved paths and nothing
else; a higher-tier one may compose freely. What changes is what the *definition* is allowed
to do, not what the person asking happens to request.

**Why this priority**: ADR-0045, and the mechanism that makes capability least-privileged
the way credentials already are. P2 because it is meaningful only once there are skills and
workflows to tier.

**Independent Test**: Give two definitions different tiers over the same pack; confirm the
lower one is confined to golden paths and that the bound is a property of the definition.

**Acceptance Scenarios**:

1. **Given** a definition pinned to a lower tier, **When** it runs, **Then** it may use only
   fully-paved workflows, and an attempt to compose beyond them is refused.
2. **Given** a definition pinned to a higher tier, **When** it runs, **Then** it may
   assemble and deviate within its other bounds.
3. **Given** any request, **When** it asks for behaviour above the definition's tier,
   **Then** the tier wins. **The tier is a property of the definition, not the request.**
4. **Given** a definition, **When** it is reviewed, **Then** its tier is visible and
   reviewable like any other part of it.

---

### Edge Cases

- **Two packs declaring the same tool name.** Which wins, and does a definition naming that
  tool become ambiguous?
- **A pack whose evals pass but whose tools reference a product that is unreachable.** Green
  gates over a capability that cannot run.
- **A matrix cell qualified for one role and not another.** The same model, permitted to
  `summarize` and not to `write`.
- **The judge model itself.** Eval-time judges are pinned, eval-promoted artifacts — so what
  qualifies the first judge, and does that reasoning terminate?
- **A skill bump that passes evals but changes behaviour in a way the evals do not cover.**
  Passing is not the same as unchanged.
- **A pack removed while a definition still pins it.** Does the definition refuse, or does
  the run?
- **Guidance that is unreachable at read time.** Consulted artifacts are fetched fresh, and
  fresh sometimes means absent.

## Requirements *(mandatory)*

### Functional Requirements

**Packs**

- **FR-001**: A capability pack MUST be a declared manifest of tools (each with a risk class
  from `read | write | destructive | secret-touching`), skills, pack hooks, workflows, and
  evals, for one managed product.
- **FR-002**: Loading a pack MUST register its tools in the one governed registry, with
  their risk classes preserved.
- **FR-003**: Every pack tool MUST be reached through the same hook-wrapped pipeline as any
  other tool. **No pack may introduce a path that bypasses it**, and this MUST be asserted
  structurally rather than by review.
- **FR-004**: Adding a product MUST NOT require a change to any core module. No core module
  may name a product.
- **FR-005**: A definition MUST reach only the packs it names, and only the tools within
  them that its ceiling already permits. **A pack MUST NOT widen a ceiling.**
- **FR-006**: Transport is a tool property: MCP where a mature server exists, native
  otherwise. Authoring an MCP server MUST NOT be required merely for protocol uniformity.
- **FR-007**: A pack MUST NOT require a new operated component (Principle VI). If one is
  genuinely needed, that is an ADR, not a pack.

**The Qualified Model Matrix**

- **FR-008**: The platform MUST maintain a matrix of eval-qualified (pack × model × role)
  cells, where role is the closed vocabulary `ask | plan | write | judge | summarize`.
- **FR-008a**: This feature MUST qualify cells for **all five roles**, so a definition can
  be fully bound without a second qualification pass. Each role's suite MUST match what the
  constitution names for it: `ask` reuses the guidance and estate-query classes; `plan`
  scores decomposition, tool selection, and risk identification; `write` runs golden-task
  correctness; `judge` measures agreement with human-labeled verdicts, calibration, and
  deny-rate stability.
- **FR-009**: A definition's binding map MUST reference only qualified cells. Pinning an
  unqualified cell MUST be refused **at definition time**, naming the cell.
- **FR-010**: At run time, fallback MUST occur only to another qualified cell and MUST be
  recorded; otherwise the run **stops with the reason recorded**. Falling back to an
  unqualified model MUST be impossible, and stopping silently MUST NOT be.
- **FR-011**: Model version bumps MUST promote through the eval gates. Auto-tracking of
  "latest" MUST NOT exist anywhere.
- **FR-012**: Eval-time judge models MUST themselves be pinned, eval-promoted artifacts. A
  judge that auto-tracked would be an ungated input to every gate.
- **FR-012a**: **The regress in FR-012 MUST be resolved before any cell is qualified**, and
  the resolution MUST be recorded. Qualifying `judge` means a judge scored the judge suite;
  what qualified *that* judge is the question, and it does not answer itself. The spec does
  not choose — this is architecture and belongs to planning — but the options are bounded
  and worth naming so planning starts informed: a **human-labeled seed set** that qualifies
  the first judge without a model in the loop; an **externally attested** judge accepted as
  a root of trust and recorded as such; or a **declared floor** where one judge is qualified
  by fiat, named in the record, and everything else chains from it. What is NOT acceptable
  is the regress being resolved implicitly by whichever judge happened to run first.

**Eval gates**

- **FR-013**: The following MUST be blocking for packs, prompts, models, and policies:
  must-deny safety suites; must-decline scope suites; citation accuracy and
  refusal-to-confabulate; estate-state fixtures.
- **FR-013a**: **Report fidelity is NOT built here and MUST be recorded as owed**, citing
  ADR-0018. `RunReport` does not exist, so a gate over it would assert something about a
  thing that is not there. Per ADR-0047 it is absent or an explicit skip naming its
  deferring record — never a passing stub, and never satisfied by asserting a weaker
  property under its name.
- **FR-014**: A gate that cannot run MUST report failure. It MUST NOT skip, and MUST NOT
  report a pass.
- **FR-015**: A model verdict MAY gate a step but MUST NEVER satisfy an approval requirement
  that policy assigns to a human, and the audit trail MUST distinguish the two.

**Skills as a supply chain**

- **FR-016**: Skills MUST be pinned to a version and MUST NOT auto-track.
- **FR-017**: Promoting a skill bump MUST require all three of: a provenance check, an
  injection-lens review, and a passing eval run. Any one absent MUST block promotion.
- **FR-018**: Content that attempts to redirect the agent's behaviour or exfiltrate context
  MUST be refused, and the refusal recorded.
- **FR-019**: Overlays authored here MUST stay distinguishable from the adopted baseline
  they layer on.

**Executed versus consulted**

- **FR-020**: Executed artifacts — skills, prompts, policies, models, pack code — MUST be
  pinned.
- **FR-021**: Consulted artifacts — reference guidance, validated designs — MUST be fetched
  fresh, with **URL, timestamp, and content hash archived with the run record**.
- **FR-022**: An attestation MUST cite consulted guidance as published at the moment of the
  decision, not as it stands at attestation time.

**Tiers and telemetry**

- **FR-023**: A definition MUST pin a competency tier, and the tier MUST bound what it may
  compose. The tier is a property of the **definition**, never of the request.
- **FR-026**: Retrieval targets MUST be recorded in aggregate, so what the agent had to look
  up — and how often — is available as the skill-authoring backlog.

**Scope of this feature**

- **FR-027**: This feature MUST ship **two** capability packs — **Terraform and Vault** —
  chosen so that each proves a different half of ADR-0004.
- **FR-027a**: The **Terraform** pack's skills MUST be *adopted* from
  [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) (MPL-2.0), pinned to
  a commit, with provenance recorded and an injection-lens review performed. This is the
  pack that gives the supply chain a real subject.
- **FR-027b**: The **Vault** pack's skills MUST be *authored here*, as the "genuine gap"
  ADR-0004 permits — upstream covers Terraform and Packer, and lists Vault as a future
  product. Vault runs in the enclave, so this is the pack whose **tools** are exercised
  against a live product.
- **FR-027d**: The authored Vault skills MUST use the same open Agent Skills format the
  upstream repository uses, so they can be contributed back to `hashicorp/agent-skills` as
  a pull request rather than a rewrite. ADR-0004's own instruction is to adopt what upstream
  ships and migrate onto it as it matures; authoring in a divergent shape would make that
  migration a rewrite and the gap permanent.
- **FR-027c**: The record MUST state that Terraform's tool layer is fixture-backed, because
  Terraform is not deployed in the enclave. The tool half is what Principle II governs, and
  a pack whose tools were never called must not read as one whose tools were.
- **FR-028**: The eval gates MUST be real and merge-blocking, scoring **recorded fixtures**
  in the hermetic lane. A separately marked lane MUST score a **live model**, and the
  conformance contract MUST record which cells have been through it. A cell qualified only
  against a fixture is qualified against a recording, and the record must not let that read
  as more than it is.
- **FR-029**: Validated-design corpora, guidance precedence, and the deviation register are
  **out of scope** and MUST be recorded as an owed gate row rather than dropped — ADR-0023
  stays unbuilt after this feature, and "silent deviation is prohibited" stays a rule
  nothing enforces.

### Key Entities

- **Capability pack**: the unit of product knowledge. Tools with risk classes, skills, pack
  hooks, workflows, evals. Named by a definition; never widening what that definition may
  already do.
- **Qualified Model Matrix cell**: (pack × model × role), green only by demonstrated
  evaluation. The only thing a binding map may reference.
- **Binding map**: a definition's `ask | plan | write | judge | summarize` → model mapping,
  each entry a qualified cell.
- **Competency tier**: what a definition may compose. Lower tiers are paved paths only.
- **Skill pin**: an adopted upstream skill at a fixed version, with provenance and review
  state.
- **Consulted-artifact record**: URL, timestamp, content hash — what was read, when, and
  exactly what it said.
- **Deviation register**: departures from a validated baseline, each with its reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least one real capability pack is loadable, and its tools are callable by
  an agent through the ordinary hook pipeline.
- **SC-002**: Zero core modules name any product. Adding a pack changes no core file.
- **SC-003**: A definition pinning an unqualified cell is refused before anything executes,
  and the refusal names the cell.
- **SC-004**: Zero paths exist by which a run reaches an unqualified model — including
  fallback, including when the pinned model is unavailable.
- **SC-005**: The four eval gates this feature builds — must-deny, must-decline, citation
  accuracy, estate-state — run and block. Report fidelity is absent by decision and points
  at FR-013a; it is the one the constitution names that this feature does not ship, and
  SC-011 states that outcome.
- **SC-005a**: **A gate that cannot run reports failure rather than absence.** A suite whose
  fixtures are missing, whose provider key is absent in the live lane, or whose pack cannot
  be read must raise — never skip, never return an empty result set, never pass. This is
  FR-014 and it is the property that stops a broken gate from reading green.
- **SC-006**: A skill bump missing any one of provenance, injection-lens review, or a
  passing eval cannot promote.
- **SC-007**: A skill containing an injection attempt is refused, and the refusal is in the
  record.
- **SC-008**: For any run that consulted guidance, the run record names the URL, timestamp,
  and content hash — and still does after the guidance changes.
- **SC-009**: A lower-tier definition cannot perform a composition its tier forbids, whatever
  the request says.
- **SC-010**: The audit trail distinguishes a model gate from a human approval in every case
  where both occur.
- **SC-011**: Four of the five eval-gate rows move from Deferred to In force. The fifth —
  report fidelity — is recorded as owed against ADR-0018, and **zero rows are recorded as
  in force without a subject**.
- **SC-012**: Two packs load side by side, and neither is reachable from a definition that
  does not name it. **Adding the second pack changed no core file** — demonstrated by the
  diff, not argued.
- **SC-012a**: The Terraform pack's skills carry a recorded upstream commit, a provenance
  record, and a completed injection-lens review. Zero adopted skills are unpinned.
- **SC-013**: The conformance contract states, per cell, whether it was qualified against a
  fixture or against a live model. Zero cells are recorded as qualified without saying
  which.
- **SC-014**: All five roles have at least one qualified cell, and a definition can be bound
  end to end without an unqualified reference.
- **SC-015**: The record names what qualified the **first** judge, and that answer does not
  itself depend on an unqualified judge. Zero cells are qualified before it is recorded.

## Assumptions

- **Packs attach to what 010 built.** Agent definitions are already real records in the
  control-plane trust fabric with ceilings an operator authored. A pack is named *by* a
  definition and bounded *by* that ceiling; this feature does not invent a second place
  where an agent's capability is decided.
- **The registry is the one 002 built.** Principle I forbids shipping a registry product;
  packs register into the existing governed registry rather than bringing their own.
- **"No core change" is testable, and will be tested.** FR-004 reads as a slogan. It is
  asserted the way this repository asserts other absences — structurally, over the actual
  tree.
- **The two packs prove different things, deliberately.** Terraform proves *adoption* —
  ADR-0004's supply chain against a real upstream repository. Vault proves *invocation* —
  tools reaching a product that actually runs in the enclave. Neither pack alone would
  exercise both halves, and a feature that shipped two authored packs would have built the
  supply chain and never tested it.
- **The clarifications shrank this feature in one place and grew it in another.** Two
  packs rather than one is more content work, taken deliberately because it is what makes
  FR-004 demonstrable. Deferring US6 removes the largest dependency. Fixtures in the
  blocking lane keep the gate trustworthy while a marked lane keeps it meaningful.
- **This feature still introduces the platform's first model call**, in the marked lane.
  Everything shipped so far calls no model at all — `pyproject.toml` says so in as many
  words — so the provider seam, whatever it turns out to be, is new ground rather than an
  extension of something.
- **The judge regress is now binding, not theoretical.** Qualifying all five roles means
  qualifying `judge`, which means a judge scored the judge suite, which means something
  qualified that one. FR-012a makes resolving it a precondition rather than a note. The
  spec deliberately does not choose the resolution — that is architecture — but it bounds
  the options and forbids the implicit answer, which is the one that happens by default.
- **Qualifying `write` on fixtures is the sharpest edge in this feature.** A `write` cell is
  a model permitted to make changes, and in the blocking lane its qualification is against a
  recording. The marked live lane is not optional for `write` in the way it arguably is for
  `summarize`, and SC-013's per-cell record is what stops the difference being invisible.

## Out of Scope

- **Portal answering** — estate-state and grounded guidance. This feature unblocks it; it
  does not build it.
- Deferred disclosure and code mode (ADR-0040/0041), both gated on proving governance
  survives them.
- Multi-tenancy (ADR-0046).
- RFC 8693 + RAR authority manufacture, and real brokered credential translation.
- **Validated designs, guidance precedence, and the deviation register (ADR-0023).**
  Deferred by the 2026-07-29 clarification and recorded as an owed gate row: after this
  feature, "silent deviation is prohibited" is still a rule nothing enforces. The corpus is
  already sourced (HashiCorp Validated Patterns, from 012's research), so the follow-on
  starts from a settled source rather than rediscovering one.
- **`RunReport` and report fidelity (ADR-0018)**, recorded as an owed gate row rather than
  built. See the clarification.
- Any registry *product*. Principle I: provider interfaces and conformance suites are the
  deliverable.
