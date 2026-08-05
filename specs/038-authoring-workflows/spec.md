# Feature Specification: The agent authors, and a person merges

**Feature Branch**: `038-authoring-workflows`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Have we tested the ability to launch an agent that writes some code, like a Terraform template?" — measured, and the answer was no: four tools exist across all packs and none of them writes anything.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11 (total interception)** — the platform gains its first tool that *produces* rather than reads or applies, and it must reach execution the same way every other tool does. **R7 (fail-closed)**. **R4, R10, R13 (evidence)** — an authored artifact is a claim about work the platform did, and the trail has to carry what was produced and why. **R6 (eval-gated promotion)** — the `write` role must be qualified before a definition may bind it. R16 (sealed core — the audit vocabulary grows) |
| **ADRs touched** | **ADR-0038** (**the integration-and-uplift family, Accepted 2026-07 and unimplemented** — this feature is its first realization), ADR-0037 (transport chosen by the standing test, not by preference), ADR-0022/0039 (the Qualified Model Matrix — the `write` role has never been bound), ADR-0041 (code mode, shipped in 036 — authoring may ride that seam), ADR-0004 (skills-first expertise), ADR-0047 (a passing stub is worse than a missing one) |
| **Evidence class** | **attestation-relevant.** The platform will produce artifacts a person merges into their own repository. What it authored, what it read to author it, and under whose authority are all claims someone will later need to reconcile to a record |

## Clarifications

### Session 2026-08-05

- Q: The pull request is a legitimate channel out of the isolation the analysis ran in. What rule keeps analysed private code from riding along? → A: **The proposal is bounded to the change**: files the change creates, plus diffs of files it edits, and nothing else from the analysed repository. Checkable by inspecting the artifact rather than by trusting the agent — a proposal either contains an untouched file or it does not. An edit legitimately shows surrounding context, and that is the change rather than a leak. What it catches is the plausible-looking way private code rides out: a pull-request body quoting the codebase, a "here is what I found" summary, an appendix of analysed source.
- Q: What decides that an authored artifact is correct? → A: **Product tooling AND a reference comparison**, because they catch different failures. Tooling catches malformed — does it parse, do the types line up. The reference catches *subtly wrong*, which is ADR-0038's actual warning: a module wiring a static credential where dynamic secrets were asked for validates perfectly and is the wrong answer. Every golden task therefore needs a human-authored reference, which is the "real work" that ADR predicted, and the corpus carries a floor that fails rather than warns (037's lesson: a corpus without one leaves the honesty of the whole half to whoever wrote the tasks).
- Q: How does a whole repository reach the isolation tier, when 037 built it for a skill diff delivered as payload with no repository mount? → A: **Read-only mount, egress allowlist unchanged.** And the reasoning is worth recording because it looks like a reversal and is not: 037's no-mount rule was never "mount nothing" — it was *do not hand a redirected agent the platform's own tree*. Here the subject is the requester's repository, it is not ours, and the platform's tree stays unmounted. Payload delivery does not survive a real codebase (a skill diff is kilobytes), and a per-run egress allowlist would make the tier's posture materially harder to assert than the static one row A0 checks structurally today.
- Q: The expectation is that the agent might apply the Terraform templates it creates. What is the scope? → A: **Author → propose → a human merges → a human applies.** ADR-0038 as written, and chosen for consistency: the same boundary holds whether the artifact is a Terraform module standing up infrastructure or a pull request building a Vault integration into an application. One rule, not one per artifact type.

  **Expressed as provenance rather than as capability**, which is what makes it enforceable: *the platform does not enact an artifact it authored.* `terraform_apply` keeps working for what it does today — applying configuration a person wrote and reviewed — and it is not removed or narrowed. What is forbidden is the platform applying its own output. Once a human merges the proposal, the artifact is ordinary reviewed configuration and applying it is the act it always was.

  Measured while deciding this: applying is **already governed** — `terraform_apply` is a registered `destructive`, non-repeatable tool with an observer required, so an interrupted apply resolves to `CANNOT_DETERMINE` and parks the run rather than guessing. The gap this feature fills is authoring, not enacting. Had the answer gone the other way, ADR-0038 would have needed amending rather than implementing: its stated reason the family is safe to offer is that *"the blast radius of a wrong answer is a rejected pull request rather than a broken application"*, and an agent that applied its own output would remove exactly that.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The agent produces something, and it is governed like anything else (Priority: P1)

A person asks the platform to author an integration — a Terraform module wiring an application to dynamic secrets, say. An agent runs, produces the files, and the work reaches the person as a proposal. Every step it took was a governed tool call: what it read, what it wrote, under whose authority. Nothing about "the agent wrote code rather than read a plan" changes how it was governed.

