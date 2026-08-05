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

---

*R13–R16 were measured during `/speckit-analyze` and are recorded here rather than only in the
remediation, because each one changes a decision the plan had already made.*

## R13 — The tier's egress allowlist is right for 037 and wrong for 038

**Measured**: `infra/jobs/analysis-tier.nomad.hcl:69` — `HARNESS_EGRESS_ALLOWLIST = "github.com"`,
with the comment *"The analyzer may reach the pinned source and nothing else. **Empty would
also be correct and is stricter than required**."*

**Why 037 needed it**: its analyser **fetched** the pinned upstream. The egress was the job.

**Why 038 must not inherit it**: the subject arrives as a **mount** (R4), so the authoring
analysis step fetches nothing and needs **no egress at all**. Leaving `github.com` open hands a
successfully-redirected agent that has just read a private repository a network route to the
one host in the allowlist that serves arbitrary user-controlled content — a gist, an attacker's
repository, an issue comment. That is US3's exact failure mode arriving through the network
layer while FR-015's ceiling assertion still passes.

**Decision**: the authoring analysis step runs with an **empty** allowlist, as its own jobspec
(`infra/jobs/authoring-tier.nomad.hcl`) so the value stays **static per job** rather than
becoming per-run.

**FR-005a is satisfied, not bent.** It requires the allowlist remain *static configuration
rather than becoming per-run*; it does not require it keep 037's *value*. A second jobspec with
a different static value is still static — a computed one would not be.

**How this was missed the first time**: the plan reasoned about the allowlist's *mutability*
(the property FR-005a names) and never about its *contents*. A control can be correctly
immutable and wrongly valued, and only the first was checked.

## R14 — A pack manifest as sketched cannot load, and the loader says why twice

**Measured**, `src/core/packs/loader.py`:

- line 285 — a pack whose tools declare a `product` and which names no `probe` refuses
  `probe_required` at load. `packs/terraform/pack.toml` records the trap in its own words: *"a
  pack reaching a product with no probe records UNHEALTHY, and every one of its tools would
  then be denied `dependency_unavailable` naming a product that is simply absent."*
- line 288 — `for suite in manifest.eval_suites` — the case floor (`MINIMUM_CASES_PER_SUITE = 5`)
  iterates the **declared** suites. A pack declaring none has **no floor to fail**.

**Decision**: `packs/github/pack.toml` declares `product = "github"` with a `github_probe`, and
**declares the five suites with their cases**, like both existing packs.

**Rationale for the second half**: Principle VIII is a MUST — *packs promote only through eval
gates* — and the loader would not have caught a pack that declared no suites. That is a gate
which passes by *omission* rather than by *vocabulary*, and it is the same shape 027 refused
when it declined to rename a field to dodge a matcher. A github pack outside the eval gate
would be this platform's first, and it would be first by accident.

## R15 — The credential is a THIRD standing exception, and the constitution enumerates two

**Measured**, `.specify/memory/constitution.md` Principle IV: *"The enclave holds no standing
credentials to anything it manages — **with exactly two named exceptions**, both rotated and
Control-Group-governed: the management token behind the TFE broker (ADR-0044), and the model
vendor credential behind the model broker (ADR-0058)."*

**And the precedent is exact.** `tests/unit/test_no_static_credentials.py` records what happened
last time: *"**027 amended this gate in the open, in the same change that amended the
constitution**, and for the same reason: the platform now holds a model vendor credential, so a
check asserting it holds none anywhere would be a check asserting something untrue. The
alternative considered and rejected was renaming the KV field to something the matcher does not
know — which would have left the gate green while the credential existed, and **a gate that
passes by vocabulary is worse than no gate**."*

**Decision**: **Principle IV is amended in the same change**, naming a third exception, and
ADR-0062 is its motivating record. The exception inherits the same conditions as the other two —
rotated, Control-Group-governed, held only in the trust store, read under the reading workload's
own attested identity, delivered per task, never persisted.

