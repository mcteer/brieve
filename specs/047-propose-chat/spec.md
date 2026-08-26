# Feature Specification: Propose chat — repo URL to phased work to pull request

> **WITHDRAWN AFTER THE FACT — the final Terraform plan gate (2026-08-26).**
>
> This spec requires a real `terraform plan` against the authored tree as the last gate
> before Propose, and lists a failed plan under R7 among the conditions that must not open a
> pull request. That gate has been removed.
>
> The reason is not cost. **A plan is only true of the environment it ran against.** The gate
> ran in the dispatch container with `-backend=false` and no state — not the estate the
> change is for — so a green result was never evidence about the target: the same
> configuration can plan clean there and fail on apply where it is actually going. A gate
> that can pass and then be wrong is worse than none, because it is read as assurance. It
> also refused correct work outright, since a configuration declaring a remote backend cannot
> be planned without initialising that backend, which the gate deliberately would not do.
>
> The check moves to the person receiving the proposal, who plans it against their own state
> and credentials — the only place the answer means anything. Judge deny, ownership failure
> and publish error still hold R7 open. `terraform_plan` remains available as a TOOL the
> model may call for context; only plan-as-gate is gone.
>
> ADR-0068 names Terraform's plan this product's impact oracle and needs a supersession note
> to match.


**Feature Branch**: `spec/047-propose-chat`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: People should not pick an agent from a dropdown. They get a
single chat surface where they paste a repository URL and ask for infrastructure work
(e.g. a Terraform template to deploy their application). Behind that prompt the platform
runs ordered phases — research, plan, write, judge, propose — which may use different
backend roles or tools, but the work is abstracted. While it runs, the person sees which
phase is active. Success is a real pull request on the repository they named. Closes the
unnumbered ROADMAP entry *"The change-proposal workflow, end to end"* for the first
user-facing intake that returns a PR (Terraform-shaped), without making Ask open PRs.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4 / R13 (evidence)** — phase outcomes and the PR are joinable on one correlation ID; refusals leave an auditable reason bound to a phase. **R7 (fail-closed)** — ownership failure, judge deny, failed final plan, or publish error must not open a PR. **R12 (eval / gate)** — phase visibility and “no PR on failure” must be expressible as rows that can lose. **R3 (scope only narrows)** — phases must not widen authority beyond what the propose path may grant |
| **ADRs touched** | **ADR-0034** (thin portal — renders phase labels and PR URL from the platform; invents no workflow). **ADR-0033** (API / MCP / portal parity for propose intake and progress). **ADR-0038 / ADR-0064 / ADR-0066** (authoring tools and VCS via adopted CLIs — consume). **ADR-0047** (gates that can fail — plan and judge must not be fixtures that always pass). **ADR-0068** (product impact evidence pattern — Terraform plan is the oracle for this product, parallel to Vault’s measurement in 042). **ADR-0039** (Ask never acts — Propose is a distinct surface; Ask remains answer-only). Consumes 038/041 authoring reachability and 042’s product-specific propose template |
| **Evidence class** | **attestation-relevant.** Opening a PR asserts that authored changes passed the platform’s gates; phase and refusal records must support that claim |

## What is actually wrong

**Ask answers; Run’s agent picker is not Propose.** A person who pastes a GitHub URL and asks
for Terraform that deploys their app reasonably expects a pull request. Today the portal
either answers in Ask (no repository side effect — correct for Ask) or starts a generic Run
turn that never builds an authoring request, never clones their repo, and never opens a PR.
Selecting “Author” from a dropdown is the wrong product: the person should not choose backend
agents; they should state the repo and the need.

**Phases exist in the architecture and are invisible in the product.** Analyzer vs proposer,
research vs publish, and (for Terraform) plan-as-context and plan-as-gate are real seams.
None of that is a user-facing progress story. A run that fails in four seconds looks like
“nothing happened.”

**Authoring machinery is proven and unwired for this intake.** Request validation, subject
acquisition, authoring tools, and real forge PRs already exist for operator/script paths.
There is no single chat that turns a pasted URL plus a task into that path with live phase
visibility.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One Propose chat: URL plus ask, PR back (Priority: P1)

Someone opens Propose (not Ask, not an agent picker). They paste a repository URL they are
allowed to propose into and describe the Terraform (or equivalent infrastructure-as-code)
change they need. When the work succeeds, they see a pull request URL for that repository in
the conversation. They never choose an agent by name.

**Why this priority**: This is the product promise. Everything else supports it.

**Independent Test**: From the Propose surface, submit an owned demo repository URL and a
clear Terraform-oriented task; when the run completes successfully, the conversation shows a
PR URL on that repository; the forge shows a corresponding open (or newly created) PR.

**Acceptance Scenarios**:

