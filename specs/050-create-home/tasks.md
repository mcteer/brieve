# Tasks: Create home

**Input**: Design documents from `/specs/050-create-home/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — empty-home 303, slider isolation, combined history, unreadable-list
notices, bubble Stop, Nocturne token discipline, a11y lane, and 047 P8 are how the
spec's success criteria can lose.

**Organization**: Setup vendors the mark. Foundational is routing + `history_items`
(blocks every story). US1 is empty home + slider + Nocturne on the new chrome. US3
is the combined searchable list. US2 is Stop in the bubble. US4 is profile /
Settings / logout. US5 is the a11y gate. Polish is leftover rail, comments,
changelog, P8.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types

| Gate type | This feature |
| --- | --- |
| **Fail-closed** | Unreadable Ask or Build list is a notice, not an empty claim (T014). Failed Build stop does not look ended (T019). Ask abort does not claim the answer ended (T018) |
| **Conformance** | 047 P8 Ask isolation still green (T032) |
| **Correlation / evidence** | N/A — no new run path |
| **Eval** | N/A — no pack, prompt, model, or policy |
| **No-secret-leak** | N/A — no new credential or tool-result path |

---

## Phase 1: Setup

- [ ] T001 Vendor the official HashiCorp logomark into
      `src/surfaces/portal/static/mark/hashicorp-logomark.svg` and write
      `src/surfaces/portal/static/mark/PROVENANCE.md` per research F6 (source file from
      the official kit, retrieved date, sha256, trademark notice, maintainer
      permission). Use the official reverse/light mark if that is the kit file for
      dark grounds; otherwise the official mark unmodified. This is the feature's
      ONE network act if the kit is fetched. Do not redraw a path. Do not add the
      Claude screenshot to the tree.

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: One empty-home address and the merge helper every page will render.

- [ ] T002 Implement `history_items` in `src/surfaces/portal/app.py` per
      `specs/050-create-home/data-model.md`: merge existing `_conversations` and
      `_builds` into `kind`, `verb`, `title`, `href`, `sort_at` (Ask
      `last_asked_at`, Build `created_at`), newest first. Omit a kind when that
      list is unreadable. Do not add a catalogue field.

- [ ] T003 Set `DEFAULT_POST_LOGIN_PATH` to `"/"` in
      `src/surfaces/portal/oidc.py` and the `/login` default in
      `src/surfaces/portal/app.py`.

- [ ] T004 In `src/surfaces/portal/app.py`: `GET /ask` with no id returns 303
      `Location: /`. Ask delete and other empty-Ask 303s go to `/`, not `/ask`.
      `GET /ask/{conversation_id}` and `GET /propose/runs/{run_id}` stay.

- [ ] T005 Write failing rows in `tests/component/test_portal_session.py` and
      `tests/component/test_portal_shell.py`: login without `next` lands on `/`;
      `GET /ask` (signed-in) is 303 `/`. Must fail before T003/T004 land.

**Checkpoint**: routing and `history_items` exist; chrome has not changed yet.

---

## Phase 3: User Story 1 — Empty home is one place to create (P1) 🎯 MVP

**Goal**: Signed-in empty `/` is mark + “Let's Create” + rounded Ask/Build
composer (slider on Ask). Nocturne tokens paint the new chrome. Empty `/ask` is
gone.

**Independent Test**: Sign in with no item open. HashiCorp mark, Let's Create,
slider on Ask. Submit Ask → ask, never a Build. `GET /ask` 303s home.

### Tests

- [ ] T006 [US1] In `tests/component/test_portal_shell.py`: signed-in `GET /`
      contains Let's Create, `/static/mark/hashicorp-logomark.svg`, slider on
      Ask, composer `action="/ask"` (not `action="/"`). Must fail on today's
      empty Build page.

- [ ] T007 [P] [US1] In `tests/component/test_portal_asks.py`: Ask selected on
      empty home has no `action="/"` or `action="/propose"` (047 P8). Must fail
      if the slider default posts Build.

### Implementation

- [ ] T008 [US1] `GET /` in `src/surfaces/portal/app.py` renders
      `src/surfaces/portal/templates/ask.html` as create home (no conversation),
      passing `history_items`. Do not add `create.html`.

- [ ] T009 [US1] Empty-home chrome in `src/surfaces/portal/templates/ask.html`:
      HashiCorp `<img src="/static/mark/hashicorp-logomark.svg" alt="">` and
      Let's Create; greeting absent when a conversation is open. Open Ask shows
      the conversation `title` at the top of the stage.

- [ ] T010 [US1] Rounded composer + Ask/Build slider in
      `src/surfaces/portal/templates/_thread_composer.html`: default `action="/ask"`;
      slider operable only on empty home; + is `disabled` / not-available-yet
      (FR-006). Without JS the form posts `/ask`.

- [ ] T011 [US1] In `src/surfaces/portal/static/portal.css` paint column,
      greeting, bubble, and slider with **Nocturne tokens only** (research F10).
      Empty-home composer in the stage; open-item composer bottom centre. No
      page-local hex. No reference orange. No second copper identity.

**Checkpoint**: empty `/` is create home; Ask is the default verb.

---

## Phase 4: User Story 3 — One history, searchable (P1)

**Goal**: Left column lists this person's Ask conversations and Builds together.
Search filters visible text. + New is `/` with Ask. Projects is a placeholder.

**Independent Test**: One Ask and one Build both appear; search leaves only the
matching row; New returns home on Ask; Projects does not navigate.

### Tests

- [ ] T012 [US3] In `tests/component/test_portal_shell.py`: a fixture with one
      conversation and one authoring run renders both rows with visible words
      Ask and Build and the existing hrefs. Search script
      `src/surfaces/portal/static/portal-history.js` is referenced from the
      history include.

- [ ] T013 [GATE:fail-closed] [US3] In `tests/component/test_portal_shell.py`:
      unreachable conversations omit Ask rows and show a notice (not “no
      conversations”). Unreachable builds do the same for Builds.

### Implementation

- [ ] T014 [US3] Add `src/surfaces/portal/templates/_history.html`: search field
      plus `[data-history-row]` list from `history_items`; empty region still
      renders; current row `aria-current="page"`. Include it from
      `src/surfaces/portal/templates/base.html` for the signed-in column.

- [ ] T015 [US3] Add `src/surfaces/portal/static/portal-history.js`: filter
      `[data-history-row]` by visible text; no-matches copy; no API call. Absent
      script leaves the full list.

- [ ] T016 [US3] In `src/surfaces/portal/templates/base.html`: **+ New** is
      `href="/"` with accessible name New. **Projects** is visible, named, and
      does not navigate (FR-009).

**Checkpoint**: one searchable history; New is empty home.

---

## Phase 5: User Story 2 — The bubble starts work and can stop it (P1)

**Goal**: Enter starts the selected verb. While Ask is answering, Stop aborts the
wait and does not claim the answer ended. While a Build is in flight, Stop in
the bubble is `POST /runs/{run_id}/stop`. Failed stop does not look ended.

**Independent Test**: Ask Stop → waiting stopped. Build Stop → existing run-stop.
`propose_run.html` has no `POST /`.

### Tests

- [ ] T017 [US2] In `tests/component/test_portal_asks.py`: Ask Stop / abort copy
      does not say the answer ended (research F5).

- [ ] T018 [US2] In `tests/component/test_portal_shell.py`:
      `src/surfaces/portal/templates/propose_run.html` has no
      `method="post" action="/"` (or `/propose`); the bubble contains
      `action="/runs/` + stop.

