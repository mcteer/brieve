---

description: "Task list for 022 — the trail records who looked"
---

# Tasks: The trail records who looked, or the surface stops saying it does

**Input**: Design documents from `/specs/022-audited-reads/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/conformance.md](./contracts/conformance.md)

**Tests**: Test tasks are included. This feature exists because a defect survived a green suite,
so the rows are the deliverable rather than a supplement to it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 per spec.md
- Exact file paths in every description

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — FR-007a makes a read's audit write enforcement | T012, T013, T026 |
| **Conformance** | **Yes** — sealed-core seam and both transport surfaces | T028, T029, T030 |
| **Correlation / evidence** | **Yes** — read records join runs by correlation id, and must not join *into* them | T014, T024, T025 |
| **No-secret-leak** | **Yes** — a record must carry no content it was shown | T015 |
| **Eval** | **No.** No model, no judge, no pack, no policy. `OWED` stays empty and no suite moves. Stated rather than omitted. | — |

## Path Conventions

Single project: `src/`, `tests/` at repository root, per plan.md's structure decision.

---

## Phase 1: Setup

- [ ] T001 Read `src/surfaces/api/evidence.py` end to end before writing anything — it is the
      pattern this feature adopts (research F1), and three of its decisions are load-bearing here:
      the stable per-tenant stream, the shape-not-rows payload, and the failing write.
- [ ] T002 Confirm the pinned digest baseline is green before any schema change, by running
      `uv run pytest tests/unit/test_audit_chain.py -q`. A later failure must be attributable to
      this feature rather than inherited.

---

## Phase 2: Foundational — blocking prerequisites

### The sealed-core change, done deliberately

- [ ] T003 Add `RECORD_READ = "record_read"` and `RECORD_READ_REFUSED = "record_read_refused"` to
      `AuditEventType` in `src/core/audit/schema.py`, each with a docstring saying why it is not
      `EVIDENCE_READ` — those members mean *someone read the audit plane*, and reusing them would
      hand an operator asking who read the trail a list of run listings.
- [ ] T004 Add `THREAD_CREATED = "thread_created"` to `AuditEventType` in
      `src/core/audit/schema.py`, with a docstring pointing at its existing counterpart: the trail
      can prove a thread was deleted and what was said in it, and cannot prove it began.
- [ ] T005 [GATE:conformance] Extend
      `tests/unit/test_audit_chain.py::test_widening_the_event_vocabulary_moves_no_existing_hash`
      with the three new members, asserting each `.value` individually rather than counting the
      enum — a count passes when one member is removed and another added, which is the change this
      row would most want to notice. **The pinned literal must not move.**

### The recording seam

- [ ] T006 Create `src/surfaces/api/record_access.py` with `RECORD_ACCESS_STREAM_PREFIX =
      "record-access"` and `record_stream_for(tenant_id)`, carrying the note that the stream is
      **stable per tenant, never per read** — a fresh correlation id each time makes every record a
      chain of one, linked to nothing and removable without trace.
- [ ] T007 Add to `src/surfaces/api/record_access.py` a docstring stating why this is a second
      stream rather than `evidence-access` (research F3): deliberate evidence reads are what an
      auditor opens first, and an editor's idle `list_runs` polling would bury them permanently
      because the trail is never sampled. Name the cost — "who looked at anything" now queries two
      streams.
- [ ] T008 Define `RecordAccessUnavailable` in `src/surfaces/api/record_access.py` as a **core
      error, not an `HTTPException`** — research F7 found the existing evidence path raises a
      FastAPI type from transport-independent code that the MCP transport does not catch, so its
      failure path has no parity. This type is what both transports map identically.
- [ ] T009 Implement `record_access(...)` in `src/surfaces/api/record_access.py` writing one entry
      to `record_stream_for(subject.tenant_id)` with the payload fields data-model.md specifies:
      `subject_user_id`, `operation`, `target_correlation_id`, `target_id`, `disposition`,
      `result_count`. No other fields.
- [ ] T010 [GATE:fail-closed] Make `record_access` raise `RecordAccessUnavailable` when the append
      fails. **No best-effort path, no swallow, no log-and-continue.** An access that succeeded
      while its record did not is the state this feature exists to end.

### The disposition, where it cannot be skipped

- [ ] T011 Add a required `audit_disposition` field to `McpOperation` in
      `src/surfaces/mcp/operations.py` — no default. An operation added without deciding must be a
      construction error, not a missed edit to a list someone has to remember (FR-009).
- [ ] T012 Set the disposition on all seventeen operations in
      `src/surfaces/mcp/operations.py`: `records` for the six covered, `no_record` for
      `list_agent_definitions` and `get_agent_definition`, `records_elsewhere` for the rest —
      and for each `records_elsewhere`, name where, because a disposition that says "recorded
      somewhere" without saying where is indistinguishable from a wrong one.

**Checkpoint**: the vocabulary, the seam, and the classification exist. No operation records yet.

---

## Phase 3: US1 — an auditor asks who read a run's output (P1)

**Goal**: the six covered operations record, with `get_run_result` the one that must work under
any reading of the rule.

**Independent test**: start a run, read its result, query the trail by that run's correlation id,
find a record naming the reader.

- [ ] T013 [US1] Record in `get_run_result`'s shared implementation in
      `src/surfaces/api/runs.py` — before returning the payload, never after. A read that answered
      first and recorded second produces the unrecorded answer on any failure between the two.
- [ ] T014 [US1] [GATE:correlation] Populate `target_correlation_id` from the run's own
      correlation id in `src/surfaces/api/runs.py`, so holding a run id is enough to find its
      readers through the existing governed query.
- [ ] T015 [US1] [GATE:no-secret-leak] Assert in `tests/component/test_record_access.py` that a
      credential-shaped value planted in a run's result payload reaches no audit entry. Plant it;
      do not reason about it.
- [ ] T016 [P] [US1] Record in `list_runs_for` in `src/surfaces/api/runs.py`, with
      `target_correlation_id` null (a listing has no single target) and `result_count` set.
- [ ] T017 [P] [US1] Record in the single-run read (`get_run`) in `src/surfaces/api/runs.py`.
- [ ] T018 [P] [US1] Record in `list_threads_for` in `src/surfaces/api/threads.py`.
- [ ] T019 [P] [US1] Record in `thread_detail_for` in `src/surfaces/api/threads.py`.
- [ ] T020 [US1] Write `THREAD_CREATED` in `create_thread_for` in `src/surfaces/api/threads.py`,
      to **the thread's own stream** (`record.correlation_id`) — matching where `THREAD_DELETED`
      is written, not the reader stream. This is a creation, not a read.
- [ ] T021 [US1] Map `RecordAccessUnavailable` to a 503 in the API routes in
      `src/surfaces/api/runs.py` and `src/surfaces/api/threads.py`, with a reason naming that the
      read was refused because it could not be recorded.
- [ ] T022 [US1] Map `RecordAccessUnavailable` to the **same** 503 verdict in the six MCP handlers
      in `src/surfaces/mcp/transport.py`. This is what makes FR-008's parity hold on the failure
      path, which research F7 measured the existing evidence path does not have.
- [ ] T023 [US1] Assert in `tests/component/test_record_access.py` that each of the six writes
      exactly one entry per call, naming caller, operation, and target.
- [ ] T024 [US1] [GATE:correlation] Assert in `tests/component/test_record_access.py` that a read
      leaves the read object's chain **byte-identical** — the entry count and the head hash of the
      run's own stream are unchanged after reading it.
- [ ] T025 [US1] [GATE:correlation] Assert in `tests/conformance/reports/` that a report compiled
      for a run after that run has been read carries **no claim about who read it**. This is the
      row protecting 021, and it is the guard against the first draft's reasoning returning.
- [ ] T026 [US1] [GATE:fail-closed] Assert in `tests/component/test_record_access.py` that with
      the sink made to fail, **all six** operations refuse and return no records — listings
      included. Listings are the case with no precedent and the one most likely to be softened
      later for convenience.
- [ ] T027 [US1] Assert in `tests/component/test_record_access.py` that a refused read records,
      and that `no_such_record` and `outside_tenant` stay distinct in the entry while remaining
      indistinguishable in the response.
- [ ] T028 [US1] Assert in `tests/component/test_record_access.py` that a read returning nothing
      still records — an empty listing discloses that the caller asked, and a trail omitting
      fruitless reads cannot show probing.
- [ ] T029 [US1] [GATE:conformance] Extend `tests/conformance/mcp/test_surface_parity.py` so the
      six operations are compared across both transports on the success path, the refusal path,
      **and** the unrecordable path.

**Checkpoint**: US1 is independently shippable. The trail answers "who read this run's output".

---

## Phase 4: US2 — the surfaces describe governance they actually perform (P1)

**Goal**: the claim cannot overclaim, because it is derived rather than written.

**Independent test**: change one operation's disposition; the surface's sentence changes with it.

- [ ] T030 [US2] Replace the hand-written governance sentence in `src/surfaces/mcp/served.py`
      (currently *"Every operation executes as the calling user and is recorded in a tamper-evident
      trail"*) with text **generated** from the operation catalogue's dispositions.
- [ ] T031 [US2] Assert in `tests/component/` that the generated sentence names the recorded
      operations accurately, by flipping one disposition and observing the sentence change.
      A row comparing the sentence to a second hand-written expectation would have passed every
      day this gap existed — research F9.
- [ ] T032 [US2] Assert in `tests/component/` that every operation whose disposition is `records`
      actually writes an entry, and every `no_record` operation writes none. This is the row that
      would have failed on 2026-08-01, and the contract names it as such.
- [ ] T033 [US2] Check the API surface for any equivalent governance claim in its title,
      description, or docs, and bring it into line or confirm in writing that it makes none.
      Parity of claims, not only of behavior.

**Checkpoint**: US2 is shippable alone. Even with no coverage change, the platform would stop
lying about what it records.

---

## Phase 5: US3 — the catalogue states each operation's disposition (P2)

**Goal**: the next operation cannot repeat this.

- [ ] T034 [US3] Write the rule where someone adding an operation will meet it — in
      `src/surfaces/mcp/operations.py` beside the field — stating the boundary and its
      justification: runs and threads are records of *activity*; agent definitions are
      *configuration*, and reading one discloses how the platform is set up rather than what
      anyone did with it.
- [ ] T035 [US3] Assert in `tests/component/` that `SC-011` holds — the two catalogue operations
      record nothing, pinned deliberately so a later widening is a visible decision rather than a
      drift nobody notices. **Do not delete this row for looking like dead weight; that is what it
      is for.**
- [ ] T036 [US3] Rename or re-docstring `tests/component/test_operations_audited.py` so it stops
      implying coverage it never had. It asserts unauthenticated refusal and always did; leaving a
      file named for this feature's check, beside this feature, is how the next reader concludes
      the question is already covered.

---

## Phase 6: The decision record

- [ ] T037 Amend `docs/adr/0035-estate-state-queries-and-audit-read-path.md` to state that the
      governed-read discipline extends past the audit plane to records about runs and threads
      (FR-012). **Same change, not a follow-up** — shipping the extension while the ADR describes
      the narrower scope puts the decision record behind the system.
- [ ] T038 In the same amendment, carry forward the separate-stream safeguard the ADR already got
      right, now load-bearing for a second reason (FR-005a): a read appended to the chain being
      read would put "who read this run" inside 021's report of that run, including reads of the
      report, growing every time anyone looked.
- [ ] T039 In the same amendment, name the consequence research F3 accepted: an auditor asking who
      looked at anything in a tenant now queries two streams.

---

## Phase 7: The adjacent fix (recommended, flagged)

**Research F7 found a live defect in the code this feature copies.** It is pre-existing and is not
one of the six covered operations. It is listed separately so that including it is a decision and
cutting it is also a decision.

- [ ] T040 Convert `_record_access` in `src/surfaces/api/evidence.py` to raise the core error
      from T008 rather than `fastapi.HTTPException`, so its failure path gains the parity its own
      docstring argues for.
- [ ] T041 Catch it in `src/surfaces/mcp/transport.py::_read_evidence` and return the same 503
      verdict the API returns, then extend the parity row to cover the evidence path's failure
      case.

**If Phase 7 is cut**, T008 still stands: the six new call sites must not copy the HTTPException
shape into transport-independent code.

---

## Phase 8: Polish & cross-cutting

- [ ] T042 Update `docs/glossary.md` with *read record*, *record-access stream*, and *audit
      disposition*.
- [ ] T043 Update `ROADMAP.md` recording 022 shipped, and that the gap was found by connecting an
      editor rather than by any check.
- [ ] T044 Run `make check` and confirm the pinned digest is unmoved and no operation lost an
      entry it wrote before this feature (SC-008).
- [ ] T045 Run `make conformance` in full on a live enclave. **Owed by name** — the enclave lane is
      `workflow_dispatch` only and will not run on the PR.
- [ ] T046 Perform quickstart scenario 5 against a **served** surface: read a run's result through
      the running service, then find the reader in the trail. SC-002 is written not to be hermetic
      on purpose — this defect survived a green suite and was found by connecting a real editor.
- [ ] T047 Request the Principle V security review on the PR for the three additive members, and
      record its discharge in `specs/022-audited-reads/contracts/conformance.md` — sealed core is
      not dischargeable by the author alone.

---

## Dependencies

```text
Phase 1 (T001–T002)
   ↓
