# Tasks: A finished authoring run leaves no proposal behind

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/payload-retention.md](contracts/payload-retention.md),
[contracts/conformance-payload-retention.md](contracts/conformance-payload-retention.md),
[quickstart.md](quickstart.md)

**Tests**: Included and mandatory — spec Independent Tests, contract rows A1–A16 / E1–E3, and
the constitution's gate types. Every hermetic row must be able to lose. The acceptance signal is
an existing row: `test_row_checkpoints_still_hold_no_credential_material`, red today because of
[#219](https://github.com/mcteer/brieve/issues/219).

**Organization**: By user story. **All three stories are P1 and US1 must not merge without US3**
— see the Ordering note. Named contracts bind exactly: `scrub_proposal_payload`,
`CONTENT_BEARING_TOOLS`, `PROPOSAL_PAYLOAD_KEY`, `proposal_from_payload`,
`_publish_the_proposal`, `scrub_authoring_requests`, `DurabilityProvider.save`. Do not
substitute a near-equivalent name, and **do not add a provider method** — research R4 rejected
that deliberately.

## Ordering note — US1 and US3 land together

US1 makes the scrub happen; US3 asserts it does **not** happen in the two places that would
break the platform. They are the same call site seen from two directions, and US1 alone is a
durability defect waiting for an interrupted publish. Phase 4 is not optional follow-up work.

US2 may land after, but not much after: a scrub satisfying US1 alone deletes the content **and**
the ability to say what happened, which is the trade ADR-0018 and Principle IX refuse.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T014, T015 — a save failure stops the run with the reason recorded, asserted **against the stored row** rather than the return value, because a scrub that reported a count while leaving the row intact is the failure nothing can detect afterwards |
| **Conformance** | T008–T013 (A1–A3, A6–A8), T016–T018 (A5, A9, A11), T019–T022 (A4, A5, A10), T024–T027 (A12–A14), T030–T032 (A15, A16); T034 named-runner E1–E3 |
| **Correlation / evidence** | T024–T027 — a scrubbed run still compiles a RunReport that names every authored path and keeps its pull request identifiable |
| **No-secret-leak** | The whole feature. T033 is the acceptance sweep: the live store holds no authored body after a completed run |
| **Eval** | None — no pack, prompt, model or policy content changes |

## Path Conventions

Single project: `src/`, `tests/`, `scripts/`, `specs/` at repository root.

---

## Phase 1: Setup

**Purpose**: One realistic fixture every later phase asserts against. No production code.

- [ ] T001 [P] Add a proposal-payload fixture to `tests/fixtures/authoring_payloads.py`: a
      payload shaped exactly as `proposal_payload` writes one — two files with bodies, a
      `rationale`, a `provenance` list carrying a path-and-digest line per file, plus `title`,
      `usage`, `task`, `target_repository`, `branch`, `disclosures`, `evidence`, `state`.
      Bodies use the harness marker from `tests/harness/secrets.py`, never credential-shaped
      literals — gitleaks caught exactly that on 051's first commit attempt
- [ ] T002 [P] Add a scrubbed-payload fixture to the same module: the expected result of
      scrubbing T001's, so the two can be diffed field by field rather than asserted key by key

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure function everything else calls. Sealed core —
`src/core/authoring/retention.py`.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [ ] T003 Add `scrub_proposal_payload(payload) -> tuple[dict[str, Any], int]` to
      `src/core/authoring/retention.py`, beside `CONTENT_BEARING_TOOLS` — the same knowledge,
      one record over. Clears `authoring_proposal.files[].body` and
      `authoring_proposal.rationale`; returns the rewritten payload and the count of bodies
      cleared
- [ ] T004 Make it **total**: a payload with no `authoring_proposal` returns unchanged with
      count 0. A run that authored nothing and one that published must not take different
      cleanup paths (FR-006)
- [ ] T005 Make it **idempotent**: re-scrubbing returns the payload unchanged with count 0.
      Terminal state can be reached more than once
- [ ] T006 Empty cleared keys to `""` rather than removing them. A reader distinguishing
      *absent* from *emptied* would treat a scrubbed run as malformed
- [ ] T007 Export it in `__all__` and record in the module docstring **why the durability
      provider gains no method**: `save` already upserts by `blob_id`, so 041's
      `scrub_closed_arguments` — a bulk `UPDATE` across a join — has no analogue here, and
      adding one would widen a sealed-core seam to do what it does (research R4)
- [ ] T008 [P] [GATE:conformance] Assert bodies and `rationale` are cleared and the count
      matches what changed, in `tests/unit/test_proposal_payload_scrub.py` (row A1)
- [ ] T009 [P] [GATE:conformance] Assert `files[].path`, `files[].is_diff`, `title`, `usage`,
      `task`, `target_repository`, `branch`, `disclosures`, `evidence` and `state` all survive
      untouched, in the same file (row A2)
- [ ] T010 [GATE:conformance] **Assert `provenance` survives by name**, and that its
      path-and-digest lines still match the surviving `files[].path` values (row A3). Asserted
      explicitly rather than inferred from the cleared list: this single field is why US1 and
      US2 do not trade against each other, and a change that took it would satisfy retention,
      destroy attestation, and look tidier doing it
- [ ] T011 [P] [GATE:conformance] Assert cleared keys are `""` and still present (row A6)
- [ ] T012 [P] [GATE:conformance] Assert a payload with no proposal returns unchanged, count 0
      (row A7)
- [ ] T013 [P] [GATE:conformance] Assert scrubbing twice returns unchanged, count 0 (row A8)

**Checkpoint**: the function is correct and provably so, with nothing yet calling it.

---

## Phase 3: User Story 1 — A completed Build leaves no copy of what it wrote (Priority: P1)

**Goal**: When a Build finishes, the control plane holds no copy of the file bodies it authored.
The customer's content lives in their repository and in the pull request they can close.

**Independent Test**: Complete a Build against a subject containing a distinctive marker. Query
the state store for that marker after terminal state. Assert absent — and assert present before
the scrub ran, so the row can lose.

### Implementation

- [ ] T014 [US1] Call `scrub_proposal_payload` in `src/surfaces/dispatch/entrypoint.py` at the
      existing scrub site, **inside the `authoring_role(...) == PROPOSER` branch and after
      `_publish_the_proposal` returns 0** — that function writes the terminal payload itself, so
      the scrub rewrites what it just wrote. Persist through `DurabilityProvider.save` with the
      same `blob_id` (FR-001, FR-010)
- [ ] T015 [US1] [GATE:fail-closed] Stop the run with the reason recorded when the save fails
      (FR-005). **Never report a clean run over content still in the store** — that is the
      failure nothing can detect afterwards

### Tests

- [ ] T016 [US1] [GATE:conformance] Assert the stored payload holds no authored body after a
      completed authoring run, reading the row back rather than trusting the return value
      (row A9). Assert it held them before the scrub, so the row can lose
- [ ] T017 [P] [US1] [GATE:fail-closed] Assert a save failure stops the run with a recorded
      reason and does not report success (row A9)
- [ ] T018 [P] [US1] [GATE:conformance] **Assert a refused run's payload contains no authored
      content in the first place** (row A11). A run refused at Judge returns before Propose and
      never composes a proposal, so FR-007 is satisfied vacuously — a row asserting "the scrub
      cleared it" would pass without exercising anything. This asserts the property that is
      actually true and can actually fail: if the refusal path ever starts carrying a proposal,
      this goes red, which is exactly when somebody needs to know

**Checkpoint**: content is cleared on the happy path. **Do not merge without Phase 4.**

---

## Phase 4: User Story 3 — An interrupted proposal still completes (Priority: P1)

**Goal**: A publish killed after Judge and before the pull request opens resumes and publishes
the same content, unchanged.

**Independent Test**: Kill a run between Judge and `open_proposal`. Resume. Assert the pull
request opens carrying the same files, and that the scrub did not run before the resume.

**⚠️ This phase is why US1 is not shippable alone.** The three rows below are the difference
between a retention fix and a durability defect.

- [ ] T019 [US3] [GATE:conformance] **Assert the analyzer branch does not scrub the payload**
      (row A4). The adjacent intents scrub is gated `authoring_role(...) is not None`, which is
      **true in the analyzer too** — safe for intents, whose SQL clears closed brackets only,
      and a defect here because the analyzer's checkpoint *is* the handoff the proposer reads.
      Copying that gate one line down makes every publish resume with nothing to publish
- [ ] T020 [US3] [GATE:conformance] Assert a **failed** publish leaves the payload intact, so
      the resumption has what it needs (row A5)
- [ ] T021 [P] [US3] [GATE:conformance] Assert `proposal_from_payload` **raises** on a scrubbed
      payload rather than reconstructing one with empty bodies (row A10). It is only called
      before publishing, so a scrubbed payload reaching it means the ordering broke — and an
      empty pull request is a worse outcome than a loud failure
- [ ] T022 [US3] Assert a run killed between Judge and publish resumes and opens a pull request
      carrying the same files, in `tests/conformance/durability/`

**Checkpoint**: the scrub happens where it must and nowhere it must not.

---

## Phase 5: User Story 2 — The run stays attestable after its content is gone (Priority: P1)

**Goal**: An auditor reading a scrubbed run six months later can establish what it proposed,
which files it touched, and that the proposal is the one the pull request carries.

**Independent Test**: Compile a RunReport from a scrubbed run. Assert it validates and names
what was proposed, and says the same things about paths and outcome as one compiled before the
scrub.

- [ ] T023 [US2] Verify no consumer breaks: `PROPOSAL_PAYLOAD_KEY` has exactly two readers —
      `proposal_from_payload` and the entrypoint that writes it — and no portal template,
      report compiler or API operation reads it (research R8). Assert that with a source scan,
      so a future reader is caught rather than discovered
- [ ] T024 [P] [US2] [GATE:correlation] Assert a RunReport compiled from a scrubbed run
      validates and names every authored path (row A12)
- [ ] T025 [P] [US2] [GATE:correlation] Assert the pull request stays identifiable from a
      scrubbed run's record (row A13)
- [ ] T026 [P] [US2] [GATE:evidence] Assert the compiled report does not claim to carry content
      the run no longer holds (row A14)
- [ ] T027 [US2] Assert a report compiled before and after the scrub agrees on paths and
      outcome — the property that says the scrub cost no attestation, rather than that the
      report merely still compiles

**Checkpoint**: what was deleted is not what a reviewer needed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The six rows already in the store, the acceptance signal, and the record.

- [ ] T028 Write `scripts/backfill-proposal-payloads.py`: one-time, idempotent, operator-invoked.
      Applies **the same `scrub_proposal_payload`** to terminal checkpoints — a second
      implementation could disagree with the first — and names each blob it changed, because a
      silent backfill is indistinguishable from one that did nothing
- [ ] T029 Scope the backfill to **terminal checkpoints only**. A non-terminal one may still be
      resumed, and scrubbing it is the same defect T019 guards against, arriving by a different
      route
- [ ] T030 [P] [GATE:conformance] Assert the backfill leaves non-terminal checkpoints intact
      (row A15)
- [ ] T031 [P] [GATE:conformance] Assert the backfill is idempotent and reports what it changed
      (row A16)
- [ ] T032 Run the backfill against the live store and record the before/after count. **Six
      checkpoints hold a proposal today, ~81 KB, every one `completed`** — a forward-only scrub
      leaves all of them, and the acceptance row sweeps the whole table rather than runs created
      after the change
- [ ] T033 [GATE:no-secret-leak] Confirm
      `tests/conformance/durability/test_dispatched_no_secret_sweep.py::test_row_checkpoints_still_hold_no_credential_material`
      **passes**, and remove the KNOWN RED note its docstring carries. That row is this
      feature's acceptance signal and closes issue #219
- [ ] T034 [GATE:conformance] Named-runner rows on the implementation PR — **Dan McTeer**:
      **E1** the stored-JSON round trip (bodies absent from the stored text, not merely from the
      object — 041's in-memory argument does not transfer, because this feature writes no SQL);
      **E2** the acceptance sweep over the live store after the backfill, recording the
      pre-backfill count; **E3** a killed publish resumes and opens a pull request carrying the
      same files
- [ ] T035 [P] Correct `proposal_payload`'s docstring in `src/surfaces/dispatch/authoring.py`.
      It already says *"the run's terminal scrub (FR-033) removes it"* — false until this
      feature lands, and the natural place somebody would have noticed. Make the sentence true
      rather than delete it (research R3)
- [ ] T036 [P] Add a `CHANGELOG.md` entry: a finished authoring run no longer leaves its
      proposal in the control plane; the path-and-digest manifest survives so a reviewer can
      still match a merged pull request against what was proposed
- [ ] T037 [P] Add `proposal payload scrub` to `docs/glossary.md`, stating what is cleared, what
      survives, and that the pull request is the durable artifact (ADR-0038) — which is what
      makes clearing the platform's copy defensible at all
- [ ] T038 Add the ROADMAP Shipped row for 052 **on the day it merges**. The file has been three
      features behind four times, warns about exactly that in its own text, and is what a
      planner reads first
- [ ] T039 Run every scenario in [quickstart.md](quickstart.md)
- [ ] T040 Run `make check`, then `make conformance`, then `make test-full`
- [ ] T041 Request **security-maintainer review** on the implementation PR.
      `src/core/authoring/retention.py` is sealed core, and this change deletes content a run
      record currently contains — constitution Principle V and `AGENTS.md` rule 4

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — no dependencies
- **Phase 2 (Foundational)** — depends on Phase 1; **blocks every story**
- **Phase 3 (US1)** — depends on Phase 2
- **Phase 4 (US3)** — depends on Phase 3, and **must merge with it**
- **Phase 5 (US2)** — depends on Phase 3; independent of Phase 4
- **Phase 6 (Polish)** — T028–T033 depend on Phase 2 (the function) and Phase 3 (the call site);
  T032 must precede T033, because the row cannot pass while the six rows remain

### Within phases

T003 → T004 → T005 → T006 → T007 (the function, then its properties, then its record).
T014 → T015 → T016. T028 → T029 → T032 → T033.

### Parallel Opportunities

- T001 ‖ T002 (Setup)
- T008 ‖ T009 ‖ T011 ‖ T012 ‖ T013 — **T010 is deliberately not marked [P]**: it is the row the
  whole attestation argument rests on and should be written with attention, not batched
- T017 ‖ T018 (US1 tests; T016 follows T014)
- T021 ‖ (T019, T020, T022 touch the same call-site behaviour)
- T024 ‖ T025 ‖ T026 (US2 rows)
- T030 ‖ T031; T035 ‖ T036 ‖ T037 (Polish)
- **Phase 5 can run in parallel with Phase 4** — different files, different subjects

### Parallel Example: Phase 2 tests

```bash
uv run pytest tests/unit/test_proposal_payload_scrub.py -n auto
```

---

## Implementation Strategy

### MVP

Phase 1 → Phase 2 → Phase 3 → **Phase 4**. That is the smallest thing that is not a defect: the
content is cleared, and it is provably not cleared where a resumption would need it.

**Stop and validate**: quickstart scenarios 1–5. Then Phase 5, then Phase 6.

### Incremental Delivery

Phase 2 → the function is correct with nothing calling it. Phase 3 → new runs stop leaving
content. Phase 4 → interrupted runs still publish. Phase 5 → the record still attests. Phase 6 →
the six existing rows are cleared and #219 closes.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Commit after each task or logical group; sign off every commit (`git commit -s`).
- Run `make check` before declaring any task complete.
- **Add no method to the durability provider.** Research R4 rejected it: `save` already upserts
  by `blob_id`, symmetry with 041 is superficial, and a method would move authoring knowledge
  into the durability provider.
- **Use `uv sync --all-extras`.** A single-extra sync replaces the installed set rather than
  adding to it and breaks ~70 modules at import — learned on 051.

### Two spec items carried from `/speckit-plan` — do not lose on regeneration

Recorded in [plan.md](plan.md) §"Carried findings that need a spec sentence". Both must reach
`/speckit-analyze` and from there `/speckit-clarify`.

1. **FR-007 asks for something unobservable.** A run refused at Judge never composes a
   proposal, so there is nothing in its payload to scrub. T018 ships the row that asserts the
   property which is actually true; the requirement still says otherwise.
2. **The backfill has no requirement behind it.** Six checkpoints already hold authored bodies,
   SC-001 says 100%, and the acceptance row sweeps the whole table. T028–T032 build it; the
   spec does not ask for it.
