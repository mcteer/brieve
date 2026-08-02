# Implementation Plan: Asking binds to the Qualified Model Matrix

**Branch**: `spec/026-ask-binds-to-matrix` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-ask-binds-to-matrix/spec.md`

## Summary

The answering path calls a model without asking whether its cell is qualified, and 024's merged
contract asserts that it refuses. This closes that gap with the ordering 020 established for runs:
**resolve first, construct after** — the surface resolves an operator-authored **ask binding
record** (trust fabric, beside the ceiling and the matrix) through the existing
`resolve_with_fallback`, and only a resolved, green, un-withdrawn `ask` cell reaches the provider.
No cell, no call: refusals are **dispositions on the ask record** (`unbound` /
`unqualified_cell` / `matrix_unreadable`), so an operator can tell "nobody decided" from "the
decision does not hold" from "the fabric is down". A substitution rides the ask record as
`cell` / `bound_cell` / `cell_disposition` — an ask consults one model, so its authorisation is an
attribute of the ask, which also dissolves the run-id collision the spec flagged (research F3).

**The load-bearing placement decision**: resolution lives in `core.authority.ask_binding`, *not*
in `core.answering` — 025's never-acts rows forbid the answering path any import containing
`authority`, and those rows keep meaning what they mean (research F1).

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: **None added.** Record parsing follows `ceiling.py`; resolution reuses
`resolve_with_fallback`; the fabric read follows the existing `MatrixSource` pattern.

**Storage**: None added. One new operator-authored record at `harness-authority/data/ask-bindings`.

**Testing**: pytest — component rows for parsing/resolution/dispositions; conformance rows for
provider-never-called (verified at the provider), surface parity of refusals, and fabric
readability on the `test_matrix_is_readable` pattern.

**Target Platform**: the existing API and MCP surfaces; a Terraform policy change in the dev
enclave for the two fabric paths.

**Project Type**: governed agent runtime — authority resolution plus surface ordering.

**Performance Goals**: none binding; one fabric read per ask, same class of cost as the evidence
read the estate half already performs.

**Constraints**: blocking lanes vendor- and enclave-free (FR-009); `core.answering` gains no
imports (FR-010, enforced by existing rows); no new operation and no response-shape change; both
surfaces refuse identically (FR-011).

**Scale/Scope**: one new module in `core/authority/`; ordering changes in `surfaces/api/ask.py` and
the MCP `_ask`; one sealed-core payload extension; fixture plumbing (`ask_authority`, shared);
~20 existing ask rows updated to arrange authority explicitly (research F5); Terraform policy +
readability row; 024's contract line replaced by a named row (FR-012).

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Record parsing and a resolver beside the ones that exist; no framework, no dependency. |
| II — Total Interception; One Governed Tool Layer | **Pass** | No tool or hook is touched. The one governed model layer is what gets enforced for asks. |
| III — Fail-Closed, In-Process Enforcement | **Pass, and it is the feature.** | Unbound refuses; unqualified refuses; unreadable refuses distinguishably. A configured provider is not a qualification (FR-004a). No default binding — a default model is an ungoverned model choice. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The binding is a record, not a credential. The surface reads the fabric the way it already reads its own governance records. |
| V — Sealed Core, Versioned Seams | **Pass, review owed and declared now.** | `ASK_ANSWERED`'s payload gains `cell`, `bound_cell`, `cell_disposition` — additive, third touch in three features. **Security review: Dan McTeer, before merge**, recorded in the conformance contract. No new event type: the run-shaped `MATRIX_FALLBACK` is deliberately not generalised (research F3). |
| VI — Lean by Default | **Pass** | One record, one module, zero dependencies, zero services. |
| VII — Anti-Fragmentation | **Pass** | One resolver (`resolve_with_fallback`) serves runs and asks; one record-family pattern; both surfaces through one implementation. A second resolver was rejected by name (research F6). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass — this feature is the principle, applied to the path that skipped it.** | Model use only via a binding over eval-qualified cells becomes true for asks. Fallback only to another qualified cell, recorded. This qualifies no cell and changes no gate. |
| IX — Evidence Over Claims | **Pass** | The trail gains which cell authorised each answer and why a refused ask was refused. US3 exists because a merged contract asserts a refusal nothing performs — the claim gets a row or the contract gets an honest "owed". |
| X — The Decision Record Governs | **Pass, no amendment.** | ADR-0022/0039 consumed as written; `ask` was already in the role vocabulary. ADR-0047 is the rule US3 enforces on 024's contract. |

**Gate result**: **PASS — proceed to Phase 0.**

**Obligations created, named now**: the Principle V review (Dan McTeer); the fabric-readability
row runs on a live enclave with the rest of `make conformance` (no new named runner — it joins an
existing lane).

## Project Structure

### Documentation (this feature)

```text
specs/026-ask-binds-to-matrix/
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
src/core/authority/
└── ask_binding.py        # NEW — parse_ask_binding_record (ceiling's discipline),
                          #   resolve_ask_cell(source, binding, cells, available)
                          #   → (QualifiedCell, fallback | None) or ResolutionRefused.
                          #   Wraps resolve_with_fallback; adds NO branch of its own.
                          #   Lives HERE, not core/answering — the never-acts rows forbid
                          #   the answering path any import containing "authority" (F1)

