# Tasks: The portal gets a visual identity

**Input**: Design documents from `/specs/034-portal-visual-identity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — the doubled accessibility lane IS the feature's proof (US3 is folded
into US1's phase because the gate extension is how the identity is judged, not a separate
increment), and the token-discipline rows are what make SC-004 a failing test instead of a
convention.

**Organization**: US1+US3 land together as the core (tokens, roles, both themes, behind the
doubled gate); US2 follows because it alone touches Python and it reads the tokens US1
defines. The only network in the whole feature is T001's one-time vendoring fetch, which is a
reviewed act recorded in provenance — nothing fetches at runtime.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Vendor Roboto into `src/surfaces/portal/static/fonts/`: Regular (400) and Bold
      (700) as woff2, from the pinned canonical upstream release. Write `PROVENANCE.md`
      beside them recording repository + release/commit, licence (Apache-2.0 — the same as
      this repository), retrieval date, the exact conversion command and tool version if
      woff2 was produced from released TTF, and the sha256 of each vendored file (research
      F7). This is the feature's ONE network act; it happens here, once, and is reviewed.

## Phase 2: Foundational

*(none — the token sheet is US1's own first task)*

## Phase 3: User Story 1 + User Story 3 — the identity, behind the doubled gate (P1)

- [ ] T002 [US1] Rewrite `src/surfaces/portal/static/portal.css` as a token sheet: the F5
      palette as custom properties in `:root` (light) and `@media (prefers-color-scheme:
      dark)` (dark, designed not inverted — FR-013), the four type-role tokens
      (`--font-heading` serif stack, `--font-prose` Roboto with system fallback,
      `--font-control`, `--font-evidence` — research F6), `@font-face` for the two vendored
      weights with `font-display: swap`, and every rule below the token blocks reading tokens
      only. The stylesheet's existing WCAG-lesson comments (header wraps at 320px — 028's
      Linux-Chromium lesson; 24px targets; visually-hidden; visible focus) survive with their
      rules restyled, and the focus ring moves to `--link-bright` where contrast rules do not
      bind (FR-008). Long-hash `word-break` is kept and extended to every evidence context —
      the mono face makes this worse before better (spec edge case).
- [ ] T003 [US1] Apply the role assignment table (data-model) across all eight templates in
      `src/surfaces/portal/templates/`: headings to the heading face; body prose inherits
      Roboto from `body`; controls (buttons, nav, form labels, composer chrome) explicitly on
      the control face; evidence (record hashes, timestamps, citations, result blocks) on the
      evidence face. Dispositions become bordered pills — a `class="pill pill--<disposition>"`
      element whose text content is the disposition word, in the evidence face, uppercase via
      CSS (structure first, colour on top — research F8). The ground note and window note get
      the provenance-block treatment from the approved mockup. **Every decision-comment named
      in research F9 is re-read in the same edit**: verb-labelled nav, references as `code`
      not `a`, conditional window note vs unconditional ground note — kept, with premises
      updated where the restyle moves them (FR-009).
- [ ] T004 [US3] Parametrize the a11y fixtures in `tests/a11y/conftest.py`: `page` and
      `anonymous_page` gain `params=["light", "dark"]` and create their browser context with
      `color_scheme=<param>`, so every existing axe state AND every keyboard row runs once
      per theme with zero row edits (research F4) and a failure names its theme in the test
      id. No row is edited; the doubling is entirely fixture-side. (Verified during analyze:
      no row creates its own context, so nothing escapes the parametrization.)
- [ ] T004a [US3] Two templates ship restyled with no axe state today (analyze G2), which is
      exactly the untested surface the dark-theme decision refused: add states in
      `tests/a11y/test_wcag.py` for `login_failed.html` (the harness IdP refuses a callback)
      and `refused.html` (the harness transport refuses a thread open — distinct from the
      already-covered ask-form refusal). If either state proves unreachable through the
      lane's session-scoped surface, it is NAMED in the contract's human-walk row rather
      than left unlisted — an unlisted gap reads as coverage.
- [ ] T005 [P] [US1] [GATE:fail-closed] Component rows in
      `tests/component/test_portal_identity.py`: token discipline — no hex/rgb/hsl literal in
      `portal.css` outside the token blocks and no `style=` attribute carrying colour in any
      template (SC-004, the row that makes the discipline enforceable); dispositions survive
      greyscale by structure — the pill exists, carries the disposition word as text, has a
      border (SC-003, asserted on the DOM not a screenshot); the vendored font files' sha256
      match `PROVENANCE.md` (the row is the verifier — research F7); and no FETCH-CAUSING
      external reference exists — `src=`, `<link href>`, CSS `url()`, `@import` pointing off
      the portal's own origin (SC-006; sharpened by analyze A3, because the offline property
      is about what the browser fetches, not what a person may click — citation anchors are
      payload-derived links and legitimately external).
- [ ] T006 [US1] Run the doubled lane to green:
      `uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y -q`.
      Contrast findings are fixed **by adjusting token values** in their theme's block — never
      by excluding a state, never by narrowing the lane (SC-001's "no exclusions added").
      Iteration here is expected and is the point of having the gate.

**Checkpoint**: the identity exists in both themes, and the same lane that guarded the old
portal guards the new one — at twice the states.

## Phase 4: User Story 2 — the page says which product it is about (P2)

- [ ] T007 [US2] `src/surfaces/api/definitions.py`: `AgentDefinitionView` gains
      `packs: tuple[str, ...] = ()`, resolved from the fabric beside the ceiling with the
      same fail-shape — a definition whose packs cannot be read shows `()` rather than being
      hidden or failing (unknown is a state, research F2). **The mechanism is designed for
      the fabric that lacks it** (analyze C1): the hermetic harness fabric has
      `list_definitions` and no `resolve_definition_bindings`, so the view reads the resolver
      via `getattr` — absent method, refused resolution, and empty bindings all land on `()`
      — and the harness fabric GAINS the method in `tests/harness/api_fixtures.py` where
      rows need real packs, so the fail-shape is exercised deliberately rather than being
      every hermetic row's accident. The view is transport-shared, so MCP and the API expose
      the field by construction; the existing definitions conformance coverage grows a shape
      row asserting the field, the unknown-as-empty behaviour, and the absent-resolver case.
- [ ] T008 [US2] `src/surfaces/portal/templates/thread.html` + `app.py`'s thread context
      (the one portal Python touch): each turn's stripe is looked up template-side from its
      `agent_definition_id` against the `definitions` list already in context — a
      `data-pack="<pack>"` attribute styled by the product tokens; exactly one known pack
      → that product's stripe; several or none → no attribute, no stripe, no reserved space
      (FR-006). The composer's agent picker shows the same identity beside each startable
      definition. `threads.html` gains the deferral comment: the LIST carries no product
      because its payload does not know one, and a stripe from a name heuristic would be the
      platform pretending to know (spec US2 scenario 4).
- [ ] T009 [P] [US2] Component render rows (in `test_portal_identity.py` or beside it): a
      turn with a known pack renders the stripe attribute; an unknown or multi-pack
      definition renders none and no gap; the thread LIST renders no product colour at all;
      the composer shows identity beside startable definitions.

**Checkpoint**: product colour appears exactly where the platform genuinely knows the
product, and nowhere it would have to guess.

## Phase 5: Polish

- [ ] T010 [P] ROADMAP entry for 034; contract status rows flipped with dates.
- [ ] T011 All gates green on the branch: `make check`, the hermetic sweep, the doubled a11y
      lane, and `make evals` untouched. Then the human half (contract's named-runner row):
      agent brings the portal up (`DEV_IDP=1 infra/bin/portal-up`), walks it to every state
      in both themes, and hands Dan the link — **Dan's visual judgement and the
      human-judgement WCAG criteria are the acts only he performs**; his review of the
      implementation PR is where they happen.

---

## Dependencies

```text
Phase 1 (T001)                                  [one network act, reviewed]
  → Phase 3 (T002 → T003 → T004 → T004a → T005∥T006)  [hermetic + browser lane]
    → Phase 4 (T007 → T008 → T009)              [the only Python touches]
      → Phase 5 (T010 ∥ T011)
```

T005 is parallel with T006 (different files; the lane and the component rows don't contend).
T004 must precede T006 (the lane must be doubled before "green" means anything).

## Notes

- **No sealed core, no new ADR, no toggle.** Theme follows the system preference; a toggle is
  state and state needs a home this feature refuses to build.
- **The one review beyond Dan's PR review**: none. The font vendoring is inside the PR.
- **What would make this fail honestly**: a dark-theme contrast finding that cannot be fixed
  by token values without leaving the approved direction — that goes back to Dan with the
  specific pair, not into a quiet exclusion.
