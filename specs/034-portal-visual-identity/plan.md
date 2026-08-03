# Implementation Plan: The portal gets a visual identity

**Branch**: `spec/034-portal-visual-identity` | **Date**: 2026-08-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/034-portal-visual-identity/spec.md`

## Summary

A token-first restyle of eight templates and one stylesheet, judged by a gate that already
exists. The stylesheet becomes a token sheet (colour and type roles defined once, referenced
everywhere) implementing the approved direction: HashiCorp's ramp, black call-to-action, link
blue darkened to clear AA, serif headings, **Roboto body** (self-hosted with ADR-0004
provenance), mono evidence, and saturated colour reserved for a product or a verdict. Both
themes ship and the accessibility lane doubles to cover dark — every axe state and the
keyboard rows run per theme. The one payload change in the whole feature is additive and
read-only: the transport-shared definitions view gains `packs`, which is what lets the thread
page stripe turns and the composer honestly instead of by name heuristic. The thread list
stays stripe-free, deferred and recorded, because its payload does not know the product.

## Technical Context

**Language/Version**: Jinja templates + one hand-written CSS file; Python touched in exactly
two places (the definitions view's additive field; the portal passing it through to the
thread template context)

**Primary Dependencies**: none added at runtime or in the lockfile. Playwright + vendored axe
already power the lane; the Roboto woff2 is a static asset, not a dependency. `fonttools` is
used once, ephemerally (`uv run --with`), to convert the vendored font and is recorded in the
font's provenance rather than added to the project

**Storage**: none — no record, no payload persisted, nothing in Vault or Postgres changes

**Testing**: the existing `tests/a11y` lane, extended: the page fixtures parametrize over
`color_scheme` (light, dark) so every axe state and every keyboard row runs twice; new
component rows for the token discipline (no colour outside the token block), the greyscale
survival of dispositions, the font files' digests against their provenance record, and the
additive `packs` field's shape

**Target Platform**: unchanged; the portal still serves its own assets with no build step

**Project Type**: existing single project; presentation + one additive view field

**Performance Goals**: none binding — one variable woff2 (222 KB, all weights) served locally
is the entire cost delta. Larger than the two-static estimate this plan first carried, because
upstream ships no statics; stated in the font's provenance rather than buried

**Constraints**: no third-party fetch at runtime (FR-002 — the fonts are self-hosted, so the
offline property survives); both themes clear AA independently (FR-013 — dark is designed,
not inverted); the templates' decision-comments survive with their premises updated (FR-009);
the header keeps wrapping at 320px (028's Linux-Chromium lesson); long hashes get
`word-break` before the mono face makes them wider

**Scale/Scope**: 8 templates, 1 stylesheet rewritten around tokens, 2 font files + provenance,
2 small Python touches, ~4 new test files, 1 lane parametrization

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No framework, no build step, no JS added; CSS custom properties and a media query |
| II — Total Interception | N/A | No tool surface |
| III — Fail-Closed | N/A | No enforcement path changes; the one view change is read-only disclosure |
| IV — Zero Standing Credentials | Pass | Nothing fetched at runtime; fonts are static files in the tree |
| V — Sealed Core, Versioned Seams | Pass | Zero core changes; the additive `packs` field lives in the surface view, same shape as prior additive payload fields |
| VI — Lean by Default | Pass | One stylesheet stays one stylesheet; tokens replace scattered hex values rather than adding a system on top |
| VII — Anti-Fragmentation | Pass | The definitions view is transport-shared, so MCP and API expose the same additive field by construction; tokens are the single source every page reads |
| VIII — Eval-Gated Promotion | N/A | No model, no cell |
| IX — Evidence Over Claims | Pass | The gate doubles rather than narrows: dark ships only because the lane covers it; the font's provenance is asserted by a row, not asserted by a README |
| X — Decision Record Governs | Pass | ADR-0034 (portal stays thin) and ADR-0039 (never-acts stays visible) consumed; ADR-0004's provenance discipline applied to the font; no new ADR |

**Gate result**: PASS — proceed.

## Project Structure

### Documentation (this feature)

```text
specs/034-portal-visual-identity/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions F1–F9
├── data-model.md        # Phase 1 — tokens, type roles, the provenance record, the packs field
├── quickstart.md        # Phase 1 — validation scenarios
├── contracts/
│   └── conformance.md   # Who runs what; the lane's doubling
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/surfaces/portal/static/portal.css        # rewritten around tokens: palette + type roles once,
                                             #   light and dark, every rule reads tokens
src/surfaces/portal/static/fonts/            # NEW: roboto-variable.woff2 + OFL.txt + PROVENANCE.md
src/surfaces/portal/templates/*.html         # eight templates onto the roles; decision-comments
                                             #   kept, premises updated where the restyle moves them
src/surfaces/api/definitions.py              # AgentDefinitionView gains `packs` (additive, read-only,
                                             #   resolved from the fabric beside the ceiling)
src/surfaces/portal/app.py                   # passes definitions' packs through to thread context
                                             #   (the only portal Python line that changes)
tests/a11y/conftest.py                       # page fixtures parametrized over color_scheme
tests/component/test_portal_identity.py      # NEW: token discipline; greyscale dispositions;
                                             #   font digests vs provenance; unknown-pack renders clean
tests/conformance/api/…                      # the additive packs field's shape row (existing file grows)
```

**Structure Decision**: the stylesheet is rewritten in place rather than split — one file was
a property worth keeping (no build step, one thing to audit), and tokens give it the structure
it lacked. The lane is parametrized rather than duplicated: the same rows, twice the states.

## Dependency order

US1 (type roles + tokens + both themes, behind the doubled gate) is the core and lands first
with US3 folded in — the gate extension IS how US1 is proven. US2 (the packs field and the
stripes) follows: it is the only part that touches Python and it reads the tokens US1 defines.

## Complexity Tracking

No violations to justify.
