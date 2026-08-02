# Implementation Plan: The portal learns to ask

**Branch**: `spec/028-portal-asks` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-portal-asks/spec.md`

## Summary

A signed-in person asks from a portal page and reads a cited answer. The portal stays a thin
client: one new page, one relayed operation, four response shapes rendered faithfully — and the
central design finding is that **the portal distinguishes refusals by rendering the API's own
words, not by classifying them** (research F1), which is how FR-009 (three refusals
distinguishable) and FR-014 (the API unchanged) hold at the same time. Waiting is per-operation
patience on the existing relay (the maintainer's decision, recorded in the spec's Clarifications),
which is a parameter on `ApiRelay.request`, not a second relay.

## Technical Context

**Language/Version**: Python 3.12 (the repository's)

**Primary Dependencies**: none new. FastAPI + Jinja2 (the portal's existing extra); the relay stays
`urllib` (containment row: the only HTTP client in the package is `relay.py`).

**Storage**: none. The portal stores nothing; the question and answer live in one request/response.

**Testing**: pytest component rows (`tests/component/test_portal_*`), the portal containment rows
(`tests/conformance/portal/`), and the WCAG 2.2 AA browser lane (`tests/a11y/`) which drives the
real portal with an injected transport.

**Target Platform**: the deployed portal allocation, unchanged.

**Project Type**: web surface (server-rendered pages; ~zero client-side machinery by design).

**Performance Goals**: SC-004 — no other portal page becomes slower. The ask's own patience is
bounded (measured answer ~2 minutes; allowance 180s, the same number the MCP demonstration used).

**Constraints**: ADR-0034 thin client (no business logic, no classification of API responses);
Principle IV (no credential reaches the browser — unchanged, asserted); FR-014 (the API's ask
operation does not change); the containment rows' egress allowlist and served-client size bound.

**Scale/Scope**: one route pair (GET form / POST ask), one template, one relay parameter, rows.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Renders and relays; no new dependency, no framework added. |
| II — Total Interception; One Governed Tool Layer | Pass | The portal reaches only the catalogued `/ask`; no tool, no second path. |
| III — Fail-Closed, In-Process Enforcement | Pass | Enforcement stays in the API; the portal renders refusals and cannot convert one to an answer. |
| IV — Zero Standing Credentials | Pass | Session stays server-side; vendor credential never leaves the enclave; nothing new holds anything. |
| V — Sealed Core, Versioned Seams | Pass | **No sealed-core touch.** No audit schema change, no core change — the first feature in five to need no Principle V review. |
| VI — Lean by Default | Pass | No new dependency; preference for zero new client-side JS (research F6 bounds any exception). |
| VII — Anti-Fragmentation | Pass | One ask operation, consumed; the portal adds a renderer, not a mechanism. |
| VIII — Eval-Gated Promotion | Pass | No model use changes; no cell is promoted or bound differently. |
| IX — Evidence Over Claims | Pass | The trail records the ask via the API exactly as any other surface's (US3 rows observe it). |
| X — The Decision Record Governs | Pass | ADR-0034/0039/0035/0018 consumed; none amended, none expected. |

**Gate result**: PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/028-portal-asks/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── conformance.md
└── tasks.md              (/speckit-tasks)
```

### Source Code (repository root)

```text
src/surfaces/portal/
├── app.py                # + GET /ask (form), POST /ask (relay + render)
├── relay.py              # + per-call timeout parameter on ApiRelay.request
└── templates/
    ├── base.html         # + nav link to /ask
    └── ask.html          # NEW — form, answered (both sources), declined, refused

tests/
├── component/test_portal_asks.py            # NEW — the four shapes, patience, token relay
├── conformance/portal/test_containment.py   # extended only if a row needs the ask exercised
└── a11y/                                    # ask page joins the WCAG + keyboard lanes
```

**Structure Decision**: everything lands inside the portal package and its existing test homes.
No API change (FR-014), no new module, no new template engine or client library.

## Complexity Tracking

No violations to justify. The one place this plan *narrows* a spec sentence: SC-003's "four
distinguishable outcomes" is delivered by faithful rendering of the API's own distinguishable
messages plus the relay's reachable/unreachable line — not by the portal maintaining a mapping
from refusal causes to portal-authored explanations, which would be classification and drift
(research F1 records why).