src/core/audit/
└── schema.py             # SEALED CORE — ASK_ANSWERED payload gains cell, bound_cell,
                          #   cell_disposition (F3). Third additive touch; review owed

src/core/answering/
└── record.py             # record_ask carries the three new fields; no other module changes

src/surfaces/api/ask.py   # ORDERING: resolve the cell BEFORE the provider is touched, both
                          #   branches; refusal dispositions unbound/unqualified_cell/
                          #   matrix_unreadable recorded then returned. ask_authority is a
                          #   parameter (None = refuse) — a configured provider is not a
                          #   qualification (FR-004a)
src/surfaces/api/app.py   # create_app gains ask_authority, passed through
src/surfaces/mcp/transport.py  # same collaborator, same shared implementation

tests/harness/api_fixtures.py  # ask_authority shared by both surfaces;
                               #   qualified_ask_authority(model=...) — EXPLICIT in rows
                               #   that answer; refusal rows get the default None (F5 —
                               #   the fixture must not auto-qualify injected providers)

infra/environments/dev/   # policy grants data/ask-bindings (+ model-matrix) to the
                          #   surface's role; optional seeded example binding

tests/component/          # parsing, resolution, disposition vocabulary
tests/conformance/answering/   # provider-never-called (counted AT the provider);
                               #   per-source refusal (SC-003a); record-on-refusal (SC-008)
tests/conformance/mcp/test_ask_parity.py  # refusal parity — all three dispositions
tests/conformance/identity/   # fabric readability row, test_matrix_is_readable pattern
specs/024-portal-answering/contracts/conformance.md  # the flat assertion becomes a named
                                                     #   row reference (FR-012)
```

**Structure Decision**: everything sits where its family already lives — the record parser with
the record parsers, the ordering at the surface where 020 put it for runs, the fixture collaborator
beside the seven that taught us the pattern. The single novel placement (authority, not answering)
is the one research F1 justifies, and it is what keeps 025's never-acts rows untouched and
meaningful.

## Constitution Re-Check (post-Phase 1)

**Re-evaluated after `data-model.md`, `contracts/conformance.md`, and `quickstart.md`. Still PASS;
no verdict moved.** Phase 1 added no dependency, no store, no operation, no event type.

One emphasis sharpened: **Principle III's watch item is the fixture** (F5). The temptation while
making ~20 rows green again is a fixture that auto-qualifies whatever provider was injected —
which would rebuild "configured = qualified" inside the harness. The contract carries a row that
asserts the fixture's default is refusal, so the trap has a tripwire.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

Two judgment calls, recorded because each could reasonably have gone the other way:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Substitution rides the ask record (F3) | An ask consults one model; its authorisation is an attribute of the ask — 024's own `source` argument | Reusing `MATRIX_FALLBACK` fabricates a run id or generalises a second sealed-core payload; a new event type doubles every ask's entries to record one enum-sized fact |
| Refusals are disposition values, not new event types (F4) | The field an investigator already filters on; 025 added `scope_empty` the same way | Three new members for three strings would grow the sealed enum where the payload vocabulary already serves |
