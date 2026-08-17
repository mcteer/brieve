# Research: Ask and Build share one conversational shell

Everything below is measured against the tree or against the maintainer's approved mockups
(spine twins, single-row centred composer). Decisions only — no open forks.

## F1 — Intake text already exists; the result view does not disclose it

**Measured**: `propose_for` writes `RunInput(run_id=correlation_id, message=…)` via
`thread_store.put_run_input` before dispatch (`src/surfaces/api/propose.py`). The dispatcher
sets `run_id or correlation_id`, and Propose does not pass `run_id`, so the portal's
`/propose/runs/{run_id}` identifier is that same id. `GET /runs/{run_id}/result` already
returns `propose_progress` for the strip (`RunResultResponse` in `src/surfaces/api/runs.py`)
and does not call the thread store. `RunHandle` is `run_id`, `correlation_id`, `state` only.
The rail title today is `_build_rail_title(run_id)` — a truncated id, not the message.

**Decision**: add **`intake_message: str | None`** to `RunResultResponse`. Populate it from
`ThreadStore.get_run_input(run_id=run_id).message` on the existing `GET /runs/{run_id}/result`
path. Portal `propose_run` already relays that GET; it passes the field into the template. No
new route, no second store, no extra portal hop.

**Failure sibling**: store miss, unreadable store, or a run that never had `RunInput` (ordinary
`POST /runs`) → `intake_message` is `null`. The template omits the quote. It MUST NOT invent
text and MUST NOT substitute the rail title. Phase progress still renders. A 047 Propose run
that wrote input before dispatch is the success path; null is the honest miss.

**Refused**: putting the field on `RunHandle` (mixes dispatch identity with content);
reconstructing the prompt from the rail slug; a new `/runs/{id}/input` route.

## F2 — In-flight composer is chrome, not a second propose

**Measured**: `propose.html` POSTs `/`. `propose_run.html` has no composer. Ask follow-up POSTs
the existing ask routes. There is no steer-the-current-run operation.

**Decision**: empty Build and every Ask state keep their posting composers. `propose_run.html`
does **not** include a `method="post" action="/"` (or `/propose`) form. The list's New control
remains the new-Build path. If the in-flight page shows composer-class chrome for shell
sameness, the only operable control in that row is a link to `/` with accessible name
**New build**. It does not post a message.

**Refused**: a writable field on the run page that POSTs `/` (second propose; FR-004 forbids
it); a disabled fake Build button as the only control in the dock (dead target).

## F3 — Dark is forced; the a11y lane stops doubling

**Measured**: 034 parametrizes `tests/a11y/conftest.py` `THEMES = ["light", "dark"]` and
defines tokens in `:root` plus `@media (prefers-color-scheme: dark)`. The spec withdraws the
light theme. A leftover light token block would be an unverified surface of the kind 034
existed to prevent.

**Decision**: one token block, `:root`, designed dark. `html { color-scheme: dark; }` so the
UA does not invert form controls. Remove the `prefers-color-scheme: dark` override. A11y
fixtures drop `params=THEMES` and create one context with `color_scheme="dark"`. One subject
is enough (the two-subject split existed only because doubling the lane doubled rate-limit
counts). Token-discipline rows look for `:root {` only.

**Refused**: keeping light parametrization "in case"; inverting 034's light tokens as a
companion.

## F4 — Mockup `--faint` is not a text colour

**Measured** (sRGB relative luminance, WCAG 2.x):

| Pair | Ratio | Floor |
| --- | --- | --- |
| ink `#e8e6e1` / bg `#0b0c0e` | 15.69 | 4.5 |
| muted `#8f8c84` / bg `#0b0c0e` | 5.83 | 4.5 |
| muted `#8f8c84` / elev `#111318` | 5.53 | 4.5 |
| copper `#c4a574` / bg `#0b0c0e` | 8.37 | 4.5 |
| copper `#c4a574` / elev `#111318` | 7.95 | 4.5 |
| cta-ink `#1a1610` / copper `#c4a574` | 7.70 | 4.5 |
| ok `#6eab7c` / bg `#0b0c0e` | 7.25 | 4.5 |
| faint `#5e5c57` / bg `#0b0c0e` | **2.93** | 4.5 — **fails as text** |

**Decision**: secondary text uses `--muted`. Borders and hairlines use `--line`. Do not assign
the mockup faint hex to labels, breadcrumbs, chips, or kickers. Copper is allowed as text
(status, chips that are identity) because it clears 4.5 on both grounds. CTA is copper fill
with `--cta-ink`. Product identity tokens from 034 (`--vault`, `--terraform`) remain; they
are identity, not chrome.

Axe holds these at runtime on the designed theme. Any token tweak diffs against this table.

## F5 — Type roles: Inter + IBM Plex Mono, vendored like Roboto

**Decision**:
- **Prose** (headings, claims, ledes, messages, footer): Inter, self-hosted.
- **Controls** (buttons, rail, labels, composer field): Inter, same file.
- **Evidence** (ids, timestamps, citations, phase names, chips, never-acts): IBM Plex Mono,
  self-hosted.

`--font-heading` remains as a token and **points at the prose stack** so three roles stay
addressable; headings are prose, not a fourth face.

