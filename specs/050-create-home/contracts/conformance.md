<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 050 — Create home

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Designed-theme axe + keyboard (24×24, 320px, focus, text-spacing) | `tests/a11y` | Chromium (the lane's CI job) | **Blocking from this feature** |
| One empty home: `GET /` has mark, Let's Create, slider on Ask; `GET /ask` is 303 to `/` | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Combined history: Ask + Build rows; each named Ask or Build; search filters visible text | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Unreadable Ask or Build list is a notice, not an empty claim | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Slider: empty home Ask posts `/ask` not `/`; `portal-composer.js` sets Build; locked on open item; no-JS still posts `/ask` | `tests/component/test_portal_asks.py` / `test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Open item: title present; greeting absent; composer has no `POST /` on `propose_run.html` | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Build Stop in the bubble is `POST /runs/{id}/stop`; failed stop does not look ended | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Ask Stop abort does not claim the answer ended | `tests/component/test_portal_asks.py` | Nothing | **Blocking from this feature** |
| + and Projects do not navigate and do not attach | `tests/component/test_portal_shell.py` | Nothing | **Blocking from this feature** |
| Login without `next` lands on `/`; + New is `/` with Ask | `tests/component/test_portal_session.py` | Nothing | **Blocking from this feature** |
| Settings, profile (`subject_user_id`), logout at the bottom of the column | `tests/component/test_portal_identity.py` | Nothing | **Blocking from this feature** |
| Mark digest matches `mark/PROVENANCE.md`; no third-party URL; no icon-rail verbs left as the only Settings path | `tests/component/test_portal_identity.py` | Nothing | **Blocking from this feature** |
| New shell colours are Nocturne tokens only — no page-local hex, no reference orange | `tests/component/test_portal_identity.py` | Nothing | **Blocking from this feature** |
| Ask isolation (047 P8 / SC-010) | existing propose conformance P8 | Nothing | **Already green — must stay** |
| Decision-comments still present, premises current (FR-017) | identity / shell template scan | Nothing | **Blocking from this feature** |
| Human half of WCAG 2.2 AA | standing record, re-walked | **Named runner: Dan McTeer** | **Owed** |

## What these rows assert

- Empty Ask and empty Build are gone; the slider is the verb. Without
  `portal-composer.js` the form posts `/ask`.
- History is this person's existing Ask conversations and Builds, merged, searchable
  without a new operation. An unreadable kind is a notice, not an empty claim.
  Operator `/run` threads are not in the list.
- Stop is the stops that already exist.
- The HashiCorp mark is a pinned file, not a runtime fetch and not a redrawing.
- Settings remains reachable from the shell.

## What these rows refuse to assert

- Taste against the Claude screenshot.
- That Ask Stop cancelled the model (it cancels the portal wait).
- A projects product or attach-context.
- Light-theme conformance.
