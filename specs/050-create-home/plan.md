# Implementation Plan: Create home

**Branch**: `spec/050-create-home` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/050-create-home/spec.md`

## Summary

Replace the 048 icon-rail split with one signed-in create home: HashiCorp logomark,
“Let's Create”, a rounded composer with an Ask/Build slider (default Ask), combined
searchable history, + New, placeholder Projects, and profile / Settings / logout at
the bottom of the left column. The shipped **Nocturne** colour schema is part of
this redesign — new chrome uses those tokens, not the reference screenshot’s
orange and not a second copper identity. Empty `/ask` 303s to `/`. Open items keep
their addresses, show a title at the top, and move the same bubble to the bottom
centre with the slider locked. Stop uses the existing Ask abort and the existing
Build run-stop. No new catalogue operation, no new payload, no CDN, no client
framework.

## Technical Context

**Language/Version**: Jinja templates + hand-written CSS and the existing portal
scripts (no framework). Python only in `src/surfaces/portal/app.py` and
`src/surfaces/portal/oidc.py` (`history_items`, `DEFAULT_POST_LOGIN_PATH`, empty
`/ask` 303).

**Primary Dependencies**: none added. HashiCorp logomark is a static SVG with
provenance. Inter and IBM Plex Mono stay.

**Storage**: none. History is a merge of `GET /ask-conversations` and `GET /runs`.

**Testing**: `tests/component/test_portal_shell.py` and `test_portal_identity.py`
updated for the new chrome; `test_portal_session.py` login default `/`;
`test_portal_asks.py` isolation (Ask selected never posts `/`); a11y lane on the
designed theme; 047 P8 remains green.

**Target Platform**: unchanged; portal still serves its own assets with no build step

**Project Type**: existing single project; presentation only

**Performance Goals**: none binding — one extra list GET on pages that already
load one list

**Constraints**: no third-party fetch (FR-012); no new operation (FR-014); Ask
never acts (ADR-0039); stop fail-closed (FR-005); 320px reflow; placeholders must
not succeed; official mark unmodified (F6)

**Scale/Scope**: `base.html` left column; `ask.html` as empty home and open Ask;
`propose_run.html` open Build; `_history.html`; `portal-history.js`; slider on the
shared composer; vendored mark; identity + a11y + session tests; icon rail removed
from the conversational shell

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No framework; CSS + existing progressive-enhancement scripts; official mark adopted |
| II — Total Interception; One Governed Tool Layer | Pass | Portal stays a thin client (ADR-0034). Slider chooses which existing POST to relay |
| III — Fail-Closed, In-Process Enforcement | Pass | Unreadable list is a notice, not an empty claim. Failed Build stop does not look ended. Ask abort does not claim the answer ended |
| IV — Zero Standing Credentials | Pass | Mark and faces are static files; no runtime fetch |
| V — Sealed Core, Versioned Seams | Pass | Zero core changes. No new catalogue field |
| VI — Lean by Default | Pass | One stylesheet; icon rail removed rather than kept beside the new column |
| VII — Anti-Fragmentation | Pass | No transport-shaped change; API/MCP untouched |
| VIII — Eval-Gated Promotion | N/A | No model, no cell |
| IX — Evidence Over Claims | Pass | A11y lane + component rows; mark provenance is a digest row |
| X — Decision Record Governs | Pass | ADR-0034, ADR-0039, ADR-0033, ADR-0004 consumed; no new ADR |

**Gate result**: PASS — proceed to Phase 0.

### Constitution Check (post-design)

Unchanged. Phase 1 names `history_items`, `DEFAULT_POST_LOGIN_PATH="/"`, and the
mark files. It does not add a store, route-as-operation, or core type. Empty
`GET /ask` is a 303, not a new resource.

## Project Structure

### Documentation (this feature)

```text
specs/050-create-home/
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
src/surfaces/portal/app.py                         # history_items; GET /ask 303; delete → /
src/surfaces/portal/oidc.py                        # DEFAULT_POST_LOGIN_PATH = "/"
src/surfaces/portal/templates/base.html            # left column; no icon rail
src/surfaces/portal/templates/ask.html             # empty home + open Ask
src/surfaces/portal/templates/propose_run.html     # open Build; bubble Stop
src/surfaces/portal/templates/_history.html        # combined list + search
src/surfaces/portal/templates/_thread_composer.html  # bubble; slider; + placeholder
src/surfaces/portal/static/portal.css              # column + bubble geometry; Nocturne tokens are the schema
src/surfaces/portal/static/portal-history.js       # search filter only
src/surfaces/portal/static/portal-ask.js           # Stop abort unchanged; first land → /ask/{id}
src/surfaces/portal/static/mark/hashicorp-logomark.svg
src/surfaces/portal/static/mark/PROVENANCE.md
tests/component/test_portal_shell.py
tests/component/test_portal_identity.py
tests/component/test_portal_session.py
tests/component/test_portal_asks.py
tests/a11y/
```

**Structure Decision**: `GET /` renders `ask.html` as create home. Do not add
`create.html`. Icon rail leaves `base.html` so it cannot drift beside the new
column. `portal.css` stays one file (034/048 audit property).

## Dependency order

US5 (tokens, a11y, mark provenance) lands with US1’s empty home — the gate is how
the shell is proven. US3 (combined history + search) is the left column US1 needs.
US2 (Stop in the bubble) follows the shared composer markup. US4 (profile /
Settings / logout) is the bottom of that column.

## Complexity Tracking

No violations to justify.
