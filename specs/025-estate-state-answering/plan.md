# Implementation Plan: Estate-state answering — the answer is bounded by who is asking

**Branch**: `spec/025-estate-state-answering` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-estate-state-answering/spec.md`

## Summary

ADR-0035's central claim — *everyone asks in the same place, and the answer is bounded by the
asker's own entitlements* — becomes executable. A question arrives through the existing `ask`
operation; a **deterministic router** decides whether it needs the pinned corpus or the evidence
plane; the estate half reads through 022's governed read (**one door**, which is what makes the
access recording and the "not yours"/"nothing happened" collapse come free), bounded by **tenant
and roles** via request narrowing rather than result filtering; every claim carries an **entry-hash
reference** that must resolve into the asker's own scoped read, or the claim drops and the answer
declines. `estate_state` stops scoring authored recordings: cases carry an expected reference set,
the path is driven with the recording as the model's output, and the **fidelity machinery** scores
precision and recall — so inventing a workspace and omitting a violation both fail, which the
current substring check cannot do (measured, research F5).

**One sealed-core touch, declared up front**: `ASK_ANSWERED`'s documented payload gains a `source`
field. 024's plan asserted no review was needed and an analysis pass proved it wrong; this plan
does not repeat that.

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: **None added.** Routing is stdlib string work; scoring reuses
`core/evals/fidelity.py`; the estate read reuses `read_evidence_for`.

**Storage**: None added. The fixture estate is TOML in the pack; the real estate is the audit
plane, which exists.

**Testing**: pytest — component rows for routing (both directions), scope, and the estate path;
conformance rows extending `tests/conformance/answering` and the ask parity file; `make evals` for
the reauthored suite; `make evals-live` for the live half, named runner.

**Target Platform**: the platform's own API and MCP surfaces; no new deployment surface.

**Project Type**: governed agent runtime — core answering path plus surface wiring.

**Performance Goals**: none binding. The only new hot-path work is one narrowed evidence query per
estate question, bounded by the read path's existing `limit`.

**Constraints**: blocking lanes stay vendor-free and enclave-free (FR-011a). No product credential
in the answering path (FR-006). `GET /evidence` behaviour unchanged — the route never passes the read function's new
`event_types` parameter, and a row asserts it (research F2, corrected by analysis I1). No new
operation — parity grows by zero.

**Scale/Scope**: `src/core/answering/` gains routing, scope, and estate modules;
`src/surfaces/api/ask.py` and the MCP transport route through the shared implementation; one
sealed-core docstring-and-payload change; two packs' `estate_state` suites reauthored plus a
fixture-estate file each; eval scoring gains an estate scorer; conformance and component rows.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | No framework enters core. Routing is string-shape matching; the estate path is a reader and a provider seam, same shape 024 established. |
| II — Total Interception; One Governed Tool Layer | **Pass** | No tool, hook, or registry is touched. The answering path continues to hold none of them — the never-acts rows extend to the new module by listing it. |
| III — Fail-Closed, In-Process Enforcement | **Pass, and it is the feature.** | Empty roles refuse (FR-004c). An unroutable question declines rather than guessing a source. A reference that does not resolve drops its claim. A store failure is distinguishable from a decline (FR-003) — the same raise-don't-shape discipline 024 built for providers. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The estate path holds no product credential and reaches no product (FR-006). It reads the platform's own records through the governed read, as the asker, bounded by the asker. |
| V — Sealed Core, Versioned Seams | **Pass, with a review owed and declared now.** | `ASK_ANSWERED`'s documented payload gains `source` — the audit schema is sealed core, and investigators parse what the docstring documents. **Security review: Dan McTeer, before merge**, recorded in the conformance contract. Additive; no existing field changes meaning. The previous feature's plan asserted no review was needed and was wrong; this one is not hedged. |
| VI — Lean by Default | **Pass** | No dependency, no service, no store, no new operation. The largest artifact is fixture data in packs. |
| VII — Anti-Fragmentation | **Pass** | One `ask` on both surfaces through one implementation; one governed read door; one scoring discipline (fidelity) reused rather than a parallel one invented. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass, and the gate gets teeth.** | `estate_state` moves from authored recordings to product output — the last suite in that state. The `ask` matrix cell stays `fixture` until the reauthored suite passes live; FR-012 names the old failure *before* the suite that failed is replaced, so the record shows what failed rather than losing it to the reauthoring. |
| IX — Evidence Over Claims | **Pass — this feature is the principle, executed.** | Answers assembled from records, references that resolve, evidence never verdicts (FR-005), access itself audited (FR-008, free via F1), declining beats confabulating. |
| X — The Decision Record Governs | **Pass, no amendment.** | ADR-0035 is executed as written at tenant+role granularity; its *team* example is recorded as owed (FR-004d) rather than approximated. ADR-0039/0033/0034/0018 consumed unchanged. |

**Gate result**: **PASS — proceed to Phase 0.**

**Obligations created, all named now**: the Principle V review (Dan McTeer); the live
`estate_state` qualification run (`make evals-live`, Dan McTeer, paid credential); FR-012's
name-the-old-failure run (Dan McTeer — ~15 calls, before reauthoring lands).

## Project Structure

### Documentation (this feature)

```text
specs/025-estate-state-answering/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance.md   # Phase 1 — the rows this feature binds
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
src/core/answering/
├── routing.py            # NEW — deterministic router, closed vocabulary, ties → estate
├── scope.py              # NEW — role → visible AuditEventTypes; empty means refuse
├── estate.py             # NEW — answer_estate_question, EstateProvider seam,
│                         #        RecordedEstateProvider; references resolve against the
│                         #        asker's own scoped read (F3)
├── answer.py             # unchanged — the corpus half
└── record.py             # record_ask gains the source field (with the schema change)

