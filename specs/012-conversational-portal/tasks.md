# Tasks: The Conversational Portal

**Input**: Design documents from `/specs/012-conversational-portal/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. Every prior feature in this repository is test-first about its
guarantees, and this one adds two gate classes (containment, accessibility) whose entire
value is that they run.

**Organization**: Setup → Foundational (the substrate every story needs) → US1–US5 in
priority order → Polish & gates. Gate tasks are tagged and live in the phase that
delivers the behavior they guard.

## Gate Task Types

| Gate type | Where it appears here |
| --- | --- |
| **Fail-closed** | Turn decision (decline/refuse start no run); SSE stream death on 403; portal auth |
| **Conformance** | Snapshot-first parity ×5; verdict parity; containment rows; a11y lane |
| **Correlation / evidence** | Evidence-first turns; trail reconstruction; deletion events |
| **Eval** | None — deliberately: no pack, prompt, model, or policy ships here (contract records the scoped absence) |
| **No-secret-leak** | Token relay (token never logged/rendered); session cookie carries only an opaque id |

## Path Conventions

Single project: `src/`, `tests/` at repository root, per plan.md.

---

## Phase 1: Setup

**Purpose**: dependencies, fixtures, and the one growth every later phase leans on.

- [X] T001 Add `portal` extra (`jinja2`) and `a11y` dev extra (`playwright`) to `pyproject.toml`, with the comment discipline the existing extras use — say why each is an extra and not a base dependency
- [X] T002 [P] Vendor pinned `axe.min.js` into `tests/a11y/vendor/` with version and license noted in `tests/a11y/vendor/README.md` (MPL-2.0; unmodified single file)
- [X] T003 Grow `tests/harness/fake_oidc_provider.py` with an authorization-code + PKCE flow: `/authorize` (code issuance bound to `code_challenge`) and `/token` (code + `code_verifier` exchange, S256 only, single-use codes). It must also mint what must be **refused**: wrong verifier, replayed code, expired code — a flow is judged by what it rejects
- [X] T004 [P] Unit rows for the PKCE flow in `tests/unit/test_fake_oidc_pkce.py`: happy path verifies; wrong verifier, replayed code, and `plain` method are refused

**Checkpoint**: `make check` green with the new extras resolving.

---

## Phase 2: Foundational (blocking all user stories)

**Purpose**: threads as records, turns as evidence, input as durable state, five
operations on both transports, and a portal skeleton that authenticates. No story is
demonstrable until this phase completes.

### The records and the sealed-core change

- [X] T005 Add `TURN_RECORDED`, `TURN_REFUSED`, and `THREAD_DELETED` to `AuditEventType` in `src/core/audit/schema.py` with docstrings carrying the D4 reasoning (a declined ask is an ask; the trail is the record). This is the feature's one sealed-core change — note the spec approval + reviewer in the commit
- [X] T006 Create `src/core/threads/__init__.py` with the package intent docstring: threads are a view, the trail is the record, nothing here is on the resume path
- [X] T007 [P] Create `src/core/threads/records.py`: `ThreadRecord`, `TurnRecord`, `TurnDisposition` (`dispatched`/`declined`/`refused`), `RunInput`, and the stated bounds `MAX_MESSAGE_BYTES = 8192`, `CONTEXT_TURNS = 5` (FR-009a — named constants, not emergent limits)
- [X] T008 [P] Create `src/core/threads/schema.sql`: `threads`; `thread_turns` **carrying denormalized `tenant_id` + `subject_user_id`** (the rate window is per-person across threads — a per-thread join answers the wrong question) with the `(tenant_id, subject_user_id, created_at)` index **on both `threads` and `thread_turns`** (the rate window sums two counts, one per table); `run_inputs` — idempotent, every statement `IF NOT EXISTS`
- [X] T009 Create `src/core/threads/store.py`: `ThreadStore` protocol + `InMemoryThreadStore` — create/get/list (keyset, no totals)/delete for threads; append/list for turns with `seq` assignment; put/get for run inputs; tenant collapse in `get` exactly as `RunIndex.get` does it
- [X] T010 Create `src/core/threads/postgres.py`: `PostgresThreadStore` under the workload credentials, `seq` assigned under `SELECT ... FOR UPDATE` on the thread row (two tabs cannot interleave into ambiguity), `migrate()` applying schema.sql, hard delete cascading turns, `run_inputs` insert-only `ON CONFLICT DO NOTHING`
- [X] T011 [P] Component rows in `tests/component/test_thread_store.py`: both stores — create/list/get/delete parity of semantics, tenant collapse, seq density under concurrent appends (in-memory), keyset paging without totals

### The turn decision

- [X] T012 Create `src/core/threads/turns.py`: `accept_turn()` implementing the contract's ordered semantics — the contract's ordered semantics with the pre-acceptance split: resolve thread → pre-acceptance checks (rate window 30/5min as the **sum of two counts — recent turns plus recent creations** — because creations write no turn row and a window counting only `thread_turns` reads zero while a subject creates ten thousand empty threads; message size) refusing with a fixed-size `TURN_REFUSED` event that never carries the message → compute context (5 most recent dispatched-with-results, record drops) → **write `TURN_RECORDED` first** for every accepted turn → decide (decline `nothing_to_dispatch` / refuse `not_permitted` via 011's `may_start` intersection / write `run_inputs` and dispatch through the same core path `start_run` uses) → append turn row. The dispatcher parameter is typed by a minimal **local Protocol in this module** — core imports surfaces nowhere in the tree, and this module does not get to be first. Reasons extend 011's frozen `OPERATION_REASONS` mapping with `rate_limited` and `message_too_large` (a message over `MAX_MESSAGE_BYTES` is refused whole, never truncated — a truncated consent record consents to something the person did not say)
- [X] T013 [GATE:correlation] Component rows in `tests/component/test_turn_evidence_first.py`: every **accepted** disposition — dispatched, declined, scope-refused — has a `TURN_RECORDED` event written **before** any dispatch or row append, carrying the message verbatim; every **pre-acceptance** refusal — rate-limited, message-too-large — has a `TURN_REFUSED` event that records the size and never the message (the trail must not be growable at HTTP rate by being refused). Break the decline branch's event write and watch the row fail, then restore
- [X] T014 [GATE:fail-closed] Component rows in `tests/component/test_turn_decision.py`: no agent selected → declined, no run; not-startable agent → refused `not_permitted`, no run; over rate window → refused `rate_limited`, no run; a store error during acceptance refuses rather than dispatching; an assembly with no audit sink refuses every turn with a typed refusal, not a 500 (FR-017a — the fail-closed direction is "no run", never "run anyway", and evidence-first means no sink = no turn)

### Run input reaches the run

- [X] T015 Create `src/core/threads/context.py::resolve_run_input(run_id, thread_store, durability)` — the **one** function that turns an input record into (message, verbatim results), returning the stored serialization of each result so comparison is defined on bytes rather than on parsed objects. Then extend `src/surfaces/dispatch/entrypoint.py` to call it under workload credentials at run start and include message + `received_context` in what the scripted run records. Absent input row = a run started outside a thread — proceed exactly as today. (The in-process dispatcher runs work via `start_governed_run`, which has no input parameter and **deliberately does not grow one** — that would be a second, unapproved sealed-core change; hermetic rows prove the resolution function, the enclave row proves the allocation path)
- [X] T016 [P] Component row in `tests/component/test_run_receives_input.py`: `resolve_run_input` against **both** stores returns each context result byte-identical to the stored serialization of the recorded original (SC-002 operationalized: compare the stored bytes, not parsed objects — a comparison on parsed objects would pass a reserialization that changed key order today and content tomorrow); a truncated-by-one-byte fixture fails; absent input resolves to none without error

### Five operations, both transports, snapshot-first

- [X] T017 [GATE:conformance] Grow `specs/008-northbound-api/contracts/operations.snapshot.json` with `POST /threads` (`create_thread`); watch parity fail; implement `src/surfaces/api/threads.py::create_thread` + MCP tool in `src/surfaces/mcp/operations.py` — creation counts against the same per-subject rate window as turns (refused `rate_limited` beyond it), and sets `title` **once** from nothing (untitled until the first accepted turn's leading fragment; no rename operation exists); watch parity pass. Repeat this loop — one operation per commit — for `send_turn` (T018), `list_threads` (T019), `get_thread` (T020), `delete_thread` (T021)
- [X] T018 [GATE:conformance] `POST /threads/{thread_id}/turns` / `send_turn` in `src/surfaces/api/threads.py` + `src/surfaces/mcp/operations.py` (snapshot grown first), delegating to `accept_turn()` — the surface owns transport shape only; the decision lives in core, which is what makes verdict parity structural
- [X] T019 [GATE:conformance] `GET /threads` / `list_threads` in `src/surfaces/api/threads.py` + `src/surfaces/mcp/operations.py` (snapshot grown first) — keyset cursor, no totals, 011's listing discipline verbatim
- [X] T020 [GATE:conformance] `GET /threads/{thread_id}` / `get_thread` in `src/surfaces/api/threads.py` + `src/surfaces/mcp/operations.py` (snapshot grown first) — turns in seq order, run state joined from the durable record at read time, never stored on the turn
- [X] T021 [GATE:conformance] `DELETE /threads/{thread_id}` / `delete_thread` in `src/surfaces/api/threads.py` + `src/surfaces/mcp/operations.py` (snapshot grown first) — `THREAD_DELETED` event first, then hard delete; runs and `run_inputs` untouched
- [X] T022 Wire the thread store into both assemblies — with the posture stated, because the tree holds two patterns and the snapshot depends on which one this takes: `src/surfaces/api/app.py` registers the thread router **unconditionally** with in-memory defaults for `thread_store` (011's `run_index` pattern, NOT the conditional `definitions` pattern — a conditionally-registered router makes the snapshot-at-15 claim assembly-dependent, which is where 011's snapshot defect lived). `accept_turn` REFUSES with a typed refusal when the audit sink or fabric is absent — evidence-first means no-sink = no-turn, a refusal rather than `_component`'s 500, because an outage-shaped answer to a misassembly sends the investigator to the wrong failure. Mirror in `src/surfaces/mcp/transport.py`, and extend `tests/harness/api_fixtures.py` `surface_under_test()` with the thread collaborators (in-memory sink included) **in this same task** — nearly every hermetic row runs through it
- [X] T023 [P] [GATE:conformance] Verdict parity rows in `tests/conformance/mcp/test_surface_parity.py`: same inputs → same disposition on both transports for dispatch, decline, refusal, and rate limit — a surface that declines on one transport and dispatches on the other is two authorization paths wearing one name

### The portal skeleton

- [ ] T024 Create `src/surfaces/portal/oidc.py`: authorization-code + PKCE public client (S256, no client secret anywhere), state + verifier held server-side pending the callback
- [ ] T025 Create `src/surfaces/portal/session.py`: in-memory store, opaque id → (subject, token, expiry); cookie `HttpOnly; Secure; SameSite=Lax`; sessions die with process or token expiry. **Deliberately not Postgres** — FR-020b's reasoning in the docstring, plus one sentence noting `Secure` works on dev loopback because browsers treat localhost as a trustworthy origin (known, not lucky)
- [ ] T026 Create `src/surfaces/portal/relay.py`: the **only** portal module with an HTTP client (urllib, matching the enclave readers); attaches the session's token; surfaces API refusals as typed results, never retries mutations
- [ ] T027 Create `src/surfaces/portal/app.py` + `templates/base.html` + `static/portal.css` + `static/portal.js`: login flow, authenticated shell, session middleware. `portal.js` stays small, readable, and fetches nothing beyond the portal origin — it will be read by a conformance row, write it knowing that
- [ ] T028 [P] [GATE:no-secret-leak] Component rows in `tests/component/test_portal_session.py`: cookie contains only an opaque id (entropy-checked, no token substring); token never appears in logs, rendered HTML, or error pages; expired session → clean re-auth redirect, not an error; callback with wrong `state` refused

### The enclave grows two jobs

- [ ] T029 Create `infra/jobs/api.nomad.hcl` serving `create_app` via uvicorn with real collaborators (Postgres stores via workload identity, Nomad dispatcher, JWKS verifier against the configured issuer) — 009's mcp.nomad.hcl pattern: read-only mount, copy, no token anywhere. **The API's first deployment (research F2)**
- [ ] T030 Create `infra/jobs/portal.nomad.hcl` serving the portal pointed at the API address and IdP; production TLS posture recorded as a jobspec comment, not solved here
- [ ] T030a Serve the fake OIDC provider as a **dev-only** process in the enclave bring-up (`infra/bin/` dev-up path or a `dev-idp` job): `/.well-known` + JWKS reachable by the API service, `/authorize` + `/token` reachable by a browser. Loudly marked dev-only in the jobspec/script comments — it is the deliberate double for the one thing outside the boundary (the customer's IdP), now needing a listener because quickstart §4 logs in through a browser and `api.nomad.hcl` verifies against a real JWKS URI. Without this task, T029/T030 configure an issuer that does not exist
- [ ] T031 Apply `core/threads/schema.sql` at bring-up wherever 011's schema is applied (`infra/bin/` bring-up path), idempotently

### The record

- [ ] T032 [P] Draft `docs/adr/0051-a-turn-is-evidence-a-thread-is-a-view.md`: every **accepted** message is trail evidence before anything else happens, including declines and scope refusals; pre-acceptance refusals get `TURN_REFUSED` (size, never content); threads are hard-deletable views; deletion is an event. **The ADR MUST own the redaction divergence** (analyze pass 3, S1): the trail's only other free-content writer is `redact_arguments`, whose posture is keys-and-hashes-never-raw-values — this ADR stores a person's text verbatim, forever, and the message also becomes run input. State why messages differ from tool arguments (a message IS the consent record; an argument merely parameterizes one), the mitigations (composer notice, 8 KiB bound, `TURN_REFUSED` carries no content), and the residual risk accepted: a pasted secret is permanent. Status: Accepted; security-maintainer sign-off (Dan) covers exactly this acceptance

**Checkpoint**: `make check` green; catalogue at fifteen on both transports; parity green; portal authenticates against the fake IdP.

---

## Phase 3: User Story 1 — Start a run from a conversation, and watch it finish (P1) 🎯 MVP

**Goal**: a person starts an agent from a thread and watches it reach a result — no
identifier visible, nothing reached except through the API.

**Independent test**: scripted portal session starts a run and sees its result with no
run id in any rendered page; every request in the relay log is a catalogued operation.

- [ ] T033 [US1] Thread page + composer in `src/surfaces/portal/templates/thread.html`: definitions rendered from `list_agent_definitions` with startable/non-startable flagged (011's disclosure, rendered not re-decided); message box; the recorded-as-evidence notice (D4's honesty requirement)
- [ ] T034 [US1] Turn submission handler in `src/surfaces/portal/app.py`: POST → relay `send_turn` → render disposition; the three run dispositions rendered distinguishably (not finished / result / ended-without, with stop reason) in `templates/thread.html`
- [ ] T035 [US1] Create `src/surfaces/portal/events.py` + SSE wiring in `portal.js`: server-side bounded polling (2s) of `get_run`/`get_run_result` with the person's token; stream ends on 403 (fail-closed) and on terminal state; per-subject concurrent-stream cap
- [ ] T036 [P] [US1] Component rows in `tests/component/test_portal_start_and_watch.py`: scripted session (fake IdP, in-memory assembly) — start → disposition renders; no run id string appears in any rendered page (SC-001); the SSE source emits state transitions and closes on terminal
- [ ] T037 [US1] [GATE:correlation] Component row in `tests/component/test_portal_run_attribution.py`: a run started from the portal carries the person as subject and is indistinguishable in the trail from the same run started directly through the API — same events, same subject, same authorization path (SC-007)
- [ ] T038 [US1] [GATE:conformance] Enclave row in `tests/conformance/api/test_thread_dispatch_enclave.py` (`host_enclave`): a turn accepted through the served API dispatches a real allocation whose entrypoint reads its `run_inputs` row; the run completes and its result is reachable through `get_run_result`

**Checkpoint**: US1 demonstrable end-to-end against the enclave.

---

## Phase 4: User Story 2 — A second turn that knows about the first (P1)

**Goal**: follow-ups carry prior results verbatim, bounded, with drops visible; authority
never carries forward.

**Independent test**: two-turn thread — the second run receives the first's result
byte-identical; a six-result thread shows exactly which result fell out of the bound.

- [ ] T039 [P] [US2] Component rows in `tests/component/test_thread_context.py`: second turn's `context_run_ids` names the first turn's run; the run receives the recorded bytes (SC-002); with six dispatched-with-result turns, the oldest is in `context_dropped` and the newest five carry (SC-002a); declined/refused turns never enter context
- [ ] T040 [US2] Render context visibility in `templates/thread.html`: what this turn carried forward, and what fell out of the bound (FR-009b — a person who does not know the platform forgot something reads a worse answer as a worse platform)
- [ ] T041 [US2] [GATE:fail-closed] Component row in `tests/component/test_turn_authority_fresh.py`: narrow the subject's roles between turn one and turn two — turn two is authorized against the narrowed roles and refused where they no longer suffice; nothing consults turn one's authority (FR-008, US2 scenario 3)
- [ ] T042 [US2] [GATE:no-secret-leak] Component row in `tests/component/test_context_carries_results_not_authority.py`: context resolution reads results only — no grant id, no token, no credential material appears in what a later run receives (ADR-0042's cached-results rule)

**Checkpoint**: US1+US2 together are the MVP — a portal that converses.

---

## Phase 5: User Story 3 — The thread survives, and is accountable (P2)

**Goal**: threads survive restarts; the trail reconstructs everything; deletion masks
nothing.

**Independent test**: restart the serving processes mid-thread and find it intact; delete
it and reconstruct the whole exchange from the trail alone.

- [ ] T043 [US3] Thread list page in `src/surfaces/portal/templates/threads.html` + handler: `list_threads` rendered newest-first, keyset "more" link, empty state that is honest about being empty rather than looking broken
- [ ] T044 [P] [US3] Component rows in `tests/component/test_thread_survival.py`: threads and turns read back identically from a fresh `PostgresThreadStore` instance (process death simulated by constructing anew); in-flight run state unchanged (marked `enclave` where the real store is needed)
- [ ] T045 [US3] [GATE:correlation] Component row in `tests/component/test_thread_reconstruction.py`: a thread with dispatched, declined, and refused turns is reconstructed **completely** from the trail alone — subject, order, messages, dispositions, resulting runs (SC-004); then delete the thread and assert the reconstruction is unchanged and the deletion appears (SC-009a)
- [ ] T046 [P] [US3] Component rows in `tests/component/test_thread_tenant_boundary.py`: another tenant's thread answers not-found identically to an absent one across get/turns/delete (SC-009); same-tenant other-subject answers `not_permitted` on send, not-found on get (the spec's refusal table)
- [ ] T047 [US3] Deletion flow in portal (`templates/` confirm + handler) and the abandoned-run row in `tests/component/test_thread_deletion.py`: delete with a run in flight — run completes, result reachable via `get_run_result`, `run_inputs` intact (FR-010d); deleted thread's turns gone from the store, present in the trail
- [ ] T048 [US3] [GATE:conformance] Enclave row in `tests/conformance/api/test_thread_survives_restart.py` (`host_enclave`): create thread + dispatch through the served API, restart the API allocation via Nomad, list again — thread intact, run state correct (US3 scenario 1 against the real substrate)

**Checkpoint**: ADR-0034's "threads are run state" claim is now tested, not asserted.

---

## Phase 6: User Story 4 — Stopping, and the pause that must not appear (P2)

**Goal**: stop from the conversation with the API's exact withdrawal semantics; no
mechanism for mid-run solicitation exists.

**Independent test**: stop a running turn from the portal — current step completes,
nothing further, terminal; grep the tree for any input-wait path and find none.

- [ ] T049 [US4] Stop control in `templates/thread.html` + handler relaying the existing `stop_run` operation (no thread-local stop — the contract's "two paths to one action" rule)
- [ ] T050 [P] [US4] Component rows in `tests/component/test_portal_stop.py`: stop from the portal produces the identical terminal state, stop reason, and trail events as `POST /runs/{run_id}/stop` (FR-013); a subsequent turn in the same thread is a fresh run, not a resumption (US4 scenario 3); the stopped run's result disposition renders as "ended without a result" with the reason
- [ ] T051 [US4] [GATE:fail-closed] Structural row in `tests/component/test_no_solicitation_path.py`: assert no operation on either transport, no portal route, and no entrypoint code path exists by which a run waits for portal input mid-flight — the mechanism's absence is the guarantee (FR-014, SC-008), asserted the way `test_no_live_dependencies` asserts absence

**Checkpoint**: ADR-0049 holds on the surface most likely to erode it.

---

## Phase 7: User Story 5 — The surface declines what it is not for (P3)

**Goal**: declines and refusals are distinct, graceful, and start nothing.

**Independent test**: submit with no agent selected → decline naming what the portal is
for; submit with a non-startable agent → scope refusal; neither starts a run.

- [ ] T052 [P] [US5] Decline and refusal rendering in `templates/thread.html`: `nothing_to_dispatch` says what the portal is for without appearing broken; `not_permitted` says this person may not — visually and textually distinct (FR-017); `rate_limited` renders as a boundary with the window, not an error
- [ ] T053 [US5] Component rows in `tests/component/test_portal_declines.py`: each decline/refusal renders its distinct shape; zero runs started across all of them (FR-017a); the API-unreachable state says so rather than rendering an empty platform (edge case)
- [ ] T054 [US5] [GATE:correlation] Component row extension in `tests/component/test_turn_evidence_first.py`: the declined turn's `TURN_RECORDED` event survives thread deletion as the only copy of that message — delete the thread, reconstruct the decline from the trail (D4's point, proven)

**Checkpoint**: all five stories demonstrable.

---

## Phase 8: Polish, containment, and the gates

- [ ] T055 [GATE:conformance] Create `tests/conformance/portal/` with the containment rows from `contracts/conformance-portal.md`: one-egress-module (the `test_no_live_dependencies` pattern over `surfaces/portal`); request-log-maps-1:1-onto-snapshot under a scripted full session; token relay with no portal credential; SSE-dies-on-403; served-JS reads clean (no external fetch, no model endpoint, no localStorage); nothing-survives-the-session. **Wire the directory into the Makefile conformance recipe in the same commit** — 010's invisible-directory lesson
- [ ] T056 [GATE:conformance] Build the a11y lane: `tests/a11y/test_wcag.py` driving Playwright over every page state (thread list empty/populated, thread with all three dispositions, decline, refusal, delete confirm, API-unreachable) with vendored axe, WCAG 2.2 AA, failing on any violation; `make a11y` target; dedicated CI job in `.github/workflows/` (no enclave needed). The run's output names the criteria it cannot assert, pointing at the contract's manual checklist
- [ ] T057 [P] Break fixtures from `contracts/conformance-portal.md`, each applied to the tree, watched to fail, reverted: dispatch-before-record (decline branch), one-byte-truncated context, relay-bypassing fetch, token-in-cookie. A row nobody has seen fail is a row nobody knows works
- [ ] T058 [P] Update `ROADMAP.md`: 012 shipped — catalogue at fifteen, portal live as a contained consumer, the answering classes' entry named as following capability packs; record F2's lesson (operation rows passed for a year against an unserved surface)
- [ ] T059 [P] Record rows **In force** in `specs/012-conversational-portal/contracts/conformance-portal.md`, including the manual-checklist run (named runner: Dan) with date; note in `specs/008-northbound-api/contracts/conformance-api.md` that the snapshot grew 10 → 15
- [ ] T060 [GATE:conformance] Run `make check`, `make conformance`, and `make a11y` against a live enclave on a clean tree; walk quickstart.md sections 4–6 in a real browser; run the manual accessibility checklist and record it

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─→ Phase 2 Foundational ─→ Phase 3 US1 (MVP start)
                                          ─→ Phase 4 US2 (needs US1's dispatch path)
                                          ─→ Phase 5 US3 (needs threads + portal pages; independent of US2)
                                          ─→ Phase 6 US4 (needs US1's watch path)
                                          ─→ Phase 7 US5 (needs turn decision rendering)
                                                     ─→ Phase 8 Polish & gates (needs all)
```

- **US2 depends on US1** (a follow-up needs a first run). US3, US4, US5 each depend only
  on Foundational + US1's page skeleton; they are independent of each other.
- Within phases: [P] tasks touch different files and may run together; snapshot-first
  tasks T017–T021 are strictly sequential (each is a red→green loop on the same snapshot).

## Parallel opportunities

- T002 ∥ T003 ∥ T004 (setup); T007 ∥ T008 (records/schema); T011 ∥ T013 ∥ T014 after
  T009/T012; T028 ∥ T029–T031 (portal rows vs jobspecs); T032 anytime after T005.
- After US1: US3, US4, US5 phases can proceed in parallel with US2.
- Polish: T057 ∥ T058 ∥ T059 after T055/T056.

## Implementation strategy

**MVP = Phase 3 (US1) + Phase 4 (US2)**: a portal that starts, watches, and follows up is
the smallest thing that is recognisably the feature. US3 makes the claim durable, US4
makes it safe, US5 makes it honest, Phase 8 makes all of it *proven* — containment and
accessibility are gates, not garnish, and the feature is not done until they run red on
their break fixtures and green on the tree.