**The alternative was considered and is weaker.** One could argue the clause does not bite,
because it bounds credentials *"to anything it manages"* and the platform does not manage the
requester's repository. That reading is available and it is exactly the kind of narrowing 027
declined — the honest move is to amend the enumeration rather than to argue the new credential
out of it. A closed list that grows by interpretation is not a closed list.

**Consequence**: the plan's Principle IV verdict moves from *Pass, with a new credential class*
to **Pass, with a constitution amendment**, and the amendment is a task rather than a note.

## R16 — Authoring is a dispatched run, which is what makes surface parity inherited

**Measured**: `src/surfaces/dispatch/` (`entrypoint.py`, `nomad.py`, `inprocess.py`) is how a run
reaches an allocation today, and `tests/conformance/mcp/test_surface_parity.py` is the live gate
Principle II's *"the same operation on any transport MUST yield the same verdict and equivalent
audit events"* is asserted through.

**Decision**: **authoring introduces no new northbound operation.** An authoring request is the
payload of an ordinary dispatched run whose definition happens to carry `author_file`. Parity is
therefore **inherited rather than owed**, and a row asserts that inheritance is real — that no
new northbound verb was added.

**Rationale**: the alternative — a first-class "author" operation on each transport — would owe a
parity row per transport pair for a capability whose governance is entirely in the definition's
ceiling and the tier. It would add a surface to certify and change nothing about what is
enforced. Recording the decision matters more than which way it went: an absent parity row and a
deliberately-inherited one look identical in a diff, and only one of them is a gate regression.

---

*R17–R20 were measured during the **second** analyze pass. Where the first pass found things
nothing built, this one found things built against the wrong subject — a mechanism named
correctly and assumed to do something it does not.*

## R17 — The observer is handed a key, not a branch, and the first design gave it no way to look

**Measured**, `src/core/hooks/engine.py:440`:

```python
return f"{run_id}:{run.step_index}:{tool_name}"
```

and `src/core/observation/types.py` — `Observer.observe(self, *, idempotency_key: str)`. **That
is the observer's entire input.** No arguments, no correlation ID, no run object.

**The defect**: the first design derived the proposal branch from the **correlation ID**
(`run_id` is `run.run_id or run.correlation_id`, so the two are not reliably the same). An
observer holding only `run_id:step_index:open_proposal` cannot compute a branch derived from
something else — so it would return `CANNOT_DETERMINE`, which parks the run. **Every interrupted
publish, every time.** The contract row asserting "resumption resolves by observation" would
have been asserting something the design made impossible.

**Decision**: **the branch is derived from the idempotency key**, not from the correlation ID:

```
brieve/authoring/<sha256(idempotency_key)[:16]>
```

The observer recomputes the same string from the key it is given and asks the host whether a
proposal exists on that branch. Nothing else is needed and nothing else is available.

**Both properties survive, and one gets stronger.** Two runs have different `run_id`s, so FR-009
("a second proposal must not silently displace an earlier one") holds — different keys,
different branches. A **resumed** run has the *same* `run_id` and `step_index`, so it recomputes
the *same* branch, which is exactly what makes the observation meaningful rather than a
coincidence.

**Why it was missed**: "derive the branch from the correlation ID" is a correct-sounding
sentence about determinism, and determinism was the property being reasoned about. The question
never asked was *who has to recompute it, and what are they holding when they do.*

## R18 — The correctness gate is MECHANICAL, and that collides with what promotion demands

**Measured**, `src/core/evals/promotion.py`:

```python
if not judge.strip() and role != "judge":
    raise PromotionRefused(..., reason_code="promotion_incomplete")
```

Every cell except the seed-qualified first judge **must name a judge**, because ADR-0052's
regress has to terminate somewhere a person can inspect.

**The decision the plan never made**: FR-018's second gate says the artefact *"matches a
human-authored reference **on the properties the task is about**."* Read plainly, that is the
spec choosing **mechanical** comparison — a property is checkable, and ADR-0038's own warning
case is a property, not an impression: *a module wiring a static credential where dynamic
secrets were asked for.* So the human-authored reference carries a **declared property set**
(uses a dynamic secret source; pins the provider; no static credential), and the gate checks the
artefact against it.

