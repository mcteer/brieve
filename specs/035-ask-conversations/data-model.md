# Data Model: Ask becomes a conversation

Two stored entities, one computed value, and two amended payloads. Nothing here touches the
sealed audit schema; `ask_answered` gains payload keys inside its existing jsonb column.

## AskConversation (stored, `ask_conversations`)

| Field | Type | Rules |
| --- | --- | --- |
| `conversation_id` | str (uuid) | Assigned by the store on first ask. Never reused. |
| `tenant_id` | str | Required. Every read and write filters on it (FR-013). |
| `subject_user_id` | str | The creator. Every read and write filters on it (FR-012). |
| `title` | str | Derived from the first question, truncated at a word boundary ≤ 60 chars (FR-008). Never user-supplied in this feature. |
| `created_at` | timestamptz | Store-assigned. |
| `last_asked_at` | timestamptz | Updated on every append; the list sorts by it, newest first. |

**State**: exists → deleted (hard delete of conversation and its exchanges; FR-011). No other
transitions. An empty conversation is unrepresentable — creation happens with the first
exchange, atomically.

## AskExchange (stored, `ask_exchanges`)

| Field | Type | Rules |
| --- | --- | --- |
| `conversation_id` | str | FK to `ask_conversations`, cascade on delete. |
| `seq` | int | Store-assigned, dense from 1, acceptance order (concurrency converges by seq). Primary key with `conversation_id`. |
| `question` | str | As submitted, after the existing empty-question refusal. |
| `source` | str | `guidance` or `estate` — what the ask actually consulted; the value inheritance reads (R2). |
| `disposition` | str | `answered`, `declined`, `refused` — decides transcript rendering and what context carries (FR-014a). |
| `outcome` | jsonb | The exact response body the API returned for this ask — claims with citations, notes, decline reason. Reopening re-renders what was seen, never re-derives it. |
| `asked_at` | timestamptz | Store-assigned. |

**Invariants**: an exchange belongs to exactly one conversation; its `outcome` is written once
and never updated; deleting the conversation deletes exchanges and provably nothing else — the
store holds no reference to `audit_entries` (FR-023, SC-006).

## CarriedContext (computed, never stored)

Built per ask by `build_context(conversation, bound)` in `core/answering/context.py`.

| Property | Rule |
| --- | --- |
| Membership | Up to the 6 most recent exchanges within a 6,000-character budget; whole exchanges only, oldest dropped first (R1, FR-015/016). |
| Per answered exchange | Question text + claim statements. No citations, no notes, no source label (R3, FR-018). |
| Per declined/refused exchange | Question text only (FR-014a). |
| Descriptor | `{"exchanges": [seq…], "dropped": N, "inherited_route": bool}` — what the record carries (R6, FR-020–022). |
| Disclosure | `dropped > 0` produces a caller-visible note that not all of the conversation was carried (FR-016, SC-012). |

## Amended: `POST /ask` request/response

| Field | Direction | Rule |
| --- | --- | --- |
| `conversation_id` | in, optional | Absent → create conversation. Present → append; unknown/foreign/cross-tenant id → 404, identical on both transports. |
| `conversation_id` | out | Always present. |
| `exchange_seq` | out | The seq this ask was stored as. |
| `context_note` | out, optional | Present when exchanges were dropped at the bound. |

## Amended: `ask_answered` payload (jsonb keys added; `AuditEntry` unchanged)

| Key | Rule |
| --- | --- |
| `conversation_id` | Present whenever the ask belonged to a conversation. |
| `carried_context` | The descriptor above; `{"exchanges": [], …}` when a conversation existed and nothing was carried — distinguishable from the key being absent (first ask / no conversation), satisfying FR-022. |

## Relationships

```text
AskConversation 1 ── n AskExchange          (cascade delete)
AskExchange     1 ── 1 ask_answered entry    (by construction: each ask writes one; the record
                                              carries conversation_id + seq, the store never
                                              points at the trail)
CarriedContext  built from AskExchange rows; exists only inside one ask's handling
```
