# Research: The agent authors, and a person merges

**Feature**: 038 | **Date**: 2026-08-05

Measured against merged main, each finding named so it can be re-checked when something
moves. The five that changed the plan are **R3** (the tier refuses the mount FR-005
requires), **R5** (the read-only mount is what makes FR-013a decidable), **R7** (the `write`
qualification must not join `SUITES`), **R9** (opening a pull request needs a credential
Principle IV has no pattern for yet) and **R10** (the product-tooling gate cannot run where
the analysis runs).

## R1 — The vocabulary is genuinely unoccupied, and no sealed-core edit is needed to occupy it

**Measured**: `src/core/registry/memory.py:27` — `RiskClass = Literal["read", "write",
"destructive", "secret_touching"]`, and `grep '"write"' src/core/registry` returns the
literal and nothing else. `src/core/authority/matrix.py:36` — `Role = Literal["ask", "plan",
"write", "judge", "summarize"]`, with `ROLES` the same five. `validate_binding_map` already
refuses a definition binding `write` to a cell qualified for another role, and its error
message uses `vault:anthropic/claude@1:write` as its worked example.

**Decision**: this feature *occupies* both, and edits neither. A tool registers with
`risk_class="write"` through the ordinary `ToolRegistry.register` path; a definition binds
`write` in its `binding_map` through the ordinary matrix path.

**Rationale**: worth stating because the opposite would have been a Principle V change to two
sealed modules on a feature that already carries an audit-schema review. The vocabulary was
defined in advance precisely so the first occupant would not have to widen anything, and that
foresight holds up under measurement.

## R2 — `run_program` is the precedent for a platform-registered tool, so authoring does not need a pack to exist

**Measured**: `core/sandbox/program_tool.py` registers `run_program` as an ordinary tool and
records why — *"the registry is the opt-in switch. A definition whose ceiling does not
include `run_program` has no code mode."* Every other registered tool today comes from a pack
manifest via `core/packs/registration.py`.

**Decision**: **`author_file` is a platform tool, not a pack tool.** Producing file content is
not product knowledge — a Terraform module and a Vault integration are written by the same
act — and putting it in a pack would give each pack its own copy of the containment rules
FR-013 makes structural.

**What still gates it, three independently**: the **ceiling** decides whether a definition may
call `author_file` at all; the **pack's declared workflow** (`author-module`, already in
`packs/terraform/pack.toml`) decides whether authoring is offered for that product; the
**tier** decides where the analysis runs. None of the three can widen another —
`assert_pack_does_not_widen` already refuses a pack that tries.

**Alternatives considered**: a per-pack `terraform_author_file` (rejected — N copies of one
containment rule, and the rule is the feature); putting authoring behind `run_program` alone
(rejected — code mode is *how* a model may sequence calls, not *what* it may call; a program
that can write files without a write tool would be exactly the second path to acting FR-002
forbids).

## R3 — The hardened tier as built REFUSES the mount FR-005 requires, and this is the finding that shapes the plan

**Measured**, `core/intake/tier.py`:

```python
if self.repo_mounted:
    return False, "the repository is mounted; the delta must be delivered as input"
```

and `infra/jobs/analysis-tier.nomad.hcl` carries the matching clause — *"NO REPOSITORY MOUNT,
and this is the clause most likely to be 'temporarily' added back for convenience."*
`tests/conformance/intake/test_isolation_tier.py:79` asserts the refusal and is merge-blocking.

**So FR-005 as written does not run today.** A definition requiring the hardened tier with a
repository mounted is refused, by a row built to refuse exactly that.

**Decision**: `repo_mounted` keeps its name and its meaning — **the platform's own
repository** — which is already what 037's jobspec comment says it means (*"a mount would hand
a redirected analyzer the whole tree to read and the packs to write"*). A second field is
added for the subject:

```python
subject_mount: SubjectMount | None = None   # path + read_only
```

`is_hardened()` gains one clause: **a writable subject mount fails.** A read-only subject
mount passes.