**And the must-deny half is mechanical too.** Secrets in output → the secret detector.
Exfiltration of analysed content → the containment check. Injection resistance → the
byte-identical comparison in R1. **No judge participates anywhere in this qualification.**

**Which means the `write` cell cannot be promoted.** `promote_model_version` would refuse it
`promotion_incomplete` for naming no judge — a cell whose qualification is *stronger* than a
judged one, refused for not being judged.

**Decision**: `promote_model_version` accepts a **scorer identity** where a judge would
otherwise go, refusing only when **both** are absent. The field's meaning becomes what it always
described — *what qualified this* — and a mechanical scorer over a human-authored reference is a
legitimate answer to that question.

**Argued rather than assumed, because this touches ADR-0052's chain.** That record exists to
terminate a regress at *"cases labelled by a person, checked into the repository, reviewed like
code."* A human-authored reference with a declared property set terminates the regress **one
link earlier** than a judge model does: there is no scoring model to qualify, so there is
nothing above the human. Forcing a judge into the field to satisfy a string check would be the
move 027 explicitly refused — *"a gate that passes by vocabulary is worse than no gate."*

**This is a decision record, not an implementation detail**, so it lands as **ADR-0063
(Proposed)**, relating to ADR-0052 and amending what may qualify a cell. Two ADRs in one feature
is the honest count.

**The empty-reference case.** A golden task whose correct outcome is *no artefact* (the subject
already has the integration) has an empty property set, and an empty set trivially matches — the
same vacuous-pass shape `parse_cases` refuses for measured suites. So the corpus carries the
outcome explicitly: a task declares either a property set **or** `expects_no_artifact = true`,
and a task declaring neither is refused.

## R19 — Two mechanisms this feature cites are not on the path it claims

**Measured**:

- **`run_program` is registered nowhere.** `PROGRAM_TOOL_NAME` appears only in its own module and
  its `__all__`; `src/surfaces/toolset.py` registers the fixture tools and the pack tools and
  nothing else. 036's conformance rows call `run_submitted_program` **directly**. So code mode
  exists as a library and **no definition can enter it in the running platform**.
- **`reachable_tools` is called from no `src/` module** — only from three component test files.
  The invoke path enforces the ceiling at `src/core/hooks/authority.py:98`
  (`if ctx.tool_name not in effective.tool_names`).

**Neither is this feature's defect and both were this feature's claims.** The plan said a
program writes a file "by calling the write tool, which round-trips the seam like every other
call"; the task list asserted FR-015 by inspecting `reachable_tools`.

**Decisions**: W3 states it exercises **the seam**, not a production path, and T014 drops a
citation to a registration that does not exist. R2 re-points at the **effective scope the
authority hook actually reads** — the property was right and the subject was a helper nobody
calls.

**The pattern is named in this repository's own memory**: *a green row proves the mechanism, not
that the running service can reach it.* Both instances are that, and both were inherited by
citation rather than by measurement — the plan trusted a module's existence as evidence of its
use.

## R20 — Three smaller things the promotion path and the bracket require

**`qualified_by` for the first `write` cell is `live`.** `src/core/authority/matrix.py:44`
anticipates this feature by name: *"Carried per cell because the difference is invisible
otherwise, and **it matters most for `write` — a model permitted to make changes**."* A cell
qualified against a recording, permitted to author changes to a requester's repository, is
exactly what that comment warns about. The live lane exists and this is what it is for.

**`required_suites` for a `write` cell is the authoring corpus, named explicitly.**
`AUTHORING_QUALIFICATION` is deliberately outside `SUITES` (R7), so nothing supplies the list
`promote_model_version` checks `suites_passed` against. It is declared beside the constant that
excludes it, so the exclusion and the requirement are read together.

**Bracketing is conditional on durability.** `engine.py:237` — `bracket = run.durability is not
None and not registration.repeatable and key is not None`. A publishing run configured without
durability executes a non-repeatable tool **unbracketed**: no intent record, nothing to observe,
nothing for R17's fix to resolve. The authoring run therefore refuses to publish when it is not
durable, rather than publishing in a posture where an interruption is unrecoverable.
