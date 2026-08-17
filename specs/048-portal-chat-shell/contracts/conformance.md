<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 048 — Ask and Build share one conversational shell

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Every existing axe state on the **designed theme** (SC-004) | `tests/a11y` — `color_scheme="dark"` only; 034's `THEMES` parametrization removed | Chromium (the lane's own CI job) | **Blocking from this feature** |
| Keyboard rows on the designed theme: focus drawn + unobscured, 24×24 targets, 320px reflow, text-spacing | same lane | as above | **Blocking from this feature** |
| Token discipline: no colour literal outside `:root`; no `style=` colour in templates | `tests/component/test_portal_identity.py` | Nothing | **Blocking from this feature** |
| Phase state and dispositions survive greyscale by structure (SC-006) | component rows (pills in `test_portal_identity.py`; spine nodes in `test_portal_shell.py` have border/shape + `.phase-status` text) | Nothing | **Blocking from this feature** |
| Font digests match `PROVENANCE.md`; Roboto files are **absent**; portal fetches nothing third-party (SC-008, FR-016) | component rows | Nothing | **Blocking from this feature** |
| `intake_message` on `RunResultResponse`: present when `RunInput` exists; `null` when missing; never a title slug | `tests/component/test_run_result.py` (API/MCP parity by construction on the shared model; no second serializer) | Nothing | **Blocking from this feature** |
| Portal in-flight Build: quote renders only from `intake_message`; no `POST /` form on `propose_run.html` | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Composer is one flex row, centred, max-width 880px; reading column `.thread .inner` max-width 680px (SC-003) | `tests/component/test_portal_identity.py` CSS assertions | Nothing | **Blocking from this feature** |
| Ask isolation regression (047 P8 / SC-009) | existing propose conformance P8 | Nothing | **Already green — must stay** |
| Icon rail accessible names are Build, Ask, Settings, Sign out | component template scan | Nothing | **Blocking from this feature** |
| Decision-comments inventory: named comments still present with premises current (FR-014, research F9) | `test_portal_identity.py` (`base.html`, `ask.html`); `test_portal_shell.py` (`_exchange.html`, `_outcome.html`) | Nothing | **Blocking from this feature** |
| The human half of WCAG 2.2 AA (judgement criteria automation cannot assert) | standing record from 012/034, re-walked against this identity | **Named runner: Dan McTeer** | **Owed** — visual-judgement half is the act only he performs |

## What these rows assert

- The designed theme exists only because the lane covers it, per state.
- The identity is enforceable: a page-local colour, an off-role font, or a leftover Roboto
  file is a failing test.
- The one payload change is additive, read-only, null-on-miss, and shaped like 047's
  `propose_progress` on the same response.
- In-flight Build cannot start a second propose from the run page.
- The offline property survives.

## What these rows refuse to assert

- Taste. The gate holds the floor; whether it matches the mockups is the maintainer's review
  of the running portal.
- A steer-the-current-run operation. This feature does not add one.
- Light-theme conformance. Light is withdrawn; a row that still parametrizes light is a
  defect.
