# Tasks: Authoring becomes reachable

**Input**: Design documents from `specs/041-authoring-becomes-reachable/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-authoring-reachable.md, quickstart.md

**Tests**: Included — this feature's deliverable *is* largely its conformance rows (A1–A21,
E1–E4). Row tasks live in the story phase that delivers the behaviour they guard, per the
template's gate rule. **New assertions land in new files**: FR-017 requires 038's row files
unedited, so no task touches `test_producing.py`, `test_containment.py`, `test_proposing.py`,
`test_provenance.py`, `test_qualification.py`, `test_redirection.py`, or `test_tier.py`.

**Organization**: By user story, in spec priority order. US1–US3 are all P1 and stack (each
consumes the previous story's wiring); US4/US5 are P2 and independent of each other.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T005, T010, T017, T018 — refusal layers (T002a supplies A2's mechanism), product-mapping guard, task scope, acquisition refusals |
| **Conformance** | T009, T011, T016, T020, T024b, T026, T028, T029, T034 — the A-rows; T030/T031 the E-rows |
| **Correlation / evidence** | T030 — E1 walks the trail end to end under one correlation ID |
| **Eval** | T019 — the `write` cells, qualified mechanically (ADR-0063), bound only where the corpus earns them |
| **No-secret-leak** | T006, T027 — the token never in logs, checkpoints, configs, or audit; T024a — subject-derived content scrubbed from kept requests at terminal state |

## The shape of the work, and why no phase closes the feature alone

The gap is five layers (spec, *The gap, measured*). US1 closes registration+vocabulary, US2
closes entrypoint+acquisition+jobspec for the analyzer, US3 closes credential+publish+jobspec
for the proposer. A2's three-layer refusal row and A4's rigged-off self-test are what keep each
layer's closure honest. **The feature ships at the US5 checkpoint or not at all** — a
registered analyzer with an unreachable publisher is 038's gap moved one layer, not closed.

## Path Conventions

Single project: `src/`, `tests/`, `infra/`, `docs/` at repository root.

---

## Phase 1: Setup

**Purpose**: The record this feature owes before code moves.

- [X] T001 [P] Author ADR-0066 — the transport determination (native `git`/`gh`, MCP
      considered and reversed on measurement, per research R2) in
      `docs/adr/0066-version-control-is-reached-through-adopted-clis.md`; add the index row in
      `docs/adr/README.md`. Records FR-023, including why core git alone cannot open a PR and
      why the MCP server was rejected for the hardened tier (Principle II determination,
      Principle VI cost avoided).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The credential exchange and the product substrate — both stories' wiring depends
on these, and the wait-forever suspension must be impossible before anything can suspend.

- [X] T002 Implement the App JWT → installation-token exchange in
      `src/core/authoring/credential.py` (`token_for()` loses its `NotImplementedError`; App
      key read from `harness-authority/data/authoring/vcs-app` under the caller's attested
      identity; token TTL-bounded, never persisted; `available()` untouched — research R5).
- [X] T002a Make the intersection refusal name its excluding term in
      `src/core/authority/intersection.py` (+ the error type beside it): a tool absent from
      the effective set is refused as unknown / outside-ceiling / outside-task-scope depending
      on **which term dropped it** — today `intersect_scopes` computes one set with no memory
      of which term excluded what, so A2's third layer has no mechanism without this.
      **Sealed-core touch (`core/authority`)**: additive, but named for Principle V review.
- [X] T003 [P] Add `PLATFORM_TOOL_PRODUCTS: dict[str, str]` (`open_proposal` → `github`) in
      `src/surfaces/toolset.py` and merge it into `dependency_products()` (FR-029).
- [X] T004 [P] Add the `github` probe to `PLATFORM_PROBES` in `src/surfaces/probes.py` — an
      authenticated reachability check keyed by product, per research R7 (FR-029).
- [X] T004a Wire platform products into the table the health checker consumes: `probes_for()`
      in `src/surfaces/probes.py` (and its callers) merges platform product→probe pairs for
      registered platform tools — today `bindings.probes` is consumed only by pack loading
      (`core/packs/registration.py:120`), so a platform product's probe is a dict entry
      nothing reads and the sweeper can never match a `github` recovery (FR-029, closes
      analysis C3).
- [X] T005 [GATE:fail-closed] Unit guard: any registered suspendable tool absent from both the
      pack-derived and platform product maps fails, in
      `tests/unit/test_platform_tool_products.py` (FR-030 — the general rule, not a trio rule).
- [X] T006 [GATE:no-secret-leak] Unit rows for the exchange: token absent from logs, exception
      text, and `repr` (the existing redaction asserted through the new path); the raw App key
      never leaves `token_for()`, in `tests/unit/test_authoring_credential_exchange.py`.

**Checkpoint**: `token_for()` real; a suspension always names a product.

---

## Phase 3: User Story 1 — A ceiling can grant authoring (P1) 🎯 MVP

**Goal**: A correct ceiling resolves instead of refusing `unknown_ceiling_entry`, and the three
refusal layers are distinguishable (SC-001, SC-008).

**Independent Test**: Author a ceiling naming `read_subject`/`author_file`, load it through the
entrypoint-built registry, confirm it resolves; confirm the three refusal reasons differ.

- [X] T007 [US1] Add the `HARNESS_AUTHORING_ROLE=analyzer` branch to
      `src/surfaces/dispatch/entrypoint.py`: build `Trees` from the mounted `/subject` and the
      allocation workspace, construct `AuthoredArtifact`, call `register_authoring_tools`
      after `build_registry()`, and feed the widened vocabulary to the fabric
      (`known_tools`/`known_actions`) — research R1. **The branch lands as an importable
      construction helper** (e.g. `authoring_registry_for(role, trees, artifact)`) called by
      the run function — the registry construction is inline today, and A1/A3/A4/A5 must drive
      the construction rigged on and off, which a private inline block cannot offer. The trio
      joins the derived vocabulary only in authoring runs; non-authoring runs are untouched
      (FR-001/002/003).
- [X] T008 [US1] Extend the harness fixtures so hermetic rows can drive the entrypoint's
      authoring construction without Nomad (role env + tmp trees), in
      `tests/harness/` (new module beside `scripted_chooser.py`; declared, never a silent
      fake-fabric row — 038's own guard catches undeclared ones).
- [X] T009 [P] [US1] [GATE:conformance] Rows A1 + A3 in
      `tests/conformance/authoring/test_reachability.py` (new file): the same ceiling record
      refuses before / resolves after, asserted as a change; ceiling-omits → no authoring
      through the entrypoint-built registry.
- [X] T010 [P] [US1] [GATE:fail-closed] Row A2 in
      `tests/conformance/authoring/test_reachability.py`: unknown tool / outside ceiling /
      outside task scope — three runs, three reason codes, each naming a different record
      (FR-019).
- [X] T011 [US1] [GATE:conformance] Row A4 in
      `tests/conformance/authoring/test_reachability.py`: with the authoring branch rigged
      off, A1 and A3 must FAIL — the suite can lose (FR-018).

**Checkpoint**: reachability real and its rows able to fail.

---

## Phase 4: User Story 2 — A dispatched run reads its subject and authors a file (P1)

**Goal**: The governed analyzer loop works against a platform-produced subject, driven by a
qualified `write` cell (SC-002's first half, SC-003).

**Independent Test**: Dispatch an analyzer run against a fixture repository; the file exists in
the workspace, the read is recorded, the lens saw the content, task scope beat the ceiling.

- [X] T012 [US2] Create `src/core/authoring/acquisition.py`: `AcquiredSubject`, shallow
      single-branch clone of `target_repository`, recorded `commit`, 512 MiB bound with the
      size in the refusal, reason codes `subject_unreachable` / `revision_missing` /
      `acquisition_refused` (FR-026/028, research R3/R4; data-model entity).
- [X] T013 [US2] Wire acquisition into the dispatcher in `src/surfaces/dispatch/nomad.py`
      (`NomadDispatcher`): acquire after `AuthoringRequest.validate()` and before dispatch,
      pass the checkout as `NOMAD_META_subject_path`, run `resolve_subject_mount` against the
      produced path, delete the checkout at terminal state (FR-027; clone credential minted in
      this context via T002). **The resume path re-acquires at the recorded `commit`, never at
      HEAD** — two attempts of one run analyse one tree; asserted by A10's resume half.
- [X] T014 [US2] Give the `analyzer` task its `args` in
      `infra/jobs/authoring-tier.nomad.hcl` — run the dispatch entrypoint with the env
      contract the jobspec already declares (FR-014).
- [X] T015 [US2] Resolve the `write` cell in the authoring branch of
      `src/surfaces/dispatch/entrypoint.py` via `resolve_write_cell` feeding `_chooser_for`'s
      ordering (validate before build; no default on a missing binding) so 040's structured
      recordings supply `path`/`content` (FR-012, research R11).
- [X] T016 [P] [US2] [GATE:conformance] Rows A6–A8 in
      `tests/conformance/authoring/test_governed_path.py` (new file): identical pipeline shape
      vs `vault_write` (A6); escape refused through the registered tool (A7); lens + record +
      budget-with-disclosure + ordered `consulted` through registered `read_subject` (A8).
- [X] T017 [P] [US2] [GATE:fail-closed] Row A9 in
      `tests/conformance/authoring/test_governed_path.py`: analyzer scope cannot publish,
      proposer scope cannot author — both refusals carry the task-scope reason.
- [X] T018 [P] [US2] [GATE:fail-closed] Rows A10–A12 in
      `tests/conformance/authoring/test_acquisition.py` (new file): subject is the target
      repository at `commit` by construction; three acquisition refusals with no workspace
      created; bound disclosed, content never.
- [ ] T019 [US2] [GATE:eval] Qualify and bind the `write` cells: run `make eval-authoring`
      against live Sonnet 5, record dated evidence, and bind a cell **only for packs the
      corpus can actually qualify** — `evals/authoring/corpus.toml` is Terraform-shaped, and
      a vault `write` cell without vault-shaped golden tasks would be an unearned cell,
      ADR-0047's exact refusal. Add the earned cells to `model_matrix_cells` in
      `infra/modules/trust-fabric/`, apply, and re-seed the model credential after the apply
      (it clobbers the KV generation — known estate behaviour). FR-012a/b; research R6.
- [X] T020 [US2] [GATE:conformance] Rows A18 + A19 in
      `tests/conformance/authoring/test_qualification_dispatch.py` (new file — 038's
      qualification file stays unedited): unqualified stops `unqualified_cell` through
      dispatch, never `provider_unavailable`; the bound cell names Sonnet 5 with ADR-0063
      evidence.

**Checkpoint**: a model authors real files in a dispatched allocation, governed end to end.

---

## Phase 5: User Story 3 — The proposer publishes what the analyzer contained (P1)

**Goal**: A real PR on a real repository, from the task that holds the credential and never
held the subject (SC-002 complete, SC-004, SC-009, SC-010, SC-012, SC-013).

**Independent Test**: Both tasks in sequence; PR exists with matching digests; analyzer
observably cannot publish; healthy handoff consumes no resume attempt.

- [X] T021 [US3] Create `src/core/authoring/publish.py`: `PublishResult`; push
      `branch_for(idempotency_key)` with `--force-with-lease` using
      `git -c credential.helper= -c credential.helper='!gh auth git-credential'` and a
      per-invocation env carrying `GH_TOKEN` only; `gh pr list --head` reuse check then
      `gh pr create`; description assembled as model rationale + provenance block
      (correlation ID, consulted paths, digests, truncation note when partial). FR-020/021,
      FR-023a, FR-025, FR-031; research R9/R10.
- [X] T022 [US3] Route the description through containment before publish in
      `src/core/authoring/publish.py`: the rationale joins `scannable_text()`'s units and a
      `Finding` refuses via the existing `ContainmentRefused` path; the platform-authored
      provenance block is appended after the scan of the model half (FR-032, research R12).
- [X] T023 [US3] Add the `HARNESS_AUTHORING_ROLE=proposer` branch to
      `src/surfaces/dispatch/entrypoint.py`: `RUN_CONTINUE` path (already checked before the
      resume branch), `register_proposal_tool` with the publish handler and the observer,
      task-scoped to `open_proposal` (FR-008/009/010).
- [X] T024 [US3] Implement the publish observer in `src/core/authoring/publish.py`: resolve
      `CANNOT_DETERMINE` by querying the head branch — existing open PR → observed, absent →
      not performed; never a second proposal (FR-010, research R10; plugs into
      `core/observation` types).
- [X] T024a [US3] [GATE:no-secret-leak] Scrub an authoring run's kept model requests at
      terminal state (FR-033): the terminal path in `src/surfaces/dispatch/entrypoint.py`
      calls a scoped scrub on the durability provider (`src/core/durability/` — both
      providers), removing `author_file`-class argument payloads for the finished run. Safe by
      040's own design: resume reads arguments only for pending steps, and the request was
      left removable rather than load-bearing. Non-authoring runs untouched.
- [X] T024b [US3] [GATE:conformance] Row A22 in
      `tests/conformance/authoring/test_publishing.py` (hermetic) plus a durability leg in
      `tests/conformance/durability/test_authoring_requests_scrubbed.py` (new file): after
      terminal state no subject-derived bytes remain in either provider's request records —
      the in-memory provider passes for free, so the Postgres leg is the one that counts
      (040's M7 shape).
- [X] T025 [US3] Give the `proposer` task its `args` in
      `infra/jobs/authoring-tier.nomad.hcl`, and settle research R8 in `infra/`: verify the
      task image carries pinned `git` and `gh`, add a derived pinned image if the base lacks
      them; the task start fails `tooling_missing` rather than installing at runtime (FR-014).
- [X] T026 [P] [US3] [GATE:conformance] Rows A13 + A14 in
      `tests/conformance/authoring/test_publishing.py` (new file, declared fake-forge seam):
      one key → one PR with `reused=true` on the second; observer converges on
      exists/absent with no second proposal on any path.
- [X] T027 [P] [US3] [GATE:no-secret-leak] Row A15 in
      `tests/conformance/authoring/test_publishing.py`: after a publish — no token under
      `$HOME`, no `hosts.yml`, none in `.git/config` or remote URLs, none in the checkpoint,
      none in any audit payload; subprocess env constructed per call.
- [X] T028 [P] [US3] [GATE:conformance] Row A16 in
      `tests/conformance/authoring/test_publishing.py`: planted secret and analysed-content
      span in the rationale each refuse publish; truncated-without-note still refuses compose
      through the production path.
- [X] T029 [US3] [GATE:conformance] Row A17 in
      `tests/conformance/authoring/test_publishing.py`: an `open_proposal` suspension carries
      product `github`, the sweeper's map resolves it, **and the probe is present in the
      table the health checker actually consumes** — not merely in `PLATFORM_PROBES`
      (depends T003/T004/T004a).
- [X] T030 [US3] [GATE:correlation] Row E1 (enclave-marked, fails-never-skips) in
      `tests/conformance/authoring/test_enclave_publish.py` (new file): clone → read → author
      → contain → checkpoint → continue → publish; real PR, digests match, description carries
      rationale + provenance, trail walkable under one correlation ID (FR-016/024, SC-002/009).
- [X] T031 [US3] Rows E2–E4 in `tests/conformance/authoring/test_enclave_publish.py`:
      re-dispatch keeps the head-branch PR count at one; the analyzer's credential read fails
      for want of attested identity, observed in-allocation; the healthy handoff consumes no
      resume attempt and `RUN_RESUME` is unset on both tasks.
- [X] T032 [US3] Run the enclave lane end to end (named runner: Dan, driving the agent
      harness — recorded in the contract): `make dev-up`, seed the App key, dispatch, verify
      E1–E4 green, record the run in the implementation record. Requires the operator
      prerequisite (App installed on the target repository).

**Checkpoint**: the founding loop of 038, executed — analysed content and the credential never
in the same task, and a person can merge what the agent proposed.

---

## Phase 6: User Story 4 — The gap cannot reopen (P2)

**Goal**: The ledger stops claiming deliberate unreachability and re-arms as the tripwire
(SC-006).

**Independent Test**: Sweep passes with no trio entries; un-register one tool, sweep fails.

- [X] T033 [US4] Move `read_subject`, `author_file`, `open_proposal` from
      `DELIBERATELY_UNREACHABLE` to a new declared record `REACHABLE_PER_RUN: dict[str,
      Registrar]` in `tests/unit/capability_inventory.py`, each entry naming its registrar
      ("dispatch entrypoint, `HARNESS_AUTHORING_ROLE=analyzer`" / proposer) — the static
      sweep cannot observe per-run registration, so a declaration carries it and
      `unaccounted()` treats declared names as accounted (FR-015; closes analysis C2).
- [X] T034 [US4] [GATE:conformance] Row A5 in `tests/unit/test_capability_inventory.py`
      (additive — the file is 040's, not 038's): the declaration is kept honest by driving
      the entrypoint's registering construction (T008's harness) and asserting every
      `REACHABLE_PER_RUN` name actually registers; with the branch rigged off the check
      FAILS; a name in neither record still fails `unaccounted()`.

---

## Phase 7: User Story 5 — Nothing that already worked has to be rewritten (P2)

**Goal**: 038's rows pass unedited; non-authoring runs are byte-identical in behaviour
(SC-005).

**Independent Test**: Empty diff over 038's row files; full suite green.

- [X] T035 [US5] Row A20 verification: `git diff $(git merge-base main HEAD) --
      tests/conformance/authoring/` shows only NEW files (T009/T016/T018/T020/T026/T030's);
      038's seven row files unedited; run the full authoring suite green. **Merge-base, not
      `main`** — main moves during implementation, and this estate has already recorded what
      a wrong baseline reports: false parity. Record the command and result in the
      implementation record (FR-017).
- [X] T036 [US5] Row A21 verification: the four recording-driven suites and 008–012's
      fixture-tool lanes pass with zero edits — non-authoring vocabulary, resolution, and
      records unchanged (`make check && make conformance-hermetic`).

---

## Phase 8: Polish & Cross-Cutting

- [X] T037 [P] Run `specs/041-authoring-becomes-reachable/quickstart.md` top to bottom as
      written; fix drift in the doc, not by hand-waving the steps.
- [X] T038 Update `ROADMAP.md` in the implementation PR: 041's Shipped row; the
      change-proposal workflow table's "author the changes" and "PR back" rows close; the
      trio's ledger note updates (the file's own landing rule).

---

## Dependencies & Execution Order

- **Setup (T001)**: independent; can land first or in parallel with Phase 2.
- **Foundational (T002–T006)**: T002 blocks T013 (clone credential) and T021 (publish);
  T002a blocks T010 (A2's third layer needs the mechanism); T003/T004/T004a block T029;
  the rest block nothing in US1.
- **US1 (T007–T011)**: needs nothing from Phase 2 — can start immediately after Setup.
  T007 → T008 → T009/T010 [P] → T011.
- **US2 (T012–T020)**: T007 first (the branch exists); T012 → T013; T014/T015 beside them;
  rows T016–T018 [P] after; T019 → T020.
- **US3 (T021–T032)**: T002 and T023 gate the rest; T021/T022 → T024; T024a after T023 (the
  terminal path exists) → T024b; T025 beside; rows T026–T028 [P]; T029 after T003/T004/T004a;
  E-rows T030/T031 after everything; T032 last.
- **US4 (T033–T034)**: after US1–US3 registration is real (the sweep must see it).
- **US5 (T035–T036)**: last before Polish — it asserts over the finished diff.

### Parallel opportunities

- T001 ∥ T002–T006; within Phase 2: T003, T004, T006 ∥ (T005 after T003).
- US1's T009/T010 together; US2's T016/T017/T18 together; US3's T026/T027/T028 together.
- US2 and the non-enclave half of US3 can proceed in parallel once T007/T002 land — different
  modules, different row files.

## Implementation Strategy

**MVP is Phases 1–3** (a ceiling resolves and the refusal layers are honest) — but **not
shippable alone**: registration without an executable jobspec is 038's defect at a new layer.
Ship at the US5 checkpoint or not at all. The enclave rows (T030–T032) are the feature's
evidence class — attestation-relevant — and T032's run is the constitution's named-runner
obligation being discharged, not a demo.

## Notes

- **42 tasks; 26 contract rows (A1–A22, E1–E4)**, and every asserting task names its rows.
  Four tasks (T002a, T004a, T024a, T024b) exist because the first analyze pass found four
  artifacts asserting what the code cannot do — the suffixed IDs mark them, and T033/T034
  were rewritten in the same pass for the same reason.
- No task edits 038's seven row files or the four recording-driven suites; T035/T036 assert it.
- The fake-forge seam (T026) is declared, per the repo's undeclared-fake-row guard.
- T019 re-seeds the model credential after `terraform apply` — the apply clobbers it
  (estate memory; the 503 `AuthenticationError` is the tell).
- Docker VM clock drift breaks dispatched-row attestation — resync the VM clock before the
  enclave gate if rows fail with empty trails (estate memory).

---

## Implementation record — what ran

**Phases 1–2, US1, US4, and the buildable half of US2/US3 are complete and green.**
`make check` equivalent: **1280 passed**, lint and mypy clean over 577 files. Authoring
conformance: **129 rows**, of which 049 are 038's, unedited.

**FR-017 verified from the merge-base, not from `main`.** `git diff $(git merge-base main HEAD)
HEAD -- tests/conformance/authoring/` lists only NEW files; all seven of 038's row files report
UNEDITED. The merge-base matters: `main` moves during implementation, and this estate has
already recorded what a wrong baseline reports — false parity.

**Four findings the rows produced rather than the plan.**

1. **A2's mechanism was in the wrong place.** The plan put the excluding-term discriminator on
   the authority hook. Measured, that hook fires only when live policy narrows authority *after*
   issuance — every ceiling and task-scope refusal is caught earlier by the pipeline's scope
   gate, so both arrived as one `out_of_scope` record and the new codes were unreachable for
   them. The reason CODE stays `out_of_scope` (nine assertions depend on a stable vocabulary)
   and the discriminator rides in the payload, which is what SC-008 asked for all along.

2. **A run may not request more than its ceiling**, so "outside ceiling" and "outside task
   scope" cannot both be per-call denials for the same tool — `manufacture_authority` refuses
   the run outright. A9 was rewritten to use a tool the task can actually resolve, because
   `open_proposal` in an analyzer refuses one layer earlier as `unregistered`, which proves
   something else.

3. **The jobspec guard found two more instances of 038's defect**, both 037's: `analysis-tier`
   and `detonation-range` declare four tasks between them with a command-taking entrypoint and
   no command. Recorded in `KNOWN_UNEXECUTABLE` with the record that owns them rather than
   fixed — inventing a command for another feature's tier would be guessing — and a row makes
   that list shrink rather than rot.

4. **FR-030's guard found `plan` and `apply`** carrying the same wait-forever suspension shape
   as `open_proposal`: they declare `product="workspace"` and no manifest ever named it. Mapped,
   and `workspace` is probed by `fixture_probe`.

**Two guards were extended rather than worked around.** `WRITE_CALLS` gained `rmtree`, which it
should always have had. And the fake-fabric scanner crashed on any `global` statement in the
tests tree (`ast.Global.names` holds strings, not aliases) — a guard failing by falling over.

## T019, and why it is the one task not done

**41 of 42.** T019 asks for a **live** `write` cell, qualified through ADR-0063's mechanical
scorer and bound in the estate. Everything around it ran: `make eval-authoring` passes (13
rows), terraform is present, and the fixture-qualified terraform `write` cell 038 declared is
in the dev estate.

**What is missing is a property detector, and it does not exist.** `score_corpus` takes a
`properties_of(task, artifact, contents) -> frozenset[str]` callable, and every implementation
in this repository is a literal map inside a row (`properties_of=lambda t, _a, _c:
properties[t.name]`). Qualifying a live model means having it author the five golden tasks and
then **mechanically detecting** whether each artefact `reads_credentials_from_secret_store`,
carries `no_literal_credential_in_source`, and gives the credential a lease.

Writing that detector hastily is the one thing this feature must not do. It is the load-bearing
half of the qualification: a lenient detector qualifies a model on a check that cannot fail,
which is the shape ADR-0047 refuses and the reason `valid_but_wrong` exists in the corpus at
all — `static_credential_lookalike` passes gate one and must fail gate two. Binding a live cell
on a detector written in the last hour of a feature would be an unearned cell, which is exactly
what this task's own text warns against.

So the cell stays fixture-qualified, the gate stays honest, and the detector is named as its
own piece of work.

## The live eval lane is red on main, independent of this feature

Measured twice on this branch and twice in a worktree at the merge-base `dbf5ce1`: identical
failure sets. `vault-must-decline-001` answers where it must decline (subject prompt *and*
answering path), the judge disagrees with a human REJECT on `seed-deny-002`, and the citation
and estate cases fail. `LIVE_MODEL` is `anthropic/claude-sonnet@5`, correct per 032, so the
configuration is right and the failures are content. Harness-protocol work, in the answering
subsystem, and not 041's.

## Implementation record — what ran

**`make check`: 1280 passed.** **`make conformance-hermetic`: 528 passed** (the merge-blocking
lane). Lint and mypy clean over 582 files. Authoring conformance: **141 rows**, of which 038's
80 are unedited.

**E1–E4 ran against a live forge — twice.** First by hand, proving the path; then as rows,
which is the difference between "it happened once" and "it keeps happening". The row run opened
`mcteer/brieve#177`, verified state, head branch, file set, provenance section and the absence
of any credential on disk, then republished to prove idempotency (one proposal, `reused=true`)
and observed it. 6 passed in 13.23s. The proposal and its branch were closed and deleted.

**FR-017 verified from the merge-base**, not from `main`: only NEW files appear under
`tests/conformance/authoring/`, and all seven of 038's row files report UNEDITED.

**Findings the rows produced rather than the plan** are recorded in the ROADMAP's 041 row: the
refusal discriminator's real location, the ceiling/task-scope collapse, two more unexecutable
tiers in 037, `plan` and `apply` carrying the wait-forever shape, and three guards extended
rather than worked around — including `core/authoring/credential.py` naming the substrate,
caught by the repository's own product-blindness gate.