1. **Given** a signed-in person on Propose, **When** they view the composer, **Then** there is
   no agent dropdown — only the means to state the repository and the task (in one message or
   equivalent single intake).
2. **Given** an owned repository URL and a supported task, **When** Propose completes
   successfully, **Then** the conversation shows a pull request URL for that repository, and
   a PR exists at the forge for that URL.
3. **Given** the same propose request on API and MCP (where the operation exists), **When**
   both complete successfully, **Then** both yield a PR outcome with the same meaning — the
   portal only renders what the platform returned (parity).

---

### User Story 2 — Live phase progress (Priority: P1)

While Propose runs, the person sees which phase the work is in, among the ordered set:
**Research**, **Plan**, **Write**, **Judge**, **Propose**. Completed phases remain visible;
the active phase is obvious; when a phase fails, that phase is marked failed with a
user-safe reason and later phases do not run.

**Why this priority**: Without this, long or failing runs repeat the “did nothing” experience.

**Independent Test**: Start a propose that progresses through at least two phases (or fails in
a middle phase); without manually refreshing in a way that loses context, the UI shows phase
transitions; a forced mid-phase failure labels that phase and does not claim a PR.

**Acceptance Scenarios**:

1. **Given** a running propose, **When** the platform advances from Research to Plan (or the
   next phase), **Then** the conversation updates to show the new current phase without the
   person having to invent a progress model.
2. **Given** a failure in Judge (or any earlier phase), **When** the run ends, **Then** that
   phase is shown as failed with a user-safe reason, later phases are not shown as completed,
   and no PR URL is presented as success.
3. **Given** Ask, **When** someone asks a question, **Then** Ask still does not open PRs and
   does not show Propose phases — the surfaces stay distinct (ADR-0039).

---

### User Story 3 — Fail closed before a PR exists (Priority: P1)

If the repository is not one the person may propose into, if the final plan gate fails, if
the judge denies publish, or if publishing cannot complete, the platform refuses without
opening a pull request. The refusal is bound to a phase and does not look like success.

**Why this priority**: A helpful-looking false PR (or a PR after a failed gate) is worse than
a clear refusal.

**Independent Test**: Drive each refusal class (not owned, plan gate fail, judge deny, publish
fail); assert no PR URL is offered as success and audit/trail can attribute the refusal to a
phase.

**Acceptance Scenarios**:

1. **Given** a repository URL the person is not allowed to propose into, **When** they submit
   Propose, **Then** the work refuses before authoring side effects that imply a proposal, with
   a reason the person can understand (without disclosing secrets or other people’s repos).
2. **Given** a run that reaches the final plan gate and that gate fails, **When** the run
   ends, **Then** no pull request is opened and Plan (or the gate’s phase) is marked failed.
3. **Given** a judge deny before publish, **When** the run ends, **Then** no pull request is
   opened and Judge is marked failed.

---

### User Story 4 — Plan uses a real product oracle (Priority: P2)

For Terraform-shaped propose work, the Plan phase uses a **real** plan against the authored
(or subject) tree as the impact oracle — not a fixture that always succeeds. A failed final
plan blocks Propose. Plan evidence that is safe to show accompanies the PR when publish
succeeds.

**Why this priority**: ROADMAP and ADR-0047: a fixture gate would be green forever. P2 only
relative to intake + phases + PR so a thin path can land first if clarify splits — **this
feature includes the real plan gate** (see Assumptions / Clarifications).

**Independent Test**: A case where the authored tree makes plan fail must not open a PR; a
case where plan succeeds may open a PR that carries bounded plan evidence.

**Acceptance Scenarios**:

1. **Given** authored changes that make the real plan fail, **When** Propose runs, **Then**
   no PR is opened and the failure is visible on Plan.
2. **Given** authored changes that make the real plan succeed, **When** Propose opens a PR,
   **Then** the PR (or the conversation’s success payload) includes bounded plan evidence
   suitable for a reviewer, without secret values.

---

### Edge Cases

- Repository URL malformed or not a recognized forge URL — refuse before work starts; no
  phase strip that pretends research began.
- Repository owned for clone but publish credentials cannot push — fail on Propose phase; no
  success PR URL.
- Person navigates away and returns — phase state and eventual PR URL are still visible from
  platform truth, not only from in-memory UI.
- Empty task with only a URL — refuse with a clear “what should change” requirement.
- Ask conversation mistakenly used for “open a PR” language — Ask still answers or declines;
  it does not open a PR (cross-surface edge).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST provide a Propose chat surface distinct from Ask, with no
  agent-definition picker as the primary control.
- **FR-002**: Propose intake MUST accept a target repository URL and a natural-language task
  in a single user submission.
