# Tasks: The agent authors, and a person merges

**Input**: Design documents from `/specs/038-authoring-workflows/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature produces artefacts a person merges into their own repository, so its
rows *are* the deliverable. Every contract row — W1–W5, T1–T3, C1–C5, R1–R2, P1–P6, V1–V3,
Q1–Q6 — has a task, and every task that asserts has a task that builds.

**Remediated after two analyze passes** — pass one 4 CRITICAL / 5 HIGH / 4 MEDIUM / 2 LOW,
pass two 2 CRITICAL / 4 HIGH / 4 MEDIUM / 1 LOW. Twenty-two tasks were added and every task
names its file. The additions are suffixed rather than renumbered so the findings stay
traceable to what fixed them.

**Remediated after three analyze passes** — pass three 2 CRITICAL / 3 HIGH / 3 MEDIUM / 1 LOW.

**Pass two found things built against the wrong subject**: the observer could never have found
the proposal (T044a); the `write` cell could never have been promoted (T061a); and two
mechanisms these tasks cited — `run_program`'s registration, `reachable_tools` — are not on the
path they claimed (T014, T039). All four arrived by **citing a real module** rather than by
measuring whether anything calls it.

**Pass four audited the remediations rather than the plan, and that is where it found things.**
All three of its significant findings descend from the pass-two two-posture split: it defined
**no handoff** (T009c — the artefact could not reach the step that publishes it), it implied
**two correlation IDs** where Principle IX requires one (resolved by the same task), and it left
the tier's mount source **per-dispatch and unvalidated**, so a dispatch naming the platform's own
tree satisfied every clause (T009b). **A remediation is a design change and deserves the
scrutiny the design got.** The recurring instance worth naming: **three controls here were
checked for the property they named and not for the value they would hold** — the egress
allowlist, the containment claim, and `repo_mounted`.

**Pass five found two of its three CRITICALs inside earlier remediations, one a single round
old.** The one-run-two-tasks fix (T009c) was **fenced by the platform's own lease** — two tasks
sharing a `run_id` are two holders, and the second kills the first — so the tasks are now
sequential (T009). The publishing task **could not do the work it was given**, since composing
diffs and scanning for subject spans both need the subject it does not mount (T009d). And
pass one's "declare the five suites" cure for the `github` pack was wrong in kind: the suites
are answering-shaped and the pack has no expertise to measure, so `open_proposal` becomes a
platform tool and **ADR-0038 is amended rather than departed from** (T041a).

**What five passes say about the process, since it is the more useful finding.** Counts were
4, 2, 2, 2, 3 — not convergence — and the *source* moved: the first two passes found defects in
the plan, the last two found them in the fixes. Each remediation was a design decision made at
the end of a report and never given a pass of its own; the plan got five readings and each fix
got at most one. **Reading also has a floor.** A lease that fences and a task that cannot read
what it needs are defects implementation surfaces in minutes, and no sixth pass finds them
faster.

**Pass three found a claim that outgrew its argument, and a layer nothing ran in.** The two-tree
design makes the *file set* unforgeable, and that was written up as containment being "not
expressible" — true of paths, **false of bytes**, since an authored file is agent-controlled
content. Nothing scanned it for two drafts (T026, T026a). And **no task registered a hook**:
two refusals sat in modules a caller must remember to call, which reads identically in a task
list and is not enforcement (T012ac). Fixing the second surfaced a requirement none of the
artefacts had noticed — the lens needs a governed **read path** (T012ab), which FR-014, FR-005b
and FR-004 were all written against and none of them had.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T008 (tier posture by clause), T012 (no qualified `write` cell refuses), T031 (containment blocks emission), T040 (a redirected analyser holds no publishing credential), T053 (ceilings disjoint) |
| **Conformance** | Phases 3–7 — both contracts, `tests/conformance/authoring/` |
| **Correlation / evidence** | T020 (`ARTIFACT_AUTHORED` carries paths and digests, never content), T048 (the human's merge is distinguishable from everything the platform did) |
| **Eval** | Phase 7 entire — the `write` role's qualification (Q1–Q6) — plus T058, the corpus floor |
| **No-secret-leak** | T029 (a seeded credential reaches neither files, commits, nor prose), T030 (`CONTAINMENT_REFUSED` carries codes and digests, never the matched text), T006b (the publishing credential is never persisted) |

**Three tasks exist to prove the others can lose.** **T034** removes the seeded secret from the
fixture subject and asserts C1 then **fails** — a must-deny suite whose subject never contains
a secret a generator could reach is the passing stub ADR-0047 forbids, and it is the most
available one in this feature. **T033** asserts the honest limit of the prose half (a
paraphrase is *not* caught), so "containment is structural" can never be read as covering the
description. **T063** runs the correctness gate with `terraform` off the path and asserts the
lane goes **red** rather than degrading to `fmt`-only while still reporting "validated".

**One task exists because the strong guarantee is not the whole guarantee**: **T053** asserts
the ceilings are disjoint (nothing to enact with) beside **T052**, which asserts the provenance
rule fires. T053 is true about today's definitions; T052 is what survives a definition somebody
writes next year. Both, never one.

**And one exists because a guarantee this feature CANNOT keep must not read like one it can**:
**T032a**. Where the analysed source is itself the sensitive thing, an authored integration is a
derivative of exactly that — containment bounds what is *copied* and cannot bound what is
*implied*.

## Phase ordering, and why it is not the story numbering

All five stories are P1. The phases follow the plan's layering — **the layer that can carry
private code out lands only once the layer that bounds it exists** — so US3 (containment)
precedes US2 (publishing), despite the numbering. Composing a proposal and publishing one are
separated for exactly this reason.

**The whole feature merges as one change.** Phase 7 lands the qualification, but T012 lands the
*refusal* in Phase 2, so there is no commit at which authoring could run under an unqualified
cell. `OWED` never has a window (FR-019).

## Path Conventions

Single project: `src/`, `tests/` at repository root. New: `src/core/authoring/`,
`src/core/isolation/` (moved), `evals/authoring/`,
`infra/jobs/authoring-tier.nomad.hcl`, `tests/conformance/authoring/`.

Conformance rows land by letter group: **W** → `test_producing.py`, **T** → `test_tier.py`,
**C** → `test_containment.py`, **R** → `test_redirection.py`, **P** → `test_proposing.py`,
**V** → `test_provenance.py`, **Q** → `test_qualification.py`, all under
`tests/conformance/authoring/`.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/authoring/__init__.py` and `tests/conformance/authoring/__init__.py`; add `tests/conformance/authoring` to the hermetic conformance lane's collection in `Makefile` so new rows run where they block merges (the 036 lesson: a gate asserted only locally is not a gate).
- [ ] T002 [P] Move `src/core/intake/tier.py` to `src/core/isolation/tier.py`, adding `src/core/isolation/__init__.py`; update imports in `tests/conformance/intake/test_isolation_tier.py` and `tests/conformance/intake/test_containment.py`, **and the path references in `specs/037-intake-gauntlet/plan.md` and `specs/037-intake-gauntlet/contracts/conformance-intake.md`**. **No behaviour change** — the module content is unchanged in this task. Two consumers now, and `core.authoring` importing `core.intake` would encode that authoring is part of the supply chain (research R3).
- [ ] T003 [P] Create `evals/authoring/README.md` stating what the directory is for and what refuses when it is empty. **No `packs/github/`** — see T041a.