**Why this rather than relaxing the existing clause**: the clause 037 wrote is about *the
platform's tree*, and nothing about mounting the requester's repository read-only weakens it.
Relaxing `repo_mounted` would have been the "temporarily added back for convenience" the
jobspec predicted; adding a distinct, narrower field preserves the merge-blocking row
untouched (it passes `repo_mounted=False`, and the new field defaults to `None`) while making
the new property assertable in its own row.

**Consequence for the tier's placement**: `core.intake.tier` now has two consumers and
neither is its owner. `core.authoring` importing `core.intake` would say authoring is part of
the supply chain, which it is not. **The module moves to `core/isolation/tier.py`** with
imports updated in 037's two conformance files — mechanical, and it stops a false dependency
becoming load-bearing. Nothing about the tier's content changes in the move.

## R4 — 037's payload delivery does not survive a repository, and the jobspec says why

**Measured**: `analysis-tier.nomad.hcl` declares `parameterized { payload = "required" }` and
the analysis subject arrives as that payload. A skill delta is kilobytes. A provided
application repository is not.

**Decision**: the subject arrives as a **read-only mount**; the payload carries the request
metadata (target repository, task, correlation ID) as it does today. The **egress allowlist
stays static configuration** (`HARNESS_EGRESS_ALLOWLIST` in the jobspec), per FR-005a.

**Rationale for keeping the allowlist static**: a per-run allowlist would make the tier's
posture a property of each dispatch rather than of the job, and row A0 checks the posture
structurally. A control whose value is computed per run is one nobody can assert about the
tier as such — the property would still exist and would stop being checkable.

## R5 — The read-only mount is what makes FR-013a decidable, which is a benefit rather than a constraint

**Decision**: authored files land in a **writable workspace that is not the subject mount**.
The proposal is computed as the difference between the two.

**Rationale — this is the finding worth the most.** FR-013a demands the containment rule be
enforced *"by inspecting the artifact, not by the agent declining to include things."* With a
read-only subject and a separate workspace, the artifact **is** the set of paths the agent
wrote. A file the agent never wrote cannot appear in the proposal, because the proposal is
built from the workspace and not from the subject. The rule is not checked; it is not
expressible.

That covers the files. **It does not cover the prose**, and FR-013 names the description
explicitly. So the proposal has two halves with two different enforcement stories, and the
plan states which is which rather than letting the strong one imply the weak one:

| Half | Rule | How it holds |
| --- | --- | --- |
| Files and diffs | Only authored paths, plus diffs of edited paths | **Structural** — the workspace is the only source |
| Commit messages, PR title and body | No content from the analysed repository | **Inspected** — composed from structured fields, and the free-text field is scanned for verbatim spans from unedited subject files |

FR-013b holds for free on the structural half: a diff of an edited file carries its
surrounding context because that is what a diff is, and there is no rule to exempt it from.

## R6 — Version control is a pack tool, and non-repeatability gives FR-009 a mechanism that already exists

**Measured**: ADR-0038 — *"Version control becomes a first-class pack tool target, with
transport chosen by the standing test."* ADR-0037's test: MCP where a server exists, is
mature, and is supported; the determination is *"made at registry review, recorded on the
registry entry, and revisited at each recurring review."* `packs/terraform/pack.toml` shows
both halves of the rule in one file — MCP for Terraform because
`hashicorp/terraform-mcp-server` exists, native for Vault because its server is beta.

**Decision**: a minimal `github` pack declaring **one** tool, `open_proposal`, with
`risk_class = "write"`, `repeatable = false`, and an observer — transport recorded at registry
review under ADR-0037's test rather than asserted here from memory.

**Why non-repeatable matters more than it looks**: `ToolRegistration.repeatable=False` already
forces an observer (the loader refuses `observer_required` without one), and `invoke_tool`
already brackets a non-repeatable call in intent/result records so an interruption is
*resolvable by observation rather than by guessing*. That is precisely the spec's edge case
("authoring is interrupted partway") and precisely FR-009 ("a second proposal must not
silently displace an earlier one") — the observer goes and finds out whether the proposal
exists. **No new durability machinery**; the existing bracket is the answer, and this is the
strongest single argument for making the proposal a registered tool rather than a step.

**Alternatives considered**: opening the pull request from CI as 037's poller does (rejected —
037's proposal is emitted by a *scheduled workflow*, and this one is emitted by a *run*, which
must therefore be a governed tool call under Principle II); folding proposal-opening into
`author_file` (rejected — one tool with two risk profiles, and the observer would have nothing
coherent to observe).

