# Research: 028 — the portal learns to ask

**Phase 0.** Measured against merged `main` on 2026-08-02, after 027 and its follow-ups. The first
finding decides the feature's central tension; the rest bound the work.

---

## F1 — The API's refusals carry their cause as prose, and that decides FR-009 vs FR-014

**Measured**: `/ask`'s refusals arrive as `HTTPException(403|503, str(exception))`, so the HTTP
body is `{"detail": "<prose>"}`. The disposition *code* (`unqualified_cell`,
`credential_unavailable`, `provider_unavailable`) is recorded in the trail and is **not** in the
HTTP response. What is in the response is prose this repository has spent five features making
precise — every refusal names its cause and what to do: *"no ask binding is configured for this
surface; a configured provider is not a qualification"*, *"no model credential is stored for
'anthropic'; the platform holds no authority to call this vendor"*.

**The tension**: FR-009 wants three refusals distinguishable on the page; FR-014 forbids changing
the API. If the portal needed the code, one of them would have to give.

**Decision**: neither gives. The portal renders the API's `detail` **verbatim**. The refusals are
distinguishable because the API's own sentences are distinguishable — and this is the
ADR-0034-correct shape, since a portal that mapped causes to portal-authored explanations would be
classifying (business logic) and would drift from the API's vocabulary the first time a new reason
code landed.

**Consequence for the existing `refused.html`**: it flattens every non-404/403 to *"The platform
refused this request"* — exactly the flattening the spec forbids for asks. The ask page renders
its own refusal block and does **not** reuse that template's generic arm. `refused.html` itself is
left alone (its callers are act-shaped operations; rewording them is not this feature).

## F2 — Per-operation patience is a parameter, not a second relay

**Measured**: `ApiRelay` carries one `timeout` attribute (10.0s, with the reason in a comment) and
`request()` passes it to every call. The a11y and component harnesses inject `transport=` at the
same seam.

**Decision**: `ApiRelay.request(..., timeout: float | None = None)` — `None` means the relay's
own. The ask calls pass `ASK_PATIENCE = 180.0` (the measured ~2-minute answer, plus headroom; the
same allowance the 2026-08-02 MCP demonstration used). Every other call site is untouched, which
is SC-004's second half by construction.

**Rejected**: a second `ApiRelay` instance with a longer timeout (two relays is two egress points
for the containment row to reason about); raising the shared default (spends an ask's patience on
a thread listing — the exact harm the 10s comment names).

## F3 — The response has exactly four shapes, all already enumerated in `ask.py`

**Measured** from the operation's own return statements:

1. **Answered, guidance**: `disposition="answered"`, `corpus_digest`, `claims[]` each with
   `statement` and `citations[]` — citations are **URLs** (`c.url(corpus)`), followable.
2. **Answered, estate**: `disposition="answered"`, `source="estate"`, `claims[]` each with
   `statement` and `references[]` — references are **entry hashes**, not links.
3. **Declined**: `disposition="declined"`, `declined_reason`, `source` naming which door was
   opened (`guidance` / `estate` / `neither`).
4. **Refused**: HTTP 403/503 with `{"detail": prose}` (F1), or status 0 from the relay when the
   API was unreachable — `ApiResponse.reachable` already keeps that line.

**Decision**: one template with four blocks, dispatching on `reachable → status → disposition`.
An estate reference renders as inert code (short-prefixed hash with the full value present), never
as an anchor — a dead link teaches people the references are decorative.

## F4 — The a11y lane drives the real portal and will collect the new page

**Measured**: `tests/a11y/conftest.py` stands the portal up with an injected transport and runs
axe-core (WCAG 2.2 AA) plus keyboard/screen-reader rows; CI runs this lane on every PR.

**Decision**: the ask form, an answered page (both sources), a declined page and a refused page
all get WCAG rows. The waiting affordance (FR-005/005a) must itself be accessible — the
expectation text is plain content, not a spinner with no name.

## F5 — Containment already covers the new route, structurally

**Measured**: `tests/conformance/portal/` asserts the only module that reaches the network is
`relay.py`, that every request the portal makes is a catalogued operation, that the portal holds
no credential, and that the served client stays small. `/ask` **is** a catalogued operation
(024; the coverage row has included it since 027 fixed the snapshot).

**Decision**: no new containment machinery. The relayed `/ask` passes the existing rows by
construction; one component row additionally asserts the relay sent the **person's own token**
(FR-011's portal half — the API half, that the record carries `subject_user_id`, is already
asserted API-side and is observed end-to-end in the quickstart).

## F6 — The waiting affordance should cost zero new JavaScript

**Measured**: `portal.js` is read in full by a containment row that bounds the served client's
size, and `test_row_the_client_does_not_reload_unconditionally` constrains its behaviour.

**Decision**: FR-005 is satisfied by the browser's own native busy state during a synchronous form
POST plus FR-005a's expectation text on the form ("an answer usually takes a minute or two —
leave this page open"). No spinner, no polling script, no new JS. If implementation finds a
double-submit guard genuinely necessary, it is a one-line `submit`-listener addition to the
existing `portal.js` inside the size bound — a tasks-level call, defaulting to *no*.

## F7 — What must not change, and what is deliberately not built

- **The API** (FR-014). Submit-then-poll is recorded in the spec as the next shape and needs the
  API to hold an in-flight ask; nothing here pre-builds toward it.
- **`refused.html` and its callers** — act-shaped operations keep their wording.
- **The trail** — no portal-side recording. The API records the ask; the portal adding its own
  would be a second record to disagree (the 011 lesson, one layer up).
- **Streaming** — rejected in the spec on correctness grounds (citations resolve after the model
  finishes); nothing here leaves a seam for it.

## Open for tasks, not for plan

- Whether the nav link text is "Ask" or something longer — a11y row will judge the accessible name.
- Whether the ask form page states the two sources (guidance / your estate) or stays neutral;
  leaning toward naming both, since the decline pages already do.