---

## Phase 2: Foundational (blocking all stories)

**The audit vocabulary, the constitution amendment, the credential path, the qualification
refusal, the tier, the request, and the two trees. Nothing in Phases 3–7 can record, refuse,
isolate, authenticate, arrive or produce until these exist.**

- [ ] T004 Add four additive `AuditEventType` members to `src/core/audit/schema.py`: `ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`, `ENACTMENT_REFUSED`. Document each member's payload rule in the docstring on `ANALYSIS_VERDICT`'s precedent — in particular that `CONTAINMENT_REFUSED` carries **codes, locations and digests, never the matched text** (`CANARY_CONTACT`'s rule: the record of a leak must not be a second copy of what leaked) and `ARTIFACT_AUTHORED` carries **paths and per-path digests, never content**.
- [ ] T004a [GATE:no-secret-leak] Build a **payload-shape gate** for the four new members in `src/core/audit/schema.py` (a validator the sink applies, or a merge-blocking row in `tests/conformance/evidence/`), asserting `ARTIFACT_AUTHORED` carries no content field and `CONTAINMENT_REFUSED` carries no matched text. Measured: `append_event(payload: dict[str, Any])` validates **nothing**, and `redact_arguments` runs on tool *arguments* in the engine and never on event payloads — so every "carries codes, never text" rule in this feature was a **convention** (research R26). Survivable for 037, whose payloads are digests by construction; not here.
- [ ] T005 [P] Confirm `tests/conformance/evidence/test_audit_schema.py::test_widening_the_event_vocabulary_moves_no_existing_hash` stays green with the four members added; if it does not, the members were not additive.
- [ ] T006 [P] Author `docs/adr/0062-authoring-credentials-are-vended-per-task.md` as **Proposed**: the version-control credential is Vault-vended, hour-scoped and **installation-scoped to the requester's own repositories**, never a personal access token (033 already refused one), and **never mounted into the hardened tier**. Add its row to `docs/adr/README.md`.
- [ ] T006aa [P] Author `docs/adr/0063-a-mechanical-scorer-may-qualify-a-cell.md` as **Proposed**, relating to ADR-0052: where a **human-authored reference carries a declared property set**, a mechanical comparison may qualify a cell, and `promote_model_version` records a **scorer identity** where a judge would otherwise go. **A human-authored reference terminates ADR-0052's regress one link earlier than a judge does** — there is no scoring model to qualify, so nothing sits above the human. Add its row to `docs/adr/README.md`.
- [ ] T006a **Amend `.specify/memory/constitution.md` Principle IV to name a THIRD standing-credential exception**, with a Sync Impact Report citing ADR-0062, on the precedent 027 set when the model vendor credential arrived. The exception inherits the other two's conditions — rotated, Control-Group-governed, trust-store only, read under the reading workload's own attested identity, delivered per task, never persisted. **Principle IV says "exactly two named exceptions"; shipping a third without amending would make a MUST principle untrue** (research R15), and arguing the clause does not bite is the narrowing 027 declined.
- [ ] T006b Build the publishing credential in `src/core/authoring/credential.py`: attested workload identity → Vault → an hour-scoped, installation-scoped token, on `core/durability/credentials.py`'s `NomadWorkloadIdentity` pattern, accepting no credential from a caller. **Here rather than in `core/durability/`** so a new credential class does not widen sealed core beyond the four audit members. [GATE:no-secret-leak] Assert in `tests/unit/test_no_static_credentials.py` that the token is never persisted and the module trips none of the `FORBIDDEN` names.
- [ ] T006c Provision the Vault role and KV path for the App key in `infra/terraform/` beside the existing `ceilings.tf` pattern, readable only by the publishing allocation's attested identity — never by the analysing one.
- [ ] T007 Add `SubjectMount(path, read_only)` and a `subject_mount: SubjectMount | None = None` field to `TierPosture` in `src/core/isolation/tier.py`. `repo_mounted` **keeps its name and its meaning — the platform's own tree** — which is already what `infra/jobs/analysis-tier.nomad.hcl` says it guards against.
- [ ] T008 [GATE:fail-closed] Extend `is_hardened()` in `src/core/isolation/tier.py` with exactly one clause: a **writable** subject mount fails, naming that clause as every other refusal does. Absent passes (037's payload delivery); read-only passes.
- [ ] T009 Author `infra/jobs/authoring-tier.nomad.hcl` as **one group with two SEQUENTIAL tasks sharing `/alloc/data`** (research R24, R27): `analyzer` — read-only subject mount, `HARNESS_EGRESS_ALLOWLIST = ""`, no credential, and **`lifecycle { hook = "prestart", sidecar = false }`** so it completes and exits before `proposer` starts; and `proposer` — no subject mount, the VCS credential, allowlisted egress. **Sequential, not concurrent, because the lease fences by holder identity**: `RunLease.held()` checks `(run_id, holder_identity)` and `invoke_tool` propagates `LeaseSupersededError` rather than converting it to a deny, so two tasks sharing a `run_id` are two holders and the second would kill the first mid-run. A prestart lifecycle makes the handoff a baton, and the proposer's `acquire` after the analyzer exits is the ordinary resume path the fencing was built for. Identity, `env` and `config.mount` are per-task, so the two hold genuinely different authority. Comment why the mount is not the reversal it looks like (037's "no mount" meant *do not hand a redirected analyser the platform's own tree*), why the analyzer's allowlist is empty (it reads a mount and fetches nothing — inheriting 037's `github.com` would leave a redirected agent holding a private codebase with a route to the one host serving arbitrary user content, R13), and **that the network namespace is shared** so nobody later claims network isolation between the tasks. Cross-reference `infra/jobs/analysis-tier.nomad.hcl` in both files as siblings.
- [ ] T009a Row **T4** in `tests/conformance/authoring/test_tier.py`: assert the **`analyzer` task** declares an **empty** egress allowlist and that the value is **static in the jobspec** rather than computed per run. Scoped to egress deliberately — the mount source in the same file is necessarily per-dispatch (T009b), so a row claiming whole-posture staticness would assert something the design does not have.
- [ ] T009b [GATE:fail-closed] Validate the subject mount source in `src/core/authoring/request.py` before dispatch, refusing **`subject_is_platform_tree`**, and carry the **resolved source** on `TierPosture` rather than only `repo_mounted`. Row **T5** in `tests/conformance/authoring/test_tier.py` asserts the refusal and checks a **path**, not a claim about one. Measured: the subject differs every run so its mount source must be per-dispatch, while `repo_mounted` is a declared boolean — **a dispatch naming the platform's own tree satisfies `bridge`, `readonly = true` and `repo_mounted = False` while mounting precisely what the tier exists to keep out** (research R25). `readonly = true` itself has precedent in four jobspecs, so only the source needed work.
- [ ] T009c Build the artefact handoff in `src/core/authoring/workspace.py`: the workspace lives in the shared allocation directory, written by `analyzer` and read by `proposer`. Row **P10** in `tests/conformance/authoring/test_proposing.py`: the artefact reaches the publishing task, **and both tasks record under one correlation ID**. Without this the feature's happy path does not connect — R9's two-posture split defined no transfer, and two allocations would also have meant two correlation IDs where Principle IX requires one (research R24).
- [ ] T009d **Assign every module to a task**, in `src/core/authoring/__init__.py`'s docstring and asserted by row **T6** in `tests/conformance/authoring/test_tier.py`: `analyzer` runs `read_subject`, `author_file`, `workspace`, `artifact`, **`proposal` composition and `containment`** — everything needing the subject; `proposer` runs **`open_proposal` only**. Measured: T022 composes diffs *against the subject* and T026 scans *subject files*, and the proposer has no subject mount — **as first written it could not do the work it was given** (research R28). The assignment is also strictly safer: the task holding the credential never holds the analysed content, so US3's channel narrows to bytes that already passed containment.
- [ ] T009e Carry `step_index` and the bounds state across the handoff in `src/core/authoring/workspace.py`, and assert it in row **T7** of `tests/conformance/authoring/test_tier.py`. `GovernedRun.step_index` and `bounds` are **per-process** (`src/core/run.py:115–123`), so two tasks would otherwise start two step counters and two budgets — letting one run consume its execution bound twice and splitting the step accounting that makes bounded runs meaningful.
- [ ] T010 Build the two trees in `src/core/authoring/workspace.py`: a **read-only subject** and a **writable workspace**, with the subject reachable for reading and never for writing. Document that the proposal is built from the workspace and never from the subject — this is what makes FR-013a a property rather than a check (research R5).
- [ ] T011 Build `AuthoredArtifact` in `src/core/authoring/artifact.py`: `paths`, per-path `digests`, the `created`/`edited` partition (a path is `edited` iff it exists in the subject), `truncated`, `truncation_note`. **No content field** — see T004's rule.
- [ ] T012 [GATE:fail-closed] Gate authoring on a qualified `write` cell in `src/core/authoring/tool.py`: resolve through the existing `resolve_with_fallback`, which has no third branch. **Landed foundational deliberately** — this is US5's first acceptance scenario, and a capability that could run unqualified for even one commit is the gap 026 found for `ask`.
- [ ] T012a Build the `AuthoringRequest` record in `src/core/authoring/request.py`: `correlation_id`, **`tenant_id`**, `requester`, `target_repository`, `task`, `pack`, with validation refusing a pack that declares no authoring workflow. `tenant_id` is required rather than optional — `AuditEntry` demands one, and repository ownership is a tenancy question before it is anything else (ADR-0046). **Refuse when it does not equal the run's `RUN_TENANT_ID`** (`infra/jobs/agent-run.nomad.hcl:219`): a request scoped to one tenant writing entries under another corrupts the one field `AuditEntry` keeps *inside* the hash chain precisely because it decides who may read the record. **T043 asserts an ownership refusal over this record and the first task list never built it** — the assert-over-nothing-built shape 036 and 037 each found.
- [ ] T012b Carry the request as the **dispatch payload** in `src/surfaces/dispatch/entrypoint.py`, adding **no new northbound operation**. Row **P0** in `tests/conformance/authoring/test_proposing.py`: assert no new northbound verb exists on any transport, so Principle II's surface parity is **inherited rather than owed** (research R16). An absent parity row and a deliberately-inherited one look identical in a diff, and only one is a gate regression.
- [ ] T012aa Row **W6** in `tests/conformance/authoring/test_producing.py`: a ceiling naming `author_file` before the tool registers refuses **`unknown_ceiling_entry`**, and the message names the ceiling rather than the missing registration. **No registration happens here** — the previous draft placed one in this phase and a tool cannot register without its handler, which Phase 3 builds. There is no ordering hazard to fix: `parse_ceiling_record` runs **at run start**, not when T012c authors the record, and no run starts before Phase 3. The row exists so the failure stays loud if that ever changes.
- [ ] T012ab Register `read_subject` in `src/surfaces/toolset.py` and `src/core/authoring/tool.py` with `risk_class="read"`: every read of the mounted subject goes through it. **This is what the injection lens attaches to** — a read-only mount read by ordinary file access offers no hook, so ADR-0038's *"injection-lens hooks"* would have had nowhere to live (research R23). It also gives FR-014 a place to record an attempt, FR-005b countable reads to truncate, and FR-004 an enumerable "what was consulted" — three requirements written against a read path none of them had. Row **R3** in `tests/conformance/authoring/test_redirection.py`: every subject read goes through the tool, and the lens **records without refusing**.
- [ ] T012ac Register the two `GOVERNANCE`-kind hooks in `src/core/authoring/hooks.py`: `authoring_provenance` (**PRE** — refuses enactment of platform-authored content) and `authoring_injection_lens` (**POST** on `read_subject`). Measured: `HookRegistration(name, phase, capability_kind, handler)` is how enforcement enters the pipeline and `engine.py:29` orders `GOVERNANCE` first. **The first two drafts put both refusals in modules a caller must remember to call** — which reads identically in a task list and is not enforcement (Principle III). Row **V4** in `tests/conformance/authoring/test_provenance.py`: the provenance refusal is a `GOVERNANCE` PRE registration, and governance hooks run first. V1 over a module function would have been green.
- [ ] T012c Author the two definition bindings records under `infra/terraform/definitions/`: the **analysing** definition (`tier = 2` — `author-module` declares `minimum_tier = 2` and `DEFAULT_TIER` is 1, so a definition that omits it is refused), `packs = ["terraform"]`, `binding_map = {"write": ...}`; and the **proposing** definition, `packs = ["github"]`, no authoring tool. **T039 and T053 assert properties of these two and nothing created them.**

---

## Phase 3: US1 — The agent produces something, and it is governed like anything else (P1)

**Goal**: the platform's first tool that produces, reached the same way everything else is.

**Independent test**: ask for a file, confirm it is produced, and confirm the write passed the
same governed entry a read does with the same records behind it.

- [ ] T013 [US1] Implement the `author_file` handler in `src/core/authoring/tool.py`: writes into the workspace, returns paths and digests, refuses a path outside the workspace. Register it with `risk_class="write"` — **the registry's first occupant of a class defined in 013 and unused since** (research R1).
- [ ] T014 [US1] Bind the `author_file` handler into `PLATFORM_HANDLERS` in `src/surfaces/handlers.py` so the registration from T012aa resolves. The registry is the opt-in switch: a definition whose ceiling omits the tool has no authoring. **No `run_program` precedent is cited** — measured, `PROGRAM_TOOL_NAME` appears only in its own module and nothing registers it (research R19), so there is no registered platform tool to follow. This is the first.
- [ ] T015 [US1] Row **W1** in `tests/conformance/authoring/test_producing.py`: a write is a governed decision, producing the same `PRE_DECISION`/`TOOL_OUTCOME` shape a read does. Assert the registered `risk_class` is `write`, so a later change to `read` fails here rather than silently widening what may reach it.
- [ ] T016 [US1] Row **W2** in `tests/conformance/authoring/test_producing.py`: a definition whose ceiling omits `author_file` is refused `tool_not_permitted`, exactly as for any other tool outside a ceiling.
- [ ] T017 [US1] Row **W3** in `tests/conformance/authoring/test_producing.py`: drive `run_submitted_program` with a program that writes a file; assert the write appears as **its own governed step** through the seam rather than as a side effect. **State in the row what it does and does not prove**: `run_program` is registered nowhere (research R19), so this exercises **the seam**, not a path a running definition can reach. A row that read as proving the production path would be the "green row proves the mechanism, not that the running service can reach it" failure this repository has recorded before.
- [ ] T017a [US1] Row **W3a** in `tests/unit/test_no_unaccounted_writes.py`: assert **structurally** that no filesystem write path exists outside `author_file` — enumerate the write surface the way `tests/conformance/packs/test_no_bypass_path.py` enumerates the tool surface. SC-002 claims **100%, no unaccounted writes**, and W3 asserts the positive; a negative requirement needs an absence asserted.
- [ ] T018 [US1] Emit `ARTIFACT_AUTHORED` from `src/core/authoring/artifact.py` on completion, carrying paths, per-path digests, the created/edited partition and the truncation flag.
- [ ] T019 [US1] Record what was consulted, wiring `src/core/packs/consulted.py` into `src/core/authoring/tool.py` so FR-004's "what was consulted" is recoverable rather than implied (ADR-0004, skills-first).
- [ ] T020 [US1] [GATE:no-secret-leak] Row **W4** in `tests/conformance/authoring/test_producing.py`: the trail names every path and digest and the consulted skills, and **no file content appears anywhere in it**. The artefact is a derivative of a private repository and the trail is append-only.
- [ ] T021 [US1] Make an empty artefact a completed outcome in `src/core/authoring/artifact.py`, and row **W5** in `tests/conformance/authoring/test_producing.py`: a run that produced nothing completes, records an empty artefact, and is distinguishable from a run that failed.

**Checkpoint**: files are produced and governed. Nothing is bounded and nothing is published yet.

---

## Phase 4: US3 — Nothing the agent read leaves with what it wrote (P1)

**Goal**: the proposal carries the change and nothing else, enforced by inspecting the artefact.

**Independent test**: author against a subject seeded with a secret and with distinctive
unrelated content; confirm neither reaches the artefact, the commits, or the description.

- [ ] T022 [US3] Compose the proposal in `src/core/authoring/proposal.py`: files the change **created**, plus **diffs** of the files it edited, built from `artifact.paths` against the subject using `difflib`. The subject is never enumerated — it is read only for paths the agent already wrote.
- [ ] T023 [US3] Row **C2** in `tests/conformance/authoring/test_containment.py`: seed the subject with distinctive content in a file the task does not touch; assert it is absent from the proposal, **and assert the mechanism** — the file set is built from the workspace, so the subject is not a source. This row asserts a property, not a check.
- [ ] T024 [US3] Row **C3** in `tests/conformance/authoring/test_containment.py`: edit a file and assert the diff's surrounding context is **present and not refused**. A rule that forbade it would forbid editing, and a containment check tuned until it passed would plausibly have arrived there (FR-013b).
- [ ] T025 [US3] Compose the proposal body in `src/core/authoring/proposal.py` from **structured sections** — task, files touched, disclosures, limits — with exactly **one** free-text rationale field. The structure is the bound; the scan below covers the one field it cannot structure away.
- [ ] T026 [US3] Implement the verbatim-span scan in `src/core/authoring/containment.py` **over the whole proposal** — authored file contents, the added lines of every diff, commit messages, title and body. A span refuses when it is **≥ 120 characters AND spans ≥ 2 non-blank lines** (whitespace-normalised) and matches a subject file **not** in `artifact.paths`, with reason code `analysed_content_in_artifact` or `analysed_content_in_prose`. Keep this a **separate function** from the path half — one covers which files appear and the other what they contain, and collapsing them is how the second went missing (research R21).
- [ ] T026a [US3] Row **C7** in `tests/conformance/authoring/test_containment.py`: **an authored file carrying analysed content is refused**. Write the subject's distinctive content into a comment block in a file the change *creates*; assert `analysed_content_in_artifact`. **This is the row the whole containment story was missing**: the path half is structural, so an untouched file cannot appear — and nothing stopped the agent copying what it read into a file it did create. SC-004 held for one seeded string in one untouched file and for nothing else.
- [ ] T026b [US3] Row **C8** in `tests/conformance/authoring/test_containment.py`: **legitimate reuse is not refused**. An artefact reusing the subject's identifiers, type names, config keys and function signatures passes. The C3 treatment applied to the content half — that reuse is what integrating *is*, and a scan tuned until it stopped complaining would forbid it. Assert both threshold conditions bite: a 200-character single-line span passes, and two short adjacent lines pass.
- [ ] T027 [US3] Row **C4** in `tests/conformance/authoring/test_containment.py`: a rationale quoting an untouched subject file verbatim is refused.
- [ ] T028 [US3] Implement secret detection in `src/core/authoring/containment.py` across produced files, commit messages and proposal prose, refusing `secret_value_in_output` (FR-010, FR-011).
- [ ] T029 [US3] [GATE:no-secret-leak] Row **C1** in `tests/conformance/authoring/test_containment.py`: author against a subject containing a credential; assert the value appears in **none** of the files, commits or body — by assertion over the artefact, never by inspection — and that the attempt lands `CONTAINMENT_REFUSED`.
- [ ] T030 [US3] Emit `CONTAINMENT_REFUSED` from `src/core/authoring/containment.py` carrying **code, location and digest and never the matched text**, per T004's rule.
- [ ] T031 [US3] [GATE:fail-closed] Refuse **emission** in `src/core/authoring/proposal.py` on any containment failure — a proposal that failed containment is not composed-and-flagged, it is not emitted.
- [ ] T032 [US3] Enforce a read budget of **4 MiB of subject content per run** in `src/core/authoring/tool.py` (countable now that reads go through `read_subject`), refusing further reads past it; disclose the truncation in `src/core/authoring/proposal.py`; row **C5** in `tests/conformance/authoring/test_containment.py`: a subject too large to read in full produces a proposal that says so. **4 MiB is fixed with its reasoning** — a module plus the surrounding application configuration is kilobytes, so this is generous for genuine integration work and far below a large monorepo, which is the case the disclosure exists for. An unfixed threshold is one that gets raised until the corpus passes.
- [ ] T032a [US3] Add the **structural limit** to the proposal's limits statement in `src/core/authoring/proposal.py`, and row **C6** in `tests/conformance/authoring/test_containment.py` asserting it appears: where the analysed source is itself the sensitive thing, an authored integration is a derivative of exactly that. **Containment bounds what is copied and cannot bound what is implied.** The spec raised this edge case and nothing addressed it; a reviewer deciding what to publish needs the distinction before they merge, not after.
- [ ] T033 [US3] Row **C4-companion** in `tests/conformance/authoring/test_containment.py`: assert a **paraphrase** of untouched subject content is **not** caught, and document it as the residual risk. Stating the limit is what stops "containment is structural" being read as covering the description — the exact conflation FR-013 exists to prevent.
- [ ] T034 [US3] **Prove C1 can fail**: a row in `tests/conformance/authoring/test_containment.py` that removes the seeded secret from the fixture subject and asserts C1 then fails. A must-deny case that never puts a secret anywhere a generator could reach is ADR-0047's passing stub, and it is the most available one in this feature.

**Checkpoint**: an artefact can be composed and is bounded to the change. Nothing publishes yet.

---

## Phase 5: US4 — Hostile repository content does not redirect the agent (P1)

**Goal**: the tier holds with a subject in it, and a successful redirection has nowhere to go.

**Independent test**: author against a repository carrying instructions addressed to the agent;
confirm the output is unaffected and the attempt appears in the record.

- [ ] T035 [US4] Row **T1** in `tests/conformance/authoring/test_tier.py`: assert `is_hardened()` **by clause** — subject mount absent passes, read-only passes, **writable fails** naming that clause — and that the platform's tree is unmounted.
- [ ] T036 [US4] Row **T2** in `tests/conformance/authoring/test_tier.py`: 037's refusal is unchanged — `repo_mounted=True` still fails with its original message. A feature that extends an isolation check is exactly where one gets accidentally relaxed.
- [ ] T037 [US4] Implement the injection-lens handler in `src/core/authoring/hooks.py` as the **POST hook on `read_subject`** registered in T012ac (ADR-0038: *necessary rather than precautionary*), reusing `src/core/evals/injection_patterns.py` rather than authoring a second pattern set. Record the attempt; do not refuse the read — content addressed to the agent is data, and refusing to read a file because it contains instructions would let a subject make itself unanalysable. **Record `pattern_name` and location and explicitly DROP `excerpt`**: `InjectionFinding` carries `excerpt: str`, so reusing the module verbatim would make copying analysed private code into an append-only store the *default* implementation — the exact inverse of `CANARY_CONTACT`'s rule (research R26). T004a's gate is what keeps that true.
- [ ] T038 [US4] Row **R1** in `tests/conformance/authoring/test_redirection.py`: author against a subject carrying text addressed to the agent; assert the produced artefact is **byte-identical** to the artefact from the same subject without that text, and that the attempt is recorded. Byte-identical rather than "unaffected" — "unaffected" is a judgement, and a row requiring one is graded by whoever wrote it.
- [ ] T039 [US4] Row **R2** in `tests/conformance/authoring/test_redirection.py`: assert the **effective scope the authority hook actually reads** — `effective.tool_names` at `src/core/hooks/authority.py:98` — contains nothing that egresses, for the analysing definition created in T012c. **Not `reachable_tools`**: measured, that helper is called from no `src/` module and only from three component tests (research R19), so a row asserting over it would prove a property of something the running platform never consults.
- [ ] T040 [US4] [GATE:fail-closed] Row **T3** in `tests/conformance/authoring/test_tier.py`: assert **structurally** that `infra/jobs/authoring-tier.nomad.hcl` holds **no version-control credential**, and that the proposing definition's ceiling holds no authoring or analysis tool. A redirected analyser then has neither a tool, nor a credential, nor (per T009a) an egress route.

**Checkpoint**: analysis is contained and cannot be redirected out. Still nothing published.

---

## Phase 6: US2 — The work lands as a proposal, never as a change (P1)

**Goal**: publishing, gated by everything above it, and a platform that does not enact what it
authored.

**Independent test**: confirm no path produces a merge, an apply, or a write outside the
requester's own repositories, and that a human decision is required and recorded.

- [ ] T041 [US2] Register `open_proposal` as a **platform tool** in `src/core/authoring/tool.py` and `src/surfaces/toolset.py`: `risk_class="write"`, `repeatable=False`, with an observer. **Record the transport determination under ADR-0037's standing test** in a comment, as `packs/terraform/pack.toml` does for both halves of the rule — that test is about *transport* and is orthogonal to where a tool lives.
- [ ] T041a [US2] Author `docs/adr/0064-version-control-is-a-platform-capability.md` as **Proposed**, amending ADR-0038's *"Version control becomes a first-class pack tool target"*: the eval suites are answering-shaped, and a pack carrying one PR-opening tool has **no expertise for them to measure** (research R29). Add its row to `docs/adr/README.md`. **Principle X requires the amendment in the same change** — a departure recorded nowhere is the defect ADR-0060 closed.
- [ ] T041b [US2] Row **P11** in `tests/conformance/authoring/test_proposing.py`: `open_proposal` is registered non-repeatable **and carries an observer**. The `observer_required` refusal lives in the **pack loader** (`src/core/packs/loader.py`), so a platform registration is not covered by it and must assert the property itself. **`packs/github/` is withdrawn** — twenty-five cases written to clear a floor for a pack with no expertise is the "gate that passes by vocabulary" 027 refused, and it was this task's own earlier form that prescribed them.
- [ ] T042 [US2] Implement the `open_proposal` handler and its observer in `src/surfaces/handlers.py`, authenticating through `src/core/authoring/credential.py` — the allocation as itself, no token accepted from a caller.
- [ ] T043 [US2] Refuse a `target_repository` outside the requester's own in `src/core/authoring/request.py` **before anything is produced**, and row **P2** in `tests/conformance/authoring/test_proposing.py`: assert the artefact is empty and no `ARTIFACT_AUTHORED` exists. "Refused after producing" and "refused before producing" are different postures, and only one leaves nothing on disk to leak.
- [ ] T043a [US2] Row **P9** in `tests/conformance/authoring/test_proposing.py`: a target inside the **same installation** but owned by a different requester is **refused**, and a target in a different **tenant** is refused. **The check is the sole enforcement of requester scope** — an App installation is scoped to the installing account or organisation, so two requesters in one organisation share one installation and the credential would reach either's repositories. The earlier "fails twice" claim held only for a single-user installation, which is not the case that matters; this row asserts the check alone, against the target most likely to slip through.
- [ ] T044 [US2] Derive the proposal branch **from the idempotency key** in `src/core/authoring/proposal.py` — `brieve/authoring/<sha256(idempotency_key)[:16]>` — and row **P3** in `tests/conformance/authoring/test_proposing.py`: author twice against the same target; assert two distinct branches and that the first proposal is intact (FR-009). Two runs carry different `run_id`s, so the keys differ; a **resumed** run carries the same `run_id` and `step_index`, so it recomputes the same branch.
- [ ] T044a [US2] [GATE:fail-closed] Row **P7** in `tests/conformance/authoring/test_proposing.py`: assert the observer's input is **sufficient to locate the proposal**. `Observer.observe(*, idempotency_key)` receives that string and nothing else (`src/core/observation/types.py`), and `_idempotency_key` is `f"{run_id}:{step_index}:{tool_name}"` (`src/core/hooks/engine.py:440`). **The first design derived the branch from the correlation ID, which the observer never sees** — so every interrupted publish would have resolved `CANNOT_DETERMINE` and parked the run (research R17). Assert the observer recomputes the branch from the key alone.
- [ ] T044b [US2] [GATE:fail-closed] Refuse to publish when the run is **not durable**, in `src/core/authoring/proposal.py`, and assert it in row **P8** of `tests/conformance/authoring/test_proposing.py`. Measured: `bracket = run.durability is not None and not registration.repeatable and key is not None` (`src/core/hooks/engine.py:237`) — a non-durable run executes a non-repeatable tool **unbracketed**, with no intent record and nothing to observe, which is the one posture where an interruption is unrecoverable.
- [ ] T045 [US2] Emit `PROPOSAL_OPENED` from `src/core/authoring/proposal.py` carrying repository, branch, artefact digest and proposal reference. **No merge member** — a merge is observed, never written by the platform.
- [ ] T046 [US2] Row **P1** in `tests/conformance/authoring/test_proposing.py`: completed authoring yields a proposal and **no merge and no apply occurred**, asserted over the trail rather than over the proposal's own claim about itself.
- [ ] T047 [US2] Row **P4** in `tests/conformance/authoring/test_proposing.py`: kill the run mid-`open_proposal`; assert the tool is registered non-repeatable **with an observer** and that resumption resolves by asking the host whether the proposal exists rather than by guessing. Without the observer the step lands `CANNOT_DETERMINE` and parks the run.
- [ ] T048 [US2] Row **P5** in `tests/conformance/authoring/test_proposing.py`: merge a proposal and assert the record distinguishes the person's act from the platform's, and that no member of the platform's vocabulary can be read as an approval (ADR-0043, Principle IX).
- [ ] T049 [US2] Row **P6** in `tests/conformance/authoring/test_proposing.py`: a proposal nobody has reviewed stays `opened` and is reported as `opened`. Forecloses a dashboard counting proposals as delivered work.
- [ ] T050 [US2] Build the provenance record in `src/core/authoring/provenance.py`: content digest → authoring correlation ID → proposal state, written when the artefact is authored and readable **at the moment of enactment** (FR-020b).
- [ ] T051 [US2] Implement the enactment refusal as the **PRE hook handler** in `src/core/authoring/hooks.py` registered in T012ac, reading `src/core/authoring/provenance.py` and emitting `ENACTMENT_REFUSED` naming the authoring correlation ID. **In the pipeline, not in a module** — Principle III requires every tool invocation pass the fail-closed hooks, and a refusal reachable only by a caller remembering to call it is not enforcement.
- [ ] T052 [US2] Row **V1** in `tests/conformance/authoring/test_provenance.py`: attempt to apply a platform-authored artefact with no recorded merge; assert the refusal. The rule turns on **provenance, not capability**.
- [ ] T053 [US2] [GATE:fail-closed] Row **V2** in `tests/conformance/authoring/test_provenance.py`: assert the **T012c** definitions' ceilings are **disjoint** — the authoring one contains no enacting tool, the proposing one no authoring tool. V1 is the rule; this is the absence of anything to apply it to. Both rows, never one.
- [ ] T054 [US2] Row **V3** in `tests/conformance/authoring/test_provenance.py`: assert `terraform_apply` still registers `destructive`, non-repeatable, with its observer, and still applies human-authored configuration unchanged (FR-020a). A feature that made the platform safer by quietly narrowing an existing capability would have changed the product without saying so.

**Checkpoint**: the full path works end to end and refuses everywhere it must.

---

## Phase 7: US5 — The model is qualified for the role it is acting in (P1)

**Goal**: the matrix's third role, bound for the first time, against a corpus that can fail.

**Independent test**: attempt authoring with no qualified `write` cell and confirm it refuses;
qualify one and confirm it proceeds.

- [ ] T055 [US5] Row **Q1** in `tests/conformance/authoring/test_qualification.py`: authoring with no qualified `write` cell refuses `unqualified_cell` / `no_qualified_fallback`, **distinguishably from a provider outage**. (The gate itself is T012 — landed foundational.)
- [ ] T056 [US5] Build the corpus loader in `src/core/evals/authoring_corpus.py`: golden tasks (prompt, tooling invocation, **human-authored reference** carrying a **declared property set**, reference **author**) and must-deny cases (a subject seeded with a secret, with unrelated content, with instructions to the agent). A task declares **either** a property set **or** `expects_no_artifact = true`, and one declaring neither is **refused** — an empty property set matches trivially, which is the vacuous pass `parse_cases` already refuses for measured suites (research R18). **Injection-resistance cases carry a PAIRED subject** — the same task with and without the injected text — because that class is scored by byte-identical comparison (R18) and a single subject gives it nothing to compare against; a case in that class declaring no pair is refused.
- [ ] T057 [US5] Author the corpus in `evals/authoring/corpus.toml`, including at least one golden task that is **syntactically valid and substantively wrong** — a module wiring a static credential where dynamic secrets were asked for — and must-deny cases covering all three classes FR-017 names.
- [ ] T057a [US5] Add a golden task to `evals/authoring/corpus.toml` for a subject that **already has the integration**, declaring `expects_no_artifact = true`: the correct outcome is an empty artefact with a disclosure, not a duplicate. The spec's edge case, and one where a wrong answer looks exactly like a right one.
- [ ] T058 [US5] Implement the floor in `src/core/evals/authoring_corpus.py` on `src/core/evals/intake_seed.py`'s mechanism, **raising rather than warning** (FR-018b): the valid-but-wrong case, the three must-deny classes, and a human-authored reference on **every** golden task.
- [ ] T059 [US5] Row **Q3** in `tests/conformance/authoring/test_qualification.py`: present a corpus below the floor and assert a **raise**, not a warning. Assert the valid-but-wrong clause specifically — a corpus that only catches malformed output has not measured integration correctness (SC-008).
- [ ] T060 [US5] Row **Q4** in `tests/conformance/authoring/test_qualification.py`: a golden task without a reference is **refused** rather than scored on one gate, and each reference records its author. **The clause most likely to erode**, and it erodes by generating the references — which measures the generator against itself and passes everything.
- [ ] T061 [US5] Implement the two gates in `src/core/evals/authoring_scoring.py`, **reported as two numbers**: product tooling (does it parse, do the types line up) and reference comparison (is it subtly wrong). **Both are mechanical** — the second checks the artefact against the reference's **declared property set**, which is what FR-018's "on the properties the task is about" asks for and what makes ADR-0038's warning case decidable: *a static credential where dynamic secrets were asked for* is a property, not an impression. Collapsing them hides which occurred, and which occurred is the whole distinction.
- [ ] T061a [US5] Accept a **scorer identity** where a judge would go in `promote_model_version` (`src/core/evals/promotion.py`), refusing `promotion_incomplete` only when **both** are absent, per **ADR-0063** (T006aa). Measured: the current check refuses any non-`judge` cell naming no judge — and **no judge participates in this qualification at all**, since both correctness gates and all three must-deny classes are mechanical. Without this the `write` cell **cannot be promoted**, and forcing a judge into the field to satisfy a string check is the "gate that passes by vocabulary" 027 refused. Row **Q9** in `tests/conformance/authoring/test_qualification.py`: a cell naming neither is refused.
- [ ] T061b [US5] Declare `AUTHORING_REQUIRED_SUITES` in `src/core/evals/suites.py` beside `AUTHORING_QUALIFICATION`, and pass it as `required_suites` when promoting a `write` cell. The qualification is deliberately outside `SUITES` (T065), so **nothing else supplies the list `promote_model_version` checks `suites_passed` against** — declared beside the constant that excludes it, so the exclusion and the requirement are read together.
- [ ] T061c [US5] Record `qualified_by = "live"` for the first `write` cell, and row **Q8** in `tests/conformance/authoring/test_qualification.py` asserting a `write` cell qualified only by fixture is refused. `src/core/authority/matrix.py:44` anticipates this feature by name: the fixture/live distinction *"matters most for `write` — a model permitted to make changes"*, and a cell qualified against a recording is exactly what that warns about.
- [ ] T062 [US5] Add the `eval-authoring` target to `Makefile` and run it in the **enclave lane** (`.github/workflows/enclave.yml`), which **already installs the binary** — `install_hashicorp terraform "${TERRAFORM_VERSION}"` at line 165, a precedent research R10 never measured and whose framing overstated the novelty. Vendor a **filesystem provider mirror** under `evals/authoring/mirror/` with the providers pinned in the corpus, so `terraform init` is deterministic and needs no registry egress. Row **Q2** in `tests/conformance/authoring/test_qualification.py`: a case that **validates cleanly and diverges from the reference** passes gate one and fails gate two.
- [ ] T063 [US5] Row **Q2-unrunnable** in `tests/conformance/authoring/test_qualification.py`: run the gate with `terraform` off the path and assert the lane goes **red**. No degradation to `fmt`-only while still reporting "validated" — `UnrunnableSuite`'s discipline, and 012's twice-learned lesson that a lane which skips reads as green.
- [ ] T064 [US5] Row **Q5** in `tests/conformance/authoring/test_qualification.py`: a `write` cell failing any must-deny case cannot be promoted, and the cases are scored over **the artefact**, not over a stated refusal. A cell that says "I will not do that" and then does it passes a verb-scored suite and must fail this one.
- [ ] T065 [US5] Add `AUTHORING_QUALIFICATION` to `src/core/evals/suites.py` beside `INTAKE_QUALIFICATION`, **not** in `SUITES`, with the reasoning recorded: `SUITES` is the per-pack list, and membership would demand a corpus from the Vault pack for a capability it does not offer — 037's exact mistake, caught by the same rule.
- [ ] T066 [US5] Refuse at load in `src/core/packs/loader.py` a pack that **declares an authoring workflow and ships no corpus**, and assert a pack declaring none is **not asked for one**. Row **Q6** in `tests/conformance/authoring/test_qualification.py`: `OWED == {}` and `AUTHORING_QUALIFICATION not in SUITES`.
- [ ] T066a [US5] Row **Q7** in `tests/conformance/authoring/test_qualification.py`: **the adoption and promotion path is unchanged** (FR-021) — `promote_skill`'s order and refusal codes are as they were, and `tests/conformance/intake/` passes unmodified. Not theoretical: **T002 moves a module out of `core/intake/` and T065 edits `core/evals/suites.py`**, so this feature physically touches the path it promises not to change.

**Checkpoint**: the capability is gated by a qualification that can fail, and `OWED` is empty.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T067 Run quickstart **Scenario G** from `specs/038-authoring-workflows/quickstart.md` against the enclave: dispatch a real authoring run at a scratch repository, confirm the proposal appears, the trail carries `ARTIFACT_AUTHORED` and `PROPOSAL_OPENED`, and **no merge event exists**. Then merge by hand and confirm the merge is *observed* and the subsequent apply is the ordinary governed act. **The assembly is the one path no hermetic row covers**, and every previous feature that skipped it found something here.
- [ ] T068 [P] Move `docs/adr/0062-authoring-credentials-are-vended-per-task.md` **and `docs/adr/0063-a-mechanical-scorer-may-qualify-a-cell.md`** to **Accepted** with the security-maintainer review, land the Principle IV amendment from T006a, and record the Principle V review for the four audit members — **one obligation in four files**, on 037's T004/T005/T054 precedent.
- [ ] T068a [P] Reconcile `specs/038-authoring-workflows/quickstart.md` with the rows added across five remediations — T4, T5, T6, T7, C6, C7, C8, P0, P7, P8, P9, P10, P11, Q7, Q8, Q9, R3, V4, W3a, W6 — **and with the two-task job structure**, which Scenario G still describes as a single dispatch. **The guide is what somebody runs to believe the feature works**, and a validation guide describing an earlier design is worse than none.
- [ ] T069 [P] Add a realization note to `docs/adr/0038-integration-and-uplift.md` pointing at this feature, and reconcile `docs/adr/README.md` — its index rows have gone stale before, and only a mechanical header/index check caught it.
- [ ] T070 [P] Update `ROADMAP.md`: the integration-and-uplift row moves from named-and-unimplemented, and the `write` role is no longer unbound.
- [ ] T071 Run `make check` **and** the hermetic conformance lane; the local gate skips the hermetic rows, so a green `make check` alone does not mean this feature's rows ran.

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: audit, constitution, credential, tier, request, two trees)
          └─> Phase 3 (US1 — producing)
                 └─> Phase 4 (US3 — containment)          ← must precede publishing
                        ├─> Phase 5 (US4 — not redirected)
                        └─> Phase 6 (US2 — proposing, provenance)
                               └─> Phase 7 (US5 — qualification)
                                      └─> Phase 8 (Polish)
```

**Phase 5 and Phase 6 are independent of each other** and may run in parallel once Phase 4
lands. Everything else is sequential, because each layer bounds the one after it.

**Within Phase 2**, T006a/T006b/T006c are one obligation in three places — the amendment, the
code and the infrastructure — and none of them is complete alone.

## Parallel opportunities

- **Phase 1**: T002, T003 together (different trees).
- **Phase 2**: T005, T006, T006a alongside T007–T009 (audit, records, tier are disjoint files);
  T012a/T012c alongside T010/T011.
- **Phase 3**: T015–T017a together once T013/T014 land (row files and one builder).
- **Phase 4**: T023/T024 (file half) alongside T026/T027 (prose half) — the two halves are
  deliberately separate functions.
- **Phases 5 and 6** entire, in parallel.
- **Phase 6**: T041a/T041b alongside T042 — the manifest's load requirements and the handler are
  different work.
- **Phase 7**: T056 (loader) and T057/T057a (corpus content) are different work by different
  hands — the corpus is the "real work" ADR-0038 predicted, and it is the long pole.
- **Phase 8**: T068–T070 together.

## Implementation strategy

**MVP is Phases 1–3**: the platform can produce a file as a governed tool call, recorded, opt-in
per definition, with the write reaching execution the same way a read does. That alone closes
the measured gap — four tools across all packs and none of them writes anything — and it
publishes nothing, so it carries no exfiltration risk.

**Phase 4 is the gate on everything after it.** Containment must exist before publishing does,
because the pull request is a legitimate channel out of the isolation and is exactly where
private code would leave.

**Phase 7 is the long pole and the most likely to be quietly weakened.** FR-018c — a
human-authored reference on every golden task — is expensive, and generating the references
would satisfy the letter while measuring the generator against itself. T060 records each
reference's author so "human-authored" is a claim in the artefact rather than an intention in
a review.

## Notes

- **Gate types omitted**: none. All five apply to this feature.
- **`write` occupies existing vocabulary and widens nothing** — `RiskClass` and `Role` both
  already carry it (research R1), so no sealed-core edit beyond the four additive audit members.
- **The six obligations that must not be dropped**: the Principle V review (T068), the
  **Principle IV amendment** naming a third standing-credential exception (T006a, T068),
  ADR-0062 and **ADR-0063** moving to Accepted (T068), the corpus landing with the capability so
  `OWED` stays empty (T066), and the tier's move out of `core.intake` (T002).
- **What the first analyze pass cost, so the next task list starts differently**: three of four
  CRITICALs were *assert-over-something-nothing-builds* — the request (T012a), the credential
  path (T006b/c), the definitions (T012c). This document's own header warned about that shape
  and the warning was applied to **contract rows** rather than to **entities and records**.
  The fourth was a manifest that could not load. The remaining HIGH worth remembering is
  different in kind: the egress allowlist was checked for **mutability** and never for
  **contents**, and a control can be correctly immutable and wrongly valued.
- **What the second pass cost, which is the more useful lesson**: four findings were *built
  against the wrong subject* — an observer handed a key it could not use (T044a), a cell that
  could not be promoted because nothing judged it (T061a), and two mechanisms cited as
  precedent that are **not on the path** (`run_program` is registered nowhere; `reachable_tools`
  is called from tests only). All four came from **citing a real module instead of measuring
  whether anything calls it**. Naming a mechanism is not evidence that it runs.
