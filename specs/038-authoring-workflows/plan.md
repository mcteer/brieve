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
mounted **read-only** and the platform's tree unmounted, and splits the run into two postures —
**one job, one group, two SEQUENTIAL tasks sharing the allocation directory** (R24, R27). The
`analyzer` task holds no credential that could publish and runs everything that needs the
subject — reading, authoring, composing and containment. The `proposer` task never mounts the
subject and does one thing: publish an already-contained proposal.

**One run means one definition and one ceiling**, so the separation is **task scope** rather
than disjoint ceilings: each task declares its own `RUN_REQUESTED_TOOLS`, and `intersect_scopes`
narrows the shared ceiling per task (R31). That is Principle IV's own mechanism — *"effective
authority = user ∩ agent ceiling ∩ task scope ∩ policy"* — already built and already enforced at
the authority hook, so FR-015 holds verbatim rather than being reworded to fit.

They are sequential rather than concurrent because concurrent tasks would race on the checkpoint
and because the capability split assumes ordering. A
`prestart` lifecycle makes the handoff a baton: the analyzer checkpoints and exits, the proposer
loads the blob, re-authenticates under its own identity, and continues. It **continues rather than
resumes** — `resume_run` counts attempts against a cap that exists to stop flapping runs, and a
planned handoff must not spend it (R35); the continuation therefore also re-manufactures authority,
which is the thing `resume_run` was otherwise doing (R37).

**And the lifecycle is the only control**: `holder_identity` derives from `NOMAD_ALLOC_ID`, which is
per-allocation, so the two tasks are one holder and the lease would **not** fence a concurrent
arrangement — it would let both through to race on the checkpoint. R27 said otherwise and is
corrected. **One allocation means one run and
one correlation ID**, which is what Principle IX requires and what two allocations would have
broken.

The **network namespace is shared**, and that is stated rather than glossed. What contains the
analyzer is: nothing egressing in its **effective scope**, no credential in its task, and a
declared empty allowlist. Three controls, not four.

**Proposing and qualifying** (US2, US5) delivers the work as a pull request through a
non-repeatable **platform** tool with an observer — which hands FR-009 and the interrupted-run edge
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
short-lived credential rather than a library. The first correctness gate runs in the **enclave
lane, which already installs the binary** (`install_hashicorp terraform`) — a precedent R10
never measured; what it adds is a `.terraform.lock.hcl` with the providers **cached in CI keyed on
that file** — determinism comes from the lock, not from committing binaries (R33).

**Storage**: none new. The workspace is ephemeral per run; authored artefacts live in the
proposal and their digests in the existing audit trail.

**Testing**: pytest — conformance rows in `tests/conformance/authoring/` (new), component
suites for the workspace/containment/proposal stages, unit gates for the structural properties
(task-scope narrowing, tier posture, provenance), and the `write` role's qualification scored
as its own corpus.

**Target Platform**: unchanged (macOS dev, Linux CI/Nomad). The analysis step is the existing
hardened-tier Nomad job with a read-only subject mount added.

