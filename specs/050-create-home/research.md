# Research: Create home

Decisions only. Measured against the tree and the clarified spec. No open forks.

## F1 — One empty home is `GET /`; empty `/ask` goes away

**Measured**: `GET /` renders empty Build (`propose.html`). `GET /ask` renders empty
Ask (`ask.html`). `GET /propose` already 303s to `/`. Login default
`DEFAULT_POST_LOGIN_PATH` is `/ask` (post-login Ask). Icon rail links `/` (Build)
and `/ask` (Ask). After delete, Ask 303s to `/ask`.

**Decision**: `GET /` is the only empty create home (`ask.html` with no
conversation: HashiCorp mark, “Let's Create”, slider on Ask, combined history).
`GET /ask` with no id **303s to `/`**. `GET /ask/{conversation_id}` stays the
open Ask. `GET /propose/runs/{run_id}` stays the open Build. `DEFAULT_POST_LOGIN_PATH`
is **`/`**. Ask delete and other empty-Ask 303s go to `/`, not `/ask`.

**Failure sibling**: an unauthenticated `GET /` still renders signed-out, not
create home. A 401 on a list load does not invent an empty history (F3).

**Refused**: keeping two empty pages; a third `/create` route; leaving
`DEFAULT_POST_LOGIN_PATH` at `/ask` after empty `/ask` is gone.

## F2 — Combined history is a portal merge of two existing lists

**Measured**: `_conversations` relays `GET /ask-conversations` (`title`,
`last_asked_at`, `conversation_id`). `_builds` relays `GET /runs` and keeps
`authoring-agent` / `propose-*` rows (`run_id`, `state`, title from
`_build_rail_title`). Run list entries already carry `created_at`. Neither list
is a mixed catalogue.

**Decision**: named helper **`history_items`** in `src/surfaces/portal/app.py`
merges those two existing reads into one newest-first list for the template.
Each item is `kind` (`ask` | `build`), `title` (conversation title, or the
existing build title), `href` (`/ask/{id}` or `/propose/runs/{id}`), `verb`
(Ask or Build), `sort_at` (`last_asked_at` or `created_at`). Sort descending
by `sort_at`. No new API field.

**Failure sibling**: conversations unreachable → Ask rows omitted and the page
says that Ask history could not be read (not “no conversations”). Builds
unreachable → same for Builds (`reachable` already exists). Both unreachable →
searchable list region still renders, empty of rows, with both notices. Never
invent a row.

**Refused**: a new list operation; client-side fetch of a third URL; sorting by
title; using `_build_rail_title` as Ask titles.

## F3 — Search filters rendered rows

**Decision**: `portal-history.js` filters `[data-history-row]` by already-visible
text (title + verb word). No platform search. No matches: a “No matches” line,
no invented rows. Script absent: the full list stays; search input does not
pretend to filter.

**Refused**: a query parameter that hits the API; filtering answer bodies.

## F4 — Slider is presentation; submit targets existing posts

**Decision**: on empty home the composer is one form. Default `action="/ask"`
(Ask). **`portal-composer.js`** (one new progressive-enhancement file; not
`portal-ask.js`) is the slider script: it sets `form.action` to `/ask` or `/`
and the submit label to Ask or Build. Enter uses the existing base.html
requestSubmit path. Without that script, the form posts `/ask` (Ask default).
Build without the script is not required; the slider’s Build value is the
progressive enhancement, same class as today’s Ask fetch enhancement.

On an open Ask the form posts `/ask` (follow-up); slider locked on Ask
(`disabled` + `aria-disabled`, still visible). On an open Build the bubble
does **not** include `method="post" action="/"` (048 F2 / FR-004). Stop is the
existing `POST /runs/{run_id}/stop` form, moved into the bubble.

**Failure sibling**: Ask selected MUST NOT post `/` or `/propose` (047 P8). A
locked slider MUST NOT change `form.action`.

**Refused**: a new propose-from-thread operation; an operable slider on an open
item.

## F5 — Ask Stop is the existing abort; Build Stop is the catalogue stop

**Measured**: `portal-ask.js` Stop aborts the in-flight `fetch` (`AbortController`).
Copy already says the question was sent. There is no catalogued Ask-cancel
operation. Build Stop is `POST /runs/{run_id}/stop` (`app.py` `stop`), already
used on the run page.

**Decision**: Ask Stop stays that abort — it is the existing Ask stop. After
abort the page MUST say waiting stopped, not that the answer ended. Build Stop
in the bubble is the existing run-stop form. If that POST fails, the page MUST
NOT hide the in-flight state (existing `_alert` / refused path).

**Refused**: a new ask-cancel catalogue operation (FR-014); a Stop that only
toggles CSS; treating fetch abort as “the model halted.”

## F6 — HashiCorp logomark is adopted, unmodified, with provenance

**Measured**: no logo files in the portal tree. HashiCorp’s trademark policy
(https://www.hashicorp.com/trademark-policy) requires express written permission
for the corporate logo. The maintainer stated that permission. Brand guidance
forbids modifying, recolouring, or stretching the mark. Dark grounds want a
**reverse** lockup when the official kit includes one.

**Decision**: vendor the official HashiCorp **logomark** (the isometric H only —
greeting is “Let's Create”, not the HashiCorp wordmark) as
`src/surfaces/portal/static/mark/hashicorp-logomark.svg`. If the official kit
includes a reverse/light mark for dark grounds, that is the file that ships;
otherwise the official mark is used unmodified. `PROVENANCE.md` beside it
records source, retrieved date, sha256, trademark notice (“HashiCorp and the
HashiCorp logo are trademarks of HashiCorp.”), and that the maintainer holds
written permission. The mark is
`<img src="/static/mark/hashicorp-logomark.svg" alt="">` next to “Let's Create”
(the greeting names the mark). Not an inline path that could be redrawn. No
runtime fetch.

**Refused**: a lookalike star; tinting the official mark to `--accent`; a CDN;
committing the Claude screenshot.

## F7 — Open item: title at top, same bubble at bottom centre

**Decision**: empty `/` shows mark + “Let's Create” and the composer in the
stage. Open Ask or Build hides that greeting. The title at the top of the
stage is the existing conversation `title` or the existing build title.
Composer is the same bubble, `position`ed at the bottom centre (CSS). 048’s
one-row 880/680 geometry is superseded; token and type-role rules are not.

**Refused**: Share, model picker, Home/Code; repeating the greeting on an open
item.

## F8 — Placeholders are disabled and named

**Decision**: + (attach) and Projects are real controls with accessible names,
`disabled` (or `aria-disabled="true"` and no navigation), and an accessible
description that they are not available yet. Activation MUST NOT attach a file
or change the URL.

**Refused**: `href="/projects"` that 404s; a hidden file input.

## F9 — Shell chrome moves into `base.html`; icon rail leaves

**Measured**: `base.html` icon rail is Build / Ask / Settings / Sign out.
Settings is linked for everyone because 044 was unreachable (comment in
`base.html`). Profile is only `subject_user_id` on the session.

**Decision**: signed-in conversational chrome is a left column: + New (`href="/"`),
Projects (placeholder), search + `history_items`, then profile
(`subject_user_id`), Settings (`/settings`), logout (`POST /logout`). Icon rail
markup is removed from pages that use this shell. Signed-out and login-failure
keep tokens without the column. Settings remains the existing page.

**Refused**: Settings only by typed URL (044 regression); a profile display name
the portal does not have.

## F10 — Nocturne is the redesign’s colour schema

**Measured**: `portal.css` already declares the Nocturne token block (`--bg-page`,
`--text-primary`, `--accent` violet, semantic success/warning/danger, aliases
`--ink` / `--muted` / `--cta`). 048 copper exists only as aliases onto that
accent.

**Decision**: the new shell **paints with those tokens**. Column, greeting,
bubble, slider, and history reference `:root` names only. Inter / IBM Plex Mono
stay. 047 P8: Ask cannot start a Build or open a PR. In-flight Build cannot
POST `/` from the run page. Decision-comments in `base.html` / `ask.html` are
rewritten for one empty home and the locked slider, not deleted.

**Refused**: Claude orange as chrome; a second `:root` block; restoring a
copper identity beside Nocturne.
