# Phase 0 Research: The Conversational Portal

**Feature**: `specs/012-conversational-portal` | **Date**: 2026-07-29

Two findings and eleven decisions. The findings came from reading the shipped code rather
than the artifacts describing it, which is the habit 011 paid for and this feature starts
with.

---

## Findings — things the spec assumed that the tree disagrees with

### F1 — A dispatched run receives no input of any kind

`StartRunRequest` carries `agent_definition_id` and `requested_tools` and nothing else
([src/surfaces/api/runs.py](../../src/surfaces/api/runs.py)); the dispatch protocol
carries identity, scope, and resume state; the entrypoint's environment
([src/surfaces/dispatch/entrypoint.py](../../src/surfaces/dispatch/entrypoint.py)) has no
input variable at all. **"Describes what they want in their own words" has nowhere to
put the words.** The spec's assumption — "the operation catalogue is sufficient for
everything except threads" — predicted its own exception clause would be needed, and this
is it, recorded rather than absorbed. Resolution: decision D6.

### F2 — Nothing serves the API

008 built `create_app` and everything since has exercised it — in tests, and mirrored
inside the MCP transport's assembly. But `infra/jobs/` holds no API job: **the API exists
as a library and a test subject, and has never been deployed.** A portal "over the API,
not beside it" needs an API to be over. Resolution: `infra/jobs/api.nomad.hcl` lands in
this feature (decision D11), and the finding is worth this sentence in the record because
it says something about parity rows: every operation row passed against an app object
while no service existed — true claims about an unserved surface.

---

## Decisions

### D1 — The client is server-rendered HTML with no build step

**Decision**: the portal service renders Jinja2 templates; the browser receives HTML, one
hand-written CSS file, and one small hand-written JS file (SSE subscription + progressive
form enhancement). No node toolchain, no bundler, no SPA framework, no npm dependency
tree.

**Rationale**: Principle VI, and — more decisively — FR-002/SC-006 become *structural*:
the thin-client rule is trivially verifiable when the client's entire executable surface
is one readable file. The containment row can enumerate every byte of JS served and
assert no fetch target beyond the portal origin, no model endpoint, no decision logic. A
bundler output cannot be audited that way; it can only be trusted. WCAG scanning is also
materially simpler over server-rendered pages (every state is a URL).

**Alternatives considered**: React/Vite SPA — a second toolchain and supply chain, and
SC-006 verification degrades from "read the file" to "audit the bundle" (rejected);
htmx — a dependency doing what ~30 lines of vanilla JS does here (rejected, barely).

### D2 — Portal authentication: OIDC authorization code + PKCE; server-side session; token relay

**Decision**: the portal is a **public** OIDC client using authorization code + PKCE — no
client secret exists anywhere. After the code exchange, the person's access token lives in
an in-memory server-side session keyed by an opaque `HttpOnly; Secure; SameSite=Lax`
cookie. Every portal request to the API relays the person's own token. Portal restart
drops sessions (people re-authenticate); threads are unaffected (they are in Postgres).

**Rationale**: FR-003 (OIDC on every operation — the API keeps verifying the same token it
verifies for every other caller, so the portal adds no authentication authority of its
own), FR-020b (the browser holds only an opaque cookie; nothing in localStorage; nothing
that can act later), Principle IV (no static keys — PKCE exists precisely to remove the
public client's secret). Token relay rather than a service identity is what makes SC-007
true for free: the API sees *the person*, so a portal-started run is indistinguishable
from an API-started one because it **is** one.

**Dev/test IdP**: the fake OIDC provider
([tests/harness/fake_oidc_provider.py](../../tests/harness/fake_oidc_provider.py)) grows
`/authorize` and a code+PKCE `/token`. It is the established, deliberate double — the
customer's IdP is the one thing outside the boundary (008's recorded rule) — and it
already signs real JWTs that PyJWT genuinely verifies. Vault's own OIDC provider was
considered and rejected: wiring it up is the RFC 8693 row's work, and dragging an
unassigned roadmap entry into this feature to save a fixture is how scope dies.

### D3 — Threads are core records: `threads` + `thread_turns`, Protocol / in-memory / Postgres

**Decision**: `src/core/threads/` with the same seam discipline as 011's run index — a
`ThreadStore` protocol, an in-memory implementation for every hermetic row and the
in-process dispatcher path, a Postgres implementation for real deployments. Turns are
insert-only. Threads are **hard-deleted** on FR-010b (rows removed), because after D4 the
trail holds everything a turn ever was — the tables are a *view*, and deleting a view
masks nothing.