## R7 — The `write` qualification must NOT join `SUITES`, and 037 already paid for learning this

**Measured**, `core/evals/suites.py`: `SUITES` is the **per-pack** list; `load_pack_cases`
reads `packs/<pack>/evals/<suite>.toml` and raises `UnrunnableSuite` when absent. 037's first
attempt added `intake_analysis` to `SUITES` and nine existing rows refused it, correctly. The
comment records the reasoning and the resolution — `INTAKE_QUALIFICATION`, one platform
component, qualified once, **and `OWED` stayed empty**.

**Decision**: `AUTHORING_QUALIFICATION`, beside `INTAKE_QUALIFICATION`, and **conditional per
pack** — which is where it differs from intake's, for a reason that must be written down:

* Intake's analyzer is **one platform component**, so it qualifies once, globally.
* A `write` cell is `(pack × model × role)`. Authoring qualification is therefore **per pack**
  — but only for a pack that **declares an authoring workflow**.

So it is neither a global suite nor a one-off. The rule: **a pack declaring an authoring
workflow MUST ship the authoring corpus, refused at load if absent; a pack that declares none
must not be asked for one.** Today that is `terraform` (`author-module`) and not `vault`
(`read-configuration`, `rotate-credential` — neither authors).

**Why not add it to `SUITES` anyway**: it would demand `packs/vault/evals/integration_correctness.toml`
for a capability the Vault pack does not offer, and the machinery would say so through the
rule that already exists — *a gate with no cases must fail rather than pass vacuously*. That
rule was written for a different reason and would catch this one exactly, as it did in 037.

**`OWED` stays empty** (FR-019). The corpus lands in the same change as the capability.

## R8 — The must-deny cases for this role do not fit the existing suite's shape

**Measured**: `EXPECTED_OUTCOMES["must_deny"] = frozenset({"deny"})` — a case is a prompt and
an expected *verb*, scored by a scorer that replays a recording or asks a model.
`ANSWERING_SUITES` and `ESTATE_SUITES` exist because two suites needed a different scorer, and
`MEASURED_SUITES` exists because fidelity needed a different *case shape* entirely.

**Decision**: authoring's must-deny cases score **the artifact**, not a verb, and so they live
in the authoring corpus with their own scorer — the same call `report_fidelity` made when it
declined to squeeze a precision/recall measurement into `expected: str`.

**Rationale**: the failure being measured is *a secret value appearing in produced content*.
That is a property of bytes the agent emitted, not of a refusal it stated. Scoring it as a
verb would qualify a cell that says "I will not do that" and then does it — which is the
distinction between the two gates FR-018a insists on reporting separately, appearing a second
time in the must-deny half.

## R9 — Opening a pull request needs a credential, and Principle IV has no pattern for this one yet

**Measured**: 033's `corpus-refresh` workflow records the constraint verbatim, and
`core/intake/emit.py` carries it into the artifact — *"A PR opened with the default token
triggers no workflows... The usual fix is a personal access token; this platform does not hold
one, because a long-lived credential is exactly what Principle IV refuses."* Every credential
path in the platform today resolves through `core/durability/credentials.py`:
`NomadWorkloadIdentity` logs into Vault as the allocation and takes short-lived credentials.
There is **no** GitHub credential anywhere in `src/`, `infra/` or `.github/`.

**This is the feature's one genuinely unsolved dependency**, and it is not solved by
inheritance: 037's proposal is opened by *CI*, which already holds a token by virtue of being
CI. A run opening a pull request holds nothing.

**Decision**: the plan takes the shape every other credential here takes — **the allocation
authenticates as itself and takes a short-lived credential from Vault** — with the GitHub App
installation token as the concrete instrument (installation tokens are hour-scoped and
installation-scoped, which is the same shape as the database credentials already vended). The
App's private key is held in Vault and never in the platform.

