# Implementation Plan: The agent authors, and a person merges

**Branch**: `038-authoring-workflows` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/038-authoring-workflows/spec.md`

## Summary

The platform's first tool that **produces**. ADR-0038 named the integration-and-uplift family
in 2026-07 and nothing implemented it; measured today, four tools exist across all packs and
none of them writes anything, while `packs/terraform/pack.toml` already declares an
`author-module` workflow with no tool behind it.

Built as **three layers, each independently shippable**, in an order chosen so the layer that
can leak lands only once the layer that bounds it exists.

**Producing** (US1) registers `author_file` in the `write` risk class the registry has carried
unused since 013, reached through `invoke_tool` like every other tool. Authored files land in
a **writable workspace that is not the subject** — which is what turns FR-013a's containment
rule from a check into a property (R5).

**Containing** (US3, US4) runs analysis in 037's hardened tier with the requester's repository
mounted **read-only** and the platform's tree unmounted, and splits the run into two postures:
the step that reads hostile content holds no credential that could publish, and the step that
publishes never reads the subject. That separation is 037's specimen/observer split arriving
for the same reason, and it makes FR-015's containment a fact about allocations rather than a
promise about a ceiling.

**Proposing and qualifying** (US2, US5) delivers the work as a pull request through a
non-repeatable pack tool with an observer — which hands FR-009 and the interrupted-run edge
case a mechanism that already exists — under a `write` cell qualified against a corpus whose
floor **fails rather than warns** and whose two correctness gates are **reported separately**.

**The platform does not enact what it authored.** Not as a capability restriction —
`terraform_apply` is untouched — but as provenance: `ARTIFACT_AUTHORED` records what the
platform produced, and enactment consults it.

## Technical Context

**Language/Version**: Python 3.12 (matches repository)

**Primary Dependencies**: **none new in `core`.** The workspace is `pathlib`; digests are
`hashlib`; the diff is `difflib` from the standard library. The one genuinely new external
dependency is a **credential path to a version-control host** (R9), which is a Vault-vended
short-lived credential rather than a library. CI gains the `terraform` binary and a pinned
provider mirror for the first correctness gate (R10) — a tool the lane runs, not a dependency
the tree imports.

**Storage**: none new. The workspace is ephemeral per run; authored artefacts live in the
proposal and their digests in the existing audit trail.

**Testing**: pytest — conformance rows in `tests/conformance/authoring/` (new), component
suites for the workspace/containment/proposal stages, unit gates for the structural properties
(ceiling disjointness, tier posture, provenance), and the `write` role's qualification scored
as its own corpus.

**Target Platform**: unchanged (macOS dev, Linux CI/Nomad). The analysis step is the existing
hardened-tier Nomad job with a read-only subject mount added.

**Project Type**: single project. New: `src/core/authoring/`, `src/core/isolation/` (the tier,
moved — R3), `packs/github/`, `evals/authoring/`.

**Performance Goals**: cost tracks the **task**, not the repository. A repository too large to
analyse in full is truncated and the truncation is **disclosed in the proposal** (FR-005b) — a
bounded read that says so, never a silent partial.

**Constraints**: `invoke_tool` stays the sole execution entry; the platform's tree stays
unmounted; **the authoring tier's egress allowlist is EMPTY and static** — the subject arrives as
a mount, so this step fetches nothing, and inheriting 037's `github.com` would hand a redirected
agent the one allowlisted host that serves arbitrary user content (R13); the proposal is bounded
to the change structurally for files and by inspection for prose; `OWED` stays empty; the audit
schema grows, so Principle V review; ADR-0062 carries the new credential class and Principle IV
is amended alongside it.

**Scale/Scope**: **one pack declares an authoring workflow today** — `terraform`
(`author-module`, `minimum_tier = 2`, `paved = false`). Vault declares none. The feature must
be correct for one and must not assume a population, which is 037's R2 lesson arriving again.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Authoring assembles what exists — the registry's unused `write` class, the matrix's unbound `write` role, 037's tier, 036's governed loop, the non-repeatable/observer bracket. What is genuinely new is the **corpus**, which is content rather than product, and which ADR-0038 predicted would be "real work". No editor, no VCS product, no diff engine — `difflib` is in the standard library. |
| II — Total Interception; One Governed Tool Layer | **Pass** | `author_file` and `open_proposal` are ordinary registered tools reaching execution through `invoke_tool`. Code mode is unchanged: a program that writes a file does so by calling the write tool, which round-trips the seam like every other call. Transport for `open_proposal` is decided by ADR-0037's standing test at registry review and recorded on the entry (R6). **Northbound: no new operation.** An authoring request is the payload of an ordinary dispatched run, so surface parity is **inherited rather than owed** (R16) — and a row asserts the inheritance is real, because an absent parity row and a deliberately-inherited one look identical in a diff and only one is a gate regression. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Every gate refuses: an unqualified `write` cell (`resolve_with_fallback` has no third branch), a non-hardened posture (`assert_tier` by clause), a secret or unrelated content heading into an artefact (`CONTAINMENT_REFUSED`), a repository the requester does not own, an enactment of platform-authored content. The corpus floor **fails rather than warns** (FR-018b). |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, with a CONSTITUTION AMENDMENT** | Every step authenticates as its own attested workload identity, and the publishing credential is Vault-vended, hour-scoped and installation-scoped to the requester's own repositories. **But Principle IV enumerates "exactly two named exceptions" and this is a third** (R15) — so the principle is **amended in the same change**, on 027's precedent, with ADR-0062 as its motivating record. The exception inherits the other two's conditions: rotated, Control-Group-governed, trust-store only, read under the reading workload's own attested identity, delivered per task, never persisted. Arguing the clause does not bite (the platform does not *manage* the requester's repository) was available and is the narrowing 027 declined — **a closed list that grows by interpretation is not a closed list**. The key is never mounted into the hardened tier: the step that reads hostile content cannot publish. |
| V — Sealed Core, Versioned Seams | **Pass, with review** | Four additive `AuditEventType` members (`ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`, `ENACTMENT_REFUSED`) on `TOOL_CHOSEN`'s precedent, carrying the approved spec and security-maintainer review. **`RiskClass` and `Role` are not edited** — `write` already exists in both (R1), which is the whole payoff of vocabulary defined in advance. |
| VI — Lean by Default | **Pass** | **No new operated component.** A pack is content; a workspace is a directory; the analysis step is the existing tier job with a mount added. The one genuinely operated thing is the version-control credential path, which is an integration rather than a service and is named in ADR-0062. |
| VII — Anti-Fragmentation | **Pass** | One authoring path for every product: the same `author_file`, the same containment, the same proposal shape whether the artefact is a Terraform module or application code. **This is why the write tool is a platform tool rather than a pack tool** (R2) — a per-pack copy would be N implementations of one containment rule. The tier moves out of `core.intake` for the same reason (R3). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass, with obligation** | The `write` cell is qualified **before** a definition may bind it, and the corpus lands **in the same change** as the capability so `OWED` stays empty (FR-019, 037's sequencing precedent). Correctness is two gates reported separately (FR-018a); the must-deny half scores the **artefact**, not a verb (R8). **The new `github` pack declares the five suites with their cases**, like both existing packs — measured (R14), the loader's floor iterates *declared* suites, so a pack declaring none has no floor to fail and would be this platform's first pack outside the eval gate, first **by accident**. |
| IX — Evidence Over Claims | **Pass** | The proposal is the product and the trail is behind it. Two load-bearing rules: `CONTAINMENT_REFUSED` carries **codes and digests, never the matched text** (`CANARY_CONTACT`'s rule — the record of a leak must not be a second copy of what leaked), and `ARTIFACT_AUTHORED` carries **paths and digests, not content**. |
| X — The Decision Record Governs | **Pass, with obligations** | **ADR-0038 is realized rather than amended** — it is already Accepted, and its four constraints are implemented as written, not reinterpreted. **ADR-0062 is new** (Proposed here, Accepted in implementation) because a new credential class under a MUST principle is exactly what the record is for. |

**Gate result**: **PASS — proceed to Phase 0.** Five obligations travel with the feature: the
Principle V review, **the Principle IV amendment naming a third standing-credential exception**,
ADR-0062's authoring, the `write` corpus landing with the capability, and the tier's move out of
`core.intake`.

## Project Structure

### Documentation (this feature)

```text
specs/038-authoring-workflows/
├── plan.md              # This file
├── research.md          # Phase 0 — what was measured, and the five findings that moved the plan
├── data-model.md        # Phase 1 — artefacts, workspaces, proposals, provenance, corpus
├── quickstart.md        # Phase 1 — how to prove each layer, including that it can refuse
├── contracts/
│   ├── conformance-authoring.md    # producing, containing, not being redirected
│   └── conformance-proposal.md     # proposing, provenance, qualification
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/core/isolation/           # NEW — MOVED from core/intake/tier.py (R3)
└── tier.py                   #   + SubjectMount: read-only subject passes, writable fails.
                              #   `repo_mounted` keeps its name and its meaning (the PLATFORM's
                              #   tree), so 037's merge-blocking row is untouched.