**Vendoring** (034 F7, including the licence lesson): retrieve from `google/fonts` at a
pinned commit, read each family's `OFL.txt` at vendoring, record whether a Reserved Font Name
is declared. Convert TTF → WOFF2 with ephemeral `fonttools` (same command shape as Roboto).
TTF → WOFF2 without touching glyph data is the transformation 034 recorded as not a Modified
Version.

**What upstream actually ships (do not rediscover at implementation):** Inter in `ofl/inter`
is a variable font. IBM Plex Mono in `ofl/ibmplexmono` is static weights. Vendor those
shapes:

- `inter-variable.woff2` — from Inter's variable TTF
- `ibm-plex-mono-regular.woff2` — weight 400
- `ibm-plex-mono-medium.woff2` — weight 500 (chips, labels, emphasis in evidence)

Italic is not vendored for either family (034's Roboto italic omission: synthetic oblique is
enough). **Do not write a licence SPDX into this file as a fact; `OFL-inter.txt` and
`OFL-ibm-plex-mono.txt` copied verbatim, plus `PROVENANCE.md` written from those files, are
the record.**

**Files (exact names)** under `src/surfaces/portal/static/fonts/`:
`inter-variable.woff2`, `ibm-plex-mono-regular.woff2`, `ibm-plex-mono-medium.woff2`,
`OFL-inter.txt`, `OFL-ibm-plex-mono.txt`, `PROVENANCE.md`.

**Removed in the same change (FR-016)**: `roboto-variable.woff2`, Roboto `OFL.txt`, every
stylesheet/`@font-face`/test reference to Roboto or the Palatino heading stack, the
`prefers-color-scheme: dark` token block, unused light-theme assertions. Approval mockups
under `tmp-ui-mockups/` are not added to the tree.

**Refused**: Google Fonts CDN (FR-007); naming Inter in a stack without vendoring (034's
San-Francisco failure); leaving Roboto beside the new files.

## F6 — Shared shell lives in `base.html`; lists stay per-verb

**Measured**: Ask already has `.app-layout` / `.app-rail` / `.app-main`. Build reuses that
pattern via `_build_rail.html`. `base.html` still has a text `<header>` nav (Build, Ask,
Settings) and a comment that Ask is the only full-width surface.

**Decision**: signed-in `base.html` renders the icon rail (Build, Ask, Settings, Sign out)
with accessible names matching those verbs (`aria-label` / visible text for AT; SVG is
decorative). The work list stays in Ask (`conversations`) and `_build_rail.html` (`builds`) —
not a mixed list. Empty list still omits the column (`app-layout--alone`). Signed-out,
`login_failed`, and `refused` inherit tokens and type without the three-column shell.

Update the `main_class` decision-comment: Ask is no longer the only full-width surface; Build
uses the same shell.

## F7 — Spine reuses 047's phase contract

**Measured**: `portal-propose-strip.js` updates `#phase-strip [data-phase="…"]` class names
and `.phase-status` textContent. It does not write innerHTML. Phase names are
`research|plan|write|judge|propose`; statuses `pending|active|completed|failed`.

**Decision**: Build spine is an ordered list that **keeps** `id="phase-strip"` and
`data-phase` / `.phase-status`. Visual classes may add spine node styling (`node`, `dot`)
without removing those hooks. The script is edited only to set the class names the new CSS
needs, still via `className` and `textContent`. Ask spine is `_exchange.html`: person's words
as `.you`, answer as a completed node; citations stay in `_outcome.html` evidence role.

Completed / current / waiting / failed are the person's labels (shape + the status word).
They map to 047 `data-phase` statuses `completed` / `active` / `pending` / `failed`
(filled / copper / empty / bordered). Colour is not the only carrier (FR-011).

## F8 — Composer geometry is CSS, one row

**Decision**: `.composer` is `display: flex; align-items: center`, `max-width: 880px`,
`margin-inline: auto`. The reading column is `.thread .inner { max-width: 680px }` (the
measure on the approved mockups). 880 > 680 is how FR-004 / SC-003 "wider than the reading
column" is testable — do not set both to 880px. Field, chips, action share the row.
`textarea` is `rows="1"` with a fixed line height (no stacked chips). Dock padding does not
stretch the bar edge-to-edge. Ask action label **Ask**; empty Build **Build**.

## F9 — Decision-comments are inventory

**Measured**: `base.html` (verb-labelled nav; 028 split; Settings linked for everyone;
`main_class` Ask-only full width); `ask.html` (rail omit when empty; no tabindex on
transcript); `_exchange.html` (one renderer; conversation id on the article);
`_outcome.html` (dispatch order; body-less 500 is not a refusal).

**Decision**: each comment is kept and re-read. Premises that the shell changes (Ask as the
only full-width surface; text nav as the never-acts visibility) are updated in the same
edit: never-acts remains visible as status on Ask (`Never acts`) and as separate pages, not
only as nav words.

## F10 — Product stripes and 047 isolation still bind

**Decision**: 034 US2 stripe rules stand (known pack → product token; none → no gap). 047 P8
stands: Ask cannot open a PR; this restyle adds no propose controls on Ask routes.
