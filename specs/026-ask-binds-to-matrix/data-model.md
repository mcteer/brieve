# Data model: 026 — asking binds to the Qualified Model Matrix

**Phase 1.** One new operator-authored record, three payload fields on an existing sealed-core
event, and a disposition vocabulary. Nothing is persisted by the platform — the record is authored
into the trust fabric by an operator, like the ceiling and the matrix it sits beside.

---

## Ask binding record

`harness-authority/data/ask-bindings` — operator-authored, read-only to the platform.

| Field | Rule |
| --- | --- |
| `schema_version` | Required, `1`. Absent or newer refuses (`unsupported_schema_version`) — the ceiling's rule, verbatim |
| `guidance_cell` | Optional. A cell reference (`pack:model:role`) whose role MUST be `ask` |
| `estate_cell` | Optional. Same rule |

- **Either cell may be omitted** — a source with no cell named refuses *for that source alone*
  (FR-005a). Both omitted is a well-formed record that refuses everything, which is an operator
  saying "not yet" legibly.
- **A cell reference naming a role other than `ask` refuses at parse** (`malformed_record`) — a
  mis-authored binding fails when written about, not when first asked through.
- **The record names cells; it never defines them.** Whether a named cell is green, withdrawn, or
  absent is the matrix's to say, at resolution. The two records are both operator-authored and can
  disagree; disagreement refuses (`unqualified_cell`), never resolves to whichever was written
  last.

## Resolution (`core.authority.ask_binding`)

`resolve_ask_cell(source, binding, cells, available)` → `(QualifiedCell, fallback | None)`, or
raise `ResolutionRefused`.

- Looks up the bound cell for `source` (`guidance` | `estate`), then delegates to the existing
  `resolve_with_fallback` — **no branch of its own**, so the no-third-branch property is inherited
  rather than re-established.
- `ResolutionRefused.reason_code` distinguishes: `unbound` (no record, or no cell for this
  source), `unqualified_cell` (named but not green for `ask`), `unsupported_schema_version` /
  `malformed_record` (parse), and the fabric reader's own unreadable failure (F4 / SC-004).
- **Ordering is the caller's obligation**: the surface resolves before the provider exists in
  scope. Same shape as 020's `resolve_bound_model` → `build_chooser`.

## The `ASK_ANSWERED` record — sealed core, three additive fields

| Field | Value |
| --- | --- |
| existing fields | unchanged (`subject_user_id`, `corpus_digest`, `model`, `disposition`, `source`) |
| `cell` **(new)** | The cell that authorised the answer — the one actually used. Empty on refusal |
| `bound_cell` **(new)** | The cell the binding named for this source. Empty when `unbound` |
| `cell_disposition` **(new)** | `pinned` \| `fallback:<reason>` \| `refused:<reason>` \| `not_applicable` |

- **Substitution is FR-006 satisfied in one record**: `bound_cell` is the pinned one, `cell` is
  the used one, `cell_disposition` carries the reason. No run id is fabricated and no second
  sealed-core payload is generalised (research F3).
- **Every call site has a defined value (analysis U4 — seven sites, measured).**
  `cell_disposition` describes the **resolution outcome**, and only that:
  - Answered, and refusals occurring **after** resolution succeeded (`scope_empty`,
    `provider_unavailable`): the resolution outcome stands — `pinned` or `fallback:<reason>`.
    The `disposition` field already says the ask failed later; overwriting the resolution
    outcome would erase the fact that governance passed.
  - The three governance refusals: `refused:<reason>` mirroring the disposition.
  - A `neither` decline: **`not_applicable`** — no source was consulted, so there was no cell
    question to answer. Not an empty string, which T008 reserves for "not yet wired".
- **Principle V review covers all three fields** (Dan McTeer, before merge). The exact-payload
  row in `tests/component/test_answering.py` grows by exactly these keys, in the same change.

## Refusal dispositions (values of the existing `disposition` field)

| Value | Meaning | Who acts |
| --- | --- | --- |
| `unbound` | No binding record, or none for this source — nobody has decided | An operator authors a binding |
| `unqualified_cell` | The binding names a cell the matrix does not qualify (absent, withdrawn, or wrong role) | An operator re-binds, or evaluation earns the cell |
| `matrix_unreadable` | The trust fabric could not be read | Whoever owns the outage |

- All three are **recorded via `record_ask` before the refusal returns** (SC-008), and all three
  are safe to show the caller — none leaks more than "refused" already does.
- `unqualified_cell` deliberately does not distinguish absent/withdrawn/wrong-role **to the
  caller**; the trail's `bound_cell` plus the matrix record answer that for an investigator.

## Ask authority (fixture collaborator)

What `surface_under_test` shares between both surfaces — a binding source and a matrix source,
in-memory in tests, fabric-backed in assembly.

- **Default `None` = every ask refuses `unbound`.** The fixture MUST NOT auto-qualify an injected
  provider (research F5) — that would rebuild "configured = qualified" inside the harness, and a
  contract row asserts the default is refusal so the trap has a tripwire.
- `qualified_ask_authority(model=...)` builds a binding + matrix pair qualifying `model` for both
  sources — called **explicitly** by rows that answer.

## State transitions

None. A binding is authored, read, and either resolves or refuses. Nothing here has platform-side
lifecycle — withdrawal and qualification remain the matrix's, unchanged.
