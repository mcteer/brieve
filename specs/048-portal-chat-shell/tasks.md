# Tasks: Ask and Build share one conversational shell

**Input**: Design documents from `/specs/048-portal-chat-shell/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the designed-theme a11y lane, token/font/FR-016 rows, `intake_message`
null-on-miss, no `POST /` on `propose_run.html`, and 047 P8 are how the spec's success
criteria can lose.

**Organization**: US1 + US3 + US4 land together (shell, composer geometry, tokens/faces/gate,
FR-016 cleanup). US2 follows: it is the only Python touch (`intake_message`) and the spine
reads the tokens US1 defines. The only network act is T001's vendoring fetch.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types

| Gate type | This feature |
| --- | --- |
| **Fail-closed** | `intake_message` is `null` when `RunInput` is missing or unreadable; template does not invent text (T013, T015) |
| **Conformance** | Additive field on shared `RunResultResponse`; 047 P8 Ask isolation still green (T016, T022) |
| **Correlation / evidence** | N/A — no new run path; intake is disclosure of an existing `RunInput` |
| **Eval** | N/A — no pack, prompt, model, or policy |
| **No-secret-leak** | N/A — no new credential or tool-result path; 047 P9 still covers phase reasons |

---

## Phase 1: Setup

- [ ] T001 Vendor Inter and IBM Plex Mono into `src/surfaces/portal/static/fonts/` per
      research F5. Pin `google/fonts` at a commit written into `PROVENANCE.md`. Read each
      family's `OFL.txt` at vendoring and copy verbatim to `OFL-inter.txt` and
      `OFL-ibm-plex-mono.txt`; record whether a Reserved Font Name is declared. Convert TTF →
      WOFF2 with ephemeral `fonttools` (same command shape as 034 Roboto). Exact files:
      `inter-variable.woff2`, `ibm-plex-mono-regular.woff2`, `ibm-plex-mono-medium.woff2`.
      Do not delete Roboto in this task. This is the feature's ONE network act. Do not add
      `tmp-ui-mockups/` to the tree (FR-016).

---

## Phase 2: Foundational

*(none — the token sheet is US1's first implementation task)*

---

## Phase 3: User Story 1 + User Story 3 + User Story 4 — shell, composer, identity gate (P1) 🎯 MVP

**Goal**: Signed-in Ask and Build share the icon rail, per-verb list, thread stage, and
one-row centred composer. Dark designed theme, Inter + IBM Plex Mono, Roboto gone. A11y
lane covers that theme. Never-acts remains visible on Ask. No phase meter in the shared
header.

**Independent Test**: Open empty Ask and empty Build without reading the URL; same shell;
composer one row, centred, max-width 880px, reading column 680px; verbs Ask vs Build. `tests/a11y` green on dark
only. `test_portal_identity.py` green; `roboto-variable.woff2` absent.

### Tests (write so they can fail, then make them pass)

- [ ] T002 [US4] Rewrite
      `tests/component/test_portal_identity.py`: token block is `:root {` only (remove
      `prefers-color-scheme: dark` from `TOKEN_BLOCKS`); digest row lists
      `inter-variable.woff2`, `ibm-plex-mono-regular.woff2`, `ibm-plex-mono-medium.woff2`,
      `OFL-inter.txt`, `OFL-ibm-plex-mono.txt`; assert `roboto-variable.woff2` and Roboto
      `OFL.txt` **do not exist**; CSS `url()` set is exactly the three new font files; no
      Palatino/Roboto in `portal.css`; dispositions still greyscale-by-structure. The row
      must fail on leftover Roboto.

- [ ] T003 [US3] In `tests/component/test_portal_identity.py` after T002: assert
      `.composer` in `src/surfaces/portal/static/portal.css` is one flex row (`align-items:
      center`), `max-width: 880px`, `margin-inline: auto` (centering the test reads from the
      rule), and `textarea` inside it is not given a stacked `min-height` that makes a
      second row. Assert `.thread .inner` has `max-width: 680px` and that the composer's
      max-width is strictly greater than the reading column's (research F8). Must fail on
      the current stacked/full-bleed composer.

- [ ] T004 [US1] Template scan in `tests/component/test_portal_identity.py` after T003: icon
      rail items in `src/surfaces/portal/templates/base.html` expose accessible names
      **Build**, **Ask**, **Settings**, **Sign out**; Ask list heading is Conversations;
      Build list heading in `_build_rail.html` is Builds. Must fail on unnamed SVGs.
      Same file, F9 comment inventory (FR-014): `base.html` still records verb-labelled nav /
      028 split, Settings linked for everyone, and `aria-current` from the path; the
      `main_class` comment's premise is updated (Ask is not the only full-width surface).
      `ask.html` still records rail-omit-when-empty and no `tabindex` on the transcript.
      Comments whose premise changed are rewritten, not deleted.

### Implementation

- [ ] T005 [US1] Rewrite `src/surfaces/portal/static/portal.css` as the designed-theme token
      sheet (data-model + research F4/F5): `:root` only; `html { color-scheme: dark; }`;
      remove `@media (prefers-color-scheme: dark)`. Tokens `--bg` `#0b0c0e`, `--elev`
      `#111318`, `--elev-2` `#171a21`, `--ink` `#e8e6e1`, `--muted` `#8f8c84`, `--line`,
      `--copper` `#c4a574`, `--copper-dim`, `--cta` / `--cta-ink` `#1a1610`, `--ok`
      `#6eab7c`; keep 034 `--vault` / `--terraform` / `--denied` (raise `--denied` if it
      fails 4.5 on `--bg`). Type tokens: `--font-prose` and `--font-control` Inter;
      `--font-heading` equals the prose stack; `--font-evidence` IBM Plex Mono.
      `@font-face` for the three vendored files, `font-display: swap`. Secondary **text**
      uses `--muted` only (F4 — do not use mockup faint as text). Composer rules per T003.
      Reading column `.thread .inner { max-width: 680px }` (F8). Keep 028 wrap-at-320px, 24px
      targets, visually-hidden, visible focus, `word-break` on evidence. Every rule below
      `:root` reads tokens only.

- [ ] T006 [US1] `src/surfaces/portal/templates/base.html`: signed-in icon rail (Build, Ask,
      Settings, Sign out) with accessible names matching those verbs; SVG decorative. Ask
      current when path starts `/ask`; Build current on `/` and `/propose`. Never-acts is
      **not** a five-phase meter. Re-read the F9 comments that live in `base.html` in this
      edit; update the `main_class` premise (Ask is no longer the only full-width surface)
      and the text-nav premise (never-acts stays visible as Ask status + separate pages,
      FR-014). Skip-to-content remains.

- [ ] T007 [US1] Shared shell on `src/surfaces/portal/templates/ask.html` and
      `src/surfaces/portal/templates/propose.html`: icon rail from base, work list
      (Conversations vs Builds), thread stage, posting composer (Ask → existing ask POST;
      empty Build → existing `POST /`). Empty list still omits the column
      (`app-layout--alone`). Ask header/status shows **Never acts** in the evidence face.
      Build header has no Research/Plan/Write/Judge/Propose meter. `_build_rail.html` New
      control unchanged. Keep/update the F9 comments in `ask.html` (rail omit when empty; no
      `tabindex` on the transcript) — rewrite premises, do not delete the comments (FR-014).

- [ ] T008 [US3] Empty Ask, Ask-with-thread, and empty Build composers in
      `src/surfaces/portal/templates/ask.html` and
      `src/surfaces/portal/templates/propose.html`: `rows="1"`, chips and action on the same
      row as the field, action labels **Ask** / **Build**. No stacked field-plus-chips block.

- [ ] T009 [US1] Remaining templates inherit tokens and type without inventing colour:
      `settings.html`, `signed_out.html`, `login_failed.html`, `refused.html`,
      `delete_confirm.html`, `ask_delete_confirm.html`, `endorsed_review.html`,
      `threads.html`, `_thread_composer.html`, `_thread_turns.html`, `_notice.html`,
      `_copy_control.html`. Signed-out / login-failure / refused: identity without the
      three-column shell (research F6). Operator `/run` (`threads.html` + composer) inherits
      identity and does not appear as a third primary rail verb.

- [ ] T010 [US4] `tests/a11y/conftest.py`: remove `THEMES = ["light", "dark"]` parametrization.
      `page` / `anonymous_page` create one context with `color_scheme="dark"`. Drop the
      two-subject split that existed only to dodge doubled rate limits. Update the comment
      that claimed 034's doubling — light is withdrawn (research F3).

- [ ] T011 [US4] FR-016 cleanup in the same change as T005's `@font-face`: delete
      `src/surfaces/portal/static/fonts/roboto-variable.woff2` and Roboto `OFL.txt`; rewrite
      `PROVENANCE.md` for Inter + IBM Plex Mono only. Grep the tree for `Roboto`,
      `roboto-variable`, `Palatino`, `Iowan Old Style` under `src/surfaces/portal/` and
      `tests/component/test_portal_identity.py` and remove leftovers. Do not commit
      `tmp-ui-mockups/`.

- [ ] T012 [US4] Run
      `uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y tests/component/test_portal_identity.py -q`
      to green. Contrast findings are fixed by adjusting token values in `:root` — never by
      excluding a state, never by reintroducing a light theme (SC-004).

**Checkpoint**: Ask and empty Build are one product with two verbs; the lane covers the
designed theme; Roboto is gone.

---

## Phase 4: User Story 2 — the thread is a conversation, including while Build runs (P1)

**Goal**: Ask thread is person/answer spine with citations as evidence. Build in-flight
shows `intake_message` as the first turn, then 047 phase nodes. No new steer operation. No
invented prompt.

**Independent Test**: In-flight Build with stored `RunInput` shows that text, then phase
nodes (`id="phase-strip"` + `data-phase`). Missing input omits the quote. `propose_run.html`
has no `method="post" action="/"`. Ask two-exchange page uses the same spine grammar.

### Tests

- [ ] T013 [P] [US2] [GATE:fail-closed] Extend `tests/component/test_run_result.py`: a run
      whose `ThreadStore` has `RunInput` for that `run_id` returns `intake_message` equal to
      that message (the string comes from the store fixture, not from a literal constructed
      inside the assertion). A run with no `RunInput` returns `intake_message is None` (not
      `""`). Store raising / unreadable still returns `propose_progress` when present.
      Must fail on today's `RunResultResponse` (no field).

- [ ] T014 [P] [US2] Template rows in `tests/component/test_portal_shell.py`:
      `propose_run.html` renders `{{ intake_message }}` only inside a truthiness guard;
      contains no `method="post"` form to `/` or `/propose`; keeps `id="phase-strip"` and
      `[data-phase]`. Each `[data-phase]` node has a visible `.phase-status` word and a
      shape class for `completed` / `active` / `pending` / `failed` (not colour alone —
      FR-011 / SC-006). `_exchange.html` uses `.you` for the question. F9 inventory:
      `_exchange.html` still records one renderer and conversation id on the article;
      `_outcome.html` still records dispatch order and that a body-less 500 is not a
      refusal. Must fail on the current phase-strip-only page.

### Implementation

- [ ] T015 [US2] `src/surfaces/api/runs.py`: add `intake_message: str | None = None` to
      `RunResultResponse` (exact name). `get_run_result` / `run_result_for` take
      `ThreadStore` (optional). On success, `get_run_input(run_id=run_id).message`; on miss
      or exception, `None` — do not fail the whole result, do not invent text (F1 failure
      sibling). All existing `RunResultResponse(...)` constructors set the field (explicit
      `None` on the miss path). Transport-shared: MCP gets it by construction.

- [ ] T016 [US2] [GATE:conformance] Assert `intake_message` on the shared
      `RunResultResponse` in `tests/component/test_run_result.py` (T013 is the shape). Those
      tests' docstring states API and MCP expose the field by construction — same model, no
      second serializer. Do **not** add a `tests/conformance/api/` run-result file. 047 P8 /
      SC-009 remains a required green row (`tests/conformance/propose/` Ask isolation).

- [ ] T017 [US2] `src/surfaces/portal/app.py` `propose_run`: pass `intake_message` from the
      existing result relay into `propose_run.html`. Do not add a second API call. Do not
      use `_build_rail_title` as a stand-in.

- [ ] T018 [US2] `src/surfaces/portal/templates/propose_run.html`: `.you` from
      `intake_message` when set; ordered spine keeping `id="phase-strip"`, `data-phase`,
      `.phase-status` (research F7). Node shape + status word for
      `completed` / `active` (current) / `pending` (waiting) / `failed` (FR-011). No
      five-phase meter in the page header.
      Composer chrome if present is **not** a posting form; operable control in that row is
      a link to `/` with accessible name **New build** (research F2). SSE outcome block
      stays.

- [ ] T019 [US2] `src/surfaces/portal/static/portal-propose-strip.js`: keep
      `#phase-strip [data-phase]` and `textContent` updates; change only `className` values
      to match the spine CSS from T005. No `innerHTML`. No new JS file.

- [ ] T020 [US2] `src/surfaces/portal/templates/_exchange.html` + `_outcome.html`: person's
      words as `.you`; answer as a completed spine node; citations remain evidence role
      (034). One include still serves first load and in-page swap. Do not put 047 phase
      names on Ask. Keep/update the F9 comments in both files (one renderer; conversation
      id on the article; dispatch order; body-less 500 is not a refusal) — rewrite
      premises, do not delete the comments (FR-014).

**Checkpoint**: in-flight Build is a conversation with real intake text; Ask uses the same
spine grammar; no second propose from the run page.

---

## Phase 5: Polish & Cross-Cutting

- [ ] T021 [P] Changelog entry for the portal restyle in `CHANGELOG.md`; no new glossary
      product name (the mockup name does not appear in `docs/glossary.md` or the UI). ROADMAP
      048 pointer in `ROADMAP.md` if that table lists portal visual work.

- [ ] T022 [GATE:conformance] `make check` and
      `uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y tests/component/test_portal_identity.py tests/component/test_portal_shell.py tests/component/test_run_result.py tests/conformance/propose -q`
      green. 047 P8 must still fail if Ask grows a propose control. Then the human half
      (contract named-runner row): `DEV_IDP=1 infra/bin/portal-up`, walk empty Ask, empty
      Build, in-flight Build, answered Ask, Settings, signed-out, 320px; **Dan McTeer**
      performs visual judgement and human WCAG criteria on the implementation PR.

---

## Dependencies & Execution Order

```text
Phase 1  T001                         [one network act]
  → Phase 3
       T002 → T003 → T004             [same file: test_portal_identity.py]
       → T005 → T006 → T007 → T008 → T009
       → T010 → T011 → T012           [a11y + FR-016 + lane green]
    → Phase 4
       T013 ∥ T014                    [test_run_result.py vs test_portal_shell.py]
       → T015 → T016 → T017 → T018 → T019 → T020
      → Phase 5  T021 ∥ T022
```

T005 must precede T011 (new `@font-face` before deleting Roboto). T015 must precede T017
(field exists before the portal reads it). T018 depends on T005 (spine CSS) and T017
(context).

### User Story mapping

- **US1**: T004, T005–T009 (shell + F9 comments on `base.html` / `ask.html`)
- **US3**: T003, T005, T008 (composer; reading column 680px)
- **US4**: T002, T010–T012 (gate + fonts + cleanup)
- **US2**: T013–T020 (intake + spine + F9 comments on `_exchange.html` / `_outcome.html`)

### MVP

T001 → Phase 3 (US1+US3+US4). Empty Ask and empty Build look like one product. US2 is the
in-flight conversation and the only payload change.

### Parallel examples

After T001, T002→T003→T004 are sequential in `test_portal_identity.py`.
After Phase 3: T013 (`test_run_result.py`) ∥ T014 (`test_portal_shell.py`).

---

## Notes

- Named contracts bind exactly: field `intake_message`; files `inter-variable.woff2`,
  `ibm-plex-mono-regular.woff2`, `ibm-plex-mono-medium.woff2`; `id="phase-strip"`;
  composer `max-width: 880px`; reading column `.thread .inner` `max-width: 680px`;
  in-flight control accessible name **New build**.
- No sealed core, no new ADR, no steer operation, no light theme, no CDN.
- What would fail honestly: leftover Roboto; invented intake text; `POST /` on
  `propose_run.html`; a11y still parametrized over light; composer and reading column both
  880px; deleted F9 decision-comments.

### Analyze remediations (2026-08-17)

Surgical edits after `/speckit-analyze` (do not regenerate): SC-009 added (047 P8); T016
pinned to `test_run_result.py` with no API conformance fork; `test_portal_shell.py` in T022 /
plan / quickstart; F9 comment row on T004 and T014; phase-status aliases in FR-006; reading
column 680px; `[GATE:fail-closed]` removed from T002; in-flight control named **New build**.
