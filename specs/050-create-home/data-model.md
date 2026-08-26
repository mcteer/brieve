# Data model: Create home

Nothing here is new storage. The entities are presentation rows, the slider verb,
and mark provenance.

## `history_items` (portal-only merge)

Built by **`history_items`** in `src/surfaces/portal/app.py` from the two lists
the portal already loads. Not a catalogue type.

| Field | Source | Rules |
| --- | --- | --- |
| `kind` | derived | `ask` or `build` |
| `verb` | derived | `Ask` or `Build` — the word on the row (not colour alone) |
| `title` | conversation `title`, or existing `_build_rail_title` | never invented |
| `href` | `/ask/{conversation_id}` or `/propose/runs/{run_id}` | existing item addresses |
| `sort_at` | `last_asked_at` or run `created_at` | ISO-comparable; newest first |
| `current` | request path matches `href` | `aria-current="page"` |

**Validation**: omit a kind when that list is unreadable; do not emit a blank
title row; do not merge operator `/run` threads.

## Slider verb

| State | Operable | Value | Form `action` |
| --- | --- | --- | --- |
| Empty home, default | yes | Ask | `/ask` |
| Empty home, person moved | yes | Build | `/` |
| Open Ask | no | Ask | `/ask` |
| Open Build | no | Build | none (Stop form only) |
| + New / sign-in | yes | Ask | `/ask` |

## Open-item title

| Kind | Field shown at top of stage |
| --- | --- |
| Ask | conversation `title` from the existing GET |
| Build | existing build title (same string as the history row) |

Greeting (mark + “Let's Create”) is empty-home only.

## Mark provenance

`src/surfaces/portal/static/mark/PROVENANCE.md`:

| Field | Content |
| --- | --- |
| Source | official HashiCorp brand kit file actually copied |
| Retrieved | date |
| Digest | sha256 of the shipped SVG |
| Trademark | HashiCorp and the HashiCorp logo are trademarks of HashiCorp |
| Permission | maintainer holds written permission (corporate logo) |
| Transformation | none — official file, or official reverse if that is the kit file shipped |

Verified by a component row recomputing the digest. Filename:
`hashicorp-logomark.svg`.

## Shell landmarks (not stored)

| Landmark | Empty home | Open Ask | Open Build |
| --- | --- | --- | --- |
| Left column | New, Projects, search, history, profile, Settings, logout | same | same |
| Stage top | mark + Let's Create | summarized title | summarized title |
| Composer | bubble in the stage, slider operable, default Ask | same bubble, bottom centre, slider locked Ask | same bubble, bottom centre, slider locked Build; Stop = existing run-stop |
| Greeting | present | absent | absent |

## Token and type roles

The redesign **uses** the shipped Nocturne `:root` block (grounds, ink, muted,
violet `--accent`, semantic status) and 048 type roles (Inter prose/control,
IBM Plex Mono evidence). New chrome references those names. This feature does
not introduce a colour literal, a second token block, or a fourth face.