**Why this priority**: This is the capability the platform's own description claims and cannot currently perform. It is also the first tool that *produces*, so it is where the governance model meets a case it has never met.

**Independent Test**: Ask for a module, confirm files are produced, and confirm every write passed the same governed entry a read does — with the same records behind it.

**Acceptance Scenarios**:

1. **Given** a definition permitted to author, **When** it produces files, **Then** each write is a governed decision with a record, indistinguishable in kind from any other tool call.
2. **Given** a definition **not** permitted to author, **When** it attempts to write, **Then** it is refused exactly as it would be for any tool outside its ceiling.
3. **Given** an authoring run, **When** its evidence is read, **Then** what was produced and what was consulted to produce it are both recoverable.

---

### User Story 2 — The work lands as a proposal, never as a change (Priority: P1)

What the agent produced arrives as a pull request against the requester's own repository. Nothing is merged, nothing is applied, and no branch outside the request's scope is touched. A person reviews and decides.

**Why this priority**: ADR-0038 is explicit that this constraint is what makes the family safe to offer — *"the blast radius of a wrong answer is a rejected pull request rather than a broken application."* A feature that could write directly would be a different product with a different risk posture.

**Independent Test**: Confirm no path produces a merge, an apply, or a write outside the requester's own repositories, and that a human decision is required and recorded.

**Acceptance Scenarios**:

1. **Given** completed authoring, **When** the platform delivers it, **Then** it is a proposal awaiting a person, and nothing has been merged or applied.
2. **Given** a request naming a repository the requester does not own, **When** authoring is attempted, **Then** it is refused before anything is produced.
3. **Given** a merged proposal, **When** the record is read, **Then** the person who merged it is distinguishable from everything the platform did.

---

### User Story 3 — Nothing the agent read leaves with what it wrote (Priority: P1)

The agent analyses a private codebase and then opens a pull request. The pull request carries the integration and **nothing else** — no analysed source beyond what the change itself requires, and no secret value anywhere in the code, the commits, or the description.

**Why this priority**: P1 and arguably the sharpest requirement in the feature. Analysing a repository and then opening a pull request creates, by construction, a legitimate channel *out* of the isolation the analysis ran in. That channel is the feature working correctly, and it is exactly where private code or a credential would leave. ADR-0038 names both risks — *"an agent that has read a private codebase must not carry it anywhere"* and secret references only — and they meet here.

**Independent Test**: Author against a repository seeded with a secret and with distinctive unrelated content; confirm neither reaches the produced artifact, the commits, or the description.

**Acceptance Scenarios**:

1. **Given** a repository containing a credential, **When** the agent authors against it, **Then** no secret value appears in the produced files, the commit history, or the proposal text — only references.
2. **Given** a repository containing content unrelated to the task, **When** a proposal is produced, **Then** that content does not appear in it.
3. **Given** an attempt to place a secret value in an authored artifact, **When** it is made, **Then** it is refused and recorded.

---

### User Story 4 — Hostile repository content does not redirect the agent (Priority: P1)

The application being analysed contains text aimed at the agent — a comment instructing it to add a backdoor, exfiltrate an environment variable, or approve its own output. The agent's behaviour is unchanged and the attempt is recorded.

**Why this priority**: ADR-0038 calls analysing arbitrary application code *"the platform's largest prompt-injection surface"*, and says the isolation tier and injection-lens hooks are *"necessary rather than precautionary"*. 037 built that tier for a subject delivered as payload; a whole provided repository is a larger subject, and whether the tier's assumptions survive it is this story's question.

**Independent Test**: Author against a repository carrying instructions addressed to the agent, and confirm the output is unaffected and the attempt appears in the record.

**Acceptance Scenarios**:

1. **Given** repository content addressed to the agent, **When** it is analysed, **Then** the produced artifact is unaffected by it and the attempt is recorded.
2. **Given** an agent redirected successfully, **When** it acts on the redirection, **Then** its ceiling offers nothing that could carry the redirection out.

---

### User Story 5 — The model is qualified for the role it is acting in (Priority: P1)

Authoring runs under a model bound to the `write` role and qualified for it: scored against integration-correctness tasks and against must-deny cases covering secrets in output, exfiltration of analysed code, and injection resistance. An unqualified cell refuses before anything is produced.

**Why this priority**: Principle VIII is a MUST, and `write` is a role the matrix has always had and nothing has ever bound. Authoring without a qualified cell would be a model acting in a role nobody qualified it for — the gap 026 found for `ask` and closed, arriving now for the role with the largest blast radius.

**Independent Test**: Attempt authoring with no qualified `write` cell and confirm it refuses; qualify one and confirm it proceeds.

**Acceptance Scenarios**:

