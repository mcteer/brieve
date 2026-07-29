# Implementation Plan: The Conversational Portal

**Branch**: `feat/012-conversational-portal` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-conversational-portal/spec.md`

## Summary

Threads land as core records with the same seam discipline as 011's run index; five thread
operations land on **both** existing transports, growing the catalogue from ten to fifteen
and the parity row with it; and the portal lands as a thin server-rendered client of the
API — the first thing that *serves* the API, which it turns out nothing does today. Two
findings shape the plan more than anything chosen in it: a dispatched run currently
receives no input of any kind, so the seam gains one; and the trail must carry every turn —
including the declined ones — or SC-004's "reconstruct the complete thread from the trail
alone" is unsatisfiable the day a thread is deleted. That second decision is large enough
to be its own record: **ADR-0051, drafted in this feature.**

## Technical Context

**Language/Version**: Python 3.12 (existing toolchain; `uv`)

**Primary Dependencies**: FastAPI + PyJWT (existing `surfaces` extra). New: `jinja2`
(portal templates, new `portal` extra), `playwright` + vendored pinned `axe-core`
(accessibility gate only, new `a11y` dev extra). **Deliberately absent**: any JS build
toolchain, any SPA framework, any model-provider SDK, any new HTTP client (the portal's
API relay uses `urllib`, as the enclave readers already do).

**Storage**: the enclave Postgres — `threads` and `thread_turns` tables beside 011's
`run_index`, same Protocol / in-memory / Postgres seam. The audit trail carries turn
evidence; thread tables are a **view**, deletable without masking anything.

**Testing**: pytest; hermetic rows against in-memory stores + the fake OIDC provider
(grown a code+PKCE flow); enclave rows against live Postgres/Vault/Nomad; a new **a11y
lane** driving a real browser (Playwright) over the rendered client with the WCAG 2.2 AA
axe ruleset.

**Target Platform**: the dev enclave (Nomad + Vault + Postgres). Two new jobs:
`api.nomad.hcl` (the API's first actual deployment) and `portal.nomad.hcl`.

**Project Type**: web service (portal) + surface extension (API/MCP thread operations) +
core records (threads) + one seam extension (run input).

**Performance Goals**: none newly binding. SSE update latency is bounded by the portal's
server-side poll interval (2s stated); nothing here is on a hot path.

**Constraints**: thin client (no orchestration/model calls in browser — structural, not
disciplinary); parity across API/MCP for every thread operation; containment for the
portal (exposes nothing the API does not); WCAG 2.2 AA automated gate with recorded
manual gaps; verbatim context under a stated bound; no static credentials anywhere
(portal is a **public** OIDC client — PKCE, no client secret).

**Scale/Scope**: single-tenant-per-deployment reality (011 FR-013a inherited); one
portal service instance; threads bounded by per-subject rate limits, not by design for
scale.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The portal is glue over the API; threads are core records; no framework enters core. The client is rendered HTML, not a product stack. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The principle itself names this surface: "the portal is a thin client: no logic, orchestration, or model calls client-side" — built here structurally (the browser receives rendered state, not machinery). No tool route is added to any surface. Thread operations land on both transports; verdicts conformance-asserted. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | No new enforcement point. Declines and refusals fail closed at the turn operation (FR-017a: no run on ambiguity); the portal adds no authorization logic to fail open *with*. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The portal holds no static credential: public OIDC client (PKCE, no secret), person's token held server-side in a memory session, relayed per-request. Every turn re-authorizes (FR-008); context carries **results**, never authority (ADR-0042's cached-results rule respected). |
| V — Sealed Core, Versioned Seams | **Pass, one recorded seam change** | `AuditEventType` gains `TURN_RECORDED` / `THREAD_DELETED` — additive schema growth, this approved spec is the required spec, security-maintainer review is Dan, recorded in the conformance contract. The obvious second change — `input=` on the dispatch seam — was **avoided** by research D6: run input is durable state read by the run, not metadata passed through the scheduler, so the seam does not move and a person's text never enters a jobspec. |
| VI — Lean by Default | **Pass** | No node toolchain, no build step, no SPA, no new operated component beyond the portal service — whose named trigger **is ADR-0034**. Playwright is a dev-lane dependency, not an operated one. |
| VII — Anti-Fragmentation | **Pass** | Same core, same control-plane posture; the portal is identical across substrates; only the substrate differs. |
| VIII — Eval-Gated Promotion | **Pass (by construction)** | Zero model use — the clarification split removed it. The portal's decline is deterministic, so no must-decline eval suite binds yet; recorded in the conformance contract so its absence reads as scoped, not forgotten. |
| IX — Evidence Over Claims | **Pass** | Every turn is a trail event under the thread's correlation ID before anything else happens — including declines. Deletion is an event. SC-004 becomes provable *because* of this. Evidence reads through the portal remain audited reads of the governed path. |
| X — The Decision Record Governs | **Pass** | ADR-0034 is built as written (minus the answering classes, split by recorded clarification). The turn-is-evidence posture is significant enough to be **ADR-0051**, drafted here, so the decision outlives the spec that made it. |

**Named-runner obligation** (constitution v1.1.0): the WCAG gate's **manual half** —
criteria automation cannot assert (FR-020a-i) — has no automated check by definition.
Named runner: **Dan**, before merge, recorded in `contracts/conformance-portal.md`.

**Gate result**: **PASS — proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/012-conversational-portal/
├── plan.md              # This file
├── research.md          # Phase 0 — findings and decisions D1–D11
├── data-model.md        # Phase 1 — threads, turns, run input, trail events
├── quickstart.md        # Phase 1 — end-to-end validation guide
├── contracts/
│   ├── thread-operations.md      # The five operations, both transports
│   └── conformance-portal.md     # Containment, thin-client, a11y rows + manual-gap record
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/core/threads/
├── __init__.py          # Package intent: threads are a view; the trail is the record
├── records.py           # ThreadRecord, TurnRecord, TurnDisposition, RunInput
├── store.py             # ThreadStore protocol + InMemoryThreadStore
├── postgres.py          # PostgresThreadStore (011's store pattern, verbatim discipline)
├── turns.py             # The turn decision: decline / refuse / dispatch, rate limit, context bound
└── schema.sql           # threads, thread_turns (idempotent, applied at bring-up)

src/core/audit/schema.py # + TURN_RECORDED, THREAD_DELETED (additive)

src/surfaces/api/
├── threads.py           # Five routes; evidence-first turn handling
└── app.py               # + thread store / rate limit wiring (same in-memory defaults rule)

src/surfaces/mcp/operations.py   # + five thread tools (parity)

src/surfaces/dispatch/entrypoint.py  # reads RunInput by run_id; resolves context to verbatim results
                                     # (the dispatch seam itself does NOT change — research D6)

src/surfaces/portal/
├── app.py               # Portal FastAPI app: pages, SSE, session, static
├── oidc.py              # Authorization-code + PKCE client (public client, no secret)
├── session.py           # In-memory session store; opaque HttpOnly cookie
├── relay.py             # The ONLY portal module with an HTTP client; token relay to the API
├── events.py            # SSE: server-side bounded polling of catalogued reads
├── templates/           # Jinja2: thread list, thread, composer, dispositions, declines, errors
└── static/              # portal.css, portal.js (small, readable, no fetch beyond portal origin)

infra/jobs/api.nomad.hcl      # The API's first deployment (008 built an app nothing serves)
infra/jobs/portal.nomad.hcl   # The portal service

tests/harness/fake_oidc_provider.py  # + /authorize + code+PKCE /token flow
tests/component/                     # thread/turn/context/deletion/rate rows (hermetic)
tests/conformance/api/               # thread operation rows incl. enclave halves
tests/conformance/mcp/               # parity grows via snapshot (no new wiring)
tests/conformance/portal/            # containment + thin-client rows  [NEW DIR — wired into Makefile explicitly]
tests/a11y/                          # WCAG 2.2 AA lane  [NEW DIR — own make target + CI job]

docs/adr/0051-a-turn-is-evidence-a-thread-is-a-view.md
```

**Structure Decision**: extend the existing single-project layout. Two new test
directories, and 010's lesson applies to both: **a directory no lane names is invisible
while green** — `tests/conformance/portal` is added to the Makefile conformance recipe and
`tests/a11y` gets its own `make a11y` target plus a dedicated CI job, in the same change
that creates them.

## Complexity Tracking

No constitution violations to justify. The two sealed-core seam changes are recorded in
the Constitution Check (Principle V) with this spec as the required approval.
