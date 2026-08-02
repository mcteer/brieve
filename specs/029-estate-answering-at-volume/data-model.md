# Data model: 029 — estate answering at real volume

**Phase 1.** Nothing new is persisted. Three shapes change, all additively, and the sealed core is
untouched — FR-006 deliberately lands on the answer rather than the record.

---

## The focus (new, `core/answering/focus.py`)

| Property | Rule |
| --- | --- |
| Input | The question string, nothing else — no roles, no clock, no store |
| Output | `frozenset[AuditEventType]` or `None` (“no focus recognised”) |
| Mechanism | Deterministic term→types table, drawn from the trail’s own vocabulary — the same discipline `routing.py` already documents |
| Composition | The ask path uses `focus ∩ visible`; **intersection, so focus only narrows** (FR-005). Empty intersection falls back to `visible` — “your role cannot see that” must not masquerade as an empty estate while FR-009 holds that question open |

Indicative table (final content is tasks-level, guarded by SC-007 and the guidance regressions):

| Question terms | Focus types |
| --- | --- |
| run, runs, ran | `RUN_START`, `RUN_STOPPED`, `RUN_RESUMED` |
| tool, tools, used | `TOOL_CHOSEN`, `TOOL_OUTCOME` |
| denied, refused | `AUTHORITY_DENIED`, `AUTHORITY_REFUSED` |
| secret, secrets | `EFFECT_OBSERVED` |
| agent, agents, active | `RUN_START` (the record that names a definition) |
| failed, error | `ENFORCEMENT_ERROR`, `RUN_STOPPED` |

## The query request (`EvidenceQueryRequest`, one additive field)

| Field | Rule |
| --- | --- |
| existing fields | unchanged, including `limit` |
| `limit_per_type: int \| None = None` **(new)** | When set with `event_types`, the read returns the newest N **of each type**, still oldest-first overall. `None` is exactly today’s read — every existing caller and row untouched |

Both implementations change together (FR-008): Postgres via one windowed query
(`ROW_NUMBER() OVER (PARTITION BY event_type ORDER BY … DESC)`), the in-memory twin via per-type
bucket fill over the same sort. One query, not one per type.

## The read result (what FR-006 needs that a bare list cannot carry)

| Property | Value |
| --- | --- |
| Entries | As today: scoped, windowed, oldest-first |
| Window accounting **(new)** | Per requested type: how many were returned vs how many matched — `COUNT(*) OVER (PARTITION BY event_type)` in the same query, no second round-trip |

Exact carrier (a `SearchResult` object vs a parallel channel) is tasks-level; the constraint is
that no existing `search()` caller breaks.

## The estate answer (one addition, rendered by both surfaces)

| Field | Rule |
| --- | --- |
| existing fields | unchanged |
| `window_note` **(new)** | Present when any requested type was truncated: what the answer rests on and roughly what was left out — *“Based on the 200 most recent run records of 1,847 today.”* Absent when nothing was truncated, so the common small-estate case renders exactly as before |

## What deliberately does not change

- **`ASK_ANSWERED`** — no payload change, no sealed-core touch, no Principle V review.
- **The access record** (ADR-0035) — still shows the narrowed request; it now simply shows a
  narrower one when a focus applied, which is the same honesty it always had.
- **Scope** — `visible_event_types` and the tenant bound, byte-for-byte.
- **`route()`’s mechanism** — only `ESTATE_TERMS` grows; ties still break toward estate.

## State transitions

None. Every shape above lives for one request.
