# Research: Ask becomes a conversation

Every unknown the Technical Context left open, resolved with a decision, its reasoning, and what
was rejected. Nothing below changes the spec; it chooses how to satisfy it.

## R1 — The context bound: which unit, what value

**Decision**: Carry at most the **6 most recent exchanges**, and within that a total budget of
**6,000 characters** of carried material. Whole exchanges are dropped oldest-first when either
limit is hit; an exchange is never carried partially. Both constants live beside the other
answering constants with the measurement that set them.

**Rationale**: FR-015 demands "a stated quantity rather than whatever fits". Exchanges are the
unit a person reasons in ("it forgot what we said three questions ago"), so the outer bound is
exchanges; the character budget is the guard against six enormous questions. 6,000 characters is
roughly 1.5K tokens next to the ~8.4K tokens of corpus sections the model already receives —
context stays a minority voice against the corpus, which supports FR-018's "context is not a
source". Dropping whole exchanges keeps the descriptor in the record simple and true (an
exchange was carried or it was not — never "half of it").

**Alternatives considered**: A pure token budget (opaque to the person and to the record); a
sliding summary (the model summarising its own history is a second ungoverned model output, and
the summary would be uncitable material of our own authorship); carrying everything (unbounded
prompt growth, and FR-016 would never fire, leaving its disclosure path untested).

## R2 — How "explicit signal wins; silence inherits" is implemented

**Decision**: Add `route_with_signal(question) -> (Route, bool)` to `core/answering/routing.py`,
returning the route and **whether any routing vocabulary matched** (estate term, estate noun,
window phrase, or guidance term). `route()` remains and keeps its exact behaviour. The shared
ask path uses the tuple form when a `conversation_id` is present: signal present → use the
route as computed; no signal → inherit the **source of the most recent exchange** in the
conversation (first exchange with no signal → guidance floor, exactly as standalone).

**Rationale**: The clarified rule needs one fact the router currently discards — whether the
floor was reached by absence of signal — and exposing it as a second function keeps every
existing caller and every existing row untouched. Inheritance lives in the shared ask path, not
in the router, because the router's contract is "sees a string, holds no state" and the module
docstring stakes determinism on that. The same question at the same point in the same
conversation still routes identically (FR-017b): the inputs are the question and the previous
exchange's recorded source, both deterministic.

