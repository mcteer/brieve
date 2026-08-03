<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 034 — the portal's visual identity

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Every existing axe state × BOTH themes (the lane's doubling — SC-001) | `tests/a11y`, fixtures parametrized over colour scheme | Chromium (the lane's own CI job) | **Green** |
| The two previously-uncovered templates gain states: `login_failed`, relay-`refused` (analyze G2) | `tests/a11y/test_wcag.py`, same parametrization | as above | **Green** |
| Keyboard rows × both themes: focus drawn + unobscured, 24×24 targets, 320px reflow, text-spacing | same lane, same parametrization | as above | **Green** |
| Token discipline: no colour literal outside token blocks; no `style=` colour in templates | `tests/component/test_portal_identity.py` | Nothing | **Green** |
| Dispositions survive greyscale by structure (pill + border + text — SC-003) | component rows | Nothing | **Green** |
| Font digests match the provenance record; portal fetches nothing third-party (SC-006) | component rows (digest recompute; template/CSS scan for external URLs) | Nothing | **Green** |
| `packs` on the definitions view: shape, unknown-as-empty, parity-by-construction noted | API conformance rows (existing definitions coverage grows) | Nothing | **Green** |
| Turn stripe: known pack striped, unknown clean with no reserved space | component render rows | Nothing | **Green** |
| Decision-comments inventory: the named template comments still present with premises current | component row over template text (the named list from research F9) | Nothing | **Green** |
| The human half of WCAG 2.2 AA (judgement criteria automation cannot assert) | the standing record from 012's contract, re-walked once against the new identity | **Named runner: Dan McTeer** — the visual-judgement half is the act only he performs; the agent drives the portal to every state for him | **Owed** — the portal is up and the link is in the PR; this is Dan's review |

## What these rows assert

- Nothing ships untested: dark exists only because the lane covers it, per state, per row.
- The identity is enforceable: a page-local colour or an off-role font is a failing test.
- The one payload change is additive, read-only, and shaped like the precedents.
- The offline property survives: no runtime fetch anywhere the scans can see.

## What these rows refuse to assert

- Taste. The gate holds the floor (AA, structure, discipline); whether it is beautiful is the
  maintainer's review of the running portal, not a row.
- Anything about the thread LIST's product — deferred until a thread carries one, recorded in
  the spec rather than approximated by a name heuristic.
