# Research: The portal gets a visual identity

Everything below is measured against the tree or against the maintainer's approved mockup.
The two findings that reshaped the spec are here first, because they bound everything else.

## F1 — The thread list cannot know its product, and pretending would be worse

**Measured**: a thread record is `thread_id, correlation_id, subject_user_id, tenant_id,
created_at, title` — no pack, no agent. Turns carry `agent_definition_id`; the fabric knows
each definition's packs; nothing joins that back to a thread list entry, and building that
join is API design work, not presentation.

**Decision**: the product stripe appears where the platform already tells the page which
definition acted — the thread page's turns and the composer's agent picker. The LIST stays
stripe-free, deferred with a dated note. The tempting middle — deriving "vault" from the
definition id's name — is refused by name: `vault-agent` happens to say its product and the
next definition won't, and a stripe from a string heuristic is the platform pretending to
know.

## F2 — One additive field, on the view both transports share

**Measured**: `definition_views()` in `surfaces/api/definitions.py` is deliberately
transport-independent — MCP reaches the same function, "so the disclosure rule is written
once." It resolves the ceiling per definition; the same fabric holds each definition's packs
(the binding records the choice lane reads). `AgentDefinitionView` today: id + may_start.

**Decision**: `packs: tuple[str, ...] = ()` joins the view, resolved beside the ceiling, with
the same fail-shape: a definition whose packs cannot be read shows `()` rather than hiding or
failing — unknown is a real state here exactly as it was for the corpus timestamp. Additive
and read-only, the `window_note`/`ground_note` precedent; parity holds by construction because
the view is shared.

## F3 — The dark theme is driven by the system, not by a toggle

**Decision**: `prefers-color-scheme` only. The portal has no client-side state and gains none:
no toggle button, no cookie, no JS. A reader's OS preference is the signal, which is also the
signal Playwright can emulate exactly.

**Rationale**: a toggle is state, state needs a home, and every home (cookie, localStorage)
adds behaviour to a feature that promised presentation. The mockup's toggle was an artifact
of the review page, not of the design.

## F4 — The lane doubles by parametrizing the fixtures, not by copying rows

**Measured**: every a11y row takes a `page` or `anonymous_page` fixture; both create a browser
context and Playwright contexts accept `color_scheme="dark" | "light"` at creation.

**Decision**: the two fixtures parametrize over the two schemes (`params=["light", "dark"]`),
so every existing row — the axe states AND the keyboard rows — runs once per theme with zero
row edits. Focus visibility, target size and reflow are theme-independent claims, but the
focus ring's *contrast* is not, which is why the keyboard rows run in dark too rather than
being assumed portable.

**Cost, stated**: the lane roughly doubles (~2× its current wall time, still minutes). That is
the price of "nothing ships untested" and it was chosen with the price visible.

## F5 — Tokens are the enforcement point, and a row makes them one

**Decision**: `portal.css` opens with the palette and type roles as custom properties —
`:root` (light), `@media (prefers-color-scheme: dark)` (dark) — and every rule below reads
tokens. A component row asserts the discipline: no hex/rgb/hsl literal outside the token
blocks, and no `style=` attribute carrying colour in any template. That turns SC-004 from an
aspiration into a failing test.

**Palette** (from the approved mockup): light — page `#FFFFFF`, raised `#F7F8F9`, ink
`#0C0C0E`, muted `#656A76`, rules `#DEDFE3`/`#EBEDEE`, link `#0F52D9` (brand `#1563FF`
reserved for non-text), CTA black-on-white; dark — page `#0C0C0E`, raised `#17181C`, ink
`#F1F2F3`, muted `#A3A7B0`, rules `#2C2E33`/`#212328`, link `#7FA9FF`, CTA white-on-black.
Verdicts: `#00764F` / `#BA2525` light, `#4FCB9B` / `#FF8A8A` dark. Products: Vault `#FFCF25`,
Terraform `#7B42BC`, both themes (identity colours don't invert). Every text/ground pair is
checked at implementation and then held by axe in both themes.

## F6 — Type roles, and where each face comes from

**Decision**:
- **Headings (prose display)**: `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia,
  serif` — a system stack; no vendoring, graceful fallback.
- **Body prose**: **Roboto**, self-hosted (F7) — `Roboto, system-ui, sans-serif` so a failed
  font load degrades to today's rendering rather than to nothing.
- **Controls**: `system-ui, -apple-system, "Segoe UI", sans-serif` — unchanged from today.
- **Evidence**: `ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace`.

The roles are tokens (`--font-prose`, `--font-heading`, `--font-control`, `--font-evidence`),
so "which face does X use" has one answer and the token row covers it.

## F7 — Roboto enters the tree the way the terraform skill did

**Decision**: two weights vendored — Regular (400) and Bold (700) — as woff2 under
`src/surfaces/portal/static/fonts/`, declared via `@font-face` with `font-display: swap`.
Weights 500/600 are not vendored; anything that wants medium emphasis uses 700 or stays 400.
Italic is not vendored; the portal's copy uses italics only for the window note, which may
keep synthetic italic or drop to normal — decided at implementation, recorded in the template
comment either way.

**Provenance** (FR-002a, ADR-0004's discipline): the files come from the pinned upstream
release of the canonical Roboto repository; a `PROVENANCE.md` beside them records repository,
release/commit, licence (Apache-2.0 — the same licence as this repository), retrieval date,
the exact conversion command if the release ships TTF and woff2 was produced from it (tool
and version pinned in the record), and the sha256 of each vendored file. A component row
recomputes the digests against the record — the row is the verifier, exactly as the pack
loader is for skill bytes.

**Refused alternative**: fetching from Google Fonts' CDN at runtime (breaks offline and adds
a third-party fetch — FR-002 forbids it) and naming Roboto in a stack without vendoring
(silently resolves to San Francisco on the maintainer's own machine — the approved design not
landing while appearing to; this is the exact failure clarify closed).

## F8 — Dispositions survive greyscale by structure, asserted by structure

**Decision**: the disposition pill is a bordered element whose accessible content is the
disposition word in the evidence face; colour is applied on top. The row asserts structure —
the pill exists, carries the text, has a border — rather than screenshotting greyscale,
because the DOM is what a screen reader gets and what survives any colour transform.

## F9 — The decision-comments are inventory, not collateral

**Measured**: the templates carry comments that record *why* — verb-labelled nav, references
as `code` not `a`, the conditional window note vs the unconditional ground note, the header
that wraps because CI's Linux Chromium renders wider. **Decision**: each comment is kept and
re-read during the restyle; where the restyle changes a premise (the ground note gains the
provenance-block treatment, say), the comment is updated in the same edit. The tasks name the
comments explicitly so "keep them" is checkable rather than hoped.