src/core/authoring/           # NEW — product-blind, like the rest of core
├── request.py                # the authoring request: requester, target repository, task, pack.
│                             #   The dispatch payload — NOT a new northbound operation (R16)
├── credential.py             # the publishing credential: attested identity → Vault → an
│                             #   hour-scoped, installation-scoped token. Here rather than in
│                             #   `core/durability/` so a new credential class does not widen
│                             #   sealed core beyond the four audit members
├── workspace.py              # the writable workspace; the subject is read-only and elsewhere
├── artifact.py               # authored paths + per-file digests; what ARTIFACT_AUTHORED carries
├── containment.py            # FR-010–013b. STRUCTURAL for files (the workspace is the only
│                             #   source), INSPECTED for prose (verbatim spans from untouched
│                             #   subject files). Two functions, because they hold for
│                             #   different reasons and one must not read as covering both.
├── proposal.py               # files created + diffs of files edited; body composed from
│                             #   structured fields; truncation disclosed (FR-005b)
├── provenance.py             # FR-020b — platform-authored digests, checkable AT enactment
└── tool.py                   # `author_file`, risk_class="write" — the registry's first

src/core/evals/
├── suites.py                 # + AUTHORING_QUALIFICATION. NOT in SUITES (R7); OWED untouched
├── authoring_corpus.py       # NEW — golden tasks, human-authored references, must-deny;
│                             #   floor FAILS rather than warns
└── authoring_scoring.py      # NEW — the two gates, scored and reported SEPARATELY