1. **Given** no qualified `write` cell, **When** authoring is requested, **Then** it refuses for that reason, distinguishably from an unavailable provider.
2. **Given** a `write` cell that fails its must-deny suites, **When** promotion is attempted, **Then** it is refused.

---

### Edge Cases

- **The repository is enormous.** Analysis cost cannot be unbounded, and a truncated read must be disclosed rather than silently partial — a proposal built from part of a codebase that does not say so is a claim about work nobody did.
- **The agent produces nothing useful.** An empty or trivially wrong proposal is a legitimate outcome and must be distinguishable from a failure.
- **The requester's repository already has the integration.** Producing a duplicate is a wrong answer that looks like a right one.
- **Authoring is interrupted partway.** Files may have been produced and nothing proposed. The run must be resolvable by observation, not by guessing.
- **The proposal is never reviewed.** An unreviewed proposal is not a completed piece of work, and nothing should report it as one.
- **Analysed content is itself a secret.** A repository whose *source* is sensitive makes "carry nothing out" harder than redaction — the produced artifact necessarily reflects what was read.
- **Two authoring runs against one repository.** Concurrent proposals touching the same files can conflict, and the second must not silently overwrite the first's branch.

## Requirements *(mandatory)*

### Functional Requirements

**Producing**

- **FR-001**: The platform MUST be able to produce file content as a governed tool call, in the risk class the registry already defines for writes and no registered tool currently uses.
- **FR-002**: An authoring call MUST reach execution through the same governed entry every other tool call uses. Producing content MUST NOT become a second path to acting.
- **FR-003**: A definition MUST NOT be able to author unless its ceiling permits it. Authoring is opt-in per definition, exactly as every other capability is.
- **FR-004**: The evidence MUST carry what was produced and what was consulted to produce it, so a reader can reconstruct the work rather than only its outcome.
- **FR-005**: Analysis of a provided repository MUST run in the isolation tier intended for untrusted content, with the repository mounted **read-only**.
- **FR-005a**: The platform's own repository MUST remain unmounted in that tier, and the tier's egress allowlist MUST remain static configuration rather than becoming per-run. This is 037's rule held rather than relaxed: "no mount" meant *do not hand a redirected agent the platform itself*, and mounting the requester's repository read-only does not do that.
- **FR-005b**: A repository too large to analyse in full MUST have the truncation **disclosed** in the proposal. A proposal built from part of a codebase that does not say so is a claim about work nobody did.

**Proposing, never changing**

- **FR-006**: Authored work MUST be delivered as a proposal against the requester's own repository. The platform MUST NOT merge and MUST NOT apply.
- **FR-007**: A request naming a repository outside the requester's own MUST be refused before anything is produced.
- **FR-008**: A human decision MUST be required for the work to land, and the record MUST distinguish that decision from everything the platform did.
- **FR-009**: A second proposal against the same target MUST NOT silently displace an earlier one.

**Carrying nothing out**

- **FR-010**: No secret value MAY appear in produced content, in commit history, or in proposal text. References only.
- **FR-011**: An attempt to place a secret value into authored output MUST be refused and recorded.
- **FR-012**: *The rule FR-013 operationalizes*: analysed content MUST NOT appear in the proposal beyond what the produced change itself requires. FR-013 is the normative form — this states the intent it serves, so a later change to FR-013 can be checked against what it was for.
- **FR-013**: A proposal MUST contain only the files the change creates and diffs of the files it edits. No other content from the analysed repository may appear — not in the files, not in the commits, not in the proposal's description.
- **FR-013a**: The rule MUST be enforced by **inspecting the artifact**, not by the agent declining to include things. A proposal either contains an untouched file or it does not, and that is decidable without a judgement call.
- **FR-013b**: Surrounding context within an edited file's diff is **the change**, not a leak, and MUST NOT be refused. A rule that forbade it would forbid editing.

**Not being redirected**

- **FR-014**: Content in an analysed repository MUST be treated as data rather than as instruction, and an attempt to instruct the agent MUST be recorded.
- **FR-015**: The authoring definition's ceiling MUST contain nothing that could carry a redirection outside the run — the containment MUST hold structurally rather than by the agent declining.

**Qualified to act**

- **FR-016**: Authoring MUST run under a model cell qualified for the `write` role, and MUST refuse when none is qualified — distinguishably from a provider being unavailable.
- **FR-017**: The `write` role's qualification MUST include integration-correctness tasks and must-deny cases covering secrets in output, exfiltration of analysed content, and injection resistance.
- **FR-018**: Correctness MUST be decided by **two independent gates**: the artifact validates under the product's own tooling, **and** it matches a human-authored reference implementation on the properties the task is about.
- **FR-018a**: The two gates MUST be reported separately, because they catch different failures — malformed versus *subtly wrong* — and collapsing them into one score would hide which occurred.
- **FR-018b**: The corpus MUST have a floor that **fails rather than warns**, and it MUST include at least one case that is syntactically valid and substantively wrong. A corpus that only catches malformed output has not measured integration correctness, and a floor nothing enforces is a suggestion.
- **FR-018c**: Every golden task MUST carry a human-authored reference. This is the "real work" ADR-0038 predicted, and a task without one cannot participate in the second gate.
- **FR-019**: The qualification MUST land with the capability rather than after it, so no gate row is owed.

