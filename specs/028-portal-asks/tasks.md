# Tasks: The portal learns to ask

**Input**: Design documents from `/specs/028-portal-asks/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the feature's central discipline (render, never classify) is exactly the
kind of property that erodes without a row pinning it.

**Organization**: by user story. The template and routes land once in US1; US2 and US3 are rows
over states US1's code already produces, which is why this feature is small and the ordering is
almost flat.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

*(none — no new dependency, no scaffolding; the portal package and every test home already
exist. A setup task here would be ceremony.)*

## Phase 2: Foundational — the relay learns per-operation patience

- [ ] T001 `ApiRelay.request` in `src/surfaces/portal/relay.py` gains
      `timeout: float | None = None` — `None` means the relay's own default, so every existing
      call site is untouched (SC-004's second half by construction). The docstring records
      research F2: per-operation patience is a parameter, not a second relay, because two relays
      would be two egress points for the containment rows to reason about, and raising the shared
      default would spend an ask's patience on a thread listing. **The injected-transport branch
      does NOT gain the parameter** — both existing harness transports
      (`tests/a11y/conftest.py`, the `_portal_over_api` pattern) share a keyword-only signature
      without it, and widening that signature would touch every fixture for a value they have no
      use for. Patience is therefore observed at the **relay seam** (T007), not the transport.

**Checkpoint**: the relay can wait differently per call and nothing that exists behaves
differently.

## Phase 3: User Story 1 — someone signs in and asks a question (P1) 🎯 MVP

**Goal**: a signed-in person asks from `/ask` and reads the answer, all four shapes rendered
faithfully.

**Independent test**: drive the portal over the real API fixture with a qualified authority and
an available credential; an ask returns an answered page whose citations are anchors.

- [ ] T002 [US1] The routes in `src/surfaces/portal/app.py`: `GET /ask` renders the form
      (session required — signed-out redirects to login, the pattern every page uses); 
      `POST /ask` strips the question, **re-renders the form with a message and zero relay calls
      when empty**, otherwise relays `POST /ask` with the session's own token and
      `ASK_PATIENCE = 180.0` (module constant beside the routes, with the measured ~2-minute
      answer and the 2026-08-02 demonstration as its rationale) and renders the outcome. Dispatch
      order is the data model's and is load-bearing: `reachable → status → disposition` —
      reachability is decided by the relay before any body exists, and a refusal has no
      disposition to read.
- [ ] T003 [US1] The template `src/surfaces/portal/templates/ask.html`: the form with FR-005a's
      expectation text as plain page content ("an answer usually takes a minute or two — leave
      this page open"; no spinner, no live region, no new JS — research F6); the **answered**
      block shaped per source (guidance: each citation an anchor to its URL; estate: each
      reference rendered inert — shortened prefix shown, full hash present, **zero anchors**);
      the **declined** block presented as an answer naming its `source`; the **refused** block
      rendering the API's `detail` **verbatim** with no portal-authored cause text (research F1 —
      this is the sentence the whole feature turns on); the **unaskable** block ("the platform
      could not be asked — nothing about your access has changed"), distinct from every refusal.
- [ ] T004 [P] [US1] The nav link in `src/surfaces/portal/templates/base.html`: "Ask" beside the
      existing brand/threads navigation, visible when signed in. Accessible name is the a11y
      row's to judge (T011).
- [ ] T005 [P] [US1] Component rows in `tests/component/test_portal_asks.py`, over the
      `_portal_over_api` pattern (`surface_under_test` + injected transport, the portal driving
      the **real** API fixture): an ask with `qualified_ask_authority()` and
      `available_credential()` returns 200 and the page carries each claim's statement with its
      citation as an anchor; an estate ask renders references with the full hash present and no
      anchor whose href contains it; a decline renders as an answer and names the door; a
      signed-out GET and POST both redirect with **zero transport calls**; an empty question
      re-renders with **zero transport calls**; the transported `Authorization` header carries
      the signed-in session's own token (FR-011's portal half).
- [ ] T006 [US1] The guidance-citation and estate-reference assertions are structural, not
      substring: parse the rendered page's anchors and assert the **set** of hrefs equals the
      citation URLs for guidance, and is **empty within the answer block** for estate — a page
      that wrapped a hash in a dead link would pass any substring check while teaching readers
      the references are decorative (FR-007's failure mode, pinned).
- [ ] T007 [US1] The patience rows, observed at the relay seam: a recording `ApiRelay` subclass
      captures `(path, timeout)` per call and delegates; driving an ask then a thread listing
      through the same portal asserts `/ask` carried `ASK_PATIENCE` and `/threads` carried
      `None` (the relay default). **Both halves asserted** — the second is what keeps SC-004 a
      design rather than a raised number, and it is the row that fails when somebody "simplifies"
      by widening the shared default.

**Checkpoint**: the MVP — a person can ask and read every shape, and nothing else got slower.

## Phase 4: User Story 2 — told what happened, not that something went wrong (P2)

**Goal**: the three refusal causes and an unreachable platform are four distinguishable pages.

**Independent test**: arrange each failure with an injected transport and read the pages; they
differ, and every refusal sentence is the API's own.

- [ ] T008 [US2] [GATE:conformance] The four-outcomes rows in
      `tests/component/test_portal_asks.py`: transports returning (a) 403 with the unbound
      detail prose, (b) 503 with the credential detail prose ("the platform holds no authority to
      call this vendor"), (c) 503 with a provider-fault detail, (d) status 0 — each renders a
      page containing **that response's own words** (or the unaskable text for status 0), and the
      four rendered pages are pairwise distinguishable. Uses the API's real detail strings as
      fixtures, imported as literals with a comment naming their source functions — so if the API
      rewords a refusal, the row still passes (the portal renders whatever arrives) and the
      fixture is merely stale, not wrong.
- [ ] T009 [US2] [GATE:conformance] **The no-classification row** — the contract's headline: the
      refusal page contains the transported `detail` string verbatim and does **not** contain
      `refused.html`'s generic arm ("The platform refused this request"), nor any portal-authored
      cause vocabulary (assert the absence of a small named list: "credential problem",
      "not qualified", "vendor error" — terms a friendly-mapping fix would reach for). This is
      the row that makes the tempting wrong fix fail a gate instead of drifting from the API's
      vocabulary the first time a reason code moves (research F1).

**Checkpoint**: refusals are the API's words, and the proof is a row rather than a review.

## Phase 5: User Story 3 — asking leaves the same trace as asking anywhere else (P3)

**Goal**: a portal ask is in the trail under the asker's identity; a refused one too.

**Independent test**: ask through the portal-over-API harness and read `surface.audit`.

- [ ] T010 [US3] [GATE:conformance] The trail rows in `tests/component/test_portal_asks.py`,
      end-to-end through the real API fixture: an answered portal ask leaves an `ask_answered`
      record whose `subject_user_id` is the **signed-in person's** subject (not "portal", not
      the relay's identity — the portal has none, which containment separately asserts); a
      **refused** portal ask (no credential arranged) leaves its record too, disposition
      `credential_unavailable`. These observe the API doing its job **through the portal's
      relay** — the portal half under test is that the person's token made the call; the API
      half is 027's rows, deliberately not re-asserted (contract: a second copy drifts).

**Checkpoint**: the portal is not a way to ask unobserved.

## Phase 6: Polish & cross-cutting

- [ ] T011 [P] Accessibility rows in `tests/a11y/test_wcag.py` (and
      `tests/a11y/test_keyboard_and_screenreader.py` for the keyboard row): the ask form with its expectation text, an answered page for **each** source, a
      declined page, and a refused page each pass WCAG 2.2 AA. The a11y `portal_server` fixture
      builds `surface_under_test()` bare — arrange the answered states by constructing the
      surface with `qualified_ask_authority()` and `available_credential()` (a fixture parameter
      or a second server fixture, whichever the conftest wears better; the transport signature
      does not change — T001's constraint).
- [ ] T012 [P] Containment green with the new route — and **the scripted session gains the
      ask** (analysis C1). `test_row_every_request_the_portal_makes_is_a_catalogued_operation`
      drives "every page and every action this portal offers" and checks the request log against
      the snapshot; a route the session never drives is a route the row never observes, so its
      strongest-form claim would silently exclude the newest page. Add a `portal.post("/ask",
      data={"question": ...})` to the session — coverage growth, not weakening; `POST /ask` is in
      the snapshot (verified), so the row passes by the same mechanism as every other action.
      Every OTHER containment row passes unmodified (egress allowlist, no credential, client
      size); one of those needing an edit is still a finding to surface. Then `make check` and
      the hermetic conformance sweep.
- [ ] T013 [P] Update this feature's `contracts/conformance.md` status rows as they land, and
      the ROADMAP entry for 028 (closing 024's named deferral; standing deferrals restated:
      corpus refresh, team granularity, per-tenant model scope, further cell promotion,
      submit-then-poll as the recorded next shape).
- [ ] T014 The demonstration (SC-001) — **named runner: Dan McTeer**, per quickstart §4:
      `portal-up`, sign in, Ask, read a cited answer with the page left open; read the trail and
      find your own `subject_user_id` on the record; ask an estate question and see identifiers,
      not links. Everything it needs has stood since 2026-08-02.

---

## Dependencies

```text
Phase 2 (T001, the relay parameter)
  → Phase 3 / US1 (T002 → T003 → T004∥T005 → T006, T007)
    → Phase 4 / US2 (T008 → T009)      [rows over states US1 renders]
    → Phase 5 / US3 (T010)             [rows over the same harness]
      → Phase 6 (T011 ∥ T012 ∥ T013 → T014 last)
```

US2 and US3 depend on US1's template and routes but not on each other.

## Parallel opportunities

- T004 ∥ T005 (different files); T006/T007 are rows in one file after T005 — sequential by
  shared file only.
- T011 ∥ T012 ∥ T013.

## Implementation strategy

**MVP = Phase 3.** One relay parameter, two routes, one template, and the rows that pin the four
shapes. US2 is the discipline (verbatim rendering, proven), US3 is the visibility, Polish is the
gates and the human demonstration. No sealed core, no API change, no new dependency — if any of
those stops being true mid-implementation, that is a finding to surface before proceeding
(FR-014, plan Constitution Check).

## Notes

- **Gate types**: conformance (T008, T009, T010); the containment and a11y lanes are existing
  gates the feature must pass rather than new ones it adds.
- **The one behavioural constant**: `ASK_PATIENCE = 180.0` — measured (~2-minute answer,
  2026-08-02), same allowance the MCP demonstration used, defined once beside the routes.
- **What would make this feature fail honestly**: the API rewording refusals into
  indistinguishable prose. That is the API's contract to keep (its own rows pin the reason
  vocabulary); the portal's no-classification row keeps the portal from papering over it.
