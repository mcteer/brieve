# Data model: 028 — the portal learns to ask

**Phase 1.** Nothing is stored, so this is a model of what one page renders. The portal holds a
question for the life of one request and an answer for the life of one response; the only durable
record of either's *occurrence* is the API's, unchanged.

---

## The ask page's states

One template, four blocks, dispatched in a fixed order — the order is the same one the relay's
own vocabulary imposes:

| Order | State | Selected by | Renders |
| --- | --- | --- | --- |
| 1 | **Unaskable** | `not response.reachable` (relay status 0) | "The platform could not be asked." Distinct from every refusal — nothing about access changed. |
| 2 | **Refused** | HTTP status not 2xx | The API's own `detail` prose, **verbatim** (research F1). No portal-authored cause. |
| 3 | **Declined** | `disposition == "declined"` | `declined_reason` and which `source` was consulted — presented as an answer, not a failure. |
| 4 | **Answered** | `disposition == "answered"` | Claims, shaped per source (below). |

The dispatch order is load-bearing: reachability is decided by the relay before any body exists,
and a refusal has no `disposition` to read.

## A claim, shaped per source

| Source | Claim carries | Rendered as |
| --- | --- | --- |
| `guidance` | `statement`, `citations[]` (URLs) | Statement with followable links — each citation resolves into the pinned corpus's published home |
| `estate` | `statement`, `references[]` (entry hashes) | Statement with **inert** identifiers: shortened prefix shown, full hash present in the page, never an anchor |

**Why a hash is never a link** (FR-007): there is nothing for it to resolve to in a browser, and a
dead link teaches the reader that references are decorative. The identifier's job is to be carried
to whoever can show the record.

## The form

| Field | Rule |
| --- | --- |
| `question` | Required, non-empty after strip. The only field — no source selector, no model selector (FR-001: the person does not choose; a parameter for either would be a request to widen scope, the same reason `AskRequest` has one field). |

Expectation text is part of the form, not an afterthought (FR-005a): an answer usually takes a
minute or two, leave the page open. The waiting affordance is the browser's native busy state
(research F6) — no client machinery.

## The relay call

| Property | Value |
| --- | --- |
| Operation | `POST /ask` with `{"question": ...}` — the catalogued operation, unmodified |
| Token | the signed-in person's own, from the server-side session (FR-011's portal half) |
| Patience | `ASK_PATIENCE = 180.0`, passed per-call; every other call keeps the relay default (SC-004) |

## What is deliberately absent

- **No portal-side record** of the question, the answer, or the ask having happened — the API's
  record is the record, and a second one would eventually disagree.
- **No ask history page.** An answer lives exactly as long as the response that carried it; a
  person who wants it again asks again (a question is not an act; it is also not free, and the
  form's expectation text says so).
- **No new session state.** The existing server-side session authenticates the relay call; nothing
  about an ask is remembered between requests.