- [ ] T019 [GATE:fail-closed] [US2] In `tests/component/test_portal_shell.py` /
      existing stop rows: a failed stop response does not present the run as
      ended.

### Implementation

- [ ] T020 [US2] Keep Ask abort in `src/surfaces/portal/static/portal-ask.js`;
      after a first land, `history.replaceState` still goes to `/ask/{id}`. Do
      not add an ask-cancel API.

- [ ] T021 [US2] Move the existing stop form into the bubble on
      `src/surfaces/portal/templates/propose_run.html` and
      `src/surfaces/portal/templates/_propose_run_main.html`. Slider locked on
      Build (`disabled`). Title at top; greeting absent. Keep
      `id="phase-strip"` and `[data-phase]`.

- [ ] T022 [US2] On an open Ask in `src/surfaces/portal/templates/ask.html`,
      lock the slider on Ask; composer at bottom centre (CSS from T011);
      follow-up still POSTs `/ask`.

**Checkpoint**: Stop is the existing stops, in the bubble.

---

## Phase 6: User Story 4 — Profile, Settings, logout (P2)

**Goal**: Bottom of the left column has `subject_user_id`, Settings (`/settings`),
and `POST /logout`.

**Independent Test**: Settings opens the existing page. Logout signs out.

- [ ] T023 [US4] In `tests/component/test_portal_identity.py`: bottom column
      exposes accessible names Settings and Sign out (or logout) and
      `href="/settings"`; profile shows `subject_user_id`.