**Rationale**: ADR-0034 says "persisted like any other run state" and 011 already
established what that means operationally: tenant-scoped tables in the enclave Postgres,
read through tenant-filtered queries, never on the resume path, droppable. Soft delete
was considered and rejected: a `deleted_at` column retains the text of every message in a
table whose whole justification for being deletable is that the *trail* is the record —
retaining a shadow copy is the worst of both.

### D4 — Every turn is evidence, written to the trail before anything else happens

**Decision**: every submitted message becomes a `TURN_RECORDED` audit event — under the
thread's correlation ID, carrying the message, the disposition (started run / declined /
refused, with reason), and the context bound's effect — **before** the turn does anything
else. Thread deletion writes `THREAD_DELETED`. Two new members on `AuditEventType`; the
one sealed-core change in this feature.

**Rationale**: this closes the clarification's deliberately-open edge ("a message that
starts nothing has no trail entry") in the only direction the success criteria permit.
SC-004 requires reconstructing a **complete** thread from the trail alone; FR-006 says
"who asked what, in what order" — a declined ask is an ask, and the declined ones are
precisely the ones an investigator wants. Without this, deleting a thread destroys the
only copy of every message that started nothing, and the reconstruction silently omits
them. With it, deletion is pure view-removal and FR-010b's "not a masking primitive" is
structural.

**Cost, stated**: every submitted message is permanent, append-only evidence. The
composer says so in the interface — a person is told their messages are recorded. That is
the honest version of a governed conversational surface, and it goes in the decision
record rather than a spec footnote: **ADR-0051 — "A turn is evidence; a thread is a
view"** is drafted in this feature.

### D5 — Five thread operations, on both transports; the catalogue grows 10 → 15

| Operation | API | MCP tool |
| --- | --- | --- |
| Create a thread | `POST /threads` | `create_thread` |
| Send a turn | `POST /threads/{thread_id}/turns` | `send_turn` |
| List my threads | `GET /threads` | `list_threads` |
| One thread, with turns | `GET /threads/{thread_id}` | `get_thread` |
| Delete a thread | `DELETE /threads/{thread_id}` | `delete_thread` |

Snapshot-first, one at a time, exactly as 011 worked: grow
`operations.snapshot.json`, watch the parity row go red, land both surfaces, watch it go
green. Explicit create rather than create-on-first-message: parity-identical semantics
are easier to hold when the operations are orthogonal, and the client needs a thread id
to subscribe to before the first turn resolves. List/get follow 011's discipline
verbatim: keyset cursors, no totals, other-tenant-answers-absent.

**Stop and result are deliberately not thread operations** — a turn's run is stopped and
read through the existing `/runs/{run_id}` operations, which the portal calls with the
person's token. Duplicating them per-thread would be two paths to one action.

### D6 — Run input is durable state, not dispatch metadata

**Decision**: a `run_inputs` record (in the threads schema: `run_id` PK, `message`,
`context_run_ids`, written by the turn operation **before** dispatch). The entrypoint
reads its input by `run_id` from Postgres under its own workload credentials — exactly
how it already reads checkpoints — and resolves `context_run_ids` to their recorded
results **verbatim** at run start. The in-process dispatcher path reads the in-memory
store. **The dispatch seam does not change.**

**Rationale**: the obvious design — threading `input=` through `RunDispatcher.dispatch`
— died on inspection of the mechanism: Nomad dispatch carries `Meta`, which lands in the
jobspec and the allocation's environment, visible to anyone with scheduler access and
outside the tenant-scoped read path. **A person's free text must not enter a jobspec.**
Making input durable state solves four things at once: no seam change (Principle V), no
user text in the scheduler, verbatim-by-construction (FR-009 — the run reads the recorded
bytes, not a copy that traveled), and hermetic rows get it for free through the in-memory
store.

**Bounds** (FR-009a, stated not emergent): `message` ≤ 8 KiB; `context_run_ids` = the
runs of the **5** most recent turns that produced results, newest first. What fell
outside the bound is recorded on the turn (`context_dropped`) and rendered by the client
(FR-009b).

### D7 — Message-to-agent mapping is explicit selection, not inference

