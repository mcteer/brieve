# Contract: Conversation operations, both transports

Every operation below exists on the API and on MCP, reaches the same shared function, and is
asserted by a parity row. The portal reaches only these operations, and the containment
session's scripted run exercises each one (FR-027/027a, SC-013).

## `POST /ask` (amended) · MCP tool `ask` (amended)

Request adds optional `conversation_id`. Response adds `conversation_id` (always),
`exchange_seq` (always), `context_note` (only when exchanges were dropped at the bound).

| Case | Behaviour |
| --- | --- |
| No `conversation_id` | Create conversation from this ask; title derived from the question; answer exactly as standalone (no context, no inheritance). |
| Valid own `conversation_id` | Build carried context per the context contract; answer; append exchange. |
| Unknown / other subject's / other tenant's id | `404 no_such_conversation` before any model call, any routing, any read. Identical wording on both transports — existence of another's conversation is never confirmed. |
| Empty question | Existing 400 refusal, unchanged, no exchange stored. |
| Provider fault mid-ask | Existing 5xx behaviour; **no exchange is stored** — the transcript only ever contains asks the platform answered, declined, or refused. |

Routing: a question with its own signal routes on its words; a signal-less question inherits the
most recent exchange's `source`; a signal-less first ask takes the guidance floor. Recorded as
`inherited_route` in the descriptor.

## `GET /ask-conversations` · MCP tool `ask_conversations`

Returns the caller's own conversations in the caller's tenant, newest `last_asked_at` first:
`[{conversation_id, title, last_asked_at, exchanges}]`. No exchange bodies. Empty list is a
valid answer; an unreadable store is 503, never an empty list (fail closed, not fail silent).

## `GET /ask-conversations/{id}` · MCP tool `ask_conversation`

Returns the conversation and every exchange in seq order, each with its stored `outcome`
verbatim. Owner/tenant miss → the same `404 no_such_conversation`.

## `DELETE /ask-conversations/{id}` · MCP tool `delete_ask_conversation`

Hard-deletes the conversation and its exchanges. Returns 204. Owner/tenant miss → same 404.
MUST NOT touch `audit_entries` — asserted by a row that compares the trail before and after
(SC-006). Portal reaches this only through its confirmation page.

## Catalogue

`specs/008-northbound-api/contracts/operations.snapshot.json` gains the three GET/DELETE
operations. The portal containment session performs: list (empty), ask (new conversation), ask
(follow-up), list (populated), get, delete-confirm page, delete — and the uncatalogued-request
assertion stays at zero.

## Conformance obligations

| Row | Lane |
| --- | --- |
| Same operation, both transports, same outcome (list/get/delete/ask-in-conversation) | fast lane, hermetic |
| Foreign and cross-tenant ids answer 404 identically on both transports | fast lane, hermetic |
| Delete leaves the trail byte-identical | fast lane, hermetic |
| Signal-carrying question routes identically standalone vs in-conversation (SC-010) | fast lane, hermetic |
| Signal-less follow-up inherits, both directions (SC-010a) | fast lane, hermetic |
| Follow-up answerability 9/10 (SC-002) and after-decline parity (SC-011a) | live lane, run by Dan McTeer before promotion — not blocking CI |

**Result of the SC-002 / SC-011a run, 2026-08-04** (ten signal-less follow-ups, three of them
after a declined exchange, at the provider seam plus the served walk-through):

    on-subject                9/10   (threshold 9/10)
    after-answer answered     7/7
    after-decline answered    2/3

The single miss follows a question about a module that does not exist, where declining is the
right answer. The first run scored **6/10** and is why retrieval now sees the conversation's
subject — see the commit that changed it.
