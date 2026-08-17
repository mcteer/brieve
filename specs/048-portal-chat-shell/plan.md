# Implementation Plan: Ask and Build share one conversational shell

**Branch**: `spec/048-portal-chat-shell` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/048-portal-chat-shell/spec.md`

## Summary

Restyle the portal so Ask and Build share one shell (icon rail, work list, thread, one-row
centred composer) and one spine grammar in the thread. Dark is the designed theme. Inter and
IBM Plex Mono are self-hosted with ADR-0004 provenance; Roboto and the Palatino stack leave
in the same change (FR-016). The one payload change is additive and read-only:
`intake_message` on the existing `GET /runs/{run_id}/result` view, read from the `RunInput`
047 already writes, so an in-flight Build can show the person's words without the template
inventing them. No new route, no steer operation, no client framework, no CDN.

## Technical Context

**Language/Version**: Jinja templates + one hand-written CSS file; Python touched on the
transport-shared run-result view (`intake_message`) and the portal passing that field through
to `propose_run.html`. Existing `portal-propose-strip.js` retargets class names on
`[data-phase]` nodes; it does not gain a framework.

**Primary Dependencies**: none added at runtime or in the lockfile. Playwright + vendored axe
already power the lane. Inter and IBM Plex Mono are static assets. `fonttools` is used once,
ephemerally (`uv run --with`), to convert vendored fonts and is recorded in provenance rather
than added to the project.

**Storage**: none new. Intake text is the `RunInput.message` 047 already stores via
`thread_store.put_run_input` (propose.py: run_id equals correlation_id; dispatcher uses
`run_id or correlation_id`). This feature discloses it on the result view; it does not persist
a second copy.

**Testing**: existing `tests/a11y` lane on the designed theme only (034's light/dark
parametrization is withdrawn with the light theme); `tests/component/test_portal_identity.py`
updated for new faces, single token block, no Roboto, F9 comment inventory on `base.html` /
`ask.html`; `tests/component/test_portal_shell.py` for in-flight no-POST, intake guard,
`_exchange.html` / `_outcome.html` F9 comments, and spine greyscale-by-structure;
`tests/component/test_run_result.py` grows `intake_message` present / null (API and MCP share
`RunResultResponse` — no new `tests/conformance/api/` run-result file); 047 P8 Ask-isolation
regression unchanged.

**Target Platform**: unchanged; the portal still serves its own assets with no build step

**Project Type**: existing single project; presentation + one additive view field

**Performance Goals**: none binding — two variable woff2 files served locally replace one
Roboto file. Sizes recorded in provenance at vendoring, not estimated here as a lock.

**Constraints**: no third-party fetch at runtime (FR-007); designed theme clears AA
independently (FR-012) — mockup `--faint` as text does not, so secondary text is `--muted`
(research F5); header/shell reflows at 320px (028); long hashes `word-break`; decision-comments
survive (FR-014); in-flight composer is not a `POST /` form (FR-004).

**Scale/Scope**: `base.html` + Ask/Build templates and includes; one stylesheet rewritten
around the designed-theme tokens; Inter variable + IBM Plex Mono Regular/Medium replacing
Roboto; 1 additive field on `RunResultResponse`; strip JS class-name retarget; identity +
a11y tests updated; superseded font files deleted

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No framework, no build step; CSS custom properties; existing strip script stays textContent-only |
| II — Total Interception; One Governed Tool Layer | Pass | No tool surface. Portal stays a thin client of the API (ADR-0034). `intake_message` is disclosure of a record 047 already wrote, not orchestration |
| III — Fail-Closed, In-Process Enforcement | Pass | Missing `RunInput` → `intake_message` is `null`; the template does not invent text. Store unreadability does not invent a prompt and does not drop phase progress |
| IV — Zero Standing Credentials | Pass | Nothing fetched at runtime; fonts are static files in the tree |
| V — Sealed Core, Versioned Seams | Pass | Zero core changes. Additive field lives on `RunResultResponse` (surface view), same shape as 034 `packs` / 047 `propose_progress` |
| VI — Lean by Default | Pass | One stylesheet stays one stylesheet; Roboto leaves when Inter/Plex land (FR-016); no second theme to maintain |
| VII — Anti-Fragmentation | Pass | `RunResultResponse` is transport-shared; API and MCP expose `intake_message` by construction |
| VIII — Eval-Gated Promotion | N/A | No model, no cell |
| IX — Evidence Over Claims | Pass | A11y lane covers the designed theme; font provenance is asserted by a row; intake text is a stored message, not a reconstructed title |
| X — Decision Record Governs | Pass | ADR-0034 (thin portal), ADR-0039 (never-acts visible), ADR-0033 (parity by shared view), ADR-0004 (font provenance) consumed; no new ADR |

**Gate result**: PASS — proceed to Phase 0.

### Constitution Check (post-design)

Unchanged. Phase 1 names `intake_message` on `GET /runs/{run_id}/result` and does not create a
new store, route, or core type. FR-016 deletion is in the same change as the new faces.

## Project Structure

### Documentation (this feature)

```text
specs/048-portal-chat-shell/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── conformance.md
└── tasks.md             # Phase 2 (/speckit-tasks) — not this command
```

### Source Code (repository root)

```text
src/surfaces/portal/templates/base.html           # icon rail; decision-comments updated
src/surfaces/portal/templates/ask.html            # shared shell; spine via _exchange.html
src/surfaces/portal/templates/propose.html        # empty Build: same shell + working composer
src/surfaces/portal/templates/propose_run.html    # spine + intake quote; no POST composer
src/surfaces/portal/templates/_exchange.html      # Ask spine: .you + answer node
src/surfaces/portal/templates/_outcome.html       # citations stay evidence role
src/surfaces/portal/templates/_build_rail.html    # list heading Builds; New unchanged
src/surfaces/portal/templates/*.html              # remaining pages inherit tokens/type
src/surfaces/portal/static/portal.css             # designed-theme tokens only; one file
src/surfaces/portal/static/portal-propose-strip.js  # class names on [data-phase]; id stays
src/surfaces/portal/static/fonts/                 # Inter + IBM Plex Mono; Roboto gone
src/surfaces/api/runs.py                          # RunResultResponse.intake_message
src/surfaces/portal/app.py                        # pass intake_message into propose_run
tests/a11y/conftest.py                            # designed theme only (THEMES withdrawn)
tests/component/test_portal_identity.py           # tokens, greyscale, new font digests, no CDN, F9 on base/ask
tests/component/test_portal_shell.py              # no POST on propose_run; intake guard; F9 on _exchange/_outcome
tests/component/test_run_result.py                # intake_message present / null; parity by construction
```

**Structure Decision**: rewrite `portal.css` in place (034: one file is the audit property).
Put the icon rail in `base.html` so Settings and signed-in non-chat pages inherit it; signed-out
and login-failure inherit tokens and type without the three-column shell. Keep
`id="phase-strip"` and `[data-phase]` on the Build spine so 047's strip script remains the
cadence path.

## Dependency order

US4 (tokens, faces, designed-theme gate, FR-016 cleanup) lands with US1's shell — the gate is
how the identity is proven. US2 (spine + `intake_message`) follows; it is the only Python
touch and it reads the tokens US1 defines. US3 (composer geometry) is CSS on the shared
composer markup and ships with US1.

## Complexity Tracking

No violations to justify.
