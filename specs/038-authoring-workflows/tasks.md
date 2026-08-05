# Tasks: The agent authors, and a person merges

**Input**: Design documents from `/specs/038-authoring-workflows/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature produces artefacts a person merges into their own repository, so its
rows *are* the deliverable. Every contract row — W1–W5, T1–T3, C1–C5, R1–R2, P1–P6, V1–V3,
Q1–Q6 — has a task, and every task that asserts has a task that builds.

**Remediated after the first analyze pass** (4 CRITICAL, 5 HIGH, 4 MEDIUM, 2 LOW). Thirteen
tasks were added and every task now names its file. The additions are suffixed rather than
renumbered so the analyze findings stay traceable to what fixed them.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T008 (tier posture by clause), T012 (no qualified `write` cell refuses), T031 (containment blocks emission), T040 (a redirected analyser holds no publishing credential), T053 (ceilings disjoint) |
| **Conformance** | Phases 3–7 — both contracts, `tests/conformance/authoring/` |
| **Correlation / evidence** | T020 (`ARTIFACT_AUTHORED` carries paths and digests, never content), T048 (the human's merge is distinguishable from everything the platform did) |
| **Eval** | Phase 7 entire — the `write` role's qualification (Q1–Q6) — plus T058, the corpus floor, and T041b, the new pack's own suites |
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
`src/core/isolation/` (moved), `packs/github/`, `evals/authoring/`,
`infra/jobs/authoring-tier.nomad.hcl`, `tests/conformance/authoring/`.

Conformance rows land by letter group: **W** → `test_producing.py`, **T** → `test_tier.py`,
**C** → `test_containment.py`, **R** → `test_redirection.py`, **P** → `test_proposing.py`,
**V** → `test_provenance.py`, **Q** → `test_qualification.py`, all under
`tests/conformance/authoring/`.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/authoring/__init__.py` and `tests/conformance/authoring/__init__.py`; add `tests/conformance/authoring` to the hermetic conformance lane's collection in `Makefile` so new rows run where they block merges (the 036 lesson: a gate asserted only locally is not a gate).
- [ ] T002 [P] Move `src/core/intake/tier.py` to `src/core/isolation/tier.py`, adding `src/core/isolation/__init__.py`; update imports in `tests/conformance/intake/test_isolation_tier.py` and `tests/conformance/intake/test_containment.py`, **and the path references in `specs/037-intake-gauntlet/plan.md` and `specs/037-intake-gauntlet/contracts/conformance-intake.md`**. **No behaviour change** — the module content is unchanged in this task. Two consumers now, and `core.authoring` importing `core.intake` would encode that authoring is part of the supply chain (research R3).
- [ ] T003 [P] Create `evals/authoring/README.md` and `packs/github/README.md`, each stating what the directory is for and what refuses when it is empty.

---

## Phase 2: Foundational (blocking all stories)

**The audit vocabulary, the constitution amendment, the credential path, the qualification
refusal, the tier, the request, and the two trees. Nothing in Phases 3–7 can record, refuse,
isolate, authenticate, arrive or produce until these exist.**