- [ ] T024 [US4] In `src/surfaces/portal/templates/base.html`: profile
      (`subject_user_id`), Settings link, logout form at the bottom of the
      column — not next to New/Projects. Keep the 044 comment that Settings is
      linked for everyone (rewrite the rail premise, do not delete the comment).

**Checkpoint**: Settings is reachable from the shell.

---

## Phase 7: User Story 5 — Accessibility and Nocturne discipline (P1)

**Goal**: Designed-theme a11y still passes. New chrome uses Nocturne tokens only.
Named controls meet 24×24.

**Independent Test**: `tests/a11y` green on dark. Identity row fails on a
page-local hex or leftover icon rail as the only Settings path.

- [ ] T025 [US5] Extend `tests/component/test_portal_identity.py`: every colour
      on the new shell traces to the Nocturne `:root` block; no reference
      orange; mark digest matches `src/surfaces/portal/static/mark/PROVENANCE.md`;
      no third-party `url(` in CSS/templates.

- [ ] T026 [US5] Update a11y fixtures/selectors in `tests/a11y` for the new
      column (New, Projects, search, slider, Stop, +, profile, Settings,
      logout). Lane stays `color_scheme="dark"` only.

- [ ] T027 [US5] Confirm 24×24, 320px reflow, visible focus, and skip-to-content
      still hold in `src/surfaces/portal/static/portal.css` and
      `src/surfaces/portal/templates/base.html`.

**Checkpoint**: the identity gate covers the new shell.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T028 Remove the icon rail from `src/surfaces/portal/templates/base.html`
      so it cannot sit beside the new column. Signed-out / `login_failed.html` /
      `refused.html` inherit tokens without the column.

- [ ] T029 Rewrite F9 decision-comments in `src/surfaces/portal/templates/base.html`
      and `src/surfaces/portal/templates/ask.html` for one empty home, locked
      slider, and Settings in the column (FR-017). Do not delete the comments.

- [ ] T030 [P] Changelog entry for the create-home shell in `CHANGELOG.md`. Do
      not add a glossary product name from the reference screenshot.

- [ ] T031 [GATE:conformance] `make check` and
      `uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y tests/component/test_portal_identity.py tests/component/test_portal_shell.py tests/component/test_portal_session.py tests/component/test_portal_asks.py tests/conformance/propose -q`
      green. 047 P8 must still fail if Ask grows a propose control.

- [ ] T032 Human half (contract named-runner row): walk empty home, open Ask,
      in-flight Build Stop, Settings, signed-out, 320px on
      https://127.0.0.1:8082/. **Named runner: Dan McTeer.**

---

## Dependencies & Execution Order

```text
Phase 1  T001
  → Phase 2  T005 → T002 → T003 → T004
  → Phase 3  T006 ∥ T007 → T008 → T009 → T010 → T011
  → Phase 4  T012 ∥ T013 → T014 → T015 → T016
  → Phase 5  T017 ∥ T018 ∥ T019 → T020 → T021 → T022
  → Phase 6  T023 → T024
  → Phase 7  T025 → T026 → T027
  → Phase 8  T028 → T029 → T030 ∥ T031 → T032
```

T002 before T008 (home needs `history_items`). T011 before T022 (open-item
composer CSS). T014 before T016 (column exists). T001 before T009 (img src).

### User Story mapping

- **US1**: T006–T011
- **US3**: T012–T016
- **US2**: T017–T022
- **US4**: T023–T024
- **US5**: T025–T027
- **Foundational / polish**: T001–T005, T028–T032

### MVP

T001 → Phase 2 → Phase 3 (US1). Empty home with Ask selected. History and Stop
follow.

### Parallel examples

After T005: T006 ∥ T007.
After T011: T012 ∥ T013.
After T016: T017 ∥ T018 ∥ T019.

---

## Notes

- Named contracts bind exactly: `history_items`; `DEFAULT_POST_LOGIN_PATH` = `/`;
  files `hashicorp-logomark.svg`, `_history.html`, `portal-history.js`;
  `GET /` renders `ask.html`; `GET /ask` 303 `/`; Ask Stop is the existing
  abort; Build Stop is `POST /runs/{run_id}/stop`.
- No sealed core, no new ADR, no new catalogue operation, no CDN, no Claude
  orange.
- What would fail honestly: leftover empty `/ask` page; slider default posting
  `/`; invented history rows; Stop that only hides a spinner; page-local hex;
  Settings only by typed URL.