Phase 2 (T003–T012)  ← blocks everything; vocabulary + seam + classification
   ↓
   ├── Phase 3 US1 (T013–T029)  ← the six record
   ├── Phase 4 US2 (T030–T033)  ← needs T011–T012 only, NOT Phase 3
   └── Phase 5 US3 (T034–T036)  ← needs T011–T012 only
   ↓
Phase 6 (T037–T039)  ← the ADR; must land in the same PR
Phase 7 (T040–T041)  ← independent of everything; needs T008
Phase 8 (T042–T047)
```

**US2 does not depend on US3.** Both need only the disposition field and its values (T011–T012).

**T025 depends on T013–T020** — there must be reads before you can prove a report ignores them.

---

## Parallel opportunities

- **T016–T019** are four independent recording sites across two files. `runs.py` (T016, T017) and
  `threads.py` (T018, T019) can proceed in parallel with each other; within a file, sequential.
- **Phase 4 and Phase 5** run in parallel once T012 lands.
- **Phase 7** is independent of Phases 3–6 once T008 exists.
- **T003 and T004** touch the same file and must be sequential despite being trivially separate.

---

## Implementation strategy

**MVP is US1 + US2, not US1 alone.** US1 makes the six record; US2 makes the claim true. Shipping
US1 without US2 leaves the surfaces still asserting that the two catalogue operations are recorded
when the coverage rule has deliberately decided they are not — trading one false claim for a
different one.

**If schedule pressure hits, cut US3 before US2.** US3 prevents recurrence and is the most
valuable long-term; US2 stops an active false statement to every connecting client. An overclaim
about governance is worse than an acknowledged gap.

**T005 is the first thing to get right.** If the pinned digest moves, stop — the encoding changed
and every entry ever written is at risk. Nothing else in this feature matters until that is
understood.

---

## Notes

**47 tasks.** The largest phase is US1 at seventeen, and eight of those are rows rather than
implementation — which is the right ratio for a feature whose entire subject is that a green suite
proved nothing.

**Three obligations here cannot go green on their own**: T045 (enclave), T046 (served
demonstration), T047 (security review). They are tasks anyway, and they are named in the
conformance contract, so merging without them is visibly a gate regression rather than an
oversight.

**One task exists to delete a trap** (T036). `test_operations_audited.py` is a good file whose name
promises this feature's check and delivers a different one. That misdirection is a measurable
contributor to eight operations shipping unrecorded across eleven additions, and it costs a rename
to remove.
