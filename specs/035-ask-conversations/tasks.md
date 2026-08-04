# Tasks: Ask becomes a conversation

**Input**: Design documents from `/specs/035-ask-conversations/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — this feature touches routing, the evidence payload, and two transports;
every behavioural change lands with the row that pins it (the repo's standing practice).

**Organization**: By user story. Foundational work (the store, the context builder, the routing
signal) blocks everything; each story is then independently completable and testable.

## Gate Task Types

| Gate type | Where it lands here |
| --- | --- |
| **Fail-closed** | T013, T021 — foreign/cross-tenant ids refuse before any work; an unreadable store is 503, never an empty list |
| **Conformance** | T024–T026 — parity across transports; the containment session covers every new operation |
| **Correlation / evidence** | T028–T030 — the record's three context states; delete leaves the trail byte-identical |
| **Eval** | T038 — the SC-002 + SC-011a live check, run before promotion, never blocking CI |
| **No-secret-leak** | T007 — the stored `outcome` is exactly the API response body, which carries no secret by construction; the row asserts no credential-shaped content is ever written to the store |

## Phase 1: Setup

*(No project scaffolding needed — the repo, gates and lanes exist. Setup is the schema.)*

- [X] T001 Create `src/core/answering/conversations/__init__.py` and `schema.sql` with `ask_conversations` + `ask_exchanges` per data-model.md (cascade delete, `(conversation_id, seq)` primary key, indexes on `(tenant_id, subject_user_id, last_asked_at)`)

## Phase 2: Foundational (blocking all stories)

- [X] T002 [P] `ConversationRecord`, `ExchangeRecord`, and `title_from` (re-implemented, not imported from threads — mirror-not-share per plan) in `src/core/answering/conversations/records.py`
- [X] T003 [P] Store protocol + `MemoryConversationStore` (hermetic twin) in `src/core/answering/conversations/store.py` — create-with-first-exchange atomic, append assigns dense `seq`, list newest-first, owner+tenant filters on every method
- [X] T004 `PostgresConversationStore` in `src/core/answering/conversations/postgres.py` mirroring `src/core/threads/postgres.py` discipline (connection, `_run`, migrate-on-start), against the real Postgres in its rows
- [X] T005 [P] `build_context()` + descriptor in `src/core/answering/context.py` — 6 exchanges / 6,000 chars, whole exchanges oldest-dropped, question+claim-statements for answered, question-only for declined/refused, citations structurally stripped (contracts/carried-context.md)
- [X] T006 [P] `route_with_signal(question) -> (Route, bool)` in `src/core/answering/routing.py`; `route()` behaviour byte-identical, existing rows untouched
- [X] T007 Component rows for T002–T005 in `tests/component/test_ask_conversations_store.py` and `tests/component/test_carried_context.py` — including [GATE:no-secret-leak] a row asserting the store's written content is exactly the response body handed to it and nothing credential-shaped, and the concurrency row: two appends racing into the same conversation through the Postgres store both land, with distinct consecutive seqs and neither exchange lost (the same-conversation-open-twice edge case)
- [X] T008 Component rows for T006 in `tests/component/test_ask_routing.py` — signal detection across the existing vocabulary, floor-without-signal distinguished from guidance-by-signal

**Checkpoint**: store, context and signal exist and are green in `make check` before any surface changes.

## Phase 3: User Story 1 — the answer stays, and the next question builds on it (P1) 🎯 MVP

**Goal**: transcript + composer on `/ask`; follow-ups answered with carried context; explicit
signal wins, silence inherits.

**Independent test**: quickstart steps 1–3 and 5 — ask, follow-up meaningless alone answered
on-subject, signalled estate question still reaches the estate; page never navigates.

- [X] T009 [US1] Amend the shared ask path in `src/surfaces/api/ask.py`: optional `conversation_id` in, create-on-absent / append-on-present, `conversation_id` + `exchange_seq` + optional `context_note` out; context built and threaded; store append only on answered/declined/refused (never on provider fault)
- [X] T010 [US1] Inheritance rule in the same shared path: `route_with_signal`, inherit most-recent exchange's `source` only when no signal; `inherited_route` recorded into the descriptor
- [X] T011 [US1] History block in the provider prompt: `LiveAnswerProvider` (and estate twin) accept optional context; `_INSTRUCTION` gains the history-is-not-citable clause (contracts/carried-context.md wording)
- [X] T012 [US1] MCP `ask` tool gains the same optional argument through the shared path in `src/surfaces/mcp/` (parity by construction, not re-implementation)
- [X] T013 [US1] [GATE:fail-closed] Unknown / foreign / cross-tenant `conversation_id` answers `404 no_such_conversation` before routing, context, or any model call — identical wording both transports; rows in `tests/conformance/answering/test_ask_conversations.py`
- [X] T014 [US1] Hermetic conformance rows for SC-010/SC-010a in `tests/conformance/answering/test_ask_conversations.py` (same file as T013/T015 — sequential): signalled question routes identically standalone vs in-conversation; signal-less follow-up inherits, both directions (docs→docs, estate→estate)
- [X] T015 [US1] Context rows in `tests/conformance/answering/test_ask_conversations.py` (same file as T013/T014, so deliberately not parallel): decline carried as question-only (FR-014a), bound trips at 7th exchange with `context_note` present (SC-012), first-ask-carries-nothing — and the SC-011 row: a scripted provider that cites something said in history has that claim dropped, because history is structurally uncitable
- [X] T016 [US1] Portal transcript: `_exchange.html` (question + included `_outcome.html`), `ask.html` reworked to transcript + sticky composer, `app.py` ask routes carry conversation state; fragment envelope becomes `X-Portal-Fragment: exchange`; `_outcome.html` renders `context_note` conditionally (present only when exchanges were dropped — the window-note reasoning: an unconditional caveat gets skipped)
- [X] T017 [US1] `portal-ask.js`: append the returned exchange fragment instead of replacing the outcome region; focus to the new answer's heading; stays ≤ 90 lines and remains the only markup-inserting script (trim, never raise the budget)
- [X] T018 [US1] Component rows in `tests/component/test_ask_answers_in_place.py` (amended): fragment carries one exchange, full page carries the transcript, fragment is literally contained in the full page, no-JS POST still renders everything
- [X] T019 [P] [US1] a11y rows: populated transcript, exchange in flight, declined and refused exchanges in transcript, focus lands on the newest answer — extend `tests/a11y/test_wcag.py` and its `_ask` helper

**Checkpoint**: quickstart steps 1–3 pass through the served portal.

## Phase 4: User Story 2 — conversations survive leaving the page (P2)

**Goal**: list, reopen, delete — on both transports and in the portal rail.

**Independent test**: quickstart steps 4 and 6 — reload lists the conversation, reopen shows
every exchange in order, delete removes it via confirmation.

- [X] T020 [US2] `src/surfaces/api/ask_conversations.py`: `GET /ask-conversations`, `GET /ask-conversations/{id}`, `DELETE /ask-conversations/{id}` per contracts/ask-conversations-api.md, wired in the API assembly
- [X] T021 [US2] [GATE:fail-closed] An unreadable store answers 503 on list — never an empty list; same 404 discipline on get/delete; rows beside T013's
- [X] T022 [US2] MCP tools `ask_conversations`, `ask_conversation`, `delete_ask_conversation` through the same shared functions
- [X] T023 [US2] `operations.snapshot.json` in `specs/008-northbound-api/contracts/` gains the three operations; `/ask` entry reflects its amendment
- [X] T024 [US2] [GATE:conformance] Parity rows in `tests/conformance/mcp/test_ask_parity.py`: list/get/delete/ask-in-conversation produce the same outcome, disposition and wording on both transports (SC-013)
- [X] T025 [US2] [GATE:conformance] The portal containment session in `tests/conformance/portal/test_containment.py` grows to: list (empty), ask (new), ask (follow-up), list (populated), get, delete-confirm, delete — uncatalogued requests still zero
- [X] T026 [US2] [GATE:conformance] Cross-owner and cross-tenant rows: a second subject and a second tenant get the identical 404 on get and delete, and their lists never contain the other's conversation (SC-004)
- [X] T027 [US2] Portal rail + list + delete confirmation: conversation `nav` with `aria-current`, a **New conversation** control that opens the empty composer without disturbing existing conversations (FR-010), `ask.html` rail (collapsing under 720px), `ask_delete_confirm.html` mirroring the thread pattern without sharing its template; a11y rows for list, empty state, delete confirmation

**Checkpoint**: full quickstart walk-through passes; both transports verified.

## Phase 5: User Story 3 — the platform can still be asked what it was shown (P2)

**Goal**: the record identifies the conversation and exactly what was carried.

**Independent test**: quickstart's psql check — descriptor present, three states
distinguishable, trail unchanged by delete.

- [X] T028 [US3] [GATE:correlation] `record_ask` in `src/core/answering/record.py` gains `conversation_id` and `carried_context`; both threaded from the shared ask path; `AuditEntry` schema untouched
- [X] T029 [US3] [GATE:correlation] Rows asserting the three states (key absent / `exchanges: []` / seqs listed), `dropped` count, and `inherited_route` — in `tests/conformance/answering/test_ask_conversations.py` (FR-020–022, SC-005)
- [X] T030 [US3] [GATE:correlation] Delete-vs-trail row: capture every `ask_answered` entry, delete the conversation, assert the entries byte-identical (FR-023, SC-006)

## Phase 6: User Story 4 — the chat surface looks like the rest of the platform (P3)

**Goal**: transcript, composer and rail styled entirely from existing tokens.

**Independent test**: identity rows green; both themes rendered and screenshotted.

- [X] T031 [US4] Transcript/composer/rail styles in `src/surfaces/portal/static/portal.css` from existing tokens only — exchange blocks, sticky composer with `scroll-padding-block-end`, rail typography; mono role for seq/timestamps/hashes
- [X] T032 [P] [US4] Extend `tests/component/test_portal_identity.py`: no colour outside token blocks still holds over the new CSS; transcript verdicts survive greyscale; no new template fetches third-party
- [X] T033 [P] [US4] Render both themes at desktop and 320px, screenshot, and fix what looks wrong before review — the 034 lesson: look at it, don't reason about it

## Phase 7: Polish & Cross-Cutting

- [X] T034 a11y sticky-composer rows: focused element never obscured by the composer with a long transcript; 320px reflow with 10+ exchanges; text-spacing override does not clip the composer (the named 028/034 traps)
- [X] T035 [P] `docs/` note or template comments carrying the two load-bearing decisions where future readers live: history-not-citable in the provider module, mirror-not-share at the store
- [X] T036 Full local gates: `make check`, `make conformance-hermetic`, `make a11y` all green
- [X] T037 Served verification per quickstart through `DEV_IDP=1 bash infra/bin/portal-up`: the six-step walk-through, zero navigations after sign-in, fresh allocation confirmed by identity age (not by grepping the mount)
- [X] T038 [GATE:eval] SC-002 + SC-011a live check: ten signal-less follow-ups across corpus families at the provider seam, of which at least three follow a DECLINED exchange, plus two through the served portal; pass ≥ 9/10 answered on-subject AND the after-decline subset answers at a rate no worse than the after-answer subset; both splits recorded in the PR body — run by Dan McTeer before promotion, never in CI
- [ ] T039 MCP served-surface spot check via `infra/bin/mcp-surface-up`: one conversation held over the MCP transport end to end
- [X] T040 Update `specs/008-northbound-api/contracts/` conformance contract notes naming the SC-002 runner (constitution v1.1.0 blocking-row ownership)

## Dependencies

```text
Phase 1 → Phase 2 → US1 (T009–T019)
                  ↘ US2 (T020–T027)   [independent of US1 except T009's /ask amendment
                                        for ask-in-conversation containment coverage]
US1 → US3 (T028–T030 read what US1 threads through)
US1 → US4 (T031–T033 style what US1 renders)
All stories → Phase 7
```

US2 can start once Phase 2 lands (list/get/delete touch only the store); its T025 containment
step needs T009. US3 is small and lands fastest after US1.

## Parallel Opportunities

- Phase 2: T002, T003, T005, T006 in parallel (distinct files); T004 after T003; T007/T008 after their subjects
- US1: T019 parallel with T013–T015 (different files); T013→T014→T015 sequential in their shared file once T009–T011 land
- US2: T020/T022 parallel; T024–T026 parallel after both
- US4: T032, T033 parallel

## Implementation Strategy

**MVP is US1 alone**: after Phase 2 + US1 the served portal holds a conversation with context —
demonstrable end to end even though nothing is listed or deletable yet. Then US2 (surfaces),
US3 (record — small, high evidence value), US4 (identity), Polish. One implementation PR per
the repo's practice, after the planning PR (spec + plan + tasks) merges.
