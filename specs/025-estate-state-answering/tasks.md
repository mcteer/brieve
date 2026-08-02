# Tasks: Estate-state answering — the answer is bounded by who is asking

**Input**: Design documents from `/specs/025-estate-state-answering/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — every gate row this feature binds is a test, and the spec's success
criteria are written to be verified rather than inspected.

**Organization**: by user story, with two orderings that are load-bearing and called out where
they bind: **FR-012 runs before the reauthoring lands** (T031 before T024), and **the sealed-core
change carries its review obligation** (T007 → contract row, review before merge).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**No project scaffolding is needed** — every directory this feature touches exists. Setup here is
the two measurements the plan's claims rest on, pinned as executable checks before anything is
built on them.

- [ ] T001 Pin the substring-scorer finding: add a failing-by-design characterization note to
      `tests/component/test_eval_gates.py` — a `match`-scored response containing the recorded
      text **plus an invented workspace** passes today. One small test, marked xfail with the
      reason string naming FR-011b, deleted by T026 when fidelity scoring replaces the verb.
      Research F5's measurement, kept executable so the reauthoring provably fixes something.
- [ ] T002 [P] Confirm the one-door premise: extend
      `tests/conformance/answering/test_asking_never_acts.py` with an import row asserting
      `core.answering` (as it stands, pre-estate) imports neither `core.audit.query` nor any
      store — the baseline the estate path will deliberately change in one place only (via
      `surfaces`-level wiring of `read_evidence_for`, T014). Documents the boundary before it
      moves.

## Phase 2: Foundational — routing, scope, and the sealed-core record

**Blocking for every story**: US1 needs scope and routing; US2 needs routing and the estate path;
US3 scores what these produce.

- [ ] T003 Create `src/core/answering/routing.py`: `Route` (`guidance` / `estate` / `neither`),
      `route(question) -> Route`, closed vocabulary constants beside the router. Deterministic —
      no state, no randomness, no model. Ties break toward `estate`, with the plan's
      visible-failure rationale in the docstring (Complexity Tracking row 1).
- [ ] T004 [P] Create `src/core/answering/scope.py`: the role → visible-`AuditEventType` map and
      `visible_event_types(roles) -> frozenset[AuditEventType]`. Union across roles; empty union
      is a refusal the caller performs (FR-004c) — this module computes, it does not raise, so the
      refusal lives beside the read where the trail can see it.
- [ ] T005 [GATE:fail-closed] Component rows for routing in
      `tests/component/test_ask_routing.py`: estate-shaped → `estate`, guidance-shaped →
      `guidance`, fits-neither → `neither` (never coerced — the spec's "decline, not a coin flip"
      edge case), the both-shaped tie → `estate`, and determinism (same question, same route,
      repeated).
- [ ] T006 [P] [GATE:fail-closed] Component rows for scope in
      `tests/component/test_estate_scope.py`: union across roles; unknown role contributes
      nothing; **empty roles produce the empty set** that T014 must refuse on; the map's domain is
      the closed enum (a test that fails if a mapping names a nonexistent event type).
- [ ] T007 [GATE:conformance] **SEALED CORE** — extend `AuditEventType.ASK_ANSWERED`'s docstring
      and payload contract in `src/core/audit/schema.py`: payload gains `source`
      (`guidance` / `estate` / `neither`), and `corpus_digest`'s documented meaning generalises to
      *identity of what was consulted* (estate asks carry the evidence-access record's correlation
      id — data-model.md § ASK_ANSWERED). Update `src/core/answering/record.py`'s `record_ask` to
      require `source`. **Principle V review: Dan McTeer, before merge** — already declared in
      plan.md and contracts/conformance.md; this task is the change it reviews.
- [ ] T008 [P] Extend the pinned-digest row in `tests/unit/test_audit_chain.py` for the payload
      contract change, the same way 024 pinned `ask_answered` itself — the sealed-core diff and
      its test move together or the review has nothing to hold.
- [ ] T009 Thread `source` through the existing guidance path: `src/surfaces/api/ask.py` and
      `src/surfaces/mcp/transport.py` pass `source="guidance"` (and `"neither"` on the unroutable
      decline once T015 lands); every existing `record_ask` call site updated in the same change —
      `make check` is the sweep that proves none was missed.

**Checkpoint**: routing and scope exist and are proven in isolation; the record can carry the
route. No estate answer exists yet.

## Phase 3: User Story 1 — a compliance analyst asks, bounded by entitlement (P1) 🎯 MVP

**Goal**: an estate question gets an answer assembled from records, bounded by tenant + roles,
every claim referenced, no verdicts.

**Independent test**: two subjects with different roles ask the identical question and receive
answers differing exactly by entitlement, each claim resolving into that subject's own scoped
read.

- [ ] T010 [US1] Create `src/core/answering/estate.py`: `EstateReference` (entry hash),
      `EstateClaim`, `EstateAnswer` (disposition / source / claims / declined_reason / dropped —
      data-model.md shapes), `EstateProvider` protocol, and `RecordedEstateProvider`. Module
      docstring carries the never-acts inheritance: a reader of scoped records and a provider
      seam, no registry, no grant, no store import.
- [ ] T011 [US1] Implement `answer_estate_question(question, records, provider)` in
      `src/core/answering/estate.py`: provider proposes claims; **every reference must resolve
      into `records` — the asker's own scoped read result — or the claim drops** (research F3);
      nothing left → decline whose reason names the records, never the corpus (FR-010c). Provider
      faults raise `ProviderUnavailable`, never shape a decline (FR-003).
- [ ] T012 [P] [US1] [GATE:fail-closed] Component rows in
      `tests/component/test_estate_answering.py`: resolvable references survive; one unresolvable
      reference drops its claim into `dropped`; all-dropped declines with the estate-naming
      reason; empty scoped read declines identically to not-yours (SC-008's response half);
      provider fault raises.
- [ ] T013 [P] [US1] [GATE:fail-closed] Verdict-vocabulary row in the same file: an answer citing
      violation records that contains *compliant / passing / healthy / safe* about the estate
      fails (SC-003, FR-005) — checked over the assembled answer, where the temptation lives, not
      the provider output.
- [ ] T014 [US1] Wire the estate branch into `ask_for()` in `src/surfaces/api/ask.py`:
      `route()` first; on `estate` — **refuse on empty `visible_event_types` before any read**
      (FR-004c, no access record because no access was attempted, SC-011), then call
      `read_evidence_for` with `event_types` narrowed by scope (research F2 — the one governed
      door, FR-008 free), then `answer_estate_question` over the result; `record_ask` with
      `source="estate"` and the access record's correlation id as the consulted identity. On
      `neither` — decline naming both sources, `source="neither"`.
- [ ] T015 [US1] The MCP side reaches the same implementation through the shared `ask_for` in
      `src/surfaces/mcp/transport.py` — parameter threading only; any logic difference between
      the surfaces is a defect by construction (ADR-0033).
- [ ] T016 [US1] [GATE:conformance] The differential-entitlement row (SC-001) in
      `tests/conformance/answering/test_estate_bounded_by_asker.py`: two subjects, same tenant,
      different roles, identical question — answers compared (not inspected) and differing
      exactly by scope; each claim's reference resolves into that subject's own read; the
      role-poorer subject's answer contains no shape of the other's records (FR-005a).
- [ ] T017 [P] [US1] [GATE:conformance] The caller/investigator row (SC-008) in the same file:
      "no records in scope" and "records exist, not yours" produce byte-identical response
      dispositions and reasons, while the trail's access records carry different dispositions —
      both halves asserted, satisfying either alone fails.
- [ ] T018 [P] [US1] [GATE:no-secret-leak] Row asserting the estate answer carries references and
      statements only — no payload content of the referenced entries beyond the claim's own text,
      and nothing credential-shaped, in `tests/conformance/answering/test_estate_bounded_by_asker.py`.
- [ ] T019 [US1] [GATE:conformance] Extend the never-acts rows in
      `tests/conformance/answering/test_asking_never_acts.py` over the estate path: the import
      row covers `routing.py` / `scope.py` / `estate.py` (replacing T002's baseline with the
      one-door shape: `estate.py` imports no query, no store, no registry), and the exercised
      rows add instruction-shaped estate questions — *"fix the workspaces that violate this
      control"* answers or declines and changes nothing (SC-004, US1 scenario 4).
- [ ] T020 [US1] [GATE:conformance] Estate verdicts join the parity rows in
      `tests/conformance/mcp/test_ask_parity.py`: estate answer, estate decline (reason
      compared, not just disposition), empty-roles refusal, and store-failure-is-not-a-decline —
      same verdict on both surfaces. Parity grows by zero operations.
- [ ] T021 [US1] [GATE:correlation/evidence] The one-hop walk row: an estate ask's
      `ask_answered` record's consulted-identity field leads to the evidence-access record for
      exactly the narrowed read this question performed, in
      `tests/conformance/answering/test_estate_bounded_by_asker.py` (data-model.md § ASK_ANSWERED).

**Checkpoint**: US1 is a viable MVP — an entitlement-bounded, referenced, verdict-free estate
answer on both surfaces, fully rowed.

## Phase 4: User Story 2 — an operator asks what changed last night (P2)

**Goal**: time-windowed questions answer from records inside the window, bounded the same way.

**Independent test**: a window with known records in and out — the answer describes only what
falls inside.

- [ ] T022 [US2] Window handling in `src/core/answering/routing.py` + `ask_for`: an
      estate-routed question's window narrows `start_time`/`end_time` on the same
      `read_evidence_for` call (temporal vocabulary is already the router's estate signal;
      unbounded questions get the read path's existing `limit` as the bound — the spec's
      "enormous window" edge case, stated in the answer when truncation occurred).
- [ ] T023 [US2] [GATE:conformance] Window rows in
      `tests/component/test_estate_answering.py`: records inside/outside a window — only inside
      described (US2 scenario 1); empty-window answer indistinguishable from
      no-records-you-may-see (US2 scenario 2, the SC-008 discipline applied to time); the
      all-time question is bounded, not unbounded.

**Checkpoint**: both personas ADR-0035 names are served through one path.

## Phase 5: User Story 3 — the gate scores the product (P3)

**Goal**: `estate_state` scores what the product produced, both failure directions, no vendor.

**Independent test**: a deliberately wrong answer — one invented reference, one omitted — fails
the suite. Before this phase it cannot (T001 proves it).

- [ ] T024 [US3] **Ordering: T031 (FR-012) must be recorded before this task merges.** Author
      `packs/vault/evals/estate_records.toml` and `packs/terraform/evals/estate_records.toml` —
      the arranged estates: entries with hashes, event types, and the payload shapes the
      questions need. No digest pin, and the file header says why (authored fixture material has
      no third party to drift from — contracts/conformance.md).
- [ ] T025 [US3] Reauthor `packs/vault/evals/estate_state.toml` and
      `packs/terraform/evals/estate_state.toml`: records-answerable prompts only (FR-006a — the
      mounted-engines and auth-methods questions are replaced), `recorded` = the model's proposed
      claims with references, `events` = the expected reference set (data-model.md § Eval case
      shape).
- [ ] T026 [US3] [GATE:eval] Estate scoring in `src/core/evals/scoring.py` +
      `src/core/evals/suites.py`: `EstateAnsweringScorer` drives `answer_estate_question` with
      `RecordedEstateProvider` over the pack's fixture estate; surviving references scored by
      `score_fidelity` against `case.events` — precision fails invention, recall fails omission
      (FR-011b); `estate_state` leaves `EXPECTED_OUTCOMES`'s `match` verb; `parse_cases` requires
      `events` for it. **Delete T001's xfail here** — its reason no longer exists.
- [ ] T027 [P] [US3] [GATE:eval] Both-directions break rows in
      `tests/component/test_eval_gates.py`: an answer with one invented reference fails; an
      answer omitting one expected reference fails; and the scorer-identity assertion extends so
      `estate_state` reverting to any other scorer fails hermetically (024's anti-reversion row,
      third member).
- [ ] T028 [US3] Membership updates in `src/core/evals/suites.py` and the live lane:
      `estate_state` joins the answering-scored set (its own scorer, asserted by name);
      `tests/evals_live/test_gates_live.py` drives the live half through the product path — a
      `LiveEstateProvider` in `src/adapters/anthropic_answering.py` offers the fixture records to
      the real model, path resolves, fidelity scores; `_grounding_for`'s special case for
      estate_state is deleted (the grounding is now the offered records, inside the path).
- [ ] T029 [P] [US3] Extend `tests/evals_live/smoke.py` with one estate probe printing proposed
      claims and per-reference resolves/DOES-NOT-RESOLVE — the same defect-shape 024's smoke
      probes exist for: a model inventing an entry hash reads as a confident answer that
      declines, invisible in a verdict.

**Checkpoint**: the last authored-recording suite is gone; every prompt-scoring suite drives the
product.

## Phase 6: Polish, the named runs, and the record

- [ ] T030 [P] Glossary entries in `docs/glossary.md`: *estate reference*, *route*, *scope* —
      linking to *answer*, *citation*, *decline* from 024.
- [ ] T031 **[FR-012 — owed by name, ordered before T024/T025 merge]** Run the OLD
      `estate_state`/vault suite against the live model with per-case output (evals-smoke
      discipline, ~15 calls): name the 2026-08-01 failing case id(s) and cause; record the
      finding in `specs/025-estate-state-answering/contracts/conformance.md` § *FR-012 finding*
      — either way (SC-006). Runner: **Dan McTeer**.
- [ ] T032 ROADMAP entry for 025: ADR-0035 executed at tenant+role granularity; **owed and
      deferred recorded**: team-granularity scope (FR-004d), the portal answering surface, corpus
      freshness — the standing three, so the next planner finds them.
- [ ] T033 [GATE:conformance] `make check`, `make evals`, and the hermetic conformance sweep
      (`pytest tests/conformance --ignore=tests/conformance/durability -m "not enclave and not
      live_model"`) all green.