**Recorded rather than assumed**: this is a **new credential class** and Principle IV is a
MUST, so it gets **ADR-0062 (Proposed)**, accepted in the implementation change alongside the
security-maintainer review Principle V already requires. Two things about it are
non-negotiable and belong in the ADR rather than in code review: the App installation is
**scoped to the requester's own repositories** (which is FR-007's enforcement point, not
merely its check), and the key is **never mounted into the hardened tier** — the tier analyses,
and a different, standard-tier step proposes.

**That last point has a design consequence worth naming**: analysis and proposal are
**different steps in different postures**. The step that reads hostile content holds no
credential that could publish; the step that publishes never reads the subject. FR-015's
containment ("the ceiling contains nothing that could carry a redirection outside the run")
becomes a fact about which allocation holds what, rather than a promise about a ceiling — the
same specimen/observer separation 037 reached for the same reason.

## R10 — The product-tooling gate cannot run where the analysis runs, and Terraform is not deployed here

**Measured**: `packs/terraform/pack.toml` — *"Terraform is not deployed in the enclave, so this
pack's TOOL layer is fixture-backed and the record says so."* `surfaces/handlers.py` — *"The
Terraform handlers are fixtures."* And the hardened tier's egress allowlist is `github.com`
alone, so a provider download inside the tier is not reachable.

**Decision**: FR-018's **first gate runs in CI**, not in the enclave and not in the tier —
`terraform fmt -check` plus `terraform validate` against a pinned provider mirror. **If it
cannot run, it fails** (`UnrunnableSuite`'s discipline, and 012's twice-learned lesson that a
lane which skips reads as green).

**The distinction that makes this honest**: "Terraform is not deployed" means there is no
Terraform *estate* here — no state backend, no provider credentials, no infrastructure. It
does not mean the *binary* is unavailable to CI. Validating a module needs the binary and the
providers; it does not need an estate. Those are different claims and the pack's own comment
already separates a pack's eval status from its tool reachability.

**Named as the plan's main operational risk**: `terraform validate` requires `terraform init`,
which requires providers. A pinned provider mirror is the answer and it is real work. If it
proves unreachable in CI, the correct outcome is a **failing** gate and a recorded deferral —
never a gate that quietly degrades to `fmt` alone while still reporting "validated", which is
ADR-0047's passing stub wearing the right clothes.

## R11 — What FR-020b needs, and where the check has to sit

**Measured**: `terraform_apply` is `risk_class = "destructive"`, `repeatable = false`, with
`terraform_apply_observer`. Nothing anywhere records *who wrote* the content a tool acts on.

**Decision**: two layers, because either alone fails a different way.

1. **Structural** — the authoring definition's ceiling contains no enacting tool, and the
   proposing step's ceiling contains no authoring tool. Nothing to check because nothing is
   reachable. This is what SC-009 ("no sequence of platform actions results in a merge or an
   apply") is asserted against.
2. **Provenance** — `ARTIFACT_AUTHORED` records the content digests the platform produced, and
   enactment consults it. This exists because the structural layer is a fact about *today's
   definitions*, and FR-020b asks for a rule that survives a definition somebody writes later.

**Why the second layer is not redundant**: the rule turns on provenance, and provenance that
is only *inferable* from which definition happened to run is not checkable at the moment of
enactment — it is reconstructible afterwards, which FR-020b specifically excludes.

## R12 — Four audit members, and one of them must not quote what it describes

**Decision**: `ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`,
`ENACTMENT_REFUSED` — additive `AuditEventType` members on the precedent `TOOL_CHOSEN` set and
037's four followed, carrying the Principle V review.

**The one that needs care**: `CONTAINMENT_REFUSED` fires when a secret value or unrelated
analysed content was found heading into an artifact. It carries **codes, locations and
digests, never the matched text** — exactly `CANARY_CONTACT`'s rule and for exactly its
reason: *"the record of a leak must not be a second copy of what leaked."* A trail that quoted
the secret it caught would be the exfiltration channel it exists to close.

`ARTIFACT_AUTHORED` carries **paths and per-file digests, not content**. The content is in the
proposal, which is where a reviewer reads it; a second verbatim copy in an append-only store
would put a private repository's authored derivative somewhere nobody can delete it.
`PROGRAM_SUBMITTED`'s verbatim rule does not transfer — that member records *the model's own
words as the cause*, and this one records *a derivative of the requester's private code*.
