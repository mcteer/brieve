# Implementation Plan: An answer is useful — primary response, supporting citations

**Branch**: `spec/046-answer-usefulness` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/046-answer-usefulness/spec.md`

## Summary

Guidance Ask today contracts the model to a JSON array of one-sentence claims and renders that
list as the answer — citation-led fragments that cannot carry a useful primary response (including
illustrative code). Separately, every existing gate can pass a true / cited / on-subject answer
that omits the asked-for fact. This plan changes the **provider contract and wire shape** to
`primary_answer` + supporting `citations`, keeps **citation resolution and the 043 relevance
gate** on an internal claim seam (one primary statement + its citations), adds an **additive
`answer_sufficiency` suite** with `must_contain` (not a relevance retune), measures retrieval
offerings for the ROADMAP case (FR-010), and leaves **estate** on today's shape.

## Technical Context

**Language/Version**: Python 3.12 (repository standard, `uv`-managed); portal Jinja templates

**Primary Dependencies**: none new. Vendor calls stay on the existing answering / relevance
adapter seams (`client_and_model`).

**Storage**: none new. Conversation outcomes gain a dual-readable JSON shape; `ask_answered`
audit payload stays content-free.

**Testing**: pytest — hermetic sufficiency cases via `RecordedProvider` + product path; existing
citation_accuracy / must_decline / relevance suites remain blocking; live SC-002 sampling is a
named-runner bar (not the merge gate).

**Target Platform**: guidance ask path shared by API + MCP (`surfaces/api/ask.py`); portal
renderer; pack eval loaders.

**Project Type**: single project — answering core + adapters + surfaces + evals.

**Performance Goals**: no additional model call on the happy path vs today (still answer +
relevance). Sufficiency is eval-time, not a second production gate.

**Constraints**: 043 relevance prompt and seed floor untouched (FR-009); never invent uncited
code (FR-005); never-acts (ADR-0039); estate out of scope (Q2-B); no new dependency (Principle VI).

**Scale/Scope**: provider instruction/parse, ask wire composition, portal template, eval suite
membership + scorer branch, pack TOML cases for **both** vault and terraform,
parity test updates. ~8–12 files; no trust-fabric variable changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | No new dependency; reuses answering + relevance seams. |
| II — Total Interception; One Governed Tool Layer | **Pass** | Ask still has no tools and no authority grant; illustrative code is answer content, not agency (ADR-0039). |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Uncited substance still dropped/declined; relevance gate unchanged; sufficiency suite fails fact-omission when the fact was available. |
| IV — Zero Standing Credentials | **Pass** | Credential brokering unchanged (027). |
| V — Sealed Core, Versioned Seams | **Pass, review owed** | `adapters/anthropic_answering.py` changes instruction/parse (sealed). Relevance adapter untouched. Security-maintainer review = Dan if the adapter change is in the sealed set. |
| VI — Lean by Default | **Pass** | No operated component; additive suite + shape. |
| VII — Anti-Fragmentation | **Pass** | One `ask_for` body for API/MCP; portal thin-renders. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No new model cell; sufficiency is an eval suite, not a promotion gate for a new role. |
| IX — Evidence Over Claims | **Pass** | Citations still resolve; audit stays content-free; trail still records disposition/cell/gate. |
| X — The Decision Record Governs | **Pass** | Consumes ADR-0039/0004/0033/0034/0047/0067 as written; no ADR amendment required for v1. |

**Gate result**: **PASS — proceed to Phase 0.**

**Post-design re-check (after Phase 1)**: still **PASS**. Design keeps governance order
(cite-resolve → relevance → compose wire), adds no egress class, does not retune the relevance
judge, and places usefulness in an additive suite that can fail (ADR-0047).

*Named-runner obligation*: live SC-002 (≥9/10 fact inclusion) and any live illustrative-code
demo (SC-004) run outside CI. **Named runner: Dan McTeer (maintainer)**, recorded in
`contracts/conformance-answer-usefulness.md`. They fail rather than skip when the credential or
lane is absent.

## Project Structure

### Documentation (this feature)

```text
specs/046-answer-usefulness/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance-answer-usefulness.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── adapters/
│   └── anthropic_answering.py    # _INSTRUCTION + parse → primary object
├── core/
│   ├── answering/
│   │   └── answer.py             # unchanged gate order preferred; compose at surface
│   └── evals/
│       ├── suites.py             # answer_sufficiency + must_contain
│       └── scoring.py            # sufficiency branch; AnsweringScorer primary text
├── surfaces/
│   ├── api/ask.py                # wire: primary_answer + citations
│   └── portal/templates/
│       └── _outcome.html         # primary first; dual-shape replay
packs/
├── vault/evals/answer_sufficiency.toml      # NEW — required
└── terraform/evals/answer_sufficiency.toml  # NEW — required (Principle VII; both packs)
tests/
├── conformance/answering/        # shape, parity, never-acts regression
└── component/                    # scorer / suite load rows
```

**Structure Decision**: Extend the existing answering + eval layout; no new package tree.

## Complexity Tracking

> None. Constitution Check has no Fail verdicts requiring justification.
