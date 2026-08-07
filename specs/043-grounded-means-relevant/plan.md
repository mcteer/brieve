# Implementation Plan: Grounded means relevant, not merely resolvable

**Branch**: `spec/043-grounded-means-relevant` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/043-grounded-means-relevant/spec.md`

## Summary

`answer_question` keeps a claim when its citations resolve and declines only when nothing
survives — a check on existence standing in for a check on relevance since 024, exposed when
035 widened the corpus to six product families. The fix is a **relevance gate**: after claims
survive citation resolution, a **separate model call** — bound to its **own qualified cell**
through the ask-binding record, qualified against a **human-labelled relevance seed set** —
judges per claim whether the surviving claims answer the question asked. Irrelevant claims are
dropped with the ground recorded; an answer whose every claim is irrelevant declines with a
reason distinguishable from "citations did not resolve"; the verdict is recorded as a
`MODEL_GATE`, never as a platform fact. An unavailable or unqualified judge declines naming
that cause — the gate is never silently absent on the production path, which a row asserts
against the production caller rather than against the function.

## Technical Context

**Language/Version**: Python 3.12 (repository standard, `uv`-managed)

**Primary Dependencies**: none new. The vendor call goes through the existing adapter seam
(`adapters/`, where `client_and_model` already owns the credential/import/model-id checks).

**Storage**: none new. The relevance binding is an operator-authored trust-fabric record on
026's pattern (a third field beside `guidance_cell`/`estate_cell`); the seed set is a TOML
file in `evals/`, reviewed like code (ADR-0052).

**Testing**: pytest — hermetic rows drive a **fixture relevance judge** (a qualified fixture
cell, exactly as every other role has one), so the blocking lanes stay green without a vendor;
the live smoke lane gains a relevance leg; the judge's qualification runs against the
human-labelled seed set with at least one supported-but-irrelevant case the judge must fail
before qualification (FR-015).

**Target Platform**: the answering path on both served surfaces (API + MCP share
`surfaces/api/ask.py`); the eval lanes.

**Project Type**: single project — governed core + surfaces + evals.

**Performance Goals**: one additional model call per ask **that survives citation resolution**
(FR-018); asks already declining pay nothing. 028's 180 s ask patience has headroom for a
second bounded call.

**Constraints**: the corpus is untouched (ADR-0004); the failing case is untouched; citation
resolution is not relaxed; hermetic gates must not need changes to pass (they gain a fixture
judge, not edits to what they assert).

**Scale/Scope**: ~4 core modules touched (`answering/relevance.py` new, `answer.py`,
`ask_binding.py`, `api/ask.py` + `service.py` wiring), 1 adapter class, 1 seed set + loader,
1 trust-fabric variable, ~14–18 conformance rows.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | No new dependency; the judge call reuses the adapter seam that owns vendor binding. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The judge call is model inference via the existing enumerated egress class (the same class the answer call uses); no new egress class, no tool added. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | An unavailable/unqualified/malformed judge **declines naming the cause** — never answers as though the check passed (FR-017). The malformed-verdict branch fails closed. |
| IV — Zero Standing Credentials | **Pass** | The judge call brokers the vendor credential exactly as the answer call does (027's path); nothing new is held. |
| V — Sealed Core, Versioned Seams | **Pass, review owed** | `adapters/` is sealed core and gains one additive class (the live relevance judge). Core answering is not in the sealed enumeration. Security-maintainer review = Dan. |
| VI — Lean by Default | **Pass** | No operated component; a seed file and a binding record. |
| VII — Anti-Fragmentation | **Pass** | One relevance implementation serves both surfaces through the shared ask path; the fixture and live judges implement one protocol. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | The relevance judge occupies its own matrix cell (`role="judge"`, its own cell key), promoted only through the seed-set gate; binding is an operator record on 026's precedent — **governance precedes availability**: unbound refuses `relevance_unbound`, distinguishable from an outage. |
| IX — Evidence Over Claims | **Pass** | The verdict is recorded as `MODEL_GATE` (the event type exists and has never had a production writer — this is its first), marked as a model judgement, never a platform fact (FR-007/FR-016). The decline reason vocabulary grows by one, distinguishable in the record (FR-002). |
| X — The Decision Record Governs | **Pass** | ADR-0052 consumed as written (a new seed set roots a new judge); ADR-0039's closed role vocabulary is **not** widened — the cell uses the existing `judge` role with its own cell identity. No ADR amendment anticipated. |

**Gate result**: **PASS — proceed to Phase 0.**

**Post-design re-check (after Phase 1)**: still PASS. The design added no egress class (the
judge call is model inference through the existing gateway class), no new role in the closed
vocabulary, and one additive adapter class named for Principle V review. `MODEL_GATE` gains its
first production writer, which is an event type being used as designed rather than a schema
change.

*Named-runner obligation (constitution v1.1.0)*: the live rows (smoke relevance leg, judge
qualification, SC-001's live decline) run outside CI. **Named runner: the agent harness, driven
by the maintainer (Dan), recorded in `contracts/conformance-relevance.md`.** They fail rather
than skip when the credential or lane is absent.

## Project Structure

### Documentation (this feature)

```text
specs/043-grounded-means-relevant/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance-relevance.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── answering/
│   │   ├── relevance.py     # NEW — RelevanceJudge protocol, per-claim verdict, strict parse
│   │   └── answer.py        # optional `relevance` param; third decline reason; Answer fields
│   ├── authority/
│   │   └── ask_binding.py   # + relevance_cell (026's pattern; unbound → relevance_unbound)
│   └── evals/
│       └── relevance_seed.py # NEW — seed loader: author required, floor, must-fail case
├── adapters/
│   └── anthropic_relevance.py # NEW — the live judge (sealed-core additive; via client_and_model)
├── surfaces/api/
│   ├── ask.py               # wires the judge; records MODEL_GATE; declines name their cause
│   └── service.py           # resolves relevance binding beside the ask binding
evals/
└── relevance-seed/seed.toml # NEW — human-labelled, authored, ≥1 supported-but-irrelevant
infra/modules/trust-fabric/  # relevance binding + fixture judge cell for the dev estate
tests/
├── conformance/answering/   # new rows file(s); existing rows unedited
└── evals_live/smoke.py      # + relevance leg (the case that caught this, live)
```

**Structure Decision**: single project, existing layout. One new core module, one new adapter
class, one new seed set. The gate lives in `core/answering` and is wired at the surface, so
both transports inherit it through the one shared path (Principle VII).

## Complexity Tracking

No constitutional violations to justify. The one deliberate addition of machinery — a fixture
relevance judge for the hermetic lanes — is the same pattern every other qualified role already
uses, and the alternative (hermetic rows calling a vendor, or the gate silently absent under
test) violates either the fork-safe lane or FR-017.
