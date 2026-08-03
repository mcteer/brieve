# Tasks: The corpus refresh — answers that can say how old their ground is

**Input**: Design documents from `/specs/033-corpus-refresh/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the contract's rows are the feature's proof, and the boundary-day rows
exist precisely because off-by-one wording is invisible without them.

**Organization**: by user story in dependency order — US2 (the pin records when) is the
foundation, US1 (the answer discloses) is the feature, US3 (the schedule proposes) is CI-side
and lands last. No vendor credential anywhere; the only network access in the whole feature
lives in the scheduled workflow, which is not a gate.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

*(none — additive fields on existing seams; no scaffolding to create)*

## Phase 2: Foundational

*(none — US2 is itself the foundation and carries its own tasks)*

## Phase 3: User Story 2 — the pin records when it was made (P1)

- [X] T001 [US2] `infra/bin/corpus_sync.py`: write `synced_at` (ISO-8601 UTC, timezone-aware
      `datetime.now(UTC)`) into the manifest at composition, beside `corpus_digest`. Mechanics
      otherwise untouched (F1 — the manifest is the pin's identity document; no sidecar).
- [X] T002 [US2] `src/core/answering/corpus.py`: `Corpus.synced_at: datetime | None = None`;
      the loader parses the manifest field with the four-state mapping from data-model.md —
      well-formed-past → parsed, absent/unparseable/future → `None`. **No exception path**:
      a bad timestamp must never take answering down over metadata (F2), and the 024 pin
      (no field at all) must load exactly as before.
- [X] T003 [P] [US2] Loader rows in `tests/component/test_corpus_synced_at.py`: the four
      manifest states map correctly; the committed 33-document manifest still loads with
      `synced_at is None`; a sync-shaped manifest with the field round-trips. Sync row: run
      `corpus_sync`'s manifest composition against fixture content twice — digest identical,
      `synced_at` moved (US2 scenario 2: "we checked" is distinguishable from "we changed").
      And the failure half (FR-007's component row, analyze G3): against a refused fixture
      the sync dies before writing — manifest and documents byte-identical afterwards.

**Checkpoint**: the pin can say when; nothing consumes it yet; every existing row green.

## Phase 4: User Story 1 — an answer discloses the age of its ground (P1)

- [X] T004 [US1] `src/core/answering/ground.py` (new): `GROUND_FRESH_DAYS = 30`,
      `GROUND_STALE_DAYS = 90` — the only place the tiers exist (F4) — and
      `describe_ground(synced_at: datetime | None, now: datetime) -> str`, a pure function
      returning the four wordings (plain / aging / stale-with-suggestion / unknown). Every
      wording carries the pinned date and age in days; the note never returns empty — a
      disclosure that appears only when things are bad trains readers that silence means
      fresh, which is the unfounded claim this feature removes.
- [X] T005 [US1] `src/core/answering/answer.py`: `Answer.ground_note: str = ""` — additive on
      the frozen dataclass, every existing constructor call stands. `answer_question` itself
      is untouched: the core has no clock, the surface owns "now" (F3, the window_note
      precedent exactly).
- [X] T006 [US1] `src/surfaces/api/ask.py`: `ask_for` GAINS `now: datetime | None = None`
      (analyze A2 — `estate_answer_for` already has it; guidance does not, and an inline
      `datetime.now()` would make the tier rows untestable, the exact midnight-CI trap the
      volume rows hit). Compose `describe_ground(corpus.synced_at, now)` where the estate
      branch composes `describe_window`, attach to the guidance `Answer`, serialize as
      `ground_note` beside `claims`. The estate branch is untouched.
- [X] T007 [P] [US1] `src/surfaces/portal/templates/ask.html`: render `ground_note` in the
      same meta block that renders `window_note`, conditionally, same styling class family.
- [X] T008 [P] [US1] Tier rows in `tests/component/test_ground_note.py`: fixture times at
      29/30/89/90/91 days word by the right tier (the contract's boundary rows); unknown and
      future-time word as unknown; the note names the pinned date and age; `describe_ground`
      never returns empty; and — FR-005's teeth — a stale pin's answer still has disposition
      `answered` through `answer_question` + the surface composition.
- [X] T009 [US1] [GATE:conformance] The full-path row in
      `tests/conformance/answering/test_the_ground_discloses.py`: a guidance question through
      `surface_under_test` carries a non-empty `ground_note` in the payload (SC-001, both
      packs); the committed 024-shaped manifest answers with the unknown wording (FR-009 —
      the row that lets this merge before the first re-sync); the estate path's
      `window_note` is unchanged by the addition.
- [X] T010 [US1] The no-fetch posture holds: run the existing no-network rows plus the
      hermetic sweep with `ground.py` imported everywhere it will be; assert no blocking
      lane gained network access (F8, SC-004). Asserted by running, not by reading.

**Checkpoint**: every guidance answer states its ground's age or that it is unknown, on the
API payload and the portal render; MCP inherits by proxy and Phase 5 asserts it.

## Phase 5: User Story 3 — the refresh has a schedule, and landing it stays reviewed (P2)

- [X] T011 [US3] Deliberately empty, kept as the record (analyze C1 → D1): the draft added
      a provenance table here; the record already exists as the loader's `UpstreamPin`, and
      the confirming row is T013's first. Nothing to build; the task ID stays so the
      numbering matches the analysis trail. PROVENANCE.md untouched throughout: it is the
      human review record (F6).
- [X] T012 [US3] `infra/bin/skills-provenance` (new): for each ADOPTED pack (the manifest's
      own `provenance` field), read `[upstream]`, compare `commit` against upstream HEAD
      (`git ls-remote`, no clone); on drift, REPORT it (recorded vs upstream, in the
      proposal's text) — **never vendor content** (F6: adoption stays a human act through
      the promotion/injection lens); on no drift, update only `retrieved` — as a TARGETED
      single-line edit, never a re-serialization (analyze I3: `tomllib` cannot write, a TOML
      writer is a new dependency, and regenerating the file erases pack.toml's comments,
      which are part of its record). An AUTHORED pack is refused by name with the reason
      (F7: `vault-secret-access` is written here and upstream-bound; a "refresh" from a
      name-colliding upstream would overwrite our own authorship).
- [X] T013 [P] [US3] Helper rows in `tests/component/test_skills_provenance.py` (fixture git
      data, no network): adopted pack checked through its existing `[upstream]` pin; drift
      reported not vendored (skills bytes and `commit` byte-identical after a drift run,
      only `retrieved` may move on a clean check); after a `retrieved` update the pack.toml
      is byte-identical EXCEPT that one line (the I3 row — comments survived); the loader's
      `UpstreamPin` is the record consumed (the C1 row); authored pack refused naming the
      reason; the vault pack specifically refused.
- [X] T014 [US3] `.github/workflows/corpus-refresh.yml` (new): weekly cron + workflow_dispatch;
      runs `infra/bin/corpus-sync` then `infra/bin/skills-provenance`; if the tree changed
      (a timestamp-only move counts — the no-op proposal is wanted, per clarify), force-push
      ONE STANDING BRANCH `chore/corpus-refresh` carrying one open PR (`corpus-refresh`
      label) until reviewed — a merged or closed PR gets a fresh one next run; never a
      stack of dated branches (analyze P2). Explicit `permissions: contents: write,
      pull-requests: write` block — the default token is read-only (analyze P1). On sync
      failure the run goes red with the tree clean and no PR (FR-007 — the sync already
      dies before writing). **No PAT** (analyze I2): the default token's PR is checkless by
      GitHub's recursion guard, the PR body says so and says why (a standing credential is
      refused by Principle IV), and the body names the reviewer's one keystroke that
      triggers CI (close/reopen or empty commit).
- [X] T015 [US3] The workflow-shape row (after T014 — it asserts that YAML; analyze O4) in
      `tests/component/test_refresh_workflow_shape.py`: the YAML's RUN STEPS invoke exactly
      the two reviewed scripts plus git/gh plumbing and nothing else (analyze P3 — "no
      network-touching step" is not assertable when checkout itself fetches; the row proves
      what the stripper can see), and the permissions block grants exactly
      contents+pull-requests write — via the shared prose-stripper
      (`tests/harness/source_reading.py`), because five prior features found gates matching
      comments instead of code (F8).
- [ ] T016 [US3] The dispatch, end to end: agent runs `gh workflow run corpus-refresh.yml`,
      watches the run, and reads back the proposal PR (exists, labelled, unmerged, diff is
      manifest-timestamp plus any provenance `retrieved` move; skills drift reported in the
      body if upstream moved; the body carries the checkless-PR explanation and the CI
      trigger instruction — analyze I2). **Known precondition, named rather than
      discovered** (analyze P1): the repo setting "Allow GitHub Actions to create and
      approve pull requests" defaults OFF and `gh pr create` fails 403 until it is on —
      flipping it is a maintainer act, recorded in the outcome when it happens. Record the
      outcome in `contracts/conformance.md`.
      **Named runner: Dan McTeer** — the review of that PR is the act only he performs;
      merging or closing it is his call and either resolution completes the row.

**Checkpoint**: the second sync in the platform's history exists as a reviewed proposal.

## Phase 6: Polish

- [ ] T017 [P] ROADMAP entry for 033; contract status rows flipped to green with dates; the
      024 deferral marked closed where it is recorded.
- [ ] T018 `make check`, the hermetic sweep, `make evals`, and `make conformance` green;
      the served-MCP ask row observed carrying `ground_note` through the proxy (the
      surfaces half of SC-001) during the conformance run. Noted where it is observed
      (analyze L5): `load_corpus` runs at service start, so a merged refresh reaches served
      answers on the next restart — SC-002's "next time the serving process reads the pin"
      is a deploy fact, not a hot reload.

---

## Dependencies

```text
Phase 3 (T001 → T002 → T003)                  [hermetic]
  → Phase 4 (T004 → T005 → T006 → T007∥T008 → T009 → T010)   [hermetic]
    → Phase 5 (T011(record) → T012 → T013∥T014 → T015 → T016) [T016 touches GitHub]
      → Phase 6 (T017 ∥ T018)
```

## Notes

- **No sealed core.** The note rides the answer object; if implementation finds an audit
  payload wanting to grow, that is a finding to surface, not a field to add.
- **The one review**: T016's proposal PR is reviewed by Dan; no other human step exists.
- **What would make this fail honestly**: the first dispatched refresh finding upstream
  restructured (dead indexes). That is FR-007's path — red run, clean tree — and the finding
  becomes the next feature's measured opening, not a silent patch inside this one.
