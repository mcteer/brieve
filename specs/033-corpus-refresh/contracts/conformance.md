<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 033 — the corpus refresh

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Loader posture: timestamp parsed; absent/unparseable/future → unknown; 024 pin loads and answers | component rows (`test_ground_note.py` + loader rows) | Nothing | Planned |
| Tier boundaries: 29/30/89/90/91-day fixture times word correctly; unknown wording; never a decline | component rows | Nothing | Planned |
| Every guidance answer carries the note — full ask path, both packs | conformance answering row | Nothing | Planned |
| The served surfaces carry it: API payload field, portal render, MCP proxy | conformance rows (hermetic where possible; served MCP row in its lane) | Enclave for the served row | Planned |
| The workflow invokes exactly the reviewed scripts (prose-stripper row) | workflow-shape row over the YAML | Nothing | Planned |
| No blocking lane gained a fetch | existing no-network posture rows stay green | Nothing | Planned (asserted, not edited) |
| Sync writes `synced_at`; unchanged upstream moves timestamp only | sync rows against fixture upstream | Nothing (fixture HTTP) | Planned |
| `skills-provenance`: declared pack checked, undeclared pack refused with the reason, drift reported not vendored | component rows | Nothing (fixture git data) | Planned |
| The weekly proposal end-to-end: dispatch the workflow, observe the PR, observe nothing merged | manual dispatch once, observed | GitHub Actions; **named runner: Dan McTeer** (agent drives the dispatch and reads back the PR; Dan's review of that PR is the act only he can perform) | Planned |
| Failure posture: unreachable upstream → clean tree, no PR, red run, pin untouched | sync row with refused fixture + the workflow's own failure branch observed once | As above | Planned |

## What these rows assert

- The disclosure exists on every guidance answer, from the pin alone, on all three surfaces.
- Unknown is a first-class state with its own wording — the 024 pin answers on merge day.
- The schedule proposes and never lands; a no-op week still produces the provable check.
- The authored vault skill is structurally out of the sync's reach.

## What these rows refuse to assert

- Anything about upstream content quality — the injection review stays human (ADR-0004).
- Any audit-event change (there is none; a row failing for wanting one is a design alarm).
- The cron actually firing weekly in perpetuity — the dispatch-driven row proves the path;
  calendar reliability is GitHub's, and a silent month shows up as the note aging, which is
  the feature working.
