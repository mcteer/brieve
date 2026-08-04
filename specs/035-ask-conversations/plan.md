# Implementation Plan: Ask becomes a conversation

**Branch**: `035-ask-conversations` | **Date**: 2026-08-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/035-ask-conversations/spec.md`

## Summary

The ask surface becomes a chat: a transcript of exchanges, a composer at the bottom, conversations that persist per person, and follow-ups answered with bounded context from earlier exchanges. Three clarified decisions shape everything: **explicit routing signal wins and silence inherits** (so context can never pull a signalled question to the wrong source), **a declined exchange contributes its question and never its verdict**, and **full API↔MCP parity** (so ADR-0033 keeps no exception).

The mechanism: a new `ask_conversations` store in core (mirroring the threads store pattern but deliberately separate from it — ADR-0039), a `conversation_id` on `POST /ask` plus three new catalogued operations (list, get, delete) on both transports, a bounded **carried-context block** built server-side from prior exchanges and handed to the existing `answer_question` path, and the `ask_answered` payload gaining `conversation_id` and a context descriptor so the record keeps describing what the model was shown. The audit schema itself (`AuditEntry`) is untouched — only payload keys are added — so sealed core stays sealed.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed, as the whole platform)

**Primary Dependencies**: FastAPI (API + portal), Jinja2 (portal templates), psycopg (Postgres stores), the existing Anthropic adapter for the live answer path. No new dependencies.

**Storage**: Postgres — a new `ask_conversations` + `ask_exchanges` pair of tables owned by a new store in `src/core/answering/conversations/`, mirroring `src/core/threads/postgres.py` (connection handling, tenant scoping, migrate-on-start) without sharing its schema or class. Memory twin for hermetic tests, per "build against the real stack" (Postgres in conformance, memory only where the harness already fakes).

**Testing**: pytest — component rows for the store, context builder, and inheritance routing; hermetic conformance rows for API↔MCP parity and the containment session; the a11y lane for every new page state; one live-lane check for SC-002 (follow-up answerability), runnable via `make evals-live`-style opt-in, never in the fast lane.

**Target Platform**: The deployed dev estate — Nomad-scheduled API and portal containers, Vault-brokered credentials, served via `infra/bin/portal-up`.

**Project Type**: Web service + thin portal client over it (existing structure; no new projects).

**Performance Goals**: An answer with context arrives inside the portal's existing `ASK_PATIENCE` (180s); context assembly adds one indexed Postgres read (< 50ms); the conversation list renders in one query.

**Constraints**: Portal serves its own assets, no build step, no CDN; every static `*.js` under 90 lines, only `portal-ask.js` may insert markup (containment rows); every portal request must be a catalogued operation; the answer region is not a live region; WCAG 2.2 AA on every state at 320px.

**Scale/Scope**: Single-tenant dev estate today; the store is tenant-scoped from day one because FR-013 demands it. Conversations per person: unbounded (kept until deleted); context per ask: bounded (research.md decides the bound).

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No framework enters core; the conversation store is core machinery, surfaces bind to it. |
| II — Total Interception; One Governed Tool Layer | Pass | New operations are catalogued northbound operations on the existing transports; the portal remains a thin client and the containment session grows to cover the new requests. |
| III — Fail-Closed, In-Process Enforcement | Pass | Conversation access checks (owner + tenant) run in-process and refuse on any miss; an unreadable store refuses rather than listing empty. |
| IV — Zero Standing Credentials; Authority Per Task | Pass | No new credentials. The store is reached through the same brokered database credential the surfaces already obtain per task. |
| V — Sealed Core, Versioned Seams | Pass | `AuditEntry` schema untouched — `ask_answered` payload (jsonb) gains keys. Identity, hooks, registries, durability, adapters untouched. New store is new core, not a sealed-core edit. |
| VI — Lean by Default | Pass | No new operated component: two tables in the Postgres that already runs, no queue, no cache, no client framework. |
| VII — Anti-Fragmentation | Pass | One store, one context builder, both transports over the same shared path — the parity decision exists to satisfy this. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | Pass | The model and corpus pins are unchanged. SC-002 gets a live check; context never becomes citable, so citation gating is untouched. |
| IX — Evidence Over Claims | Pass | The record gains `conversation_id` + carried-context descriptor, which is this principle applied: the trail keeps describing what produced the answer. |
| X — The Decision Record Governs | Pass | ADR-0039/0034/0033 honoured explicitly; no ADR amendment required because no exception is taken. |

**Gate result**: PASS — proceed to Phase 0.

**Blocking-row ownership** (constitution v1.1.0, Quality Gates): the new conformance rows run in the fast lane (hermetic) and the a11y job — both automated on every PR. The SC-002 live check is explicitly *not* blocking and is run by Dan McTeer before promotion, recorded in the conformance contract.

## Project Structure

### Documentation (this feature)

```text
specs/035-ask-conversations/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── ask-conversations-api.md   # New operations, both transports, and the /ask change
│   └── carried-context.md         # What is carried, its bound, and what the record says
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/core/answering/conversations/
├── __init__.py
├── records.py           # ConversationRecord, ExchangeRecord, title derivation
├── store.py             # Store protocol + MemoryConversationStore (hermetic twin)
├── postgres.py          # PostgresConversationStore (mirrors threads/postgres.py)
└── schema.sql           # ask_conversations + ask_exchanges

src/core/answering/
├── context.py           # NEW: build_context() — bounded carried context + descriptor
└── routing.py           # route_with_signal() added; route() unchanged

src/surfaces/api/
├── ask.py               # conversation_id in/out; context built and threaded; record gains keys
└── ask_conversations.py # NEW: GET list / GET one / DELETE — the three new operations

src/surfaces/mcp/        # ask gains conversation_id; three new tools via the shared path

src/surfaces/portal/
├── app.py               # /ask routes become conversation routes; fragment envelope kept
├── templates/
│   ├── ask.html         # transcript + composer + conversation list
│   ├── _exchange.html   # NEW: one exchange (question + _outcome) — the shared renderer
│   └── _outcome.html    # unchanged renderer, now included per exchange
└── static/
    ├── portal-ask.js    # posts composer, appends exchange fragment (stays ≤ 90 lines)
    └── portal.css       # transcript/composer/list styles from existing tokens

tests/component/         # store, context builder, inheritance, title, record keys
tests/conformance/answering/   # parity + routing-inheritance rows (hermetic)
tests/conformance/portal/      # containment session grows to the new operations
tests/a11y/              # transcript states, list, delete confirmation, 320px + scroll
specs/008-northbound-api/contracts/operations.snapshot.json   # +3 operations, /ask amended
```

**Structure Decision**: mirror-not-share with threads. The conversation store copies the *pattern* of `src/core/threads/` (records/store/postgres/schema quartet, tenant scoping, migrate-on-start) but shares no table, no class and no vocabulary with it, because FR-024/025 make "an ask conversation is not a thread" a testable property rather than a convention. The context builder lives beside `answer.py` in `core/answering/` because both transports must reach it through one path (Principle VII).

## Complexity Tracking

No constitution violations to justify. The one deliberate cost accepted: full transport parity roughly doubles the operation surface (three new operations × two transports + the `/ask` change), chosen over an ADR exception in clarification Q3 with the cost stated.