- [ ] T004 Add four additive `AuditEventType` members to `src/core/audit/schema.py`: `ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`, `ENACTMENT_REFUSED`. Document each member's payload rule in the docstring on `ANALYSIS_VERDICT`'s precedent — in particular that `CONTAINMENT_REFUSED` carries **codes, locations and digests, never the matched text** (`CANARY_CONTACT`'s rule: the record of a leak must not be a second copy of what leaked) and `ARTIFACT_AUTHORED` carries **paths and per-path digests, never content**.
- [ ] T005 [P] Confirm `tests/conformance/evidence/test_audit_schema.py::test_widening_the_event_vocabulary_moves_no_existing_hash` stays green with the four members added; if it does not, the members were not additive.
- [ ] T006 [P] Author `docs/adr/0062-authoring-credentials-are-vended-per-task.md` as **Proposed**: the version-control credential is Vault-vended, hour-scoped and **installation-scoped to the requester's own repositories**, never a personal access token (033 already refused one), and **never mounted into the hardened tier**. Add its row to `docs/adr/README.md`.
- [ ] T006a **Amend `.specify/memory/constitution.md` Principle IV to name a THIRD standing-credential exception**, with a Sync Impact Report citing ADR-0062, on the precedent 027 set when the model vendor credential arrived. The exception inherits the other two's conditions — rotated, Control-Group-governed, trust-store only, read under the reading workload's own attested identity, delivered per task, never persisted. **Principle IV says "exactly two named exceptions"; shipping a third without amending would make a MUST principle untrue** (research R15), and arguing the clause does not bite is the narrowing 027 declined.
- [ ] T006b Build the publishing credential in `src/core/authoring/credential.py`: attested workload identity → Vault → an hour-scoped, installation-scoped token, on `core/durability/credentials.py`'s `NomadWorkloadIdentity` pattern, accepting no credential from a caller. **Here rather than in `core/durability/`** so a new credential class does not widen sealed core beyond the four audit members. [GATE:no-secret-leak] Assert in `tests/unit/test_no_static_credentials.py` that the token is never persisted and the module trips none of the `FORBIDDEN` names.
- [ ] T006c Provision the Vault role and KV path for the App key in `infra/terraform/` beside the existing `ceilings.tf` pattern, readable only by the publishing allocation's attested identity — never by the analysing one.
- [ ] T007 Add `SubjectMount(path, read_only)` and a `subject_mount: SubjectMount | None = None` field to `TierPosture` in `src/core/isolation/tier.py`. `repo_mounted` **keeps its name and its meaning — the platform's own tree** — which is already what `infra/jobs/analysis-tier.nomad.hcl` says it guards against.
- [ ] T008 [GATE:fail-closed] Extend `is_hardened()` in `src/core/isolation/tier.py` with exactly one clause: a **writable** subject mount fails, naming that clause as every other refusal does. Absent passes (037's payload delivery); read-only passes.
- [ ] T009 Author `infra/jobs/authoring-tier.nomad.hcl`: the hardened posture with a **read-only subject mount** and **`HARNESS_EGRESS_ALLOWLIST = ""`**. Comment why the mount is not the reversal it looks like (037's "no mount" meant *do not hand a redirected analyser the platform's own tree*; the subject is the requester's) **and why the allowlist is empty**: this step reads a mount and fetches nothing, so inheriting 037's `github.com` would leave a redirected agent holding a private codebase with a route to the one allowlisted host that serves arbitrary user content (research R13).
- [ ] T009a Row **T4** in `tests/conformance/authoring/test_tier.py`: assert `infra/jobs/authoring-tier.nomad.hcl` declares an **empty** egress allowlist and that the value is **static in the jobspec** rather than computed per run. FR-005a requires the allowlist be static, not that it keep 037's value — and a control can be correctly immutable and wrongly valued.
- [ ] T010 Build the two trees in `src/core/authoring/workspace.py`: a **read-only subject** and a **writable workspace**, with the subject reachable for reading and never for writing. Document that the proposal is built from the workspace and never from the subject — this is what makes FR-013a a property rather than a check (research R5).
- [ ] T011 Build `AuthoredArtifact` in `src/core/authoring/artifact.py`: `paths`, per-path `digests`, the `created`/`edited` partition (a path is `edited` iff it exists in the subject), `truncated`, `truncation_note`. **No content field** — see T004's rule.
- [ ] T012 [GATE:fail-closed] Gate authoring on a qualified `write` cell in `src/core/authoring/tool.py`: resolve through the existing `resolve_with_fallback`, which has no third branch. **Landed foundational deliberately** — this is US5's first acceptance scenario, and a capability that could run unqualified for even one commit is the gap 026 found for `ask`.
- [ ] T012a Build the `AuthoringRequest` record in `src/core/authoring/request.py`: `correlation_id`, `requester`, `target_repository`, `task`, `pack`, with validation refusing a pack that declares no authoring workflow. **T043 asserts an ownership refusal over this record and the first task list never built it** — the assert-over-nothing-built shape 036 and 037 each found.
- [ ] T012b Carry the request as the **dispatch payload** in `src/surfaces/dispatch/entrypoint.py`, adding **no new northbound operation**. Row **P0** in `tests/conformance/authoring/test_proposing.py`: assert no new northbound verb exists on any transport, so Principle II's surface parity is **inherited rather than owed** (research R16). An absent parity row and a deliberately-inherited one look identical in a diff, and only one is a gate regression.
- [ ] T012c Author the two definition bindings records under `infra/terraform/definitions/`: the **analysing** definition (`tier = 2` — `author-module` declares `minimum_tier = 2` and `DEFAULT_TIER` is 1, so a definition that omits it is refused), `packs = ["terraform"]`, `binding_map = {"write": ...}`; and the **proposing** definition, `packs = ["github"]`, no authoring tool. **T039 and T053 assert properties of these two and nothing created them.**

---

## Phase 3: US1 — The agent produces something, and it is governed like anything else (P1)

**Goal**: the platform's first tool that produces, reached the same way everything else is.

**Independent test**: ask for a file, confirm it is produced, and confirm the write passed the
same governed entry a read does with the same records behind it.

- [ ] T013 [US1] Implement the `author_file` handler in `src/core/authoring/tool.py`: writes into the workspace, returns paths and digests, refuses a path outside the workspace. Register it with `risk_class="write"` — **the registry's first occupant of a class defined in 013 and unused since** (research R1).
- [ ] T014 [US1] Register `author_file` in `src/surfaces/toolset.py` so it is reachable only through a definition's ceiling, on `run_program`'s precedent — the registry is the opt-in switch, not a flag somebody must remember.
- [ ] T015 [US1] Row **W1** in `tests/conformance/authoring/test_producing.py`: a write is a governed decision, producing the same `PRE_DECISION`/`TOOL_OUTCOME` shape a read does. Assert the registered `risk_class` is `write`, so a later change to `read` fails here rather than silently widening what may reach it.
- [ ] T016 [US1] Row **W2** in `tests/conformance/authoring/test_producing.py`: a definition whose ceiling omits `author_file` is refused `tool_not_permitted`, exactly as for any other tool outside a ceiling.
- [ ] T017 [US1] Row **W3** in `tests/conformance/authoring/test_producing.py`: submit a program that writes a file; assert the write appears as **its own governed step** through the seam rather than as a side effect of `run_program`.
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
- [ ] T026 [US3] Implement the verbatim-span scan in `src/core/authoring/containment.py`: a span of at least N characters matching a subject file **not** in `artifact.paths` refuses `analysed_content_in_prose`. Keep this a **separate function** from the file half — they hold for different reasons, and one function would let the strong half read as covering both.
- [ ] T027 [US3] Row **C4** in `tests/conformance/authoring/test_containment.py`: a rationale quoting an untouched subject file verbatim is refused.
- [ ] T028 [US3] Implement secret detection in `src/core/authoring/containment.py` across produced files, commit messages and proposal prose, refusing `secret_value_in_output` (FR-010, FR-011).
- [ ] T029 [US3] [GATE:no-secret-leak] Row **C1** in `tests/conformance/authoring/test_containment.py`: author against a subject containing a credential; assert the value appears in **none** of the files, commits or body — by assertion over the artefact, never by inspection — and that the attempt lands `CONTAINMENT_REFUSED`.
- [ ] T030 [US3] Emit `CONTAINMENT_REFUSED` from `src/core/authoring/containment.py` carrying **code, location and digest and never the matched text**, per T004's rule.
- [ ] T031 [US3] [GATE:fail-closed] Refuse **emission** in `src/core/authoring/proposal.py` on any containment failure — a proposal that failed containment is not composed-and-flagged, it is not emitted.
- [ ] T032 [US3] Disclose truncation in `src/core/authoring/proposal.py`, and row **C5** in `tests/conformance/authoring/test_containment.py`: a subject too large to read in full produces a proposal that says so.
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
- [ ] T037 [US4] Wire the injection-lens hooks onto the analysis path in `src/core/authoring/tool.py` (ADR-0038: *necessary rather than precautionary*), reusing `src/core/evals/injection_patterns.py` rather than authoring a second pattern set.
- [ ] T038 [US4] Row **R1** in `tests/conformance/authoring/test_redirection.py`: author against a subject carrying text addressed to the agent; assert the produced artefact is **byte-identical** to the artefact from the same subject without that text, and that the attempt is recorded. Byte-identical rather than "unaffected" — "unaffected" is a judgement, and a row requiring one is graded by whoever wrote it.
- [ ] T039 [US4] Row **R2** in `tests/conformance/authoring/test_redirection.py`: assert `reachable_tools(bindings, loaded, ceiling)` for the **analysing definition created in T012c** contains nothing that egresses. This is what keeps FR-015 structural rather than a promise about the agent declining.
- [ ] T040 [US4] [GATE:fail-closed] Row **T3** in `tests/conformance/authoring/test_tier.py`: assert **structurally** that `infra/jobs/authoring-tier.nomad.hcl` holds **no version-control credential**, and that the proposing definition's ceiling holds no authoring or analysis tool. A redirected analyser then has neither a tool, nor a credential, nor (per T009a) an egress route.

**Checkpoint**: analysis is contained and cannot be redirected out. Still nothing published.

---

## Phase 6: US2 — The work lands as a proposal, never as a change (P1)

**Goal**: publishing, gated by everything above it, and a platform that does not enact what it
authored.

**Independent test**: confirm no path produces a merge, an apply, or a write outside the
requester's own repositories, and that a human decision is required and recorded.

- [ ] T041 [US2] Author `packs/github/pack.toml` declaring one tool, `open_proposal`: `risk_class = "write"`, `repeatable = false`, `observer` required, `product = "github"`. **Record the transport determination under ADR-0037's standing test** — MCP where a server exists, is mature and is supported; native otherwise — in a comment, as `packs/terraform/pack.toml` does for both halves of the rule.
- [ ] T041a [US2] Declare `probe = "github_probe"` in `packs/github/pack.toml` and bind it in `src/surfaces/probes.py`. **Measured: a pack whose tools declare a product and names no probe refuses `probe_required` at load** (`src/core/packs/loader.py:285`) — the pack as first sketched could not have loaded, and the terraform manifest already records the trap.
- [ ] T041b [US2] Declare the five eval suites in `packs/github/pack.toml` and ship their cases under `packs/github/evals/*.toml` at the floor of five each. **The loader's floor iterates DECLARED suites** (`src/core/packs/loader.py:288`), so a pack declaring none has no floor to fail — it would be this platform's first pack outside the eval gate, and first **by accident**. Principle VIII is a MUST and both existing packs declare all five.
- [ ] T042 [US2] Implement the `open_proposal` handler and its observer in `src/surfaces/handlers.py`, authenticating through `src/core/authoring/credential.py` — the allocation as itself, no token accepted from a caller.
- [ ] T043 [US2] Refuse a `target_repository` outside the requester's own in `src/core/authoring/request.py` **before anything is produced**, and row **P2** in `tests/conformance/authoring/test_proposing.py`: assert the artefact is empty and no `ARTIFACT_AUTHORED` exists. "Refused after producing" and "refused before producing" are different postures, and only one leaves nothing on disk to leak.
- [ ] T044 [US2] Derive the proposal branch from the correlation ID in `src/core/authoring/proposal.py`, and row **P3** in `tests/conformance/authoring/test_proposing.py`: author twice against the same target; assert two distinct branches and that the first proposal is intact (FR-009).
- [ ] T045 [US2] Emit `PROPOSAL_OPENED` from `src/core/authoring/proposal.py` carrying repository, branch, artefact digest and proposal reference. **No merge member** — a merge is observed, never written by the platform.
- [ ] T046 [US2] Row **P1** in `tests/conformance/authoring/test_proposing.py`: completed authoring yields a proposal and **no merge and no apply occurred**, asserted over the trail rather than over the proposal's own claim about itself.
- [ ] T047 [US2] Row **P4** in `tests/conformance/authoring/test_proposing.py`: kill the run mid-`open_proposal`; assert the tool is registered non-repeatable **with an observer** and that resumption resolves by asking the host whether the proposal exists rather than by guessing. Without the observer the step lands `CANNOT_DETERMINE` and parks the run.
- [ ] T048 [US2] Row **P5** in `tests/conformance/authoring/test_proposing.py`: merge a proposal and assert the record distinguishes the person's act from the platform's, and that no member of the platform's vocabulary can be read as an approval (ADR-0043, Principle IX).
- [ ] T049 [US2] Row **P6** in `tests/conformance/authoring/test_proposing.py`: a proposal nobody has reviewed stays `opened` and is reported as `opened`. Forecloses a dashboard counting proposals as delivered work.
- [ ] T050 [US2] Build the provenance record in `src/core/authoring/provenance.py`: content digest → authoring correlation ID → proposal state, written when the artefact is authored and readable **at the moment of enactment** (FR-020b).
- [ ] T051 [US2] Refuse enactment of platform-authored content with no recorded human merge in `src/core/authoring/provenance.py`, emitting `ENACTMENT_REFUSED` naming the authoring correlation ID.
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
- [ ] T056 [US5] Build the corpus loader in `src/core/evals/authoring_corpus.py`: golden tasks (prompt, tooling invocation, **human-authored reference**, reference **author**) and must-deny cases (a subject seeded with a secret, with unrelated content, with instructions to the agent).
- [ ] T057 [US5] Author the corpus in `evals/authoring/corpus.toml`, including at least one golden task that is **syntactically valid and substantively wrong** — a module wiring a static credential where dynamic secrets were asked for — and must-deny cases covering all three classes FR-017 names.
- [ ] T057a [US5] Add a golden task to `evals/authoring/corpus.toml` for a subject that **already has the integration**: the correct outcome is an empty artefact with a disclosure, not a duplicate. The spec's edge case, and one where a wrong answer looks exactly like a right one.
- [ ] T058 [US5] Implement the floor in `src/core/evals/authoring_corpus.py` on `src/core/evals/intake_seed.py`'s mechanism, **raising rather than warning** (FR-018b): the valid-but-wrong case, the three must-deny classes, and a human-authored reference on **every** golden task.
- [ ] T059 [US5] Row **Q3** in `tests/conformance/authoring/test_qualification.py`: present a corpus below the floor and assert a **raise**, not a warning. Assert the valid-but-wrong clause specifically — a corpus that only catches malformed output has not measured integration correctness (SC-008).
- [ ] T060 [US5] Row **Q4** in `tests/conformance/authoring/test_qualification.py`: a golden task without a reference is **refused** rather than scored on one gate, and each reference records its author. **The clause most likely to erode**, and it erodes by generating the references — which measures the generator against itself and passes everything.
- [ ] T061 [US5] Implement the two gates in `src/core/evals/authoring_scoring.py`, **reported as two numbers**: product tooling (does it parse, do the types line up) and reference comparison (is it subtly wrong). Collapsing them hides which occurred, and which occurred is the whole distinction.
- [ ] T062 [US5] Add the `eval-authoring` target to `Makefile` running the gate lane with the `terraform` binary and a pinned provider mirror, and row **Q2** in `tests/conformance/authoring/test_qualification.py`: a case that **validates cleanly and diverges from the reference** passes gate one and fails gate two.
- [ ] T063 [US5] Row **Q2-unrunnable** in `tests/conformance/authoring/test_qualification.py`: run the gate with `terraform` off the path and assert the lane goes **red**. No degradation to `fmt`-only while still reporting "validated" — `UnrunnableSuite`'s discipline, and 012's twice-learned lesson that a lane which skips reads as green.
- [ ] T064 [US5] Row **Q5** in `tests/conformance/authoring/test_qualification.py`: a `write` cell failing any must-deny case cannot be promoted, and the cases are scored over **the artefact**, not over a stated refusal. A cell that says "I will not do that" and then does it passes a verb-scored suite and must fail this one.
- [ ] T065 [US5] Add `AUTHORING_QUALIFICATION` to `src/core/evals/suites.py` beside `INTAKE_QUALIFICATION`, **not** in `SUITES`, with the reasoning recorded: `SUITES` is the per-pack list, and membership would demand a corpus from the Vault pack for a capability it does not offer — 037's exact mistake, caught by the same rule.
- [ ] T066 [US5] Refuse at load in `src/core/packs/loader.py` a pack that **declares an authoring workflow and ships no corpus**, and assert a pack declaring none is **not asked for one**. Row **Q6** in `tests/conformance/authoring/test_qualification.py`: `OWED == {}` and `AUTHORING_QUALIFICATION not in SUITES`.
- [ ] T066a [US5] Row **Q7** in `tests/conformance/authoring/test_qualification.py`: **the adoption and promotion path is unchanged** (FR-021) — `promote_skill`'s order and refusal codes are as they were, and `tests/conformance/intake/` passes unmodified. Not theoretical: **T002 moves a module out of `core/intake/` and T065 edits `core/evals/suites.py`**, so this feature physically touches the path it promises not to change.

**Checkpoint**: the capability is gated by a qualification that can fail, and `OWED` is empty.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T067 Run quickstart **Scenario G** from `specs/038-authoring-workflows/quickstart.md` against the enclave: dispatch a real authoring run at a scratch repository, confirm the proposal appears, the trail carries `ARTIFACT_AUTHORED` and `PROPOSAL_OPENED`, and **no merge event exists**. Then merge by hand and confirm the merge is *observed* and the subsequent apply is the ordinary governed act. **The assembly is the one path no hermetic row covers**, and every previous feature that skipped it found something here.
- [ ] T068 [P] Move `docs/adr/0062-authoring-credentials-are-vended-per-task.md` to **Accepted** with the security-maintainer review, land the Principle IV amendment from T006a, and record the Principle V review for the four audit members — **one obligation in three files**, on 037's T004/T005/T054 precedent.
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
- **The five obligations that must not be dropped**: the Principle V review (T068), the
  **Principle IV amendment** naming a third standing-credential exception (T006a, T068),
  ADR-0062 moving to Accepted (T068), the corpus landing with the capability so `OWED` stays
  empty (T066), and the tier's move out of `core.intake` (T002).
- **What the first analyze pass cost, so the next task list starts differently**: three of four
  CRITICALs were *assert-over-something-nothing-builds* — the request (T012a), the credential
  path (T006b/c), the definitions (T012c). This document's own header warned about that shape
  and the warning was applied to **contract rows** rather than to **entities and records**.
  The fourth was a manifest that could not load. The remaining HIGH worth remembering is
  different in kind: the egress allowlist was checked for **mutability** and never for
  **contents**, and a control can be correctly immutable and wrongly valued.
