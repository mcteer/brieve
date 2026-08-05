# Tasks: The agent authors, and a person merges

**Input**: Design documents from `/specs/038-authoring-workflows/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature produces artefacts a person merges into their own repository, so its
rows *are* the deliverable. Every contract row — W1–W5, T1–T3, C1–C5, R1–R2, P1–P6, V1–V3,
Q1–Q6 — has a task, and every task that asserts has a task that builds.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T008 (tier posture by clause), T012 (no qualified `write` cell refuses), T031 (containment blocks emission), T040 (a redirected analyser holds no publishing credential), T053 (ceilings disjoint) |
| **Conformance** | Phases 3–7 — both contracts, `tests/conformance/authoring/` |
| **Correlation / evidence** | T020 (`ARTIFACT_AUTHORED` carries paths and digests, never content), T048 (the human's merge is distinguishable from everything the platform did) |
| **Eval** | Phase 7 entire — the `write` role's qualification (Q1–Q6) — plus T058, the corpus floor |
| **No-secret-leak** | T029 (a seeded credential reaches neither files, commits, nor prose), T030 (`CONTAINMENT_REFUSED` carries codes and digests, never the matched text) |

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

## Phase ordering, and why it is not the story numbering

All five stories are P1. The phases follow the plan's layering — **the layer that can carry
private code out lands only once the layer that bounds it exists** — so US3 (containment)
precedes US2 (publishing) despite the numbering. Composing a proposal and publishing one are
separated for exactly this reason.

**The whole feature merges as one change.** Phase 7 lands the qualification, but T012 lands the
*refusal* in Phase 2, so there is no commit at which authoring could run under an unqualified
cell. `OWED` never has a window (FR-019).

## Path Conventions

Single project: `src/`, `tests/` at repository root. New: `src/core/authoring/`,
`src/core/isolation/` (moved), `packs/github/`, `evals/authoring/`,
`tests/conformance/authoring/`.

---

## Phase 1: Setup

- [ ] T001 Create `src/core/authoring/__init__.py` and `tests/conformance/authoring/__init__.py`; add `tests/conformance/authoring` to the hermetic conformance lane's collection so new rows run where they block merges (the 036 lesson: a gate asserted only locally is not a gate).
- [ ] T002 [P] Move `src/core/intake/tier.py` to `src/core/isolation/tier.py` with `src/core/isolation/__init__.py`; update the imports in `tests/conformance/intake/test_isolation_tier.py` and `tests/conformance/intake/test_containment.py`. **No behaviour change** — the module content is unchanged in this task. Two consumers now, and `core.authoring` importing `core.intake` would encode that authoring is part of the supply chain (research R3).
- [ ] T003 [P] Create `evals/authoring/` and `packs/github/` with a README in each stating what the directory is for and what refuses when it is empty.

---

## Phase 2: Foundational (blocking all stories)

**The audit vocabulary, the qualification refusal, the tier's new clause, and the two trees.
Nothing in Phases 3–7 can record, refuse, isolate or produce until these exist.**

- [ ] T004 Add four additive `AuditEventType` members to `src/core/audit/schema.py`: `ARTIFACT_AUTHORED`, `PROPOSAL_OPENED`, `CONTAINMENT_REFUSED`, `ENACTMENT_REFUSED`. Document each member's payload rule in the docstring on `ANALYSIS_VERDICT`'s precedent — in particular that `CONTAINMENT_REFUSED` carries **codes, locations and digests, never the matched text** (`CANARY_CONTACT`'s rule: the record of a leak must not be a second copy of what leaked) and `ARTIFACT_AUTHORED` carries **paths and per-path digests, never content**.
- [ ] T005 [P] Confirm `test_widening_the_event_vocabulary_moves_no_existing_hash` stays green with the four members added; if it does not, the members were not additive.
- [ ] T006 [P] Author `docs/adr/0062-authoring-credentials-are-vended-per-task.md` as **Proposed**: the version-control credential is Vault-vended, hour-scoped and **installation-scoped to the requester's own repositories**, never a personal access token (033 already refused one), and **never mounted into the hardened tier**. Add its row to `docs/adr/README.md`.
- [ ] T007 Add `SubjectMount(path, read_only)` and a `subject_mount: SubjectMount | None = None` field to `TierPosture` in `src/core/isolation/tier.py`. `repo_mounted` **keeps its name and its meaning — the platform's own tree** — which is already what `analysis-tier.nomad.hcl` says it guards against.
- [ ] T008 [GATE:fail-closed] Extend `is_hardened()` with exactly one clause: a **writable** subject mount fails, naming that clause as every other refusal does. Absent passes (037's payload delivery); read-only passes.
- [ ] T009 Add the read-only subject mount to `infra/jobs/analysis-tier.nomad.hcl`, with a comment stating why this is not the reversal it looks like: 037's "no mount" rule meant *do not hand a redirected analyser the platform's own tree*, and the subject is the requester's. **Keep `HARNESS_EGRESS_ALLOWLIST` static configuration** (FR-005a).
- [ ] T010 Build the two trees in `src/core/authoring/workspace.py`: a **read-only subject** and a **writable workspace**, with the subject reachable for reading and never for writing. Document that the proposal is built from the workspace and never from the subject — this is what makes FR-013a a property rather than a check (research R5).
- [ ] T011 Build `AuthoredArtifact` in `src/core/authoring/artifact.py`: `paths`, per-path `digests`, the `created`/`edited` partition (a path is `edited` iff it exists in the subject), `truncated`, `truncation_note`. **No content field** — see T004's rule.
- [ ] T012 [GATE:fail-closed] Gate authoring on a qualified `write` cell in `src/core/authoring/tool.py`: resolve through the existing `resolve_with_fallback`, which has no third branch. **Landed foundational deliberately** — this is US5's first acceptance scenario, and a capability that could run unqualified for even one commit is the gap 026 found for `ask`.

---

## Phase 3: US1 — The agent produces something, and it is governed like anything else (P1)

**Goal**: the platform's first tool that produces, reached the same way everything else is.

**Independent test**: ask for a file, confirm it is produced, and confirm the write passed the
same governed entry a read does with the same records behind it.

- [ ] T013 [US1] Implement the `author_file` handler in `src/core/authoring/tool.py`: writes into the workspace, returns paths and digests, refuses a path outside the workspace. Register it with `risk_class="write"` — **the registry's first occupant of a class defined in 013 and unused since** (research R1).
- [ ] T014 [US1] Wire registration so the tool is reachable only through a definition's ceiling, on `run_program`'s precedent — the registry is the opt-in switch, not a flag somebody must remember.
- [ ] T015 [US1] Row **W1** in `tests/conformance/authoring/test_producing.py`: a write is a governed decision, producing the same `PRE_DECISION`/`TOOL_OUTCOME` shape a read does. Assert the registered `risk_class` is `write`, so a later change to `read` fails here rather than silently widening what may reach it.
- [ ] T016 [US1] Row **W2**: a definition whose ceiling omits `author_file` is refused `tool_not_permitted`, exactly as for any other tool outside a ceiling.
- [ ] T017 [US1] Row **W3**: submit a program that writes a file; assert the write appears as **its own governed step** through the seam rather than as a side effect of `run_program`. Forecloses a sandbox that touches the filesystem directly, which would make code mode a way to act without a write tool.
- [ ] T018 [US1] Emit `ARTIFACT_AUTHORED` on completion, carrying paths, per-path digests, the created/edited partition and the truncation flag.
- [ ] T019 [US1] Record what was consulted to produce the artefact, wiring `src/core/packs/consulted.py` into the authoring path so FR-004's "what was consulted" is recoverable rather than implied (ADR-0004, skills-first).
- [ ] T020 [US1] [GATE:no-secret-leak] Row **W4**: the trail names every path and digest and the consulted skills, and **no file content appears anywhere in it**. The artefact is a derivative of a private repository and the trail is append-only.
- [ ] T021 [US1] Make an empty artefact a completed outcome rather than a failure, and row **W5**: a run that produced nothing completes, records an empty artefact, and is distinguishable from a run that failed.

**Checkpoint**: files are produced and governed. Nothing is bounded and nothing is published yet.

---

## Phase 4: US3 — Nothing the agent read leaves with what it wrote (P1)

**Goal**: the proposal carries the change and nothing else, enforced by inspecting the artefact.

**Independent test**: author against a subject seeded with a secret and with distinctive
unrelated content; confirm neither reaches the artefact, the commits, or the description.

- [ ] T022 [US3] Compose the proposal in `src/core/authoring/proposal.py`: files the change **created**, plus **diffs** of the files it edited, built from `artifact.paths` against the subject using `difflib`. The subject is never enumerated — it is read only for paths the agent already wrote.
- [ ] T023 [US3] Row **C2**: seed the subject with distinctive content in a file the task does not touch; assert it is absent from the proposal, **and assert the mechanism** — the file set is built from the workspace, so the subject is not a source. This row asserts a property, not a check.
- [ ] T024 [US3] Row **C3**: edit a file and assert the diff's surrounding context is **present and not refused**. A rule that forbade it would forbid editing, and a containment check tuned until it passed would plausibly have arrived there (FR-013b).
- [ ] T025 [US3] Compose the proposal body from **structured sections** — task, files touched, disclosures, limits — with exactly **one** free-text rationale field. The structure is the bound; the scan below is what covers the one field it cannot structure away.
- [ ] T026 [US3] Implement the verbatim-span scan in `src/core/authoring/containment.py`: a span of at least N characters matching a subject file **not** in `artifact.paths` refuses `analysed_content_in_prose`. Keep this a **separate function** from the file half — they hold for different reasons, and one function would let the strong half read as covering both.
- [ ] T027 [US3] Row **C4**: a rationale quoting an untouched subject file verbatim is refused.
- [ ] T028 [US3] Implement secret detection across produced files, commit messages and proposal prose, refusing `secret_value_in_output` (FR-010, FR-011).
- [ ] T029 [US3] [GATE:no-secret-leak] Row **C1**: author against a subject containing a credential; assert the value appears in **none** of the files, commits or body — by assertion over the artefact, never by inspection — and that the attempt lands `CONTAINMENT_REFUSED`.
- [ ] T030 [US3] Emit `CONTAINMENT_REFUSED` carrying **code, location and digest and never the matched text**, per T004's rule.
- [ ] T031 [US3] [GATE:fail-closed] Refuse **emission** on any containment failure — a proposal that failed containment is not composed-and-flagged, it is not emitted.
- [ ] T032 [US3] Disclose truncation in the proposal, and row **C5**: a subject too large to read in full produces a proposal that says so. A proposal built from part of a codebase that does not say so reads identically to a complete one.
- [ ] T033 [US3] Row **C4-companion**: assert a **paraphrase** of untouched subject content is **not** caught, and document it as the residual risk. Stating the limit is what stops "containment is structural" being read as covering the description — the exact conflation FR-013 exists to prevent.
- [ ] T034 [US3] **Prove C1 can fail**: a row that removes the seeded secret from the fixture subject and asserts C1 then fails. A must-deny case that never puts a secret anywhere a generator could reach is ADR-0047's passing stub, and it is the most available one in this feature.

**Checkpoint**: an artefact can be composed and is bounded to the change. Nothing publishes yet.

---

## Phase 5: US4 — Hostile repository content does not redirect the agent (P1)

**Goal**: the tier holds with a subject in it, and a successful redirection has nowhere to go.

**Independent test**: author against a repository carrying instructions addressed to the agent;
confirm the output is unaffected and the attempt appears in the record.

- [ ] T035 [US4] Row **T1**: assert `is_hardened()` **by clause** — subject mount absent passes, read-only passes, **writable fails** naming that clause — and that the platform's tree is unmounted and the egress allowlist is static rather than per-run.
- [ ] T036 [US4] Row **T2**: 037's refusal is unchanged — `repo_mounted=True` still fails with its original message. A feature that extends an isolation check is exactly where one gets accidentally relaxed.
- [ ] T037 [US4] Wire the injection-lens hooks onto the analysis path (ADR-0038: *necessary rather than precautionary*), reusing `core/evals/injection_patterns.py` rather than authoring a second pattern set.
- [ ] T038 [US4] Row **R1**: author against a subject carrying text addressed to the agent; assert the produced artefact is **byte-identical** to the artefact from the same subject without that text, and that the attempt is recorded. Byte-identical rather than "unaffected" — "unaffected" is a judgement, and a row requiring one is graded by whoever wrote it.
- [ ] T039 [US4] Row **R2**: assert `reachable_tools(bindings, loaded, ceiling)` for the analysing definition contains nothing that egresses. This is what keeps FR-015 structural rather than a promise about the agent declining.
- [ ] T040 [US4] [GATE:fail-closed] Row **T3**: assert **structurally** that the hardened-tier allocation's environment holds **no version-control credential**, and that the publishing step's ceiling holds no authoring or analysis tool. A redirected analyser then has neither a tool nor a credential — containment as a fact about which allocation holds what.

**Checkpoint**: analysis is contained and cannot be redirected out. Still nothing published.

---

## Phase 6: US2 — The work lands as a proposal, never as a change (P1)

**Goal**: publishing, gated by everything above it, and a platform that does not enact what it
authored.

**Independent test**: confirm no path produces a merge, an apply, or a write outside the
requester's own repositories, and that a human decision is required and recorded.

- [ ] T041 [US2] Author `packs/github/pack.toml` declaring one tool, `open_proposal`: `risk_class = "write"`, `repeatable = false`, `observer` required. **Record the transport determination under ADR-0037's standing test** — MCP where a server exists, is mature and is supported; native otherwise — in a comment, as `packs/terraform/pack.toml` does for both halves of the rule.
- [ ] T042 [US2] Implement the `open_proposal` handler and its observer in `src/surfaces/handlers.py`, authenticating through the ADR-0062 credential path — the allocation as itself, a short-lived installation-scoped token from Vault, no token accepted from a caller.
- [ ] T043 [US2] Refuse a `target_repository` outside the requester's own **before anything is produced**, and row **P2**: assert the artefact is empty and no `ARTIFACT_AUTHORED` exists. "Refused after producing" and "refused before producing" are different postures, and only one leaves nothing on disk to leak.
- [ ] T044 [US2] Derive the proposal branch from the correlation ID, and row **P3**: author twice against the same target; assert two distinct branches and that the first proposal is intact (FR-009).
- [ ] T045 [US2] Emit `PROPOSAL_OPENED` carrying repository, branch, artefact digest and proposal reference. **No merge member** — a merge is observed, never written by the platform.
- [ ] T046 [US2] Row **P1**: completed authoring yields a proposal and **no merge and no apply occurred**, asserted over the trail rather than over the proposal's own claim about itself.
- [ ] T047 [US2] Row **P4**: kill the run mid-`open_proposal`; assert the tool is registered non-repeatable **with an observer** and that resumption resolves by asking the host whether the proposal exists rather than by guessing. Without the observer the step lands `CANNOT_DETERMINE` and parks the run.
- [ ] T048 [US2] Row **P5**: merge a proposal and assert the record distinguishes the person's act from the platform's, and that no member of the platform's vocabulary can be read as an approval (ADR-0043, Principle IX).
- [ ] T049 [US2] Row **P6**: a proposal nobody has reviewed stays `opened` and is reported as `opened`. Forecloses a dashboard counting proposals as delivered work.
- [ ] T050 [US2] Build the provenance record in `src/core/authoring/provenance.py`: content digest → authoring correlation ID → proposal state, written when the artefact is authored and readable **at the moment of enactment** (FR-020b).
- [ ] T051 [US2] Refuse enactment of platform-authored content with no recorded human merge, emitting `ENACTMENT_REFUSED` naming the authoring correlation ID.
- [ ] T052 [US2] Row **V1**: attempt to apply a platform-authored artefact with no recorded merge; assert the refusal. The rule turns on **provenance, not capability**.
- [ ] T053 [US2] [GATE:fail-closed] Row **V2**: assert the authoring definition's ceiling contains no enacting tool and the proposing definition's contains no authoring tool — the ceilings are **disjoint**. V1 is the rule; this is the absence of anything to apply it to. Both rows, never one.
- [ ] T054 [US2] Row **V3**: assert `terraform_apply` still registers `destructive`, non-repeatable, with its observer, and still applies human-authored configuration unchanged (FR-020a). A feature that made the platform safer by quietly narrowing an existing capability would have changed the product without saying so.

**Checkpoint**: the full path works end to end and refuses everywhere it must.

---

## Phase 7: US5 — The model is qualified for the role it is acting in (P1)

**Goal**: the matrix's third role, bound for the first time, against a corpus that can fail.

**Independent test**: attempt authoring with no qualified `write` cell and confirm it refuses;
qualify one and confirm it proceeds.

- [ ] T055 [US5] Row **Q1**: authoring with no qualified `write` cell refuses `unqualified_cell` / `no_qualified_fallback`, **distinguishably from a provider outage**. (The gate itself is T012 — landed foundational.)
- [ ] T056 [US5] Build the corpus loader in `src/core/evals/authoring_corpus.py`: golden tasks (prompt, tooling invocation, **human-authored reference**, reference **author**) and must-deny cases (a subject seeded with a secret, with unrelated content, with instructions to the agent).
- [ ] T057 [US5] Author the corpus in `evals/authoring/`, including at least one golden task that is **syntactically valid and substantively wrong** — a module wiring a static credential where dynamic secrets were asked for — and must-deny cases covering all three classes FR-017 names.
- [ ] T058 [US5] Implement the floor in the loader on `intake_seed`'s mechanism, **raising rather than warning** (FR-018b): the valid-but-wrong case, the three must-deny classes, and a human-authored reference on **every** golden task.
- [ ] T059 [US5] Row **Q3**: present a corpus below the floor and assert a **raise**, not a warning. Assert the valid-but-wrong clause specifically — a corpus that only catches malformed output has not measured integration correctness (SC-008).
- [ ] T060 [US5] Row **Q4**: a golden task without a reference is **refused** rather than scored on one gate, and each reference records its author. **The clause most likely to erode**, and it erodes by generating the references — which measures the generator against itself and passes everything.
- [ ] T061 [US5] Implement the two gates in `src/core/evals/authoring_scoring.py`, **reported as two numbers**: product tooling (does it parse, do the types line up) and reference comparison (is it subtly wrong). Collapsing them hides which occurred, and which occurred is the whole distinction.
- [ ] T062 [US5] Add the `eval-authoring` make target running the gate lane with the `terraform` binary and a pinned provider mirror, and row **Q2**: a case that **validates cleanly and diverges from the reference** passes gate one and fails gate two.
- [ ] T063 [US5] Row **Q2-unrunnable**: run the gate with `terraform` off the path and assert the lane goes **red**. No degradation to `fmt`-only while still reporting "validated" — `UnrunnableSuite`'s discipline, and 012's twice-learned lesson that a lane which skips reads as green.
- [ ] T064 [US5] Row **Q5**: a `write` cell failing any must-deny case cannot be promoted, and the cases are scored over **the artefact**, not over a stated refusal. A cell that says "I will not do that" and then does it passes a verb-scored suite and must fail this one.
- [ ] T065 [US5] Add `AUTHORING_QUALIFICATION` to `src/core/evals/suites.py` beside `INTAKE_QUALIFICATION`, **not** in `SUITES`, with the reasoning recorded: `SUITES` is the per-pack list, and membership would demand a corpus from the Vault pack for a capability it does not offer — 037's exact mistake, caught by the same rule.
- [ ] T066 [US5] Refuse at pack load a pack that **declares an authoring workflow and ships no corpus**, and assert a pack declaring none is **not asked for one**. Row **Q6**: `OWED == {}` and `AUTHORING_QUALIFICATION not in SUITES`.

**Checkpoint**: the capability is gated by a qualification that can fail, and `OWED` is empty.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T067 Run quickstart **Scenario G** against the enclave: dispatch a real authoring run at a scratch repository, confirm the proposal appears, the trail carries `ARTIFACT_AUTHORED` and `PROPOSAL_OPENED`, and **no merge event exists**. Then merge by hand and confirm the merge is *observed* and the subsequent apply is the ordinary governed act. **The assembly is the one path no hermetic row covers**, and every previous feature that skipped it found something here.
- [ ] T068 [P] Move `docs/adr/0062-*.md` to **Accepted** with the security-maintainer review, and record the Principle V review for the four audit members in the same change.
- [ ] T069 [P] Add a realization note to `docs/adr/0038-integration-and-uplift.md` pointing at this feature, and reconcile `docs/adr/README.md` — its index rows have gone stale before, and only a mechanical header/index check caught it.
- [ ] T070 [P] Update `ROADMAP.md`: the integration-and-uplift row moves from named-and-unimplemented, and the `write` role is no longer unbound.
- [ ] T071 Run `make check` **and** the hermetic conformance lane; the local gate skips the hermetic rows, so a green `make check` alone does not mean this feature's rows ran.

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: audit, refusal, tier, two trees)
          └─> Phase 3 (US1 — producing)
                 └─> Phase 4 (US3 — containment)          ← must precede publishing
                        ├─> Phase 5 (US4 — not redirected)
                        └─> Phase 6 (US2 — proposing, provenance)
                               └─> Phase 7 (US5 — qualification)
                                      └─> Phase 8 (Polish)
```

**Phase 5 and Phase 6 are independent of each other** and may run in parallel once Phase 4
lands. Everything else is sequential, because each layer bounds the one after it.

## Parallel opportunities

- **Phase 1**: T002, T003 together (different trees).
- **Phase 2**: T005, T006 alongside T007–T009 (audit, ADR, tier are disjoint files).
- **Phase 3**: T015–T017 together once T013/T014 land (three row files, one builder).
- **Phase 4**: T023/T024 (file half) alongside T026/T027 (prose half) — the two halves are
  deliberately separate functions.
- **Phases 5 and 6** entire, in parallel.
- **Phase 7**: T056 (loader) and T057 (corpus content) are different work by different hands —
  the corpus is the "real work" ADR-0038 predicted, and it is the long pole.
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
- **The three obligations that must not be dropped**: the Principle V review (T068), ADR-0062
  moving to Accepted (T068), and the corpus landing with the capability so `OWED` stays empty
  (T066).
