# Tasks: Asking binds to the Qualified Model Matrix

**Input**: Design documents from `/specs/026-ask-binds-to-matrix/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the feature exists because a merged contract asserted an untested refusal,
so every property here lands as a row.

**Organization**: by user story. One ordering is load-bearing: **the sealed-core change (T006)
carries its declared review**, and the fixture work (T012–T014) must land the refusal default
*before* the ~20 existing rows are updated, so each updated row is seen to fail first for the
right reason rather than edited pre-emptively.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Pin the gap as an executable measurement in
      `tests/conformance/answering/test_ask_binds_to_matrix.py`: a row asserting the
      FR-001-**correct** behaviour — a counting provider injected with **no** authority records
      **zero calls** — marked `xfail(strict=True)` with a reason naming 024's SC-006, because
      today the provider answers. When T015 wires the ordering, strict xfail errors on the xpass
      and T015 removes the **marker**, not the test — the row then *is* SC-009's tripwire and
      FR-012's named row, forever. (025's T001 pattern, which worked.)

## Phase 2: Foundational — the resolver and the record

- [X] T002 Create `src/core/authority/ask_binding.py`: `AskBinding` (optional `guidance_cell` /
      `estate_cell`), `parse_ask_binding_record` on `ceiling.py`'s discipline —
      `schema_version` required and `1`, absent/newer refuses `unsupported_schema_version`, a
      cell reference whose role is not `ask` refuses `malformed_record` **at parse** (a
      mis-authored binding fails when written about, not when first asked through). Module
      docstring carries research F1: this lives in `authority`, not `answering`, because 025's
      never-acts rows forbid the answering path any import containing "authority".
- [X] T003 Implement `resolve_ask_cell(source, binding, cells, available)` in the same file:
      look up the bound cell for the source, refuse `unbound` when the record or the source's
      cell is absent, then **delegate to `resolve_with_fallback`** — no branch of this module's
      own, so the no-third-branch property is inherited rather than re-established.
- [X] T004 [P] [GATE:fail-closed] Component rows for parsing in
      `tests/component/test_ask_binding.py`: well-formed parses; either cell omissible; both
      omitted is well-formed and refuses everything; missing/newer schema_version refuses;
      non-`ask` role refuses at parse; malformed table refuses.
- [X] T005 [P] [GATE:fail-closed] Component rows for resolution in the same file: bound + green
      resolves `pinned`; `unbound` for no record and for no cell-for-this-source; withdrawn
      refuses like absent (SC-002, asserted though inherited — inherited properties nobody
      asserts stop being inherited); a `plan` cell never authorises (SC-003); unavailable model
      with a qualified alternative returns the fallback pair; without one, refuses.
- [X] T006 [GATE:conformance] **SEALED CORE** — `AuditEventType.ASK_ANSWERED`'s documented
      payload in `src/core/audit/schema.py` gains `cell`, `bound_cell`, `cell_disposition`
      (data-model.md table — the substitution rides the ask record, research F3, so no run id is
      fabricated and `MATRIX_FALLBACK` is not generalised). Update
      `src/core/answering/record.py`'s `record_ask` to require the three fields.
      **Principle V review: Dan McTeer, before merge** — declared in plan and contract; this
      task is the change it reviews.
- [X] T007 [P] Extend the exact-payload row in `tests/component/test_answering.py` by exactly
      the three keys, and annotate the pinned-digest row in `tests/unit/test_audit_chain.py`
      the way 025 did — the payload contract and its test move together or the review has
      nothing to hold.
- [X] T008 Thread the three fields through every existing `record_ask` call site
      (`src/surfaces/api/ask.py` ×3 paths, `src/surfaces/mcp/transport.py`,
      `tests/component/test_answering.py`) with the interim value
      `cell="", bound_cell="", cell_disposition=""` and a comment naming T010 as the task that
      makes them real — an empty string is visibly "not yet wired", where a fabricated
      `refused:unbound` on an answered record would be a contradictory record in the diff
      (analysis A1). `make check` is the sweep that proves no call site was missed.

**Checkpoint**: the record can carry authorisation and the resolver refuses correctly in
isolation. Nothing consults it yet; T001 still xfails.

## Phase 3: User Story 1 — an unqualified model is never reached (P1) 🎯 MVP

**Goal**: resolve before the provider is touched, on both surfaces, for both sources; three
distinguishable recorded refusals.

**Independent test**: a counting provider with no authority records zero calls (T001's row,
marker off).

- [X] T009 [US1] Define the `AskAuthority` collaborator in `src/core/authority/ask_binding.py`:
      holds a binding reader and a matrix reader (callables — in-memory in tests, fabric-backed
      in assembly), exposes `resolve(source, available)`; reader failure surfaces as the
      unreadable refusal, **distinct from empty** (SC-004 — `MatrixSource`'s own documented
      distinction, kept).
- [X] T010 [US1] Wire the ordering into `src/surfaces/api/ask.py`: `build_router` and
      `estate_answer_for`/guidance branch gain `ask_authority` (default `None` = refuse
      `unbound` — **a configured provider is not a qualification**, FR-004a); resolution runs
      **before any provider call in both branches**, and the refusal order is fixed (analysis
      U3): **governance first** (`unbound` / `unqualified_cell` / `matrix_unreadable`), then
      scope (`scope_empty`), then provider availability (`provider_unavailable`) — an unbound
      surface refuses `unbound` even with no provider, because "nobody decided" is the answer an
      operator needs before "nothing is wired". Today the provider-None check runs first
      (measured, `ask.py:249,297`); this task inverts that. The three refusals are **recorded
      via `record_ask` then returned** (SC-008); a produced answer records `cell`, `bound_cell`,
      `cell_disposition` (SC-005). **All seven call sites get their defined value** (analysis
      U4, data-model § ASK_ANSWERED): post-resolution refusals (`scope_empty`,
      `provider_unavailable`) keep the resolution outcome, and the `neither` decline records
      `not_applicable` — no site is left inventing one.
- [X] T011 [US1] `create_app` in `src/surfaces/api/app.py` and `McpTransport` in
      `src/surfaces/mcp/transport.py` gain `ask_authority`, threaded to the one shared
      implementation — parity by construction, not by twin edits (ADR-0033).
- [X] T012 [US1] Fixture plumbing in `tests/harness/api_fixtures.py`: `surface_under_test`
      gains `ask_authority`, **one instance shared by both surfaces** like the eight before it;
      add `qualified_ask_authority(model=...)` building an in-memory binding + matrix pair
      qualifying `model` for both sources. **The default stays `None` and the fixture never
      auto-qualifies an injected provider** (research F5 — that would rebuild
      "configured = qualified" inside the harness).
- [X] T013 [US1] [GATE:conformance] The headline rows in
      `tests/conformance/answering/test_ask_binds_to_matrix.py` (T001's file, marker removed
      here): provider-never-called with no authority (SC-001, **counted at the provider**, both
      surfaces, both sources); fixture-default-refuses (SC-003b — provider injected, no
      authority, `unbound`); withdrawn-refuses-like-absent and wrong-role-refuses through the
      wired surface (SC-002/SC-003); unreadable ≠ empty (SC-004); each refusal recorded with its
      disposition (SC-008); **per-source** (SC-003a, analysis C1) — guidance bound + estate
      unbound answers guidance and refuses estate in the same session; the **plain pinned
      answer's record** carries `cell_disposition="pinned"` with `cell == bound_cell` (SC-005's
      answered half, analysis C1 — T018 covers fallback, this covers the common case); and the
      **combined-absence** case (analysis U3) — no authority AND no provider refuses `unbound`,
      not `provider_unavailable`, proving governance precedes availability.
- [X] T014 [US1] Update the ~20 existing answering rows to arrange authority **explicitly**:
      `tests/conformance/answering/test_ask_routes_by_shape.py`,
      `tests/conformance/answering/test_estate_bounded_by_asker.py`,
      `tests/conformance/mcp/test_ask_parity.py`, and any component row that drives `ask_for` —
      each gains `ask_authority=qualified_ask_authority(...)`. **Run the suite before editing**:
      every one of these must be seen failing `unbound` first, which is the refusal default
      demonstrating itself across the whole surface area.
- [X] T015 [US1] Remove T001's xfail marker — the row now passes for the right reason and
      becomes SC-009's tripwire. Verify by commenting out the resolution step locally
      (quickstart §3) and watching it fail; restore.
- [X] T016 [US1] [GATE:conformance] Refusal parity rows in
      `tests/conformance/mcp/test_ask_parity.py`: all three dispositions produce the same
      verdict and the same reason on both surfaces (SC-007, FR-011).

**Checkpoint**: the MVP — an unqualified model is unreachable, verifiably, on both surfaces.

## Phase 4: User Story 2 — a substituted model is visible, never silent (P2)

**Goal**: fallback reaches only another qualified cell, and the ask record says so.

**Independent test**: pinned model unavailable + qualified alternative → answer with
`bound_cell` ≠ `cell` and a reason; no alternative → refusal.

- [ ] T017 [US2] Thread `available` into `AskAuthority.resolve` in
      `src/core/authority/ask_binding.py` and `src/surfaces/api/ask.py`, and it is **exactly
      `{the injected provider's model}`** — one element, the model the provider was constructed
      for (analysis U2). Anything wider lets fallback select a cell for a model the provider
      cannot call, and the ask record would then name cell X while the provider called model Y:
      record/actual divergence on an attestation-relevant record, which is the worst available
      outcome. The docstring says this in exactly those words.
- [ ] T018 [US2] [GATE:conformance] Substitution rows in
      `tests/conformance/answering/test_ask_binds_to_matrix.py`: pinned unavailable + qualified
      alternative → answered, record carries `bound_cell`, `cell`,
      `cell_disposition="fallback:model_unavailable"` (SC-006, FR-006); **no alternative →
      refusal, provider never called** (FR-007); fallback never selects a withdrawn or
      wrong-role cell — the no-third-branch property exercised for asks; and **record/actual
      agreement** (analysis U2): the used cell's model equals the model the provider was
      constructed for, asserted by comparing the record against the provider's own
      configuration — divergence here would be the trail naming an authorisation for a model
      that never ran.
- [ ] T019 [P] [US2] [GATE:correlation/evidence] The investigator walk row: for a substituted
      answer, the ask record alone names what was asked for and what was used — no second
      event, no run id anywhere in the payload (research F3's claim, asserted).

**Checkpoint**: every answer's provenance is one record, pinned or not.

## Phase 5: User Story 3 — the contract stops claiming something untrue (P3)

**Goal**: 024's assertion gains the row that backs it, with the gap's dates recorded.

**Independent test**: T001's row fails when the check is removed (verified at T015); the 024
contract names it.

- [ ] T020 [US3] Correct `specs/024-portal-answering/contracts/conformance.md` (FR-012): the
      line *"An unqualified cell refuses before any provider call"* gains the named row
      reference (`test_ask_binds_to_matrix.py::`provider-never-called) and a dated note that
      the assertion was unbacked between 024's merge (2026-08-02) and 026's — recorded plainly,
      because a claim nobody re-measured is the defect class this lineage keeps closing.
- [ ] T021 [P] [US3] Update 026's own `specs/026-ask-binds-to-matrix/contracts/conformance.md`
      status table as rows land, and record the Principle V review outcome when given.

## Phase 6: Polish, deployment, and the named runs

- [ ] T022 [P] Terraform policy in `infra/environments/dev/`: the **`mcp-surface`** role — the
      served surface's own identity (measured, `served.py:58`), distinct from the service's
      `mcp` and from the run role `test_matrix_is_readable` covers — reads
      `harness-authority/data/ask-bindings` and `data/model-matrix`. **A two-path grant to a
      named role, not an increment**: no dev policy grants either path to any surface role
      today (analysis U5); seed an example ask-binding
      record **and the two `ask` cells it names** into the dev matrix record — honest only as a
      pair (research: a seeded binding naming cells the matrix lacks would make `make dev-up`
      produce a surface that refuses `unqualified_cell` out of the box, which reads as broken
      rather than unbound).
- [ ] T023 [GATE:conformance] The readability row in
      `tests/conformance/identity/test_matrix_is_readable.py` (or sibling): authenticating **as
      `mcp-surface`** — not the run role — reads `data/ask-bindings` and `data/model-matrix`
      against the live fabric — a grant in HCL and an effective grant
      are different claims (010's lesson, the plan's named row).
- [ ] T024 [P] Glossary entries in `docs/glossary.md`: *ask binding*, *cell disposition* —
      linking *scope*, *route*, and the matrix vocabulary.
- [ ] T025 [P] ROADMAP entry for 026: the gap (a merged contract asserting an unperformed
      refusal), the fix, and the standing deferrals (portal answering, corpus freshness, team
      scope, **and — new here — real served answering**: the served surface holds no vendor
      credential and wiring one is an undecided deployment posture, so the served check proves
      resolution by disposition progression instead; analysis U1) so the next planner finds
      them.
- [ ] T026 [GATE:conformance] `make check`, `make evals`, and the hermetic conformance sweep
      all green; then `make conformance` on a live enclave (includes T023's row). **Runner: Dan
      McTeer** for the enclave lane, as every feature.
- [ ] T027 The served-process check per quickstart §5, **credential-free by design (analysis
      U1)**: wire `ask_authority` (fabric-backed) into `src/surfaces/mcp/served.py` — which
      already holds workload identity and a Vault fabric client, but wires no ask collaborator
      (measured). Then the progression proves resolution without any vendor key in the service:
      unwired/unseeded → `unbound`; binding + cells seeded → the refusal **moves to
      `provider_unavailable`**, which can only happen if governance resolution PASSED; withdraw
      a cell → `unqualified_cell`. A real served ANSWER needs a vendor credential inside the
      service, which no feature has decided — deferred, recorded in T025. **Runner: Dan
      McTeer.**

---

## Dependencies

```text
Phase 1 (T001, xfail)
  → Phase 2 (T002→T003→{T004,T005} ∥ T006→T007→T008)
    → Phase 3 / US1 (T009→T010→T011→T012 → T013→T014→T015 → T016)
      → Phase 4 / US2 (T017→T018→T019)     [needs the wired ordering]
      → Phase 5 / US3 (T020, T021)          [needs T015's row to exist to name]
        → Phase 6 (T022∥T024∥T025 anytime after US1; T023 after T022; T026→T027 last)
```

**The one intra-phase ordering rule**: T014 runs its suites **before** editing (each row seen
failing `unbound`), and only after T013's default-refuses row exists — so the mass update is
demonstrably fixing refusals, not silencing them.

## Parallel opportunities

- T004 ∥ T005 after T003; T007 with T006's diff; T006-chain ∥ T002-chain.
- Within US1: T013 and T016 are different files after T012.
- T019 after T018; T020 ∥ T021; T022 ∥ T024 ∥ T025.

## Implementation strategy

**MVP = Phase 3.** The refusal ordering with the provider-call count is the constitutional gap
closed; substitution (US2) and the contract correction (US3) complete the guarantee's other half
and its honesty. T001-first mirrors 025: the gap is pinned as a strict xfail so the wiring
provably fixes something, and the same row then guards it forever.

## Notes

- **Gate types**: fail-closed (T004, T005, T010's refusals via T013), conformance (T006, T013,
  T016, T018, T023, T026), correlation/evidence (T019). No eval gate — this feature changes no
  suite and qualifies no cell (plan, Principle VIII note). No-secret-leak not implicated: the
  binding record holds cell names only.
- **Sealed core**: exactly one task (T006), review declared with reviewer named.
- **`core.answering` is untouched except `record.py`'s field threading** — the never-acts rows
  are the enforcement and they run unmodified.