- [ ] T034 Run `make conformance` on a live enclave, then one served estate ask per
      quickstart.md § 5 — answer resolves, `ask_answered` carries `source: estate`, access
      record one hop away. **Owed by name: Dan McTeer.**
- [ ] T035 Qualify the reauthored `estate_state` via `make evals-live` (both packs, product
      path). On green, move the `ask` cell's matrix column to `live` **in the same change that
      records the run**; on red, record the failing cases (which T029's probe now names) and the
      column stays. **Owed by name: Dan McTeer, paid credential.**

---

## Dependencies

```text
Phase 1 (T001–T002)
  → Phase 2 (T003–T009: routing ∥ scope, then schema T007→T008→T009)
    → Phase 3 / US1 (T010→T011→{T012,T013} → T014→T015 → rows T016–T021)
      → Phase 4 / US2 (T022→T023)                    [needs the estate branch, not US1's rows]
      → Phase 5 / US3 (T024→T025→T026→{T027,T028,T029})  [scores the path US1 built]
        → Phase 6 (T030 ∥ T032 anytime; T031 BEFORE T024/T025 merge; T033→T034→T035 last)
```

**The one cross-phase ordering rule**: T031 (name the old failure) completes before T024/T025
(replace the old suite) merge. The contract says why: a reauthoring that lands first replaces the
evidence of what failed with a suite that never contained it.

## Parallel opportunities

- T003 ∥ T004 (different files); T005 ∥ T006 after their modules; T008 with T007's diff.
- Within US1: T012 ∥ T013; T016–T018 and T021 are separate rows in two files; T019 ∥ T020.
- Within US3: T027 ∥ T028 ∥ T029 after T026.
- T030 and T032 anytime after Phase 5's shape is fixed.

## Implementation strategy

**MVP = Phase 3.** Routing + scope + the estate path with the differential-entitlement row is a
demonstrable slice: the ADR-0035 sentence, executable. US2 is one narrowing parameter on the same
read. US3 is where the schedule pressure came from, but it scores what US1 builds — building it
first would recreate 013's original defect (a suite for a capability that does not exist).

## Notes

- **Gate types**: fail-closed (T005, T006, T012, T013), conformance (T007, T016, T017, T019,
  T020, T021, T023, T033), correlation/evidence (T021), eval (T026, T027), no-secret-leak (T018).
  None omitted — every type is implicated.
- **Sealed core**: exactly one task (T007), reviewed by name before merge.
- **Nothing under `src/surfaces/portal/` changes** — 024's containment row already asserts the
  portal imports no `core.answering`; it keeps holding here without a new task.