- **FR-003**: The platform MUST refuse Propose when the target repository is not in the set
  the requester may propose into (ownership bound to the requester, not only to an
  installation-wide credential).
- **FR-004**: A successful Propose MUST result in a real pull request on the named
  repository; the conversation MUST present that PR’s URL as the success outcome.
- **FR-005**: Propose MUST run an ordered phase sequence visible to the user: Research, Plan,
  Write, Judge, Propose. The user MUST see the current phase while work is in progress and
  which phases have completed.
- **FR-006**: When a phase fails or refuses, the platform MUST mark that phase failed with a
  user-safe reason, MUST NOT run later phases, and MUST NOT present a PR URL as success.
- **FR-007**: Phase labels and PR URL MUST be produced by the platform and only rendered by
  the portal (thin client). The portal MUST NOT invent phase order or success.
- **FR-008**: All phases of one propose MUST share one correlation ID joining intake → phase
  transitions → tool decisions → PR outcome in the audit trail.
- **FR-009**: For Terraform-shaped propose, the Plan phase MUST use a real plan oracle (not a
  always-green fixture). A failed final plan MUST block opening a PR (ADR-0047).
- **FR-010**: Before opening a PR, a Judge phase MUST be able to deny publish; deny MUST fail
  closed with no PR.
- **FR-011**: On successful publish, plan evidence that is safe for reviewers MUST be
  available with the PR (body or linked conversation payload), without secret values.
- **FR-012**: Ask MUST remain unable to open pull requests or run Propose phases (ADR-0039).
- **FR-013**: API and MCP MUST expose the same propose capability and progress meaning as the
  portal consumes (ADR-0033), so no transport invents a second workflow.
- **FR-014**: User-visible phase messages and refusals MUST NOT include secret values, raw
  credentials, or installation tokens.

### Key Entities

- **Propose submission**: Requester, tenant, target repository URL, task text, correlation ID.
- **Phase progress**: Ordered phase name, state (pending / active / completed / failed),
  optional user-safe reason, timestamps as needed for display.
- **Propose outcome**: Success (PR URL + bounded evidence summary) or refusal (phase +
  reason); never “success” without a PR.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a scripted walkthrough on an owned demo repository, a successful Propose
  shows a forge PR URL in the conversation in one continuous session, with no agent picker
  used.
- **SC-002**: During a successful run, a reviewer observing the UI can name the active phase
  at least once before completion without refreshing into a blank state (live progress).
- **SC-003**: 100% of fixture/conformance cases that inject ownership failure, final-plan
  failure, or judge deny end with no PR URL presented as success.
- **SC-004**: Ask regression: submitting “open a PR for …” on Ask does not create a forge PR.
- **SC-005**: A case where the real plan oracle fails is demonstrably red (gate can lose);
  a fixture-only “plan always ok” path is not accepted as the Plan gate.

## Assumptions

- Propose is the user-facing name for this surface; exact nav label may be “Propose” or
  equivalent wording that is not “Ask” and not “pick an agent.”
- Target repositories are GitHub (or the forge already used by `open_proposal`); URL forms
  normalize to the ownership and clone identifiers the platform already understands.
- “Owned” means membership in the requester’s allowed propose set enforced at request
  validation (existing authoring ownership rule), configured for the deployment (e.g. demo
  repo allowlisted for the operator in dev).
- Backend may map phases onto multiple agent definitions or roles; that mapping is not shown
  as an agent picker.
- Existing Run-with-agent-picker threads may remain for operators but are not the primary
  path for “URL → PR.”
- Terraform is the first product shape; Vault policy authoring (042) remains the parallel
  product-specific path and is not replaced by this chat in this feature.
- Real plan requires Terraform available where Plan runs; deploying that capability is in
  scope for this feature’s Plan gate (not deferred to “fixture forever”).

## Clarifications

### Ownership of pasted URLs

Resolved for this feature: Propose refuses unless the target repository is in the
requester’s allowed propose set (same ownership bound as authoring requests). Dev/demo
deployments configure that set so a known demo repository (e.g. the operator’s
`brieve-demo`) can succeed; unknown or disallowed URLs refuse before Research completes as
success.

### Terraform plan in 047

Resolved: **in scope.** Plan phase uses a real plan oracle; failed final plan blocks PR
(FR-009, SC-005). Bounded plan evidence ships with successful PRs (FR-011).

### Judge bar

Resolved: Judge is a fail-closed publish gate (FR-010). Exact scoring rubric may reuse
patterns from answering sufficiency/relevance where appropriate, but “always allow” is not
a valid Judge. Deny produces a failed Judge phase and no PR.

### Ask vs Propose navigation

Resolved: Ask stays Q&A (never opens PRs). Propose is a separate primary nav entry with the
single chat intake. Agent dropdown is not the Propose UX.
