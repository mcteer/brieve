# Implementation Plan: The estate eval scores the path a person's question takes

**Branch**: `spec/030-estate-eval-scores-the-real-path` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-estate-eval-scores-the-real-path/spec.md`

## Summary

Estate cases gain a declared **asker role**, and the scorer narrows the fixture estate to that
role's visibility before the answering function sees a record — so a case depending on records its
role cannot see fails loudly instead of passing on evidence production would withhold. Both granted
roles are scored, each against its own cases. What a passing suite then *means* for a matrix cell
is settled in **ADR-0059** rather than inherited silently: the matrix's `role` stays the agent
role, and the cell's estate evidence is declared to span the asker roles its cases name. The two
live cells are re-examined by re-running the corrected live lane (named runner), with
withdraw-or-confirm recorded in the matrix.

## Technical Context

**Language/Version**: Python 3.12 (the repository's)

**Primary Dependencies**: none new. The narrowing is `visible_event_types` — already in core — applied
to an in-memory tuple.

**Storage**: none. Fixtures stay TOML data in the packs; no store, no access records (the stated
answer to FR-007/SC-006: with scope narrowing alone, a scoring run records nothing new).

**Testing**: the blocking eval gate (`tests/component/test_eval_gates.py`) plus new rows for the
narrowing, the load-time visibility check, and the mutation direction; the live lane re-run is a
named human activity.

**Target Platform**: the eval lanes — hermetic blocking, live behind a named runner. No deployed
surface changes.

**Project Type**: eval-harness correction + case-schema addition + one decision record.

**Performance Goals**: none material; the fixture estate is five records per pack.

**Constraints**: the blocking lane stays hermetic and deterministic (FR-006); role visibility is
not widened (FR-011); the governed read is untouched (FR-012); fixtures stay data (FR-013); the
matrix **schema** is untouched — what changes is the recorded *meaning*, via ADR-0059.

**Scale/Scope**: one field on `EvalCase`, one validation, one narrowing in
`EstateAnsweringScorer`, role tags on 10 cases across two packs, ADR-0059, a live re-run.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | A field, a filter, a validation. |
| II — Total Interception | Pass | No execution path changes. |
| III — Fail-Closed | Pass | An untagged or role-impossible estate case is `UnrunnableSuite` — loud, never a silent pass or a default role. |
| IV — Zero Standing Credentials | Pass | Untouched. |
| V — Sealed Core, Versioned Seams | Pass — no touch | No audit schema, no registry schema; `EvalCase` is eval-domain, versioned by addition. |
| VI — Lean by Default | Pass | The full-path scorer (an evidence store inside the eval) was rejected partly on this ground. |
| VII — Anti-Fragmentation | Pass | One visibility source: the scorer imports `ROLE_VISIBILITY`'s own function rather than growing a second table. |
| VIII — Eval-Gated Promotion | **Pass — and the subject** | The feature exists to make the gate's evidence honest; US3 re-examines the two live cells rather than grandfathering them. |
| IX — Evidence Over Claims | Pass | Every finding measured; the re-run is the evidence for keeping the cells. |
| X — The Decision Record Governs | Pass | **ADR-0059 is a deliverable** (FR-002a): what a cell's estate evidence asserts, decided in the open. |

**Gate result**: PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/030-estate-eval-scores-the-real-path/
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
src/core/evals/
├── suites.py             # EvalCase gains asker_role; parse_cases validates it for estate cases
└── scoring.py            # EstateAnsweringScorer narrows to the case's role; load-time
                          #   visibility check (case ∩ role, against the fixture's types)

packs/vault/evals/estate_state.toml       # 5 cases tagged (001/003/005 compliance-analyst)
packs/terraform/evals/estate_state.toml   # 5 cases tagged (the denied ones likewise)
docs/adr/0059-*.md                        # what a cell's estate evidence asserts

tests/component/
├── test_eval_gates.py                    # existing gate keeps passing over tagged cases
└── test_estate_eval_scores_visibility.py # NEW — narrowing, refusal, mutation direction
```

**Structure Decision**: the visibility check lives beside the scorer (the one place cases and the
fixture estate are both in hand); `parse_cases` validates only what a case file alone can prove
(the tag's presence and vocabulary). No new module.

## Complexity Tracking

No violations. One narrowing to note: SC-003's "deliberate defect fails the suite" cannot be shown
by re-running the tagged suite without narrowing — correctly tagged cases pass either way, since
each case's expected records are visible to its role. The defect is observable at the **provider's
input** (an operator-declared case must never hand authority records to the provider) and at the
**load-time check** (an operator case expecting an authority record refuses to load). Both
directions get rows; research F4 records why the naive form is vacuous.