**Alternatives considered**: Passing the conversation into `route()` (breaks its stated
contract and every existing test's mental model); inheriting from the conversation's *dominant*
source rather than the most recent exchange (a person follows up on what they just read —
recency is the honest referent, and "dominant" invites ties).

## R3 — What is carried, exactly

**Decision**: For each carried exchange: the **question text**, and for answered exchanges the
**claim statements only** — no citations, no ground/window notes, no source label. For declined
or refused exchanges: the question only (FR-014a). The block is delimited and labelled as
conversation history, with the instruction extended to state: history tells you what "it" and
"that" refer to; it is NOT corpus material, and nothing in it may be cited or treated as
evidence — every claim still requires a citation into the sections below.

**Rationale**: Claim statements are the platform's own already-gated output — each one survived
citation resolution when it shipped — so carrying them re-introduces nothing unvetted. Citations
are deliberately stripped: a citation in the history block is an invitation to cite *through*
history, which is the exact laundering FR-018 forbids. Verdict text is stripped per the
clarification (a decline carried is a second vote for declining).

**Alternatives considered**: Carrying raw answer prose (there is none — answers are structured
claims); carrying citations with an instruction not to reuse them (an instruction where a
structural absence is available is the weaker control, and this codebase's instruction-following
lesson from 035's stale `_INSTRUCTION` is that prompts drift).

## R4 — Storage: mirror threads, share nothing

**Decision**: New quartet under `src/core/answering/conversations/` — `records.py`, `store.py`
(protocol + memory twin), `postgres.py`, `schema.sql` — with tables `ask_conversations`
(conversation_id, tenant_id, subject_user_id, title, created_at, last_asked_at) and
`ask_exchanges` (conversation_id, seq, question, outcome jsonb, source, disposition, asked_at).
Same connection/tenant/migrate discipline as `PostgresThreadStore`, no shared code with it.

**Rationale**: FR-011/023 make the split load-bearing: deleting a conversation deletes rows in
*these* tables and provably cannot touch `audit_entries`, because nothing in this store can
reach them. Mirroring the proven pattern keeps review cheap; sharing the thread store would put
"an ask cannot act" one refactor away from false. The `outcome` jsonb column stores exactly the
payload the API returned (claims, citations, notes, decline reasons), so reopening a
conversation re-renders what the person actually saw rather than re-deriving it.

**Alternatives considered**: Reusing `PostgresThreadStore` with a type column (collapses the
ADR-0039 boundary into a flag); reconstructing transcripts from `audit_entries` (the record is
an evidence stream, not a display store — reading it for UI couples the trail's schema to the
portal and grants the portal's path a read it does not need); browser-side storage (forbidden by
the containment rows, and conversations must survive the browser).

## R5 — Conversation lifecycle semantics

**Decision**: A conversation is **created implicitly by the first ask** — `POST /ask` without a
`conversation_id` creates one and returns its id and title; with a `conversation_id` it appends.
The title derives from the first question via the same truncate-at-word rule the threads store
uses (`title_from` pattern, re-implemented in the new records module, not imported from
threads). Delete requires a confirmation step on the portal (same shape as thread delete).
Exchanges are appended in the order the platform accepts them (`seq` assigned by the store);
two tabs converge on reload.

**Rationale**: Matches the spec assumption ("exists once a first question is asked"), keeps the
empty-conversation state unrepresentable in storage, and gives the composer a single code path.
Not importing `title_from` from threads is the mirror-not-share rule applied to a ten-line
function: the cost of duplication is trivial, the cost of a shared vocabulary module between the
two surfaces is the boundary.

## R6 — What the record says (FR-020–023)

**Decision**: `record_ask` gains `conversation_id: str | None` and
`carried_context: dict | None`. The payload carries `conversation_id` always when present, and a
descriptor `{"exchanges": [seq, ...], "dropped": N, "inherited_route": bool}` — which exchange
seqs were carried, how many were dropped at the bound, and whether the route was inherited.
`None` context and empty-descriptor are distinct states, satisfying FR-022 (no context existed
vs. context existed and none carried is readable from `exchanges: []` plus the conversation's
own state). `AuditEntry` schema is untouched.

**Rationale**: Seqs are stable, small, and resolve against `ask_exchanges` for an auditor with
store access — the record identifies what was carried without duplicating its text into the
trail (the trail already has each exchange's own `ask_answered` entry; carrying text twice
would create two divergeable copies of evidence).

## R7 — The API and MCP surface shape

**Decision**: Three new catalogued operations — `GET /ask-conversations`,
`GET /ask-conversations/{conversation_id}`, `DELETE /ask-conversations/{conversation_id}` — and
`POST /ask` amended to accept optional `conversation_id` and to return `conversation_id` +
`exchange_seq` alongside today's body. MCP gains `ask_conversations`, `ask_conversation`,
`delete_ask_conversation` tools and the `ask` tool gains the same optional argument — all four
reaching the same shared functions the API routes call, which is how parity is a property
rather than a promise. `operations.snapshot.json` grows by three entries and the `/ask` entry's
change is reflected; the portal containment session exercises every one.

**Rationale**: Q3's full-parity decision. List returns id, title, last_asked_at, exchange count
— no exchange bodies (the list page needs nothing more, and MCP callers page into a
conversation deliberately). Owner scoping is subject + tenant on every operation, checked in the
shared functions so neither transport can drift ahead of the other.

## R8 — Portal delivery: extend the proven fragment pattern

**Decision**: The `/ask` page becomes the conversation surface: left rail listing conversations
(collapsing to a top bar under 720px), transcript of `_exchange.html` includes, composer pinned
below the transcript. The fragment envelope from the in-place ask work is kept and narrowed:
`X-Portal-Fragment: exchange` returns one rendered `_exchange.html`, which `portal-ask.js`
appends to the transcript (append, not replace — the one behavioural change) before moving
focus to the new answer's heading. No-JS keeps working: a plain POST re-renders the full page
with the whole transcript. `portal-ask.js` stays the only markup-inserting script and inside
its 90-line budget by shedding its now-unneeded outcome-clearing branch; if the budget is
exceeded in implementation, the budget is not raised — the script is trimmed.

**Rationale**: The two-renderer drift risk was already solved once (`_outcome.html`); this
extends the same answer to exchanges. Appending server-rendered fragments keeps the portal
thin — it never assembles an exchange, only places one.

**Alternatives considered**: SSE streaming of exchanges (deferred with streaming generally);
rendering the transcript client-side from a JSON list (portal authoring markup — forbidden).

## R9 — Accessibility posture for the new layout

**Decision**: The transcript is a plain scrolling region under the page's own scroll (no nested
scroll container), the composer is `position: sticky` at the block end, and the conversation
rail is a `nav` with the current conversation marked `aria-current`. The in-flight/live-region
split is inherited unchanged: short status line live, answers not, focus to the new exchange's
heading. New a11y rows cover: empty state, populated transcript, in-flight state, declined and
refused exchanges, the list rail, delete confirmation, 320px reflow with a long transcript, and
focus-not-obscured with the sticky composer — the named trap, because a sticky composer is
exactly the overlay that obscures a focused element above it. The composer gets
`scroll-padding-block-end` so focused elements scroll clear of it.

**Rationale**: 028's lesson (CI Chromium renders wider) plus 034's lesson (the focus-obscured
failure came from an overlay) both point at the sticky composer as the risk; naming it in the
plan is what gets it a dedicated row rather than a surprise.