src/core/audit/schema.py      # additive: ARTIFACT_AUTHORED, PROPOSAL_OPENED,
                              #           CONTAINMENT_REFUSED, ENACTMENT_REFUSED
packs/github/                 # NEW — one tool: `open_proposal`, write, non-repeatable,
├── pack.toml                 #   observer required. Transport per ADR-0037 at registry review.
│                             #   Declares a PROBE (a product with none refuses at load) and the
│                             #   five eval suites (a pack declaring none has no floor to fail)
└── evals/*.toml              #   5 cases per suite, on both existing packs' precedent
evals/authoring/              # NEW — the corpus. Every golden task carries a HUMAN-AUTHORED
                              #   reference (FR-018c) — the expensive clause, and the one most
                              #   likely to erode into generated references
infra/jobs/authoring-tier.nomad.hcl  # NEW — the hardened tier with a READ-ONLY SUBJECT MOUNT
                              #   and an EMPTY egress allowlist. Its own jobspec so the value
                              #   stays static per job rather than becoming per-run (R13)
.specify/memory/constitution.md      # AMENDED — Principle IV names a third exception (R15)
docs/adr/0062-*.md            # NEW (Proposed) — the authoring credential class
tests/
├── conformance/authoring/    # both contracts
├── component/                # workspace, containment, proposal, corpus floor
└── unit/                     # structural: ceiling disjointness, tier posture, provenance
```

**Structure Decision**: authoring lives in `core/` and is **product-blind** — it knows about
workspaces, diffs and digests, not about Terraform or HCL. The **write tool is a platform
tool** and the **proposal tool is a pack tool**, which is not an inconsistency: producing a
file is the same act for every product, while reaching a version-control host is a product
integration with a transport determination under ADR-0037.

Layering **Producing → Containing → Proposing/Qualifying** is deliberate: the layer that can
carry private code out lands only once the layer that bounds it exists, and the capability
never exists ahead of the qualification that gates it.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed; three were sharpened by design decisions:

- **III** — R5 turned FR-013's file half from a rule to enforce into a property that cannot be
  violated: the proposal is built from the workspace, so a file the agent never wrote has no
  route into it. The prose half stayed a check, and the data model keeps them as two functions
  rather than one, so nobody later reads the strong half as covering both.
- **IV** — R9 moved the credential from an assumption into a decision record. The design
  consequence that came with it is the better half: **analysis and proposal became different
  steps in different postures**, so FR-015's containment is now a fact about which allocation
  holds what rather than an assertion about a ceiling.
- **IX** — the data model gives `CONTAINMENT_REFUSED` its own member carrying codes and
  digests rather than a field on the artefact record, because a refusal that quoted what it
  caught would be the exfiltration channel it exists to close.

**What the first analyze pass found, recorded here so it is not re-derived.** Four CRITICALs
and five HIGHs, and they cluster into two shapes rather than nine independent mistakes.

The first shape is **assert-over-something-nothing-builds**, which is the same defect 036 and
037 each found and which this plan's own task header warned about — then repeated, because the
warning was applied to *contract rows* and not to *entities and records*. Three instances: the
authoring request (asserted by an ownership refusal, built by nothing), the ADR-0062 credential
path (authored and consumed, never implemented), and the analysing/proposing definitions (their
ceilings asserted disjoint, neither created).

The second shape is **a control checked on the wrong axis**. The egress allowlist was reasoned
about for its *mutability* — the property FR-005a names — and never for its *contents*. A
control can be correctly immutable and wrongly valued, and only the first was checked. Inheriting
037's `github.com` would have left a redirected agent, holding a private codebase, with a network
route to the one allowlisted host that serves arbitrary user content, while every ceiling
assertion in the feature still passed.

**Two constitution findings came with them**: Principle IV's exception list is closed at two and
this is a third (R15), and Principle II's parity gate needed the inheritance stated rather than
assumed (R16). Neither was visible from the artefacts alone — both required reading the
constitution's text and the loader's code against the plan.

**One risk moved into the record rather than being resolved**: R10's first correctness gate
depends on `terraform init` reaching a pinned provider mirror from CI. If that proves
unreachable, the correct outcome is a **failing** gate and a recorded deferral — never a gate
that silently degrades to `fmt`-only while still reporting "validated". That is ADR-0047's
passing stub in the exact costume it would wear here, and tasks must not leave room for it.

**Two things flagged for analyze**, both from the spec's own checklist notes: **US3 is the
sharpest tension** in the feature (analysing a private repository and then publishing *is* a
channel out of the isolation, by design), and **FR-018c** — every golden task carrying a
human-authored reference — is the requirement most likely to be satisfied by generated
references, which would measure the generator against itself.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **A third standing-credential exception**, against Principle IV's enumerated list of exactly two | A run that opens a pull request must authenticate as something. 037's precedent does not transfer: its proposal is opened by **CI**, which holds a token by virtue of being CI; a run holds nothing | **A personal access token** is the usual fix and is the standing credential Principle IV refuses — 033 already declined it and recorded the consequence rather than acquiring one. **Opening the PR from CI** would move the act outside `invoke_tool`, making the platform's own publication the one thing it does not govern (Principle II). **Arguing the enumeration does not bite** — the platform does not *manage* the requester's repository — was available and is the narrowing 027 declined; a closed list that grows by interpretation is not a closed list. So the principle is **amended in the open**, on 027's precedent, with ADR-0062 as the motivating record |
| **A second hardened-tier jobspec** (`authoring-tier`), where one job could have served both callers | The two callers need **different egress**: 037's analyser fetches a pinned upstream and needs `github.com`; 038's reads a mount and needs nothing. One job cannot hold two static values | **Reusing 037's job** keeps `github.com` open for a step that fetches nothing, which is R13's finding. **Parameterising the allowlist per run** would satisfy the security concern and break FR-005a — a computed allowlist makes the tier's posture a property of each dispatch rather than of the job, and row A0 checks the posture structurally |
| **A second module tree** (`core/isolation/`) for one file moved out of `core/intake/` | The tier now has two consumers and neither owns it. `core.authoring` importing `core.intake` would encode that authoring is part of the supply chain, which is false and would eventually be relied upon | **Leaving it in `core.intake`** costs nothing today and one wrong dependency forever; **duplicating it** is the fragmentation Principle VII forbids, and two copies of an isolation check would eventually disagree about what "hardened" means |

ADR-0062 carries the first, alongside the Principle IV amendment. The third is mechanical and
changes no behaviour — 037's two conformance files update their import and nothing else.