**Decision**: the composer requires choosing an agent definition (from the existing 011
disclosure — startable and non-startable both visible, flagged). The message is the run's
input, not a routing problem. No agent selected or none available → **decline**
(`nothing_to_dispatch`); an agent the person may not start → **refusal** on scope —
distinct answers, per FR-017. Neither starts a run (FR-017a).

**Rationale**: with the answering classes split out there is no model, and intent routing
without a model is keyword matching — a decline path that guesses. Explicit selection
makes US5 deterministic and keeps "conversational" honest: the conversation is the
*thread* (context, follow-ups, results in place), not a natural-language command parser.
Intent routing is `ask`/`plan`-shaped model work and belongs to the answering feature.

### D8 — Progress without polling: server-side bounded polling, SSE to the browser

**Decision**: the browser subscribes to `GET /portal/threads/{id}/events` (SSE, on the
**portal**, not on the catalogue). The portal service polls the API server-side — the
person's own token, catalogued reads only (`get_run`, `get_run_result`), 2s interval,
bounded stream lifetime, per-subject concurrent-stream cap — and pushes state changes to
the browser.

**Rationale — and this needs the explicit defense, because it is exactly the "just a UI
concern" the spec warns about**: the SSE endpoint adds no *capability*. Every byte it
emits is sourced from catalogued reads made with the requesting person's token; it
computes nothing, authorizes nothing, and a 403 from the API ends the stream. The
capability "observe a run" exists on all transports; SSE is a delivery cadence for it.
The containment row asserts this structurally: the portal's `relay.py` is the only module
with an HTTP client, and its request log for any session maps onto catalogued operations
one-to-one. A `watch` operation on the catalogue was considered (it would bind parity and
serve MCP too) and rejected for this feature: it grows the catalogue for cadence, not
capability, and MCP clients poll `get_run` today without complaint.

### D9 — Rate limits live in the turn operation, counted from the store

**Decision**: a fixed-window per-subject limit — **30 turns per 5 minutes** — enforced
inside the turn operation (core, so both transports inherit it), counted from
`thread_turns` with one query. Exceeding it is a refusal (`rate_limited`), audited like
any other, and rendered as a boundary rather than an error.

**Rationale**: FR-016 names this surface the easiest place to consume resources
accidentally. Counting from the store is stateless, restart-safe, and costs one indexed
query per turn — no new component (Principle VI). SSE concurrent-stream caps (D8) bound
the read side; the turn limit bounds the write side; there is no loop to bound because
nothing in this feature acts without a person's message.

### D10 — The WCAG 2.2 AA gate: Playwright + vendored axe-core, its own lane

**Decision**: `tests/a11y/` drives a real browser (Playwright) over every rendered page
state — thread list (empty and populated), a thread showing all three run dispositions,
decline, scope-refusal, delete confirmation, API-unreachable — injecting a **pinned,
vendored** `axe.min.js` and failing on any WCAG 2.2 AA violation. New `a11y` dev extra
(`playwright`), new `make a11y` target, new dedicated CI job (no enclave needed; the lane
runs the portal app in-process against in-memory stores and the fake IdP).

**The manual half is recorded, not implied** (FR-020a-i): the conformance contract lists
the criteria automation cannot assert — focus order *adequacy*, screen-reader flow,
meaningful alt text, 2.2's focus-appearance and target-size judgment calls — with **Dan
named as the party who runs that checklist before merge** (constitution v1.1.0's
named-runner rule, applied to a gate class where "not automated" is a permanent property
rather than a temporary gap).

### D11 — Two new Nomad jobs: the API's first deployment, and the portal

**Decision**: `api.nomad.hcl` serves `create_app` via uvicorn (assembled with the real
collaborators: Postgres-backed stores, Nomad dispatcher, JWKS verifier against the
configured issuer); `portal.nomad.hcl` serves the portal app pointed at the API service
address and the IdP. Both follow 009's mcp.nomad.hcl pattern exactly — read-only source
mount, copy before install, workload identity for Vault, no token anywhere.

**Rationale**: F2 — the portal cannot be over an API that is not there. Portal → API
traffic stays inside the enclave on loopback for dev; the production TLS posture is a
deployment concern recorded in the jobspec comments, not solved speculatively here.

---

## Resolved unknowns from Technical Context

All NEEDS CLARIFICATION markers: none remained after the clarification session. The
technical unknowns (client stack D1, auth flow D2, input channel D6, update mechanism D8,
gate mechanics D10) are resolved above.
