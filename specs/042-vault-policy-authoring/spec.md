# Feature Specification: Vault policy authoring, end to end

**Feature Branch**: `spec/042-vault-policy-authoring`

**Created**: 2026-08-07

**Status**: Draft

**Input**: Measured against merged main (`d723efd`) — 041 made authoring reachable and product-blind. This is the first product to reach it, and Vault is the only one genuinely present in the enclave.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11 (total interception)** — every policy read and every capability check is a registered, hook-wrapped tool call, like every other product interaction. **R2, R3 (authority per task)** — the run reads and reasons under a bounded identity, and **never holds authority to change what bounds it**. **R7 (fail-closed)** — an impact check that cannot run refuses the proposal rather than publishing one whose evidence is missing. **R4, R13 (evidence)** — the proposal carries the diff, the capability results and the guidance citations, so a reviewer can reconstruct the judgement without rerunning it |
| **ADRs touched** | **ADR-0038/0064/0066** (the authoring tier and its publishing path, consumed from 041 unchanged), **ADR-0025** (registry isolation — this feature is the first that could plausibly ask an agent to author the records that bound it, and the first where refusing must be structural), **ADR-0004** (the pinned Vault operating guides as the grounding corpus), **ADR-0018/0035** (evidence with citations, never verdicts), ADR-0047 (**the row that decides this feature's honesty**: an impact oracle that is a fixture is green forever, which is why Terraform is not the first product), ADR-0051 (what capability-check output may become) |
| **Evidence class** | **attestation-relevant.** The proposal becomes the record a person merges from, and the capability-check results are the evidence it rests on. What must never enter it: any secret **value**, and any policy body belonging to the platform's own trust fabric |

## Clarifications

### Session 2026-08-07

- Q: How is a *proposed* policy's impact measured, given Vault has no plan equivalent? → A:
  **A scratch policy and a real token.** The proposed document is written under a throwaway
  name, a token carrying only it is minted, Vault's own capability checks are run against that
  token, and both are destroyed. **Vault itself answers the question**, which is the property
  that makes this feature worth building ahead of Terraform's — a derived answer would be the
  fixture problem wearing better clothes.
  **This reverses an assumption written earlier in this spec**: the feature *does* write to
  Vault. Bounded to a scratch namespace, never attached to any entity, always destroyed, and
  never able to name a protected policy — which makes the FR-004 refusal load-bearing twice
  over rather than once.
- Q: Whose token do reads and capability checks run as? → A: **Reads keep the platform
  identity**, matching the vault pack's existing `product_mode = "none"` posture; the
  capability check runs as the **scratch token carrying only the proposed policy**, because
  the question it answers is *"what would this policy allow"* and that is independent of who is
  asking. **The cost is recorded rather than absorbed**: reading as the allocation means the run
  can see policies the requester could not, so the evidence may describe more of the estate than
  the requester is entitled to know. Requester-scoped reads are ADR-0044 credential-translation
  territory that 013 scoped out and nothing has built — this is owed, not solved.

## The shape, and the one thing that makes it different from Terraform

The workflow is the same one the ROADMAP names for Terraform. **What differs per product is the
impact instrument**, and naming it per product is what keeps the workflow honest rather than
generic.

| | Terraform | Vault policy |
| --- | --- | --- |
| read what exists | state and config, via plan | policies and what is attached to them, via reads |
| impact oracle | `terraform plan` — the product's own engine answers *what would happen* | **there is no plan-equivalent for a policy as a whole.** Capability checks answer *what a token could do* per path; the rest is read-and-diff plus reasoning |
| a better way, given the outcome | the corpus's Terraform guides | the corpus's **Vault operating guides**, already pinned and already the answering surface's ground |
| the proposal | a PR carrying the final plan | a PR carrying the policy diff, the capability results, and the citations |

**Vault is first because its product is actually here.** `terraform_plan` is self-described as
*"a shape, not a plan… Terraform is not deployed in the enclave"*, and a soundness gate built on
a fixture is green forever — ADR-0047's exact shape. Vault runs the trust fabric, so this
feature's impact check can be a real instrument on the first day.

## The constraint that outranks everything else

**The Vault in this enclave holds the platform's own governance records.** Measured:
`vault_policy.agent_ceiling` (every definition's ceiling), `vault_policy.authoring_publisher`,
`vault_policy.authority_change`, `vault_policy.harness_database`,
`vault_policy.audit_egress_credential`.

So the first product to reach the authoring tier is also the first that could be asked — by a
prompt, by a mistake, or by an instruction hidden in a subject — to **author the policies that
bound the agent authoring them**. Principle IV is unambiguous: *"Agents are structurally
excluded from managing their own platform."* ADR-0025 made a run observably unable to write what
bounds it, and 041 refused `subject_is_platform_tree` for the same reason one layer over.

This feature's central refusal is that one, in policy space. It must be **structural, not a
rule the model is asked to follow**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The agent reads what policy exists (Priority: P1)

An operator asks for a policy change. The agent reads the policies that exist and what they are
attached to, so its reasoning starts from the estate rather than from the prompt.

**Why this priority**: Every later step is a claim about a change to something. Without reading
what is there, the proposal is a guess dressed as a diff.

**Independent Test**: Ask for a change to a named policy; confirm the run reads that policy and
its attachments, that the read is recorded, and that no secret value appears anywhere.

**Acceptance Scenarios**:

1. **Given** a request naming a policy, **When** the run reads it, **Then** the policy document
   and its attachments are available to the reasoning and the read is recorded.
2. **Given** a policy that does not exist, **When** the run reads it, **Then** absence is
   reported as absence — distinguishable from a policy the run may not see.
3. **Given** any read, **When** it returns, **Then** no secret **value** is present, matching
   `vault_read`'s existing posture.

---

### User Story 2 — The platform's own policies are unreachable (Priority: P1)

A request that names a trust-fabric policy is refused, and so is one that reaches one
indirectly. The refusal is a property of the system, not an instruction the model complied with.

**Why this priority**: This is the feature's safety case. Everything else is a productivity
feature; this is the one that stops the platform being edited by the thing it governs.

**Independent Test**: Ask, in several wordings and via an instruction planted in a subject, for
a change to `agent_ceiling`. Confirm every attempt refuses, and that the refusal comes from the
platform rather than from the model declining.

**Acceptance Scenarios**:

1. **Given** a request naming a trust-fabric policy, **When** it is validated, **Then** it is
   refused before anything is read or authored.
2. **Given** a subject containing an instruction to modify a trust-fabric policy, **When** the
   run analyses it, **Then** the instruction is recorded as an attempt and changes nothing.
3. **Given** a model that *tries* to author a trust-fabric policy anyway, **When** it does,
   **Then** the act refuses — the guarantee must not rest on the model not trying.

---

### User Story 3 — The impact is measured, not asserted (Priority: P1)

Before a proposal is opened, the platform measures what the proposed policy would actually
permit, using Vault's own capability checks rather than the agent's opinion.

**Why this priority**: This is the row that decides whether the feature is worth anything. A
proposal whose "impact" is model prose is a review that has been reassured rather than informed
— 037's finding, in a new place.

**Independent Test**: Propose a policy that widens access; confirm the capability results show
the widening, and that a proposal cannot be opened when the check did not run.

**Acceptance Scenarios**:

1. **Given** a proposed policy, **When** the impact is checked, **Then** the result states what
   a token under it could do on the paths the change touches.
2. **Given** a change that grants a capability the current policy denies, **When** checked,
   **Then** the difference is present in the evidence rather than left for a reviewer to infer.
3. **Given** an impact check that cannot run, **When** publishing is attempted, **Then** it is
   **refused** — never published with the evidence absent, and never with a fabricated result.

---

### User Story 4 — The proposal carries its evidence (Priority: P1)

A person reviewing the pull request can see the policy diff, what the capability check found,
and which pieces of pinned guidance the reasoning rests on.

**Why this priority**: The proposal is the whole product. 041 proved the platform can open one;
this decides whether opening one is useful.

**Independent Test**: Open a proposal and read only the pull request; confirm a reviewer can
answer "what changed", "what does it now permit", and "on what basis".

**Acceptance Scenarios**:

1. **Given** a published proposal, **When** a reviewer reads it, **Then** it carries the diff,
   the capability results, and citations resolving against the pinned corpus.
2. **Given** reasoning that cites nothing, **When** the proposal is composed, **Then** that
   absence is disclosed rather than passed off as unsupported confidence.
3. **Given** any proposal, **When** it is composed, **Then** no secret value and no trust-fabric
   policy body appears in it.

---

### User Story 5 — Nothing 041 proved has to be rebuilt (Priority: P2)

The authoring trio, containment, provenance and the publishing path are consumed unchanged.

**Why this priority**: 041's tier is product-blind on purpose. A product feature that forked it
would prove the design wrong.

**Independent Test**: Confirm the policy path registers no second publisher and edits no 041
conformance row.

**Acceptance Scenarios**:

1. **Given** this feature, **When** a proposal is opened, **Then** it goes through
   `open_proposal` and the 041 publishing path.
2. **Given** 041's rows, **When** the suite runs, **Then** they pass unedited.

---

### Edge Cases

- A policy is attached to an entity the run cannot see: attachment reported as partial, with the
  bound disclosed, never silently truncated.
- The proposed policy is syntactically invalid: refused by Vault's own parsing, reported as a
  policy error rather than as an impact result.
- The requested change is already present in the repository: an empty proposal with a
  disclosure, as 041's corpus already requires for the duplicate case.
- The capability check names a path the diff does not touch: excluded, or the evidence grows to
  a size nobody reads — 029's lesson (1,000 of 63,947 entries).
- Two runs propose changes to the same policy concurrently: the deterministic branch keeps them
  distinct; a reviewer sees two proposals rather than one silently overwritten.
- A policy grants a capability on a path that does not exist yet: reported as granted, because a
  path appearing later would inherit it.
- The run is killed between writing the scratch policy and destroying it: the policy is orphaned
  in Vault, which is a standing grant nobody decided to make — detectable and removable
  afterwards (FR-023), because "always cleaned up" is a claim and not a guarantee.
- Two runs derive the same scratch name: the name is derived from the run, so they cannot — and
  a row asserts that rather than trusting it.
- A model asks for a scratch policy named `agent_ceiling`: refused by the protected set on the
  scratch path (FR-025), not only on the authoring path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST be able to read Vault policies and what they are attached to,
  through a registered, hook-wrapped tool on the same governed path every other product
  interaction takes.
- **FR-002**: No policy read MAY return a secret value, matching `vault_read`'s existing rule —
  the reasoning is about policy structure, and a value belongs in the process that consumes it.
- **FR-003**: A policy that does not exist MUST be distinguishable from one the run may not see.
- **FR-004**: The platform's own trust-fabric policies MUST be unreachable for authoring, and
  the refusal MUST be structural rather than a rule the model is asked to obey.
- **FR-005**: The refusal in FR-004 MUST hold against an instruction planted in a subject, and
  such an attempt MUST be recorded.
- **FR-006**: The set of protected policies MUST be derived from what the trust fabric actually
  declares, never from a hand-maintained list that drifts the first time a policy is added.
- **FR-007**: The impact of a proposed policy MUST be measured with Vault's own capability
  checks against the real product, never with a fixture and never with model prose.
- **FR-008**: An impact check that cannot run MUST refuse the proposal. A proposal published
  without its evidence is the reassurance failure this feature exists to avoid.
- **FR-009**: The impact evidence MUST state what the change *alters* — what is newly permitted
  and what is newly denied — rather than only what the proposed policy permits.
- **FR-010**: Capability-check output reaching the model MUST be bounded to the paths the change
  touches, and the bound MUST be disclosed when it truncates.
- **FR-011**: The proposal MUST carry the policy diff, the capability results, and citations
  that resolve against the pinned Vault operating guides.
- **FR-012**: Reasoning that resolves no citation MUST be disclosed as unsupported rather than
  presented as grounded.
- **FR-013**: No secret value and no trust-fabric policy body MAY appear in a published
  proposal.
- **FR-014**: Authoring, containment, provenance and publishing MUST be consumed from 041
  unchanged; this feature registers no second publishing path.
- **FR-015**: 041's conformance rows MUST pass unedited.
- **FR-016**: At least one row MUST run against the **real Vault in the enclave** and MUST fail
  rather than skip when it is unavailable — the impact instrument's whole claim is that it is
  real.
- **FR-017**: A row MUST exist that **fails** when the trust-fabric refusal is removed, so the
  safety case can lose.
- **FR-018**: Policy reads MUST run under the allocation's platform identity, as the vault
  pack's tools already do. Requester-scoped reads are owed and out of scope.
- **FR-019**: Impact MUST be measured by writing the proposed policy under a scratch name,
  minting a token carrying **only** that policy, running Vault's capability checks against it,
  and destroying both. The product answers; the platform does not infer.
- **FR-020**: A scratch policy MUST be named from a reserved namespace that no trust-fabric
  policy can occupy, and the name MUST be derived from the run rather than chosen by a model.
- **FR-021**: A scratch policy MUST NOT be attached to any entity, role, or auth mount. It
  exists to be checked and for nothing else.
- **FR-022**: A scratch policy and its token MUST be destroyed when the check finishes,
  **including when the run fails, is interrupted, or is killed** — an orphaned policy is a
  standing grant nobody decided to make.
- **FR-023**: An orphaned scratch policy MUST be detectable and removable after the fact,
  because "always destroyed" is a claim that needs a way of being checked.
- **FR-024**: The scratch write MUST traverse the same governed pipeline as every other write —
  registered tool, hooks, records — and MUST be refused when the run's ceiling does not carry
  it. A privileged side channel for the platform's own convenience is the shape Principle II
  forbids.
- **FR-025**: The protected-set refusal MUST bind on the **scratch write path** as well as the
  authoring path, so a run cannot reach a trust-fabric policy name by way of the impact check.

### Key Entities

- **Policy record**: a named policy, its document, and what it is attached to.
- **Protected set**: the trust-fabric policies no authoring run may touch, derived rather than
  listed.
- **Impact result**: per path, what a token under the proposed policy could do, and how that
  differs from today.
- **Policy proposal**: 041's proposal, carrying diff, impact and citations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer reading only the pull request can state what changed, what it now
  permits, and on what basis — without rerunning anything.
- **SC-002**: 100% of attempts to author a trust-fabric policy refuse, across wordings and
  including one planted in a subject.
- **SC-003**: The safety case can lose: removing the refusal makes a row fail.
- **SC-004**: Every published proposal carries an impact result produced by the real product.
- **SC-005**: Zero proposals are published when the impact check did not run.
- **SC-006**: Zero secret values and zero trust-fabric policy bodies appear in any proposal.
- **SC-007**: At least one row runs against the real Vault and fails rather than skips when it
  is absent.
- **SC-008**: 041's rows pass unedited, measured as an empty diff over their files.
- **SC-009**: A change that widens access is visibly wider in the evidence — asserted with a
  case that would read identically if the diff were reported without the impact.
- **SC-010**: Zero scratch policies survive a completed run, and zero survive a killed one once
  the sweep has run.
- **SC-011**: Zero scratch policies are ever attached to an entity, role, or auth mount.
- **SC-012**: A scratch write naming a protected policy refuses, in 100% of attempts.

## Assumptions

- **The subject is a policy repository, and Vault is the context.** The agent authors into a
  repository through 041's path and reads the live estate to know what exists.
- **This feature proposes; it never applies** — with one bounded exception, clarified above and
  stated plainly because burying it would be worse than the exception itself. Measuring impact
  writes a **scratch** policy, checks a token carrying only it, and destroys both. Nothing is
  attached, nothing outlives the check, and no existing policy is altered. What a person merges
  is still the only thing that changes the estate.
- **The grounding corpus is already pinned** (`/validated-designs/vault-operating-guides-adoption`,
  62 entries) and needs no new content.
- **The intake surface is still the successor.** A *user* declaring workspace, repository and
  scope remains the composition feature the ROADMAP names; requests here are operator-authored,
  as 041's are.
- **041's tier stays product-blind.** Vault knowledge lives in the pack and the surfaces, never
  in `core/authoring` — the product-blindness gate already refuses otherwise, and it caught 041.
- **Terraform is deliberately not first.** Its impact oracle is a fixture, and a soundness gate
  on a fixture is ADR-0047's shape.
