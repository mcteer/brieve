# Data model: The portal gets a visual identity

Almost nothing here is data in the storage sense — the entities are the stylesheet's tokens,
one additive view field, and one provenance record. Nothing persists, nothing migrates.

## The design tokens (CSS custom properties, the single source)

| Token group | Members | Rule |
| --- | --- | --- |
| Ground | `--page`, `--raised` | page and panel backgrounds |
| Text | `--ink`, `--muted` | body and secondary |
| Rules | `--rule`, `--rule-soft` | borders and hairlines |
| Action | `--link`, `--link-bright`, `--cta`, `--cta-ink` | `--link` clears AA on `--page`; `--link-bright` is non-text only (focus ring, active underline); the CTA pair flips together |
| Verdict | `--allowed`, `--denied` | semantic, never decorative, distinct from Action |
| Product | `--vault`, `--terraform` | identity, both themes, never inverted |
| Type roles | `--font-heading`, `--font-prose`, `--font-control`, `--font-evidence` | F6's stacks; every `font-family` reads one of these |

Defined in `:root` (light) and redefined under `@media (prefers-color-scheme: dark)`.
**Discipline is a row, not a convention**: no colour literal outside the token blocks; no
`style=` colour in any template (SC-004).

## The type roles (assignment table)

| Content | Role |
| --- | --- |
| Page + section headings, thread titles | heading (serif stack) |
| Claims, messages, ledes, notices, footer prose | prose (Roboto) |
| Buttons, nav, form labels, select/textarea chrome | control (system sans) |
| Record hashes, dispositions, timestamps, correlation ids, citations, the result block | evidence (mono) |

Every piece of template content maps to exactly one role; a piece that maps to none is a
finding for the tasks, not a judgement call in CSS.

## The additive view field

`AgentDefinitionView` (transport-shared, `surfaces/api/definitions.py`):

| Field | Type | New? | Rules |
| --- | --- | --- | --- |
| `agent_definition_id` | str | no | unchanged |
| `may_start` | bool | no | unchanged |
| `packs` | tuple of str | **yes** | resolved from the fabric beside the ceiling; a definition whose packs cannot be read shows `()` — unknown is a state, not an error; additive and read-only, parity by construction (shared view) |

Portal pass-through: the thread page's context already carries `definitions`; each turn's
stripe is looked up template-side from its `agent_definition_id` against that list. No new
route, no new relay call.

Stripe rule (FR-006): one known pack → that product's token; several or none → no stripe, no
reserved space.

## The font provenance record

`src/surfaces/portal/static/fonts/PROVENANCE.md`:

| Field | Content |
| --- | --- |
| Repository / release | the canonical Roboto upstream, pinned |
| Licence | Apache-2.0, recorded (same licence as this repository) |
| Retrieved | date |
| Conversion | exact command + tool version, if woff2 was produced from released TTF |
| Digests | sha256 per vendored file |

Verified by a component row that recomputes the digests — the row is the verifier, as the
pack loader is for skills.

## The theme (not a stored state)

Theme follows `prefers-color-scheme`. There is no toggle, no cookie, no JS, and therefore no
state model. The accessibility lane emulates the preference per parametrized fixture.