**Boundaries**

- **FR-020**: The platform MUST NOT enact an artifact it authored — no merge, no apply, no equivalent. **The rule turns on provenance, not on capability**: it is not that applying is forbidden, it is that applying *one's own output* is. This holds identically for a Terraform module and for application code, so there is one boundary rather than one per artifact type.
- **FR-020a**: Existing capabilities MUST NOT be narrowed by this feature. `terraform_apply` continues to do what it does today — apply configuration a person wrote and reviewed — and a merged proposal is exactly that, so applying it afterwards is the ordinary governed act it always was.
- **FR-020b**: The platform MUST be able to tell its own output from a person's. A rule that turns on provenance requires provenance to be recorded and checkable at the moment of enactment, not inferred later.
- **FR-021**: This feature MUST NOT change how content is adopted or promoted. It adds a capability; the supply chain is unchanged.

### Key Entities

- **Authoring request** — what a person asked for, and which repository of theirs it targets.
- **Subject** (the analysed repository) — the provided application. Adversarial by assumption, regardless of who supplied it. Called the *subject* throughout the plan and the design, because it is what the tier mounts and what the containment rules are stated against.
- **Authored artifact** — what the agent produced. The feature's output, and a claim about work the platform did.
- **Proposal** — the artifact delivered for a person to decide on. The only way work leaves the platform.
- **Write cell** — the qualified model binding authoring runs under. The matrix's third role, unbound until now.
- **Correctness case** — a task with a known-good outcome, used to qualify the `write` role. Must include the syntactically-valid-but-wrong.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can ask for an integration and receive a reviewable proposal containing the produced files, without the platform having merged or applied anything.
- **SC-002**: Every authoring action appears in the record as a governed decision — **100%, no unaccounted writes**, since one is the gap the whole governance model is claimed not to have.
- **SC-003**: A repository seeded with a secret produces a proposal containing **no secret value** in files, commits, or description — demonstrated by assertion, not inspection.
- **SC-004**: A repository seeded with distinctive unrelated content produces a proposal that does **not** contain it.
- **SC-005**: Repository content addressed to the agent leaves the produced artifact **unchanged**, and the attempt is in the record.
- **SC-006**: Authoring with no qualified `write` cell **refuses**, and the reason is distinguishable from a provider outage.
- **SC-007**: A model cell that fails any must-deny suite for this role **cannot be promoted** — demonstrated by attempting it.
- **SC-008**: The correctness corpus catches a syntactically valid but substantively wrong artifact. A corpus that only catches malformed output has not measured integration correctness.
- **SC-009**: No sequence of platform actions results in a merge or an apply — **no tolerated exception**.

## Assumptions

- **The substrate from 036 and 037 is available and its fit is to be tested, not assumed.** Code mode governs every call a model-written program makes, and authoring plausibly rides that seam; the hardened tier is where analysis belongs. Both were built for different subjects, and this feature checks them against a new one rather than inheriting them silently.
- **The `write` risk class and the `write` role already exist and are unoccupied.** This feature is the first to use either — the vocabulary was defined in advance and left for whoever needed it.
- **Version control is a pack tool target**, per ADR-0038, with transport decided by ADR-0037's standing test rather than by preference.
- **Expertise is skills-first**: the adopted skills are what the agent applies, with retrieval only on a gap.
- **The sealed core is in play.** Recording authored artifacts and proposals adds audit vocabulary, so this needs a Principle V review.
- **Only products whose pack declares an authoring workflow are in scope.** The Terraform pack already declares `author-module`; nothing else does.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Applying the change.** The agent proposes; a person merges; a person applies. Applying remains the separate, already-governed act it is today (`destructive`, non-repeatable, observer required) — this feature neither extends nor narrows it.
- **The agent enacting its own output**, under any framing. Decided rather than deferred: the answer is no, and it is FR-020 rather than a future question.
- **Authoring for products without a declared workflow.** A pack that has not said it supports authoring has not been reviewed for it.
- **Iterating on review feedback.** A proposal that comes back with comments is a new request, not a conversation this feature manages.
- **Authoring against repositories the requester does not own.** The scope constraint is ADR-0038's and is not negotiated here.
- **Changing the adoption or promotion path.** This adds a capability; how content enters the platform is untouched.