**Project Type**: single project. New: `src/core/authoring/`, `src/core/isolation/` (the tier,
moved — R3) and `evals/authoring/`. **No `packs/github/`** — R29 withdrew it.

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
| II — Total Interception; One Governed Tool Layer | **Pass** | `author_file` and `open_proposal` are ordinary registered tools reaching execution through `invoke_tool`. Code mode is unchanged **and is not on the path this feature ships**: measured, `run_program` is registered nowhere (R19), so a program that writes a file does so through the seam in conformance rows rather than in a running definition. The seam's guarantee is asserted; the production path is 036's to complete, and this feature must not claim it. Transport for `open_proposal` is decided by ADR-0037's standing test at registry review and recorded on the entry (R6). **Northbound: no new operation.** An authoring request is the payload of an ordinary dispatched run, so surface parity is **inherited rather than owed** (R16) — and a row asserts the inheritance is real, because an absent parity row and a deliberately-inherited one look identical in a diff and only one is a gate regression. |
| III — Fail-Closed, In-Process Enforcement | **Pass, with two registrations** | Every gate refuses: an unqualified `write` cell (`resolve_with_fallback` has no third branch), a non-hardened posture (`assert_tier` by clause), a secret or analysed content heading into an artefact (`CONTAINMENT_REFUSED`), a repository the requester does not own, an enactment of platform-authored content. The corpus floor **fails rather than warns** (FR-018b). **The provenance refusal and the injection lens are `GOVERNANCE`-kind `HookRegistration`s, not module functions** — the first two drafts placed both in modules a caller must remember to call, which reads identically in a task list and is not enforcement (R23). The lens attaches to a registered `read_subject` tool, because a read-only mount read by ordinary file access offers no hook to attach to. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, with a CONSTITUTION AMENDMENT** | Every step authenticates as its own attested workload identity, and the publishing credential is Vault-vended, hour-scoped and installation-scoped to the requester's own repositories. **But Principle IV enumerates "exactly two named exceptions" and this is a third** (R15) — so the principle is **amended in the same change**, on 027's precedent, with ADR-0062 as its motivating record. The exception inherits the other two's conditions: rotated, Control-Group-governed, trust-store only, read under the reading workload's own attested identity, delivered per task, never persisted. Arguing the clause does not bite (the platform does not *manage* the requester's repository) was available and is the narrowing 027 declined — **a closed list that grows by interpretation is not a closed list**. The key is never mounted into the hardened tier, and **task scope narrows the shared ceiling per task** so the analysing half's effective authority carries nothing that egresses — Principle IV's own user ∩ ceiling ∩ task scope ∩ policy, used as intended (R31). |
| V — Sealed Core, Versioned Seams | **Pass, with review** | Four additive `AuditEventType` members (`ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`, `ENACTMENT_REFUSED`) on `TOOL_CHOSEN`'s precedent, carrying the approved spec and security-maintainer review. **`RiskClass` and `Role` are not edited** — `write` already exists in both (R1), which is the whole payoff of vocabulary defined in advance. |
| VI — Lean by Default | **Pass** | **No new operated component.** A pack is content; a workspace is a directory; the analysis step is the existing tier job with a mount added. The one genuinely operated thing is the version-control credential path, which is an integration rather than a service and is named in ADR-0062. |
| VII — Anti-Fragmentation | **Pass** | One authoring path for every product: the same `author_file`, `read_subject` and `open_proposal`, the same containment, the same proposal shape whether the artefact is a Terraform module or application code. **All three are platform tools rather than pack tools** — a per-pack copy would be N implementations of one containment rule (R2), and **publishing is as product-blind as authoring** (R29): a pull request against a Terraform module and one against application code are the same act. The tier moves out of `core.intake` for the same reason (R3). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass, with an ADR** | The `write` cell is qualified **before** a definition may bind it, and the corpus lands **in the same change** as the capability so `OWED` stays empty (FR-019, 037's sequencing precedent). Correctness is two gates reported separately (FR-018a); the must-deny half scores the **artefact**, not a verb (R8). **Both gates are MECHANICAL** — the reference carries a declared property set, and the must-deny half is the secret detector, the containment check and a byte-identical comparison — so **no judge participates**, and `promote_model_version` would refuse the cell for naming none (R18). It accepts a **scorer identity** instead, refusing only when both are absent: a human-authored reference terminates ADR-0052's regress *one link earlier* than a judge does. **ADR-0063** carries that. `qualified_by = "live"` (R20), because the matrix module says the fixture/live distinction *"matters most for `write` — a model permitted to make changes"*. **No `github` pack exists to gate.** R14 correctly found that a pack declaring no suites escapes the floor entirely, and prescribed declaring all five — which was the wrong cure: the suites are answering-shaped, and a pack carrying one PR-opening tool has **no expertise for them to measure** (R29). Twenty-five cases written to clear a floor is the "gate that passes by vocabulary" 027 refused, so `open_proposal` becomes a platform tool and the pack is withdrawn. |
| IX — Evidence Over Claims | **Pass, with a payload gate** | The proposal is the product and the trail is behind it. **One correlation ID**, because authoring and publishing are two tasks in one allocation rather than two runs (R24). Two load-bearing payload rules: `CONTAINMENT_REFUSED` carries **codes and digests, never the matched text** (`CANARY_CONTACT`'s rule — the record of a leak must not be a second copy of what leaked), and `ARTIFACT_AUTHORED` carries **paths and digests, not content**. **Those rules are now asserted rather than documented**: `append_event` takes `dict[str, Any]` and validates nothing, and `redact_arguments` runs on tool arguments and never on event payloads — so every such rule in this feature was a convention, while `InjectionFinding` carries an `excerpt` that would have made copying analysed private code into an append-only store the *default* implementation (R26). |
| X — The Decision Record Governs | **Pass, with obligations** | ADR-0038's four safety constraints are implemented as written, not reinterpreted — but **one clause is amended rather than departed from**: *"Version control becomes a first-class pack tool target"* does not survive contact with the eval gate (R29), so **ADR-0064** records version control as a platform capability, with ADR-0037's transport test still applying at registry review (that test is about *transport* and is orthogonal to where a tool lives). **Three new records**: **ADR-0062** (a new credential class under a MUST principle), **ADR-0063** (what may qualify a cell, amending ADR-0052's chain — R18), **ADR-0064**. All Proposed here, Accepted in implementation. |

**Gate result**: **PASS — proceed to Phase 0.** Seven obligations travel with the feature: the
Principle V review, **the Principle IV amendment naming a third standing-credential exception**,
ADR-0062, ADR-0063 and **ADR-0064** authored and accepted, the `write` corpus landing with the
capability, and the tier's move out of `core.intake`.

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
├── containment.py            # FR-010–013b. TWO CLAIMS OF DIFFERENT STRENGTH, and conflating
│                             #   them is how the second went missing for two drafts:
│                             #   STRUCTURAL over which PATHS appear (the workspace is the only
│                             #   source), INSPECTED over what those paths CONTAIN — authored
│                             #   bytes, diff additions AND prose. An authored file is
│                             #   agent-controlled content; the earlier "not expressible"
│                             #   claim was earned for paths and false for bytes (R21)
├── proposal.py               # files created + diffs of files edited; body composed from
│                             #   structured fields; truncation disclosed (FR-005b)
├── provenance.py             # FR-020b — platform-authored digests, checkable AT enactment
├── hooks.py                  # the two GOVERNANCE-kind HookRegistrations: the provenance
│                             #   refusal (PRE) and the injection lens (POST). A refusal in a
│                             #   module and a refusal in the pipeline read alike in a task
│                             #   list, and only one is enforcement (R23)
└── tool.py                   # THREE platform tools. `author_file` (write) — the registry's
                              #   first occupant of that class. `read_subject` (read) — what
                              #   the lens attaches to, and the read path FR-014/FR-005b/FR-004
                              #   were all written against and none of them had. `open_proposal`
                              #   (write, non-repeatable, observer) — a platform tool because
                              #   publishing is as product-blind as authoring (R29); the
                              #   observer_required refusal is a MANIFEST check, so this
                              #   registration asserts it itself

                              # NO bespoke state carrier: the analyzer CHECKPOINTS and the proposer
                              #   LOADS AND CONTINUES on the existing durability seam (R32, R35).
                              #   Principle V seals durability and a second mechanism in a feature
                              #   module is Principle VII's fragmentation — but `resume_run` is NOT
                              #   called: it counts attempts against RESUME_ATTEMPT_CAP, and a
                              #   planned handoff must not spend a budget that exists to stop
                              #   flapping runs. A row pins `resume_count == 0`

docs/adr/0064-*.md            # NEW (Proposed) — version control is a platform capability,
                              #   amending ADR-0038's "pack tool target" clause

src/core/evals/
├── suites.py                 # + AUTHORING_QUALIFICATION. NOT in SUITES (R7); OWED untouched.
│                             #   + AUTHORING_REQUIRED_SUITES — what `promote_model_version`
│                             #   checks a `write` cell against, declared beside the constant
│                             #   that excludes it so both are read together (R20)
├── promotion.py              # `promote_model_version` accepts a SCORER identity where a judge
│                             #   would go, refusing only when both are absent (R18, ADR-0063)
├── authoring_corpus.py       # NEW — golden tasks, human-authored references carrying a
│                             #   DECLARED PROPERTY SET, must-deny; floor FAILS rather than warns
└── authoring_scoring.py      # NEW — the two gates, both MECHANICAL, reported SEPARATELY

src/core/audit/schema.py      # additive: ARTIFACT_AUTHORED, PROPOSAL_OPENED,
                              #           CONTAINMENT_REFUSED, ENACTMENT_REFUSED
                              # NO `packs/github/` — WITHDRAWN (R29). The eval suites are
                              #   answering-shaped and a pack with one PR-opening tool has no
                              #   expertise for them to measure; `open_proposal` is a platform
                              #   tool beside `author_file`. ADR-0064 records the amendment
evals/authoring/              # NEW — the corpus. Every golden task carries a HUMAN-AUTHORED
                              #   reference (FR-018c) — the expensive clause, and the one most
                              #   likely to erode into generated references
infra/jobs/authoring-tier.nomad.hcl  # NEW — ONE GROUP, TWO TASKS sharing /alloc/data (R24):
                              #   `analyzer` (read-only subject mount, EMPTY egress allowlist,
                              #   no credential) and `proposer` (no subject mount, VCS
                              #   credential). Identity/env/mount are per-task; the network
                              #   namespace is SHARED and the plan says so. Its own jobspec
                              #   rather than 037's, so the allowlist stays static per job
                              #   rather than becoming per-run (R13) — sibling to
                              #   analysis-tier.nomad.hcl, and each names the other
.specify/memory/constitution.md      # AMENDED — Principle IV names a third exception (R15)
docs/adr/0062-*.md            # NEW (Proposed) — the authoring credential class
docs/adr/0063-*.md            # NEW (Proposed) — a mechanical scorer over a human-authored
                              #   reference may qualify a cell (amends ADR-0052's chain)
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

- **III** — R5 turned FR-013's **path** half into a property that cannot be violated: the
  proposal is built from the workspace, so a file the agent never wrote has no route into it.
  **That claim was then over-extended to the artefact as a whole and was wrong** (R21) — an
  authored file is agent-controlled bytes, and its contents were scanned by nothing for two
  drafts. Containment is now two claims of different strength, and the scan covers the whole
  proposal. A guarantee that is genuinely airtight over a narrow subject is the easiest kind to
  over-generalise: the confidence transfers and the reasoning does not.
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

**The second analyze pass found a third shape, and it is the one to carry forward.** Where pass
one found things nothing built, pass two found **things built against the wrong subject** — a
mechanism named correctly and assumed to do something it does not. The observer was handed an
idempotency key and the branch was derived from a correlation ID, so it could never have looked
(R17). The correctness gate was mechanical all along and `promote_model_version` refuses a cell
naming no judge, so the cell could never have been promoted (R18). And two mechanisms this plan
cited — `run_program`'s registration and `reachable_tools` — are **not on the path it claimed**:
one is registered nowhere, the other is called from tests only (R19).

That last pair is this repository's own recorded lesson — *a green row proves the mechanism, not
that the running service can reach it* — and both arrived here by **citation rather than
measurement**. Naming a real module is not evidence that anything calls it, and the plan treated
it as though it were.

**The third pass found a fourth shape: a claim that outgrew its argument.** The two-tree design
genuinely makes the *file set* unforgeable, and that strength was written up as containment
being *"not expressible"* — a sentence true of paths and false of the artefact's bytes, repeated
across three documents (R21). Nothing stopped an agent writing what it read into a file it did
create. **The confidence transferred and the reasoning did not**, which is the failure mode to
watch for wherever a design earns a strong guarantee over a narrow subject.

Its companion was structural in a different way: **nothing in this feature was going to run
inside the hook pipeline** (R23). Two refusals sat in modules a caller must remember to call,
and both passes had checked *whether* a refusal existed rather than *where it would run*. The
fix surfaced a requirement none of the artefacts had noticed — the injection lens needs a
governed **read path** to attach to, which FR-014, FR-005b and FR-004 were all written against
and none of them had.

**The fourth pass audited the remediations rather than the plan, and that is where it found
things.** All three of its significant findings descend from R9's two-posture split — a fix
introduced in pass two and never re-examined. It had **no handoff** (the artefact could not
reach the step that publishes it), it implied **two correlation IDs** where Principle IX
requires one, and it left the tier's mount source **per-dispatch and unvalidated** so a dispatch
naming the platform's own tree satisfied every clause. One job with two tasks resolves the first
two together (R24); a validated, asserted mount source resolves the third (R25).

**A remediation is a design change and deserves the scrutiny the design got.** Three passes
treated earlier fixes as settled while re-examining the original plan, and the defects had
migrated into the fixes. The recurring instance is worth naming on its own: **three separate
controls in this feature were checked for the property they named and not for the value they
would hold** — the egress allowlist (R13), the containment claim (R21), and now `repo_mounted`
(R25). A declaration is only as good as whatever validates it.

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
