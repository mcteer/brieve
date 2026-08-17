# Data model: Ask and Build share one conversational shell

Almost nothing here is storage. The entities are tokens, type roles, the additive result
field, font provenance, and the shell landmarks. Intake text is already a `RunInput`; this
feature discloses it.

## The design tokens (CSS custom properties, the single source)

Defined once in `:root`. There is no second theme block.

| Token group | Members | Rule |
| --- | --- | --- |
| Ground | `--bg`, `--elev`, `--elev-2` | page, list, raised panel |
| Text | `--ink`, `--muted` | body and secondary. `--muted` is the only secondary *text* colour (F4) |
| Rules | `--line` | borders and hairlines — not a text colour |
| Chrome | `--copper`, `--copper-dim`, `--cta`, `--cta-ink` | mark, primary action, current conversational state. `--copper` may colour text (clears 4.5 on `--bg` / `--elev`). `--cta` is the copper fill; `--cta-ink` is `#1a1610` |
| Verdict / phase | `--ok`, `--denied` | complete / allowed vs failed / denied. Distinct from chrome |
| Product | `--vault`, `--terraform` | 034 identity colours, both unused-as-chrome; never inverted |
| Type roles | `--font-prose`, `--font-control`, `--font-heading`, `--font-evidence` | F5. Heading token equals the prose stack |

**Discipline is a row**: no colour literal outside the `:root` token block; no `style=` colour
in any template (SC-007).

Hex values (designed theme, F4):

| Token | Value |
| --- | --- |
| `--bg` | `#0b0c0e` |
| `--elev` | `#111318` |
| `--elev-2` | `#171a21` |
| `--ink` | `#e8e6e1` |
| `--muted` | `#8f8c84` |
| `--line` | `rgba(232, 230, 225, 0.08)` |
| `--copper` | `#c4a574` |
| `--copper-dim` | `#7a6548` |
| `--cta` | `--copper` |
| `--cta-ink` | `#1a1610` |
| `--ok` | `#6eab7c` |

`--denied` keeps 034's dark denied token unless the identity row shows it fails on `--bg`;
then it is raised until it clears 4.5. Product tokens unchanged from 034.

## The type roles (assignment table)

| Content | Role |
| --- | --- |
| Page + section headings, thread titles, answer titles | prose (Inter) |
| Claims, messages, ledes, notices, footer | prose (Inter) |
| Buttons, icon rail, list labels, composer field, New | control (Inter) |
| Record hashes, dispositions, timestamps, correlation ids, citations, phase names, chips, never-acts, breadcrumbs | evidence (IBM Plex Mono) |

Every piece of template content maps to exactly one role.

## The additive view field

`RunResultResponse` (`src/surfaces/api/runs.py`), served by `GET /runs/{run_id}/result`
(API and MCP; portal already relays this GET):

| Field | Type | New? | Rules |
| --- | --- | --- | --- |
| `run_id` | str | no | unchanged |
| `disposition` | str | no | unchanged |
| `result` | Any \| None | no | unchanged |
| `stop_reason` | str \| None | no | unchanged |
| `propose_progress` | dict \| None | no | unchanged (047) |
| `intake_message` | str \| None | **yes** | `ThreadStore.get_run_input(run_id).message` when that row exists; **`null` when it does not or cannot be read**. Never an empty string standing in for missing. Never derived from the rail title. Additive, read-only. Parity by construction (shared model) |

Portal pass-through: `propose_run` context gains `intake_message` from the existing result
relay. SSE does not need to stream it — the text does not change during the run.

Failure: an unreadable store leaves `intake_message` null and still returns
`propose_progress`. The page omits `.you`. Inventing the prompt is a defect a row can find
(template contains only `{{ intake_message }}` inside a guard).

## Font provenance

`src/surfaces/portal/static/fonts/PROVENANCE.md` — one document, two families:

| Field | Content |
| --- | --- |
| Repository / commit / upstream path | pinned per family, written at vendoring |
| Licence | copied from that family's `OFL-*.txt`; RFN presence recorded |
| Retrieved | date |
| Conversion | exact command + pinned `fonttools` version |
| Digests | sha256 for each vendored woff2, each OFL file, and the upstream source |

Verified by `tests/component/test_portal_identity.py` recomputing those digests. Exact
vendored files: `inter-variable.woff2`, `ibm-plex-mono-regular.woff2`,
`ibm-plex-mono-medium.woff2`, `OFL-inter.txt`, `OFL-ibm-plex-mono.txt`. Roboto's files and
digests are absent after FR-016.

## Shell landmarks (not stored)

| Landmark | Ask | Build empty | Build in flight |
| --- | --- | --- | --- |
| Icon rail | current = Ask | current = Build | current = Build |
| Work list | Conversations | Builds | Builds |
| Thread | spine of Q/A | quiet start | `.you` from `intake_message` + phase nodes |
| Reading column | `.thread .inner` max-width **680px** | same | same |
| Composer | POST Ask, max-width **880px** | POST Build, 880px | no POST; New build link only if chrome is shown |

## Spine node states (Build)

| Status (047 `data-phase`) | Person's label (FR-006) | Shape | Label |
| --- | --- | --- | --- |
| `completed` | completed | filled `--ok` | status word visible |
| `active` | current | filled `--copper` | status word visible |
| `pending` | waiting | empty circle | status word visible |
| `failed` | failed | bordered `--denied` | status word + `reason` |

Ask answer nodes are completed-shaped; they are not 047 phases.