src/core/audit/
└── schema.py             # SEALED CORE — ASK_ANSWERED payload docstring gains `source`

src/core/evals/
├── scoring.py            # EstateAnsweringScorer; estate branch scores via fidelity
└── suites.py             # estate_state case shape: events = expected references

src/surfaces/api/ask.py   # route first, then corpus path or estate path; decline names source
src/surfaces/api/evidence.py  # ONE additive parameter: read_evidence_for gains
                              #   event_types (default None = today's unnarrowed read).
                              #   Analysis I1: the function builds its request internally
                              #   and exposed no way to narrow by type — the design's key
                              #   call was impossible as planned. GET /evidence never
                              #   passes it; a row asserts the route is unchanged (T009a)
src/surfaces/mcp/transport.py  # same, through the shared ask_for

src/adapters/
└── anthropic_answering.py  # live estate provider (offers fixture records, model proposes)

packs/{vault,terraform}/evals/
├── estate_state.toml     # REAUTHORED — records-answerable prompts, events carry references
└── estate_records.toml   # NEW — the arranged estate the cases ask about

tests/component/          # routing both directions, scope narrowing, estate path, scorer
tests/conformance/answering/  # never-acts extends to estate; differential entitlement (SC-001)
tests/conformance/mcp/test_ask_parity.py  # estate verdicts on both surfaces
```

**Structure Decision**: everything new lives where 024 put its analogues — the path in
`core.answering`, the live provider in `adapters`, scoring beside the suites, fixtures in packs.
The one deliberate asymmetry: **`scope.py` is in `answering`, not `authority`**, because it maps
roles to *visibility of records*, not to authority to act — putting it in `authority` would invite
the reading that an estate answer grants something.

## Constitution Re-Check (post-Phase 1)

**Re-evaluated after `data-model.md`, `contracts/conformance.md`, and `quickstart.md`. Still PASS;
no verdict moved.** Phase 1 added no dependency, no store, no operation.

Two emphases sharpened:

- **Principle III**: the data model makes "neither" a first-class routing outcome with its own
  decline text — the router never coerces a question into a source to avoid saying it does not
  know (the spec's *"decline, not a coin flip"* edge case).
- **Principle VIII**: the contract orders FR-012 explicitly **before** reauthoring in the task
  flow, so the old failure is named while the failing suite still exists to name it.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

One judgment call, recorded because it could reasonably have gone the other way:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Routing tie-break toward **estate** | The estate-side failure is visible to the asker (a decline naming the evidence plane), so it gets reported and fixed | Tie toward guidance produces plausible-looking answers from the wrong source — an invisible failure; and tie toward "neither" would decline questions both sources could serve |
| `source` on `ASK_ANSWERED` rather than a new event type | An ask consults exactly one source; the source is an attribute of the ask, not an event of its own | A routing event would double every ask's trail entries to record one enum-sized fact |
